-- ==============================================================================
-- 04_ptp_cleaning.sql
-- CredResolve Collections Performance Forensics: Phase 2 Data Cleaning
-- Purpose: Promise-to-Pay (PTP) validation, fulfillment flags, and UTC alignment.
-- ==============================================================================

-- 1. Create Raw PTP Staging Table
CREATE TABLE IF NOT EXISTS stg_raw_promises_to_pay (
    ptp_id          VARCHAR(64) PRIMARY KEY,
    account_id      VARCHAR(64),
    borrower_id     VARCHAR(64),
    event_at        TIMESTAMP,
    agent_id        VARCHAR(64),
    promised_amount DECIMAL(18, 2),
    promised_date   TIMESTAMP,
    status          VARCHAR(32),
    source          VARCHAR(32)
);

-- 2. Audit Uniqueness and Null Values
SELECT 
    COUNT(*) AS total_ptp_records,
    COUNT(DISTINCT ptp_id) AS unique_ptp_ids,
    SUM(CASE WHEN account_id IS NULL THEN 1 ELSE 0 END) AS null_accounts,
    SUM(CASE WHEN promised_amount <= 0 THEN 1 ELSE 0 END) AS invalid_amounts,
    SUM(CASE WHEN promised_date < event_at THEN 1 ELSE 0 END) AS past_dated_promises
FROM stg_raw_promises_to_pay;

-- 3. Create Clean PTP Table (Golden Dataset)
CREATE TABLE IF NOT EXISTS ptp_clean AS
SELECT 
    p.ptp_id,
    p.account_id,
    p.borrower_id,
    p.event_at AS event_at_original,
    a.timezone AS account_timezone,
    -- Timezone conversion to UTC using account timezone
    CASE 
        WHEN a.timezone = 'UTC' THEN p.event_at
        WHEN a.timezone = 'Asia/Kolkata' THEN p.event_at - INTERVAL '5 hours 30 minutes'
        WHEN a.timezone = 'Asia/Dubai' THEN p.event_at - INTERVAL '4 hours'
        ELSE p.event_at
    END AS event_at_utc,
    p.agent_id,
    p.promised_amount,
    p.promised_date AS promised_date_original,
    CASE 
        WHEN a.timezone = 'UTC' THEN p.promised_date
        WHEN a.timezone = 'Asia/Kolkata' THEN p.promised_date - INTERVAL '5 hours 30 minutes'
        WHEN a.timezone = 'Asia/Dubai' THEN p.promised_date - INTERVAL '4 hours'
        ELSE p.promised_date
    END AS promised_date_utc,
    p.status,
    p.source,
    -- Analytical Fulfillment Flags
    CASE WHEN p.status = 'KEPT' THEN TRUE ELSE FALSE END AS is_kept,
    CASE WHEN p.status = 'BROKEN' THEN TRUE ELSE FALSE END AS is_broken,
    CASE WHEN p.status = 'CANCELLED' THEN TRUE ELSE FALSE END AS is_cancelled,
    CASE WHEN p.status = 'OPEN' THEN TRUE ELSE FALSE END AS is_open
FROM stg_raw_promises_to_pay p
JOIN accounts_clean a ON p.account_id = a.account_id;

-- 4. PTP Conversion Metrics Audit Query
SELECT 
    status,
    COUNT(*) AS ptp_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_ptp,
    SUM(promised_amount) AS total_promised_amount,
    ROUND(AVG(promised_amount), 2) AS avg_promised_amount
FROM ptp_clean
GROUP BY status
ORDER BY ptp_count DESC;
