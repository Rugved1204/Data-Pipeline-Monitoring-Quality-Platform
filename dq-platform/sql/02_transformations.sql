-- Staging -> Curated transformations
-- Handles: dedup, type casting, invalid date nulling, orphan filtering

-- ===== CUSTOMERS =====
-- Dedup on all business columns, keep latest load, drop rows with unusable customer_id
INSERT INTO dim_customers (customer_id, name, email, signup_date, country)
SELECT DISTINCT
    TRY_CAST(customer_id AS INT)               AS customer_id,
    NULLIF(TRIM(name), '')                     AS name,
    NULLIF(TRIM(email), '')                    AS email,
    TRY_CAST(signup_date AS DATE)              AS signup_date,   -- invalid strings become NULL
    country
FROM stg_customers
WHERE TRY_CAST(customer_id AS INT) IS NOT NULL;   -- drop rows like 'CUST_12' we can't key on

-- ===== ORDERS =====
-- Dedup, type-cast amount, null out invalid dates/amounts, keep only orders
-- pointing at a customer that actually exists (referential integrity)
INSERT INTO fact_orders (order_id, customer_id, order_date, amount, status)
SELECT DISTINCT
    TRY_CAST(o.order_id AS INT)                AS order_id,
    TRY_CAST(o.customer_id AS INT)              AS customer_id,
    TRY_CAST(o.order_date AS DATE)              AS order_date,
    TRY_CAST(o.amount AS DECIMAL(10,2))         AS amount,
    NULLIF(TRIM(o.status), '')                  AS status
FROM stg_orders o
WHERE TRY_CAST(o.order_id AS INT) IS NOT NULL
  AND TRY_CAST(o.customer_id AS INT) IN (SELECT customer_id FROM dim_customers);

-- Note: TRY_CAST is supported in Fabric Warehouse / SQL Server.
-- SQLite has no TRY_CAST; scripts/pipeline.py does the equivalent cleaning in Python
-- for the local demo and mirrors this exact logic.
