-- ==============================================================================
-- 03_call_cleaning.sql
-- CredResolve Collections Performance Forensics: Phase 2 Data Cleaning
-- Purpose: Call deduplication, conflict isolation, quarantine partitioning,
--          and multi-timezone conversion to UTC.
-- ==============================================================================

-- 1. Create Raw Calls Staging Table
CREATE TABLE IF NOT EXISTS stg_raw_calls (
    call_id         VARCHAR(64),
    account_id      VARCHAR(64),
    borrower_id     VARCHAR(64),
    event_at        TIMESTAMP,
    agent_id        VARCHAR(64),
    campaign_id     VARCHAR(64),
    direction       VARCHAR(16),
    vendor_id       VARCHAR(32),
    call_status     VARCHAR(32),
    duration_sec    INTEGER,
    timezone        VARCHAR(32)
);

-- 2. Classify Calls: Unique vs Exact Duplicate vs Conflicting
WITH call_id_groups AS (
    SELECT 
        call_id,
        COUNT(*) AS row_count,
        COUNT(DISTINCT account_id) AS distinct_accounts,
        COUNT(DISTINCT event_at) AS distinct_timestamps,
        COUNT(DISTINCT agent_id) AS distinct_agents,
        COUNT(DISTINCT call_status) AS distinct_statuses,
        COUNT(DISTINCT duration_sec) AS distinct_durations,
        COUNT(DISTINCT timezone) AS distinct_timezones
    FROM stg_raw_calls
    GROUP BY call_id
    HAVING COUNT(*) > 1
),
call_classification AS (
    SELECT 
        c.*,
        cig.row_count,
        CASE 
            WHEN cig.call_id IS NULL THEN 'UNIQUE'
            WHEN cig.distinct_accounts = 1 
             AND cig.distinct_timestamps = 1 
             AND (cig.distinct_agents = 1 OR (c.agent_id IS NULL AND cig.distinct_agents = 0))
             AND cig.distinct_statuses = 1 
             AND cig.distinct_durations = 1 
             AND cig.distinct_timezones = 1 
            THEN 'VERIFIED_EXACT_DUPLICATE'
            ELSE 'CONFLICTING_ATTRIBUTES'
        END AS record_category,
        ROW_NUMBER() OVER (
            PARTITION BY c.call_id, c.account_id, c.event_at, c.agent_id, c.campaign_id, c.direction, c.vendor_id, c.call_status, c.duration_sec, c.timezone
            ORDER BY c.event_at
        ) AS exact_dup_rank
    FROM stg_raw_calls c
    LEFT JOIN call_id_groups cig ON c.call_id = cig.call_id
)

-- 3. Quarantine Conflicting Call Records
CREATE TABLE IF NOT EXISTS quarantine_call_conflicts AS
SELECT 
    call_id,
    account_id,
    borrower_id,
    event_at,
    agent_id,
    campaign_id,
    direction,
    vendor_id,
    call_status,
    duration_sec,
    timezone,
    'Conflicting timestamps or attributes across identical call_id' AS quarantine_reason
FROM call_classification
WHERE record_category = 'CONFLICTING_ATTRIBUTES';

-- 4. Create Analytical Clean Calls Table (Golden Dataset)
CREATE TABLE IF NOT EXISTS calls_clean AS
SELECT 
    c.call_id,
    c.account_id,
    c.borrower_id,
    c.event_at AS event_at_original,
    c.timezone,
    -- Timezone conversion to unified UTC
    CASE 
        WHEN c.timezone = 'UTC' THEN c.event_at
        WHEN c.timezone = 'Asia/Kolkata' THEN c.event_at - INTERVAL '5 hours 30 minutes'
        WHEN c.timezone = 'Asia/Dubai' THEN c.event_at - INTERVAL '4 hours'
        ELSE c.event_at
    END AS event_at_utc,
    c.agent_id,
    c.campaign_id,
    c.direction,
    c.vendor_id,
    c.call_status,
    c.duration_sec
FROM call_classification c
WHERE (c.record_category = 'UNIQUE' OR (c.record_category = 'VERIFIED_EXACT_DUPLICATE' AND c.exact_dup_rank = 1))
  AND c.record_category != 'CONFLICTING_ATTRIBUTES';

-- 5. Call Cleaning Validation Summary
SELECT 
    'Raw Calls' AS dataset_layer,
    COUNT(*) AS total_records,
    COUNT(DISTINCT call_id) AS unique_call_ids
FROM stg_raw_calls
UNION ALL
SELECT 
    'Quarantined Calls' AS dataset_layer,
    COUNT(*) AS total_records,
    COUNT(DISTINCT call_id) AS unique_call_ids
FROM quarantine_call_conflicts
UNION ALL
SELECT 
    'Clean Calls' AS dataset_layer,
    COUNT(*) AS total_records,
    COUNT(DISTINCT call_id) AS unique_call_ids
FROM calls_clean;
