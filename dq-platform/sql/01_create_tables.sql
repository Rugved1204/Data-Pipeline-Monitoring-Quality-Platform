-- Fabric Lakehouse/Warehouse DDL
-- Run against your Fabric Warehouse (or SQLite/SQL Server for local testing)

-- ===== STAGING (raw, untyped landing zone) =====
CREATE TABLE stg_customers (
    customer_id   VARCHAR(50),
    name          VARCHAR(200),
    email         VARCHAR(200),
    signup_date   VARCHAR(50),
    country       VARCHAR(100),
    load_ts       DATETIME2 DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE stg_orders (
    order_id      VARCHAR(50),
    customer_id   VARCHAR(50),
    order_date    VARCHAR(50),
    amount        VARCHAR(50),
    status        VARCHAR(50),
    load_ts       DATETIME2 DEFAULT CURRENT_TIMESTAMP
);

-- ===== CURATED (typed, cleaned, deduplicated) =====
CREATE TABLE dim_customers (
    customer_id   INT PRIMARY KEY,
    name          VARCHAR(200),
    email         VARCHAR(200),
    signup_date   DATE,
    country       VARCHAR(100)
);

CREATE TABLE fact_orders (
    order_id      INT PRIMARY KEY,
    customer_id   INT,
    order_date    DATE,
    amount        DECIMAL(10,2),
    status        VARCHAR(50)
);

-- ===== MONITORING / LOGGING =====
CREATE TABLE pipeline_run_log (
    run_id        INT IDENTITY(1,1) PRIMARY KEY,
    pipeline_name VARCHAR(100),
    run_start     DATETIME2,
    run_end       DATETIME2,
    status        VARCHAR(20),          -- SUCCESS / FAILED / SUCCESS_WITH_WARNINGS
    rows_read     INT,
    rows_loaded   INT,
    rows_rejected INT,
    error_message VARCHAR(2000)
);

CREATE TABLE data_quality_log (
    check_id      INT IDENTITY(1,1) PRIMARY KEY,
    run_id        INT,
    table_name    VARCHAR(100),
    check_name    VARCHAR(100),
    severity      VARCHAR(20),          -- INFO / WARNING / CRITICAL
    rows_affected INT,
    check_ts      DATETIME2 DEFAULT CURRENT_TIMESTAMP,
    details       VARCHAR(2000)
);
