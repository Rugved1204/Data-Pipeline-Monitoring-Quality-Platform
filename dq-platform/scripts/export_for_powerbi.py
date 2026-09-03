"""Exports warehouse tables/views to CSV so Power BI (or Fabric) can import them directly."""
import sqlite3
import csv

DB = "/home/claude/dq-platform/data/staging/warehouse.db"
OUT = "/home/claude/dq-platform/powerbi"

QUERIES = {
    "pipeline_run_log": "SELECT * FROM pipeline_run_log",
    "data_quality_log": "SELECT * FROM data_quality_log",
    "fact_orders": "SELECT * FROM fact_orders",
    "dim_customers": "SELECT * FROM dim_customers",
    "dq_score_by_table": """
        SELECT table_name,
               SUM(CASE WHEN severity='CRITICAL' THEN rows_affected ELSE 0 END) AS critical_rows,
               SUM(CASE WHEN severity='WARNING' THEN rows_affected ELSE 0 END) AS warning_rows,
               COUNT(DISTINCT run_id) AS runs_checked
        FROM data_quality_log GROUP BY table_name
    """,
}

conn = sqlite3.connect(DB)
for name, query in QUERIES.items():
    cur = conn.execute(query)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    with open(f"{OUT}/{name}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print(f"exported {name}.csv ({len(rows)} rows)")
