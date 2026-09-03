"""
End-to-end pipeline run over SQLite (local stand-in for a Fabric Lakehouse/Warehouse).
Mirrors the logic in sql/02_transformations.sql and sql/03_data_quality_checks.sql
(SQLite has no TRY_CAST, so casting/cleaning is done in Python instead).

Usage:
    python3 pipeline.py                 # normal run
    python3 pipeline.py --simulate-fail # simulate a hard pipeline failure
"""
import argparse
import csv
import sqlite3
from datetime import datetime, date

DB_PATH = "/home/claude/dq-platform/data/staging/warehouse.db"
RAW_DIR = "/home/claude/dq-platform/data/raw"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")
    return conn


def init_schema(conn):
    """Create tables only if this is a fresh database. pipeline_run_log and
    data_quality_log must persist across runs so monitoring has real history."""
    cur = conn.cursor()
    exists = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_run_log'"
    ).fetchone()
    if exists:
        # staging is always cleared before a fresh load; curated is rebuilt in transform()
        cur.execute("DELETE FROM stg_customers")
        cur.execute("DELETE FROM stg_orders")
        cur.execute("DELETE FROM dim_customers")
        cur.execute("DELETE FROM fact_orders")
        conn.commit()
        return
    with open("/home/claude/dq-platform/sql/01_create_tables.sql") as f:
        ddl = f.read()
    ddl = ddl.replace("INT IDENTITY(1,1) PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
    ddl = ddl.replace("DATETIME2 DEFAULT CURRENT_TIMESTAMP", "TEXT DEFAULT CURRENT_TIMESTAMP")
    for stmt in ddl.split(";"):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)
    conn.commit()


def load_staging(conn):
    cur = conn.cursor()
    with open(f"{RAW_DIR}/customers_raw.csv") as f:
        rows = [r for r in csv.reader(f)][1:]
        cur.executemany(
            "INSERT INTO stg_customers (customer_id,name,email,signup_date,country) VALUES (?,?,?,?,?)",
            [r[:5] + [None] * (5 - len(r)) for r in rows]
        )
    with open(f"{RAW_DIR}/orders_raw.csv") as f:
        rows = [r for r in csv.reader(f)][1:]
        cur.executemany(
            "INSERT INTO stg_orders (order_id,customer_id,order_date,amount,status) VALUES (?,?,?,?,?)",
            [(r + [None] * 5)[:5] for r in rows]  # pad ragged/incomplete rows
        )
    conn.commit()
    return len(rows)


def try_int(v):
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return None


def try_float(v):
    try:
        return round(float(str(v).strip()), 2)
    except (ValueError, TypeError):
        return None


def try_date(v):
    try:
        return date.fromisoformat(str(v).strip()).isoformat()
    except (ValueError, TypeError):
        return None


def transform(conn):
    cur = conn.cursor()

    # --- customers: cast, clean, dedupe ---
    cur.execute("SELECT customer_id, name, email, signup_date, country FROM stg_customers")
    seen, clean_customers = set(), []
    for cid, name, email, sdate, country in cur.fetchall():
        cid_i = try_int(cid)
        if cid_i is None:
            continue
        name = (name or "").strip() or None
        email = (email or "").strip() or None
        row = (cid_i, name, email, try_date(sdate), country)
        key = row
        if key in seen:
            continue
        seen.add(key)
        clean_customers.append(row)
    cur.executemany(
        "INSERT OR REPLACE INTO dim_customers (customer_id,name,email,signup_date,country) VALUES (?,?,?,?,?)",
        clean_customers
    )

    valid_customer_ids = {r[0] for r in clean_customers}

    # --- orders: cast, clean, dedupe, enforce referential integrity ---
    cur.execute("SELECT order_id, customer_id, order_date, amount, status FROM stg_orders")
    seen, clean_orders = set(), []
    for oid, cid, odate, amt, status in cur.fetchall():
        oid_i, cid_i = try_int(oid), try_int(cid)
        if oid_i is None or cid_i is None or cid_i not in valid_customer_ids:
            continue
        row = (oid_i, cid_i, try_date(odate), try_float(amt), (status or "").strip() or None)
        if row in seen:
            continue
        seen.add(row)
        clean_orders.append(row)
    cur.executemany(
        "INSERT OR REPLACE INTO fact_orders (order_id,customer_id,order_date,amount,status) VALUES (?,?,?,?,?)",
        clean_orders
    )
    conn.commit()


