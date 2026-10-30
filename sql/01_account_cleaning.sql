-- ==============================================================================
-- 01_account_cleaning.sql
-- CredResolve Collections Performance Forensics: Phase 2 Data Cleaning
-- Purpose: Clean and validate accounts master, establish account_id as primary anchor,
--          detect orphan borrower keys, and normalize opening dates to UTC.
-- ==============================================================================

-- 1. Create Raw Accounts Staging Table
CREATE TABLE IF NOT EXISTS stg_raw_accounts (
    account_id          VARCHAR(64) PRIMARY KEY,
    borrower_id         VARCHAR(64),
    loan_type           VARCHAR(32),
    principal_amount    DECIMAL(18, 2),
    outstanding_amount  DECIMAL(18, 2),
    dpd                 INTEGER,
    risk_segment        VARCHAR(32),
    status              VARCHAR(32),
    opened_at           TIMESTAMP,
    timezone            VARCHAR(32),
    schema_version      VARCHAR(16)
);

-- 2. Audit Uniqueness & Missingness
-- Verify that account_id is 100% unique across all 30,000 accounts
SELECT 
    COUNT(*) AS total_rows,
    COUNT(DISTINCT account_id) AS unique_accounts,
    COUNT(*) - COUNT(DISTINCT account_id) AS duplicate_account_ids,
    SUM(CASE WHEN account_id IS NULL THEN 1 ELSE 0 END) AS null_account_ids,
    SUM(CASE WHEN borrower_id IS NULL OR TRIM(borrower_id) = '' THEN 1 ELSE 0 END) AS null_borrower_ids
FROM stg_raw_accounts;

-- 3. Detect Orphan Borrower References
-- Identifies accounts where borrower_id does not exist in the raw borrowers table
SELECT 
    a.account_id,
    a.borrower_id,
    a.loan_type,
    a.principal_amount,
    a.outstanding_amount,
    CASE 
        WHEN a.borrower_id IS NULL OR TRIM(a.borrower_id) = '' THEN 'UNASSIGNED_NULL'
        WHEN b.borrower_id IS NULL THEN 'ORPHAN_BORROWER_ID'
        ELSE 'VALID_BORROWER'
    END AS borrower_link_status
FROM stg_raw_accounts a
LEFT JOIN (
    SELECT DISTINCT borrower_id 
    FROM stg_raw_borrowers
) b ON a.borrower_id = b.borrower_id
WHERE a.borrower_id IS NULL 
   OR TRIM(a.borrower_id) = '' 
   OR b.borrower_id IS NULL;

-- 4. Create Clean Accounts Dimension (Golden Dataset)
-- Preserves original attributes and adds normalized opened_at_utc and audit flags
CREATE TABLE IF NOT EXISTS accounts_clean AS
SELECT 
    a.account_id,
    a.borrower_id,
    a.loan_type,
    a.principal_amount,
    a.outstanding_amount,
    a.dpd,
    a.risk_segment,
    a.status,
    a.opened_at AS opened_at_original,
    a.timezone,
    a.schema_version,
    -- Timezone conversion to UTC
    CASE 
        WHEN a.timezone = 'UTC' THEN a.opened_at
        WHEN a.timezone = 'Asia/Kolkata' THEN a.opened_at - INTERVAL '5 hours 30 minutes'
        WHEN a.timezone = 'Asia/Dubai' THEN a.opened_at - INTERVAL '4 hours'
        ELSE a.opened_at
    END AS opened_at_utc,
    -- Audit classification of borrower referential integrity
    CASE 
        WHEN a.borrower_id IS NULL OR TRIM(a.borrower_id) = '' THEN TRUE
        WHEN b.borrower_id IS NULL THEN TRUE
        ELSE FALSE
    END AS is_orphan_borrower_ref,
    CASE 
        WHEN a.borrower_id IS NULL OR TRIM(a.borrower_id) = '' THEN 'UNASSIGNED_NULL'
        WHEN b.borrower_id IS NULL THEN 'ORPHAN_ID'
        ELSE 'VALID_REFERENCE'
    END AS borrower_status
FROM stg_raw_accounts a
LEFT JOIN (
    SELECT DISTINCT borrower_id 
    FROM stg_raw_borrowers
) b ON a.borrower_id = b.borrower_id;
