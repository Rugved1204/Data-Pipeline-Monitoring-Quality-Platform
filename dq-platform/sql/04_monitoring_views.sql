-- Views Power BI connects to directly (Import or DirectQuery over the Fabric Warehouse)

CREATE VIEW vw_pipeline_run_summary AS
SELECT
    run_id, pipeline_name, run_start, run_end,
    DATEDIFF(SECOND, run_start, run_end) AS duration_seconds,
    status, rows_read, rows_loaded, rows_rejected,
    CASE WHEN rows_read = 0 THEN 0
         ELSE ROUND(100.0 * rows_rejected / rows_read, 2) END AS pct_rejected
FROM pipeline_run_log;

CREATE VIEW vw_dq_issues_by_run AS
SELECT
    l.run_id, r.pipeline_name, l.table_name, l.check_name,
    l.severity, l.rows_affected, l.check_ts
FROM data_quality_log l
JOIN pipeline_run_log r ON l.run_id = r.run_id;

CREATE VIEW vw_dq_score_by_table AS
SELECT
    table_name,
    SUM(CASE WHEN severity = 'CRITICAL' THEN rows_affected ELSE 0 END) AS critical_rows,
    SUM(CASE WHEN severity = 'WARNING' THEN rows_affected ELSE 0 END)  AS warning_rows,
    COUNT(DISTINCT run_id) AS runs_checked
FROM data_quality_log
GROUP BY table_name;