def run_quality_checks(conn, run_id):
    cur = conn.cursor()
    checks = [
        ("dim_customers", "missing_email", "WARNING",
         "SELECT COUNT(*) FROM dim_customers WHERE email IS NULL", "email is NULL"),
        ("fact_orders", "missing_amount", "CRITICAL",
         "SELECT COUNT(*) FROM fact_orders WHERE amount IS NULL", "amount is NULL"),
        ("fact_orders", "missing_status", "WARNING",
         "SELECT COUNT(*) FROM fact_orders WHERE status IS NULL", "status is NULL"),
        ("fact_orders", "invalid_order_date", "CRITICAL",
         "SELECT COUNT(*) FROM fact_orders WHERE order_date IS NULL", "order_date failed to parse"),
        ("fact_orders", "negative_amount", "WARNING",
         "SELECT COUNT(*) FROM fact_orders WHERE amount < 0", "amount < 0"),
        ("fact_orders", "row_reconciliation", "INFO",
         "SELECT (SELECT COUNT(*) FROM stg_orders) - (SELECT COUNT(*) FROM fact_orders)",
         "rows dropped between staging and curated (dupes, orphans, bad keys)"),
    ]
    total_critical = 0
    for table, name, severity, query, details in checks:
        n = cur.execute(query).fetchone()[0]
        if severity == "CRITICAL":
            total_critical += n
        cur.execute(
            "INSERT INTO data_quality_log (run_id,table_name,check_name,severity,rows_affected,details) VALUES (?,?,?,?,?,?)",
            (run_id, table, name, severity, n, details)
        )
    conn.commit()
    return total_critical


def log_run(conn, name, start, end, status, rows_read, rows_loaded, rows_rejected, error=None):
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO pipeline_run_log
           (pipeline_name, run_start, run_end, status, rows_read, rows_loaded, rows_rejected, error_message)
           VALUES (?,?,?,?,?,?,?,?)""",
        (name, start.isoformat(), end.isoformat(), status, rows_read, rows_loaded, rows_rejected, error)
    )
    conn.commit()
    return cur.lastrowid


def main(simulate_fail: bool):
    conn = get_conn()
    init_schema(conn)
    start = datetime.now()

    if simulate_fail:
        # Simulate a real failure mode: an upstream schema change (extra/renamed column)
        # breaks the loader before any rows are committed to curated tables.
        try:
            raise RuntimeError(
                "Schema mismatch: source file 'orders_raw.csv' contains unexpected "
                "column count on row 837 (expected 5, got 3) — load aborted"
            )
        except RuntimeError as e:
            end = datetime.now()
            log_run(conn, "customer_orders_pipeline", start, end, "FAILED", 0, 0, 0, str(e))
            print(f"PIPELINE FAILED: {e}")
            conn.close()
            return

    rows_read = load_staging(conn)
    transform(conn)

    cur = conn.cursor()
    rows_loaded = cur.execute("SELECT COUNT(*) FROM fact_orders").fetchone()[0]
    rows_rejected = rows_read - rows_loaded
    end = datetime.now()

    # run_id must exist before quality checks reference it, so log first with placeholder end time
    run_id = log_run(conn, "customer_orders_pipeline", start, end, "RUNNING", rows_read, rows_loaded, rows_rejected)
    critical_issues = run_quality_checks(conn, run_id)

    final_status = "SUCCESS_WITH_WARNINGS" if critical_issues > 0 else "SUCCESS"
    conn.execute("UPDATE pipeline_run_log SET status=? WHERE run_id=?", (final_status, run_id))
    conn.commit()

    print(f"Run {run_id}: {final_status} | read={rows_read} loaded={rows_loaded} "
          f"rejected={rows_rejected} critical_dq_issues={critical_issues}")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate-fail", action="store_true")
    args = parser.parse_args()
    main(args.simulate_fail)
