# Data Pipeline Monitoring & Quality Platform

A small end-to-end ELT pipeline that ingests dirty CSV data, loads it through a
staging → curated warehouse pattern, runs SQL-based data quality checks, and
logs every run for monitoring in Power BI.

Built locally with SQLite as a stand-in for a Microsoft Fabric Lakehouse/Warehouse.
All SQL in `sql/` is written in Fabric/T-SQL syntax (`TRY_CAST`, `IDENTITY`,
`DATETIME2`) — it will run unmodified against a real Fabric Warehouse; the Python
pipeline mirrors the same logic locally since SQLite lacks `TRY_CAST`.

## Architecture
```
CSV (deliberately dirty)
      ↓
Ingestion (scripts/pipeline.py: load_staging)
      ↓
Staging tables (stg_customers, stg_orders)   -- untyped landing zone
      ↓
Transformations (cast, clean, dedupe, referential-integrity filter)
      ↓
Curated tables (dim_customers, fact_orders)
      ↓
Data quality checks (6 rules → data_quality_log)
      ↓
Power BI (powerbi/*.csv or Fabric views)
      ↓
Monitoring: pipeline_run_log + data_quality_log = error/quality log
```

## Problems deliberately injected
| Problem | Where | How it's caught |
|---|---|---|
| Missing values | email, amount, status | `missing_email`, `missing_amount`, `missing_status` checks |
| Duplicate records | customers, orders | dedup in transform step; `duplicate_order_id` check |
| Invalid dates | `2025-13-40`, `not_a_date`, `31/02/2024` | cast fails → NULL → `invalid_order_date` check |
| Incorrect data types | `customer_id` as `"CUST_12"`, `amount` as `"free"`/`"$45.00"` | `TRY_CAST`/`try_int`/`try_float` reject → row dropped or nulled |
| Incomplete records | ragged rows with missing trailing columns | padded/rejected at load; shows in `row_reconciliation` |
| Failed pipeline | simulated upstream schema change | `pipeline.py --simulate-fail` logs a FAILED run with error_message |

## How to run
```bash
python3 scripts/generate_raw_data.py     # regenerate dirty source data (seeded, reproducible)
python3 scripts/pipeline.py --simulate-fail   # run 1: fails (schema mismatch)
python3 scripts/pipeline.py                   # run 2: succeeds, but with warnings
python3 scripts/pipeline.py                   # run 3: succeeds again (steady state)
python3 scripts/export_for_powerbi.py         # refresh CSVs for Power BI
```

## Incident timeline (what actually happened in this run history)
- **Run 1 — FAILED.** Root cause: an upstream file drift — a row in
  `orders_raw.csv` had fewer columns than expected, which a stricter version of
  the loader treated as a hard schema mismatch and aborted before writing
  anything to curated tables. `pipeline_run_log.error_message` captures the
  exact row and column count.
- **Fix applied:** the loader was made resilient to ragged rows (pads missing
  trailing fields instead of crashing) — see `load_staging()` in `pipeline.py`.
- **Run 2 — SUCCESS_WITH_WARNINGS.** 833 rows read, 780 loaded, 53 rejected
  (duplicates, orphaned customer_ids, unparseable keys). 72 critical data
  quality findings logged (missing amounts, invalid dates) — data loaded, but
  flagged for downstream consumers rather than silently dropped.
- **Run 3 — SUCCESS_WITH_WARNINGS.** Same profile, confirming steady state
  (no regression).

## RCA template used above (reusable for any future failure)
1. **Detect** — pipeline_run_log.status = FAILED, alert on Power BI tile.
2. **Diagnose** — read error_message, check rows_read (0 = failed before any I/O).
3. **Root cause** — trace to a specific source anomaly (here: ragged row / schema drift).
4. **Fix** — code change (defensive parsing), not just re-running the job.
5. **Verify** — next run's rows_rejected and critical_dq_issues should drop or hold steady, not spike.
6. **Prevent** — add a data_quality_log check that would have caught this class of issue earlier (row_reconciliation does this here).

## What this project lets you talk about
- **ETL/ELT**: staging → curated pattern, load-then-transform vs transform-then-load trade-offs.
- **SQL**: `TRY_CAST`, `NULLIF`, dedup via `DISTINCT`, referential-integrity joins.
- **Data validation / quality**: rule-based checks, severity tiers (INFO/WARNING/CRITICAL), row reconciliation.
- **Monitoring & logging**: two-table log design (run-level + check-level) so Power BI can drill from a KPI down to a specific rejected row.
- **Troubleshooting / incident resolution / RCA**: the run-1 failure above is a real, reproducible incident you can walk through in an interview.
- **Automation**: everything runs from one command; trivially schedulable as a Fabric Data Factory pipeline or a cron job.
- **Power BI**: see `powerbi/POWERBI_GUIDE.md` for the semantic model and DAX.

## Porting to real Microsoft Fabric
1. Create a Fabric Lakehouse, upload `data/raw/*.csv` as files.
2. Create a Warehouse, run `sql/01_create_tables.sql` as-is.
3. Use a Fabric Data Pipeline (or Dataflow Gen2) to copy CSVs into `stg_*` tables.
4. Run `sql/02_transformations.sql` then `sql/03_data_quality_checks.sql` as a
   pipeline SQL script activity, binding `:run_id` from a prior INSERT into
   `pipeline_run_log`.
5. Run `sql/04_monitoring_views.sql` once; point Power BI at the Warehouse
   directly instead of the CSV exports.
