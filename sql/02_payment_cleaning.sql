-- ==============================================================================
-- 02_payment_cleaning.sql
-- CredResolve Collections Performance Forensics: Phase 2 Data Cleaning
-- Purpose: Payment deduplication, conflict isolation, quarantine partitioning,
--          reversal accounting, and realized recovery reconciliation.
-- ==============================================================================

-- 1. Create Raw Payments Staging Table
CREATE TABLE IF NOT EXISTS stg_raw_payments (
    payment_id          VARCHAR(64),
    account_id          VARCHAR(64),
    borrower_id         VARCHAR(64),
    event_at            TIMESTAMP,
    payment_reference   VARCHAR(64),
    amount              DECIMAL(18, 2),
    payment_status      VARCHAR(32),
    payment_method      VARCHAR(32),
    provider_id         VARCHAR(32)
);

-- 2. Classify Exact Duplicates vs. Conflicting Payment IDs
-- Groups records by payment_id and checks for attribute variances
WITH payment_id_groups AS (
    SELECT 
        payment_id,
        COUNT(*) AS row_count,
        COUNT(DISTINCT account_id) AS distinct_accounts,
        COUNT(DISTINCT event_at) AS distinct_timestamps,
        COUNT(DISTINCT amount) AS distinct_amounts,
        COUNT(DISTINCT payment_status) AS distinct_statuses,
        COUNT(DISTINCT payment_reference) AS distinct_references,
        COUNT(DISTINCT payment_method) AS distinct_methods,
        COUNT(DISTINCT provider_id) AS distinct_providers
    FROM stg_raw_payments
    GROUP BY payment_id
    HAVING COUNT(*) > 1
),
payment_classification AS (
    SELECT 
        p.*,
        pig.row_count,
        CASE 
            WHEN pig.payment_id IS NULL THEN 'UNIQUE'
            WHEN pig.distinct_accounts = 1 
             AND pig.distinct_timestamps = 1 
             AND pig.distinct_amounts = 1 
             AND pig.distinct_statuses = 1 
             AND pig.distinct_references = 1 
             AND pig.distinct_methods = 1 
             AND pig.distinct_providers = 1 
            THEN 'VERIFIED_EXACT_DUPLICATE'
            ELSE 'CONFLICTING_ATTRIBUTES'
        END AS record_category,
        ROW_NUMBER() OVER (
            PARTITION BY p.payment_id, p.account_id, p.event_at, p.amount, p.payment_status, p.payment_reference, p.payment_method, p.provider_id 
            ORDER BY p.event_at
        ) AS exact_dup_rank
    FROM stg_raw_payments p
    LEFT JOIN payment_id_groups pig ON p.payment_id = pig.payment_id
)

-- 3. Quarantine Conflicting Payment Records
-- Route all non-identical occurrences sharing a payment_id to quarantine
CREATE TABLE IF NOT EXISTS quarantine_payment_conflicts AS
SELECT 
    payment_id,
    account_id,
    borrower_id,
    event_at,
    payment_reference,
    amount,
    payment_status,
    payment_method,
    provider_id,
    'Conflicting attributes across records sharing identical payment_id' AS quarantine_reason
FROM payment_classification
WHERE record_category = 'CONFLICTING_ATTRIBUTES';

-- 4. Create Analytical Clean Payments Table (Golden Dataset)
-- Keep 1 copy of unique and verified exact duplicates; exclude conflicts
CREATE TABLE IF NOT EXISTS payments_clean AS
SELECT 
    p.payment_id,
    p.account_id,
    p.borrower_id,
    p.event_at AS event_at_original,
    a.timezone AS account_timezone,
    -- Timezone normalized to UTC based on account timezone
    CASE 
        WHEN a.timezone = 'UTC' THEN p.event_at
        WHEN a.timezone = 'Asia/Kolkata' THEN p.event_at - INTERVAL '5 hours 30 minutes'
        WHEN a.timezone = 'Asia/Dubai' THEN p.event_at - INTERVAL '4 hours'
        ELSE p.event_at
    END AS event_at_utc,
    p.payment_reference,
    p.amount,
    p.payment_status,
    p.payment_method,
    p.provider_id,
    -- Financial Recovery Classification Flags
    CASE WHEN p.payment_status = 'SUCCESS' THEN TRUE ELSE FALSE END AS is_realized_recovery,
    CASE WHEN p.payment_status = 'REVERSED' THEN TRUE ELSE FALSE END AS is_reversal,
    CASE 
        WHEN p.payment_status = 'SUCCESS' THEN 'REALIZED_RECOVERY'
        WHEN p.payment_status = 'REVERSED' THEN 'REVERSED_CLAWBACK'
        WHEN p.payment_status = 'FAILED' THEN 'FAILED_TRANSACTION'
        WHEN p.payment_status = 'PENDING' THEN 'PENDING_SETTLEMENT'
        ELSE 'OTHER'
    END AS recovery_category,
    -- Signed Cashflow Impact (Net Cash Recovery)
    CASE 
        WHEN p.payment_status = 'SUCCESS' THEN p.amount
        WHEN p.payment_status = 'REVERSED' THEN -p.amount
        ELSE 0.00
    END AS net_cash_impact
FROM payment_classification p
JOIN accounts_clean a ON p.account_id = a.account_id
WHERE (p.record_category = 'UNIQUE' OR (p.record_category = 'VERIFIED_EXACT_DUPLICATE' AND p.exact_dup_rank = 1))
  AND p.record_category != 'CONFLICTING_ATTRIBUTES';

-- 5. Financial Reconciliation Audit Query
-- Proves reconciliation totals before and after cleaning
SELECT 
    'Raw Payments' AS layer,
    payment_status,
    COUNT(*) AS txn_count,
    SUM(amount) AS total_amount
FROM stg_raw_payments
GROUP BY payment_status
UNION ALL
SELECT 
    'Clean Payments' AS layer,
    payment_status,
    COUNT(*) AS txn_count,
    SUM(amount) AS total_amount
FROM payments_clean
GROUP BY payment_status
ORDER BY layer, payment_status;
