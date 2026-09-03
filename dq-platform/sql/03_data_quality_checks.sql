-- Data quality checks run after each load. Each check inserts one row per
-- rule violation into data_quality_log. :run_id is bound by the pipeline.

-- 1. Missing values (critical fields null after cast)
INSERT INTO data_quality_log (run_id, table_name, check_name, severity, rows_affected, details)
SELECT :run_id, 'dim_customers', 'missing_email', 'WARNING', COUNT(*), 'email is NULL'
FROM dim_customers WHERE email IS NULL;

INSERT INTO data_quality_log (run_id, table_name, check_name, severity, rows_affected, details)
SELECT :run_id, 'fact_orders', 'missing_amount', 'CRITICAL', COUNT(*), 'amount is NULL'
FROM fact_orders WHERE amount IS NULL;

-- 2. Invalid dates (cast to NULL that weren't NULL in staging = bad format)
INSERT INTO data_quality_log (run_id, table_name, check_name, severity, rows_affected, details)
SELECT :run_id, 'fact_orders', 'invalid_order_date', 'CRITICAL', COUNT(*), 'order_date failed to parse'
FROM fact_orders WHERE order_date IS NULL;

-- 3. Duplicate records (should be zero post-transform; flags if dedup logic regresses)
INSERT INTO data_quality_log (run_id, table_name, check_name, severity, rows_affected, details)
SELECT :run_id, 'fact_orders', 'duplicate_order_id', 'CRITICAL', COUNT(*) - COUNT(DISTINCT order_id), 'duplicate order_id in fact_orders'
FROM fact_orders;

-- 4. Referential integrity (orphaned orders that lost their customer at cast time)
INSERT INTO data_quality_log (run_id, table_name, check_name, severity, rows_affected, details)
SELECT :run_id, 'fact_orders', 'orphan_customer_ref', 'CRITICAL', COUNT(*), 'customer_id not found in dim_customers'
FROM fact_orders f
LEFT JOIN dim_customers c ON f.customer_id = c.customer_id
WHERE c.customer_id IS NULL;

-- 5. Value range checks
INSERT INTO data_quality_log (run_id, table_name, check_name, severity, rows_affected, details)
SELECT :run_id, 'fact_orders', 'negative_amount', 'WARNING', COUNT(*), 'amount < 0'
FROM fact_orders WHERE amount < 0;

-- 6. Row-count reconciliation (source vs curated -> shows how much was dropped)
INSERT INTO data_quality_log (run_id, table_name, check_name, severity, rows_affected, details)
SELECT :run_id, 'fact_orders', 'row_reconciliation', 'INFO',
       (SELECT COUNT(*) FROM stg_orders) - (SELECT COUNT(*) FROM fact_orders),
       'rows dropped between staging and curated'
FROM (SELECT 1) x;
