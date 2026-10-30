-- ==============================================================================
-- 05_reconciliation_views.sql
-- CredResolve Collections Performance Forensics: Phase 2 Data Cleaning
-- Purpose: Analytical reconciliation views joining accounts, payments, calls, and PTP;
--          calculates portfolio recovery rates, net cash realized, and QA integrity checks.
-- ==============================================================================

-- 1. Account-Level Financial Performance View
CREATE OR REPLACE VIEW v_account_recovery_performance AS
SELECT 
    a.account_id,
    a.loan_type,
    a.risk_segment,
    a.dpd,
    a.status AS account_status,
    a.principal_amount,
    a.outstanding_amount,
    -- Financial Aggregations from Clean Payments
    COALESCE(p.gross_success_amount, 0.00) AS gross_recovered_amount,
    COALESCE(p.reversed_amount, 0.00) AS reversed_amount,
    COALESCE(p.net_realized_recovery, 0.00) AS net_realized_recovery,
    COALESCE(p.failed_amount, 0.00) AS failed_amount,
    COALESCE(p.success_payment_count, 0) AS success_payment_count,
    COALESCE(p.reversed_payment_count, 0) AS reversed_payment_count,
    -- PTP Commitments
    COALESCE(ptp.total_promised_amount, 0.00) AS total_promised_amount,
    COALESCE(ptp.kept_ptp_count, 0) AS kept_ptp_count,
    COALESCE(ptp.broken_ptp_count, 0) AS broken_ptp_count,
    -- Telephony Contacts
    COALESCE(c.total_call_count, 0) AS total_call_count,
    COALESCE(c.answered_call_count, 0) AS answered_call_count,
    -- Recovery Rate % (Net Realized Recovery / Outstanding Amount)
    CASE 
        WHEN a.outstanding_amount > 0 
        THEN ROUND((COALESCE(p.net_realized_recovery, 0.00) / a.outstanding_amount) * 100.0, 2)
        ELSE 0.00 
    END AS net_recovery_rate_pct
FROM accounts_clean a
LEFT JOIN (
    SELECT 
        account_id,
        SUM(CASE WHEN payment_status = 'SUCCESS' THEN amount ELSE 0 END) AS gross_success_amount,
        SUM(CASE WHEN payment_status = 'REVERSED' THEN amount ELSE 0 END) AS reversed_amount,
        SUM(net_cash_impact) AS net_realized_recovery,
        SUM(CASE WHEN payment_status = 'FAILED' THEN amount ELSE 0 END) AS failed_amount,
        SUM(CASE WHEN payment_status = 'SUCCESS' THEN 1 ELSE 0 END) AS success_payment_count,
        SUM(CASE WHEN payment_status = 'REVERSED' THEN 1 ELSE 0 END) AS reversed_payment_count
    FROM payments_clean
    GROUP BY account_id
) p ON a.account_id = p.account_id
LEFT JOIN (
    SELECT 
        account_id,
        SUM(promised_amount) AS total_promised_amount,
        SUM(CASE WHEN is_kept THEN 1 ELSE 0 END) AS kept_ptp_count,
        SUM(CASE WHEN is_broken THEN 1 ELSE 0 END) AS broken_ptp_count
    FROM ptp_clean
    GROUP BY account_id
) ptp ON a.account_id = ptp.account_id
LEFT JOIN (
    SELECT 
        account_id,
        COUNT(*) AS total_call_count,
        SUM(CASE WHEN call_status = 'ANSWERED' THEN 1 ELSE 0 END) AS answered_call_count
    FROM calls_clean
    GROUP BY account_id
) c ON a.account_id = c.account_id;

-- 2. Portfolio-Level Macro Financial Reconciliation View
CREATE OR REPLACE VIEW v_portfolio_reconciliation_summary AS
SELECT 
    COUNT(DISTINCT account_id) AS total_portfolio_accounts,
    SUM(principal_amount) AS total_principal_balance,
    SUM(outstanding_amount) AS total_outstanding_balance,
    SUM(gross_recovered_amount) AS total_gross_recovered,
    SUM(reversed_amount) AS total_reversed_clawback,
    SUM(net_realized_recovery) AS total_net_realized_recovery,
    ROUND((SUM(gross_recovered_amount) / SUM(outstanding_amount)) * 100.0, 2) AS gross_recovery_rate_pct,
    ROUND((SUM(net_realized_recovery) / SUM(outstanding_amount)) * 100.0, 2) AS net_recovery_rate_pct
FROM v_account_recovery_performance;

-- 3. Segmented Recovery Forensics View (by Risk Segment & Loan Type)
CREATE OR REPLACE VIEW v_recovery_by_risk_segment AS
SELECT 
    risk_segment,
    COUNT(*) AS account_count,
    SUM(outstanding_amount) AS total_outstanding,
    SUM(net_realized_recovery) AS total_net_recovery,
    ROUND((SUM(net_realized_recovery) / SUM(outstanding_amount)) * 100.0, 2) AS net_recovery_rate_pct,
    SUM(success_payment_count) AS total_success_payments,
    SUM(total_call_count) AS total_calls
FROM v_account_recovery_performance
GROUP BY risk_segment
ORDER BY total_outstanding DESC;
