# Power BI Monitoring Dashboard

## Data source
Import the 5 CSVs in this folder directly (Get Data → Text/CSV), or — if you have
a real Fabric workspace — point Power BI at the Warehouse using the views in
`sql/04_monitoring_views.sql` instead (Get Data → SQL Server / Fabric Warehouse
connector, DirectQuery or Import).

Tables: `pipeline_run_log`, `data_quality_log`, `fact_orders`, `dim_customers`,
`dq_score_by_table`.

## Relationships
- `data_quality_log[run_id]` → `pipeline_run_log[run_id]` (many-to-one)
- `fact_orders[customer_id]` → `dim_customers[customer_id]` (many-to-one)

## Core DAX measures
```
Total Runs = COUNTROWS(pipeline_run_log)

Failed Runs = CALCULATE(COUNTROWS(pipeline_run_log), pipeline_run_log[status] = "FAILED")

Pipeline Success Rate =
DIVIDE([Total Runs] - [Failed Runs], [Total Runs], 0)

Critical DQ Issues =
CALCULATE(SUM(data_quality_log[rows_affected]), data_quality_log[severity] = "CRITICAL")

Rejection Rate =
DIVIDE(SUM(pipeline_run_log[rows_rejected]), SUM(pipeline_run_log[rows_read]), 0)

Latest Run Status =
CALCULATE(
    SELECTEDVALUE(pipeline_run_log[status]),
    FILTER(pipeline_run_log, pipeline_run_log[run_id] = MAX(pipeline_run_log[run_id]))
)
```

## Suggested pages
1. **Pipeline Health** — KPI cards (Success Rate, Failed Runs, Latest Run Status),
   a run timeline (run_start vs duration), rows_read/rows_loaded/rows_rejected as
   a stacked bar per run.
2. **Data Quality** — matrix of `check_name` × `severity` with `rows_affected`,
   a bar chart of `dq_score_by_table` (critical vs warning), trend of critical
   issues over `run_id`.
3. **Incident Detail** — table visual filtered to `status = "FAILED"` showing
   `error_message`, for the RCA narrative.

## Alerting concept (talk track, no extra tooling needed)
Set a Power BI data alert on **Critical DQ Issues** or **Pipeline Success Rate**
tiles (via a published dashboard) so a threshold breach — e.g. more than 5
critical issues in a run — notifies you. In a production Fabric setup this maps
to Fabric's pipeline alerting / Data Activator monitoring the same metric.
