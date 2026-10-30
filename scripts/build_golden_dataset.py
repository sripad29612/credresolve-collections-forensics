import os
import csv
import json
from datetime import datetime, timedelta
from collections import Counter, defaultdict

# Base directories
BASE_DIR = r"c:\Users\puram\Desktop\credresolve project"
RAW_DIR = os.path.join(BASE_DIR, "collections_30k_dataset (1)")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
QUARANTINE_DIR = os.path.join(BASE_DIR, "data", "quarantine")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
SQL_DIR = os.path.join(BASE_DIR, "sql")
NOTEBOOKS_DIR = os.path.join(BASE_DIR, "notebooks")
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")
DOCS_DIR = os.path.join(BASE_DIR, "docs")

def setup_directories():
    print("Setting up directory structure...")
    for d in [PROCESSED_DIR, QUARANTINE_DIR, REPORTS_DIR, SQL_DIR, NOTEBOOKS_DIR, DASHBOARD_DIR, DOCS_DIR]:
        os.makedirs(d, exist_ok=True)
        print(f"  Created/verified: {d}")

def parse_iso(dt_str):
    if not dt_str or dt_str.strip() in ("", "NULL", "None", "nan"):
        return None
    s = dt_str.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None

def convert_to_utc(dt, tz_name):
    """
    Converts a naive datetime object to a UTC ISO string based on known regional timezones.
    Asia/Kolkata is UTC+05:30 -> subtract 5h 30m.
    Asia/Dubai is UTC+04:00 -> subtract 4h.
    UTC is unchanged.
    If timezone is unknown or missing, returns None to avoid false assumptions.
    """
    if dt is None:
        return None
    if not tz_name or tz_name.strip() == "":
        return None
    tz = tz_name.strip()
    if tz == "UTC":
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    elif tz == "Asia/Kolkata":
        utc_dt = dt - timedelta(hours=5, minutes=30)
        return utc_dt.strftime("%Y-%m-%d %H:%M:%S")
    elif tz == "Asia/Dubai":
        utc_dt = dt - timedelta(hours=4)
        return utc_dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return None

def execute_cleaning_pipeline():
    setup_directories()
    
    summary_metrics = {
        "pipeline_run_at": datetime.now().isoformat(),
        "tables": {},
        "quarantine_summary": {},
        "financial_reconciliation": {},
        "referential_integrity": {}
    }

    # ==========================================
    # 1. LOAD REFERENCE DATA (Borrowers & Accounts)
    # ==========================================
    print("\n--- STEP 1: LOADING & PROFILING BORROWERS ---")
    borrowers_raw_path = os.path.join(RAW_DIR, "borrowers.csv")
    with open(borrowers_raw_path, "r", encoding="utf-8") as f:
        borrower_rows = list(csv.DictReader(f))
    raw_borrower_count = len(borrower_rows)
    print(f"Raw borrower records: {raw_borrower_count}")

    # Build borrower ID index and conflict profile
    borrower_by_id = defaultdict(list)
    for r in borrower_rows:
        borrower_by_id[r["borrower_id"]].append(r)
    
    known_borrower_ids = set(borrower_by_id.keys())
    print(f"Distinct borrower IDs: {len(known_borrower_ids)}")

    # Identity exception analysis
    borrower_exceptions = []
    for bid, rlist in borrower_by_id.items():
        if len(rlist) > 1:
            names = set(r["name"] for r in rlist)
            phones = set(r["phone"] for r in rlist if r["phone"])
            emails = set(r["email"] for r in rlist if r["email"])
            cities = set(r["city"] for r in rlist)
            states = set(r["state"] for r in rlist)
            if len(names) > 1 or len(phones) > 1 or len(cities) > 1:
                borrower_exceptions.append({
                    "borrower_id": bid,
                    "record_count": len(rlist),
                    "distinct_names": len(names),
                    "sample_names": " | ".join(list(names)[:3]),
                    "distinct_phones": len(phones),
                    "sample_phones": " | ".join(list(phones)[:3]),
                    "distinct_cities": len(cities),
                    "sample_cities": " | ".join(list(cities)[:3]),
                    "sample_states": " | ".join(list(states)[:3])
                })

    # Save borrower identity exception report
    borrower_exc_path = os.path.join(REPORTS_DIR, "borrower_identity_exceptions.csv")
    if borrower_exceptions:
        with open(borrower_exc_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(borrower_exceptions[0].keys()))
            writer.writeheader()
            writer.writerows(borrower_exceptions)
        print(f"Wrote {len(borrower_exceptions)} borrower identity exceptions to {borrower_exc_path}")

    # ==========================================
    # 2. ACCOUNT CLEANING
    # ==========================================
    print("\n--- STEP 2: CLEANING ACCOUNTS ---")
    accounts_raw_path = os.path.join(RAW_DIR, "accounts.csv")
    with open(accounts_raw_path, "r", encoding="utf-8") as f:
        account_rows = list(csv.DictReader(f))
    raw_account_count = len(account_rows)
    print(f"Raw account records: {raw_account_count}")

    # Map account_id to timezone and borrower_id for downstream event normalization
    account_tz_map = {}
    clean_account_rows = []
    orphan_borrower_ref_count = 0
    null_borrower_count = 0
    total_principal = 0.0
    total_outstanding = 0.0

    for r in account_rows:
        aid = r["account_id"]
        bid = r["borrower_id"].strip() if r["borrower_id"] else ""
        tz = r["timezone"].strip()
        account_tz_map[aid] = tz

        # Validate borrower reference
        is_null_borrower = (bid == "" or bid.lower() in ("null", "none"))
        is_orphan = is_null_borrower or (bid not in known_borrower_ids)

        if is_null_borrower:
            null_borrower_count += 1
        elif is_orphan:
            orphan_borrower_ref_count += 1

        # Calculate UTC opened_at
        opened_dt = parse_iso(r["opened_at"])
        opened_at_utc = convert_to_utc(opened_dt, tz)

        p_amt = float(r["principal_amount"])
        o_amt = float(r["outstanding_amount"])
        total_principal += p_amt
        total_outstanding += o_amt

        clean_row = dict(r)
        clean_row["opened_at_utc"] = opened_at_utc if opened_at_utc else r["opened_at"]
        clean_row["is_orphan_borrower_ref"] = "TRUE" if is_orphan else "FALSE"
        clean_row["borrower_status"] = "UNASSIGNED_NULL" if is_null_borrower else ("ORPHAN_ID" if is_orphan else "VALID_REFERENCE")
        clean_account_rows.append(clean_row)

    accounts_clean_path = os.path.join(PROCESSED_DIR, "accounts_clean.csv")
    fieldnames_acc = list(clean_account_rows[0].keys())
    with open(accounts_clean_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_acc)
        writer.writeheader()
        writer.writerows(clean_account_rows)
    print(f"Wrote clean accounts to {accounts_clean_path} ({len(clean_account_rows)} rows)")
    print(f"  Null borrower IDs: {null_borrower_count}")
    print(f"  Orphan borrower IDs (not in borrowers.csv): {orphan_borrower_ref_count}")
    print(f"  Total Portfolio Principal: INR {total_principal:,.2f}")
    print(f"  Total Portfolio Outstanding: INR {total_outstanding:,.2f}")

    summary_metrics["tables"]["accounts"] = {
        "raw_rows": raw_account_count,
        "clean_rows": len(clean_account_rows),
        "quarantined_rows": 0,
        "null_borrower_ids": null_borrower_count,
        "orphan_borrower_ids": orphan_borrower_ref_count,
        "total_principal": total_principal,
        "total_outstanding": total_outstanding
    }

    # ==========================================
    # 3. PAYMENT CLEANING & FINANCIAL RECONCILIATION
    # ==========================================
    print("\n--- STEP 3: CLEANING PAYMENTS & FINANCIAL RECONCILIATION ---")
    payments_raw_path = os.path.join(RAW_DIR, "payments.csv")
    with open(payments_raw_path, "r", encoding="utf-8") as f:
        payment_rows = list(csv.DictReader(f))
    raw_payment_count = len(payment_rows)
    print(f"Raw payment records: {raw_payment_count}")

    # Track raw totals by status
    raw_pay_counts = Counter()
    raw_pay_amounts = defaultdict(float)
    for r in payment_rows:
        st = r["payment_status"]
        amt = float(r["amount"])
        raw_pay_counts[st] += 1
        raw_pay_amounts[st] += amt

    # Group payments by payment_id
    p_by_id = defaultdict(list)
    for r in payment_rows:
        p_by_id[r["payment_id"]].append(r)

    clean_payments = []
    quarantine_payments = []
    exact_duplicate_payment_count = 0
    exact_duplicate_amounts = defaultdict(float)

    for pid, rlist in p_by_id.items():
        if len(rlist) == 1:
            clean_payments.append(rlist[0])
        else:
            first_t = tuple(rlist[0].items())
            all_identical = all(tuple(r.items()) == first_t for r in rlist)
            if all_identical:
                # Keep exactly 1 verified copy
                clean_payments.append(rlist[0])
                # Count the redundant duplicates
                for dup_row in rlist[1:]:
                    exact_duplicate_payment_count += 1
                    exact_duplicate_amounts[dup_row["payment_status"]] += float(dup_row["amount"])
            else:
                # Conflicting records! Quarantine all occurrences
                for conflict_row in rlist:
                    q_row = dict(conflict_row)
                    q_row["quarantine_reason"] = "Conflicting attributes across records sharing identical payment_id"
                    quarantine_payments.append(q_row)

    # Process clean payments: add UTC timestamp, net financial impact, and accounting flags
    processed_clean_payments = []
    clean_pay_counts = Counter()
    clean_pay_amounts = defaultdict(float)

    for r in clean_payments:
        pid = r["payment_id"]
        aid = r["account_id"]
        st = r["payment_status"]
        amt = float(r["amount"])
        
        clean_pay_counts[st] += 1
        clean_pay_amounts[st] += amt

        # Timezone conversion using account timezone
        acc_tz = account_tz_map.get(aid, "UTC")
        ev_dt = parse_iso(r["event_at"])
        ev_at_utc = convert_to_utc(ev_dt, acc_tz)

        # Financial recovery accounting logic:
        # SUCCESS = Realized gross recovery
        # REVERSED = Subtracted clawback
        # FAILED, PENDING = Excluded from recovery
        is_realized = (st == "SUCCESS")
        is_reversal = (st == "REVERSED")
        
        if is_realized:
            net_impact = amt
            recovery_category = "REALIZED_RECOVERY"
        elif is_reversal:
            net_impact = -amt
            recovery_category = "REVERSED_CLAWBACK"
        elif st == "FAILED":
            net_impact = 0.0
            recovery_category = "FAILED_TRANSACTION"
        elif st == "PENDING":
            net_impact = 0.0
            recovery_category = "PENDING_SETTLEMENT"
        else:
            net_impact = 0.0
            recovery_category = "UNKNOWN"

        clean_row = dict(r)
        clean_row["account_timezone"] = acc_tz
        clean_row["event_at_utc"] = ev_at_utc if ev_at_utc else r["event_at"]
        clean_row["is_realized_recovery"] = "TRUE" if is_realized else "FALSE"
        clean_row["is_reversal"] = "TRUE" if is_reversal else "FALSE"
        clean_row["recovery_category"] = recovery_category
        clean_row["net_cash_impact"] = f"{net_impact:.2f}"
        processed_clean_payments.append(clean_row)

    # Save clean payments
    payments_clean_path = os.path.join(PROCESSED_DIR, "payments_clean.csv")
    fieldnames_pay = list(processed_clean_payments[0].keys())
    with open(payments_clean_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_pay)
        writer.writeheader()
        writer.writerows(processed_clean_payments)
    print(f"Wrote clean payments to {payments_clean_path} ({len(processed_clean_payments)} rows)")

    # Save quarantined payments
    payment_quarantine_path = os.path.join(QUARANTINE_DIR, "payment_conflicts.csv")
    fieldnames_pay_q = list(quarantine_payments[0].keys()) if quarantine_payments else fieldnames_pay + ["quarantine_reason"]
    with open(payment_quarantine_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_pay_q)
        writer.writeheader()
        writer.writerows(quarantine_payments)
    print(f"Wrote {len(quarantine_payments)} quarantined payment conflicts to {payment_quarantine_path}")

    # Financial Reconciliation Calculations
    gross_recovery_clean = clean_pay_amounts["SUCCESS"]
    reversed_amount_clean = clean_pay_amounts["REVERSED"]
    net_realized_clean = gross_recovery_clean - reversed_amount_clean

    gross_recovery_raw = raw_pay_amounts["SUCCESS"]
    reversed_amount_raw = raw_pay_amounts["REVERSED"]
    net_realized_raw = gross_recovery_raw - reversed_amount_raw

    print("\n--- PAYMENT FINANCIAL AUDIT ---")
    print(f"Raw Gross Success: INR {gross_recovery_raw:,.2f} ({raw_pay_counts['SUCCESS']} txns)")
    print(f"Clean Gross Success: INR {gross_recovery_clean:,.2f} ({clean_pay_counts['SUCCESS']} txns)")
    print(f"Clean Reversals: INR {reversed_amount_clean:,.2f} ({clean_pay_counts['REVERSED']} txns)")
    print(f"Clean Net Realized Recovery (SUCCESS - REVERSED): INR {net_realized_clean:,.2f}")
    print(f"Clean Excluded Volume (FAILED + PENDING): INR {clean_pay_amounts['FAILED'] + clean_pay_amounts['PENDING']:,.2f}")

    summary_metrics["tables"]["payments"] = {
        "raw_rows": raw_payment_count,
        "clean_rows": len(processed_clean_payments),
        "exact_duplicates_removed": exact_duplicate_payment_count,
        "quarantined_conflicts": len(quarantine_payments),
        "clean_counts_by_status": dict(clean_pay_counts),
        "clean_amounts_by_status": dict(clean_pay_amounts)
    }

    summary_metrics["financial_reconciliation"]["payments"] = {
        "raw_gross_recovery_success": gross_recovery_raw,
        "raw_reversed_amount": reversed_amount_raw,
        "raw_net_recovery": net_realized_raw,
        "clean_gross_recovery_success": gross_recovery_clean,
        "clean_reversed_amount": reversed_amount_clean,
        "clean_net_realized_recovery": net_realized_clean,
        "clean_excluded_failed_amount": clean_pay_amounts["FAILED"],
        "clean_excluded_pending_amount": clean_pay_amounts["PENDING"]
    }

    # ==========================================
    # 4. CALL CLEANING
    # ==========================================
    print("\n--- STEP 4: CLEANING CALLS ---")
    calls_raw_path = os.path.join(RAW_DIR, "calls.csv")
    with open(calls_raw_path, "r", encoding="utf-8") as f:
        call_rows = list(csv.DictReader(f))
    raw_call_count = len(call_rows)
    print(f"Raw call records: {raw_call_count}")

    c_by_id = defaultdict(list)
    for r in call_rows:
        c_by_id[r["call_id"]].append(r)

    clean_calls = []
    quarantine_calls = []
    exact_duplicate_call_count = 0

    for cid, rlist in c_by_id.items():
        if len(rlist) == 1:
            clean_calls.append(rlist[0])
        else:
            first_t = tuple(rlist[0].items())
            all_identical = all(tuple(r.items()) == first_t for r in rlist)
            if all_identical:
                # Keep 1 verified copy
                clean_calls.append(rlist[0])
                exact_duplicate_call_count += (len(rlist) - 1)
            else:
                # Conflicting call ID! Quarantine all
                for c_row in rlist:
                    q_c = dict(c_row)
                    q_c["quarantine_reason"] = "Conflicting timestamps or attributes across identical call_id"
                    quarantine_calls.append(q_c)

    # Add normalized UTC timestamps to clean calls
    processed_clean_calls = []
    for r in clean_calls:
        tz = r.get("timezone", "").strip()
        ev_dt = parse_iso(r["event_at"])
        ev_at_utc = convert_to_utc(ev_dt, tz)

        clean_row = dict(r)
        clean_row["event_at_utc"] = ev_at_utc if ev_at_utc else r["event_at"]
        processed_clean_calls.append(clean_row)

    # Save clean calls
    calls_clean_path = os.path.join(PROCESSED_DIR, "calls_clean.csv")
    fieldnames_calls = list(processed_clean_calls[0].keys())
    with open(calls_clean_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_calls)
        writer.writeheader()
        writer.writerows(processed_clean_calls)
    print(f"Wrote clean calls to {calls_clean_path} ({len(processed_clean_calls)} rows)")

    # Save quarantined calls
    call_quarantine_path = os.path.join(QUARANTINE_DIR, "call_conflicts.csv")
    fieldnames_calls_q = list(quarantine_calls[0].keys()) if quarantine_calls else fieldnames_calls + ["quarantine_reason"]
    with open(call_quarantine_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_calls_q)
        writer.writeheader()
        writer.writerows(quarantine_calls)
    print(f"Wrote {len(quarantine_calls)} quarantined call conflicts to {call_quarantine_path}")

    summary_metrics["tables"]["calls"] = {
        "raw_rows": raw_call_count,
        "clean_rows": len(processed_clean_calls),
        "exact_duplicates_removed": exact_duplicate_call_count,
        "quarantined_conflicts": len(quarantine_calls)
    }

    # ==========================================
    # 5. PTP CLEANING
    # ==========================================
    print("\n--- STEP 5: CLEANING PROMISES TO PAY (PTP) ---")
    ptp_raw_path = os.path.join(RAW_DIR, "promises_to_pay.csv")
    with open(ptp_raw_path, "r", encoding="utf-8") as f:
        ptp_rows = list(csv.DictReader(f))
    raw_ptp_count = len(ptp_rows)
    print(f"Raw PTP records: {raw_ptp_count}")

    clean_ptp_rows = []
    ptp_status_counts = Counter()
    ptp_status_amounts = defaultdict(float)

    for r in ptp_rows:
        aid = r["account_id"]
        st = r["status"]
        amt = float(r["promised_amount"])
        ptp_status_counts[st] += 1
        ptp_status_amounts[st] += amt

        acc_tz = account_tz_map.get(aid, "UTC")
        ev_dt = parse_iso(r["event_at"])
        pr_dt = parse_iso(r["promised_date"])

        ev_at_utc = convert_to_utc(ev_dt, acc_tz)
        pr_at_utc = convert_to_utc(pr_dt, acc_tz)

        clean_row = dict(r)
        clean_row["account_timezone"] = acc_tz
        clean_row["event_at_utc"] = ev_at_utc if ev_at_utc else r["event_at"]
        clean_row["promised_date_utc"] = pr_at_utc if pr_at_utc else r["promised_date"]
        clean_row["is_kept"] = "TRUE" if st == "KEPT" else "FALSE"
        clean_row["is_broken"] = "TRUE" if st == "BROKEN" else "FALSE"
        clean_ptp_rows.append(clean_row)

    ptp_clean_path = os.path.join(PROCESSED_DIR, "ptp_clean.csv")
    fieldnames_ptp = list(clean_ptp_rows[0].keys())
    with open(ptp_clean_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_ptp)
        writer.writeheader()
        writer.writerows(clean_ptp_rows)
    print(f"Wrote clean PTP to {ptp_clean_path} ({len(clean_ptp_rows)} rows)")
    print(f"  PTP Status Counts: {dict(ptp_status_counts)}")
    print(f"  PTP Status Amounts: {dict(ptp_status_amounts)}")

    summary_metrics["tables"]["promises_to_pay"] = {
        "raw_rows": raw_ptp_count,
        "clean_rows": len(clean_ptp_rows),
        "exact_duplicates_removed": 0,
        "quarantined_conflicts": 0,
        "status_counts": dict(ptp_status_counts),
        "status_amounts": dict(ptp_status_amounts)
    }

    # ==========================================
    # 6. AGENT PROFILING LOG
    # ==========================================
    print("\n--- STEP 6: PROFILING AGENT DIMENSION ---")
    agents_raw_path = os.path.join(RAW_DIR, "agents.csv")
    with open(agents_raw_path, "r", encoding="utf-8") as f:
        agent_rows = list(csv.DictReader(f))
    raw_agent_count = len(agent_rows)
    print(f"Raw agent records: {raw_agent_count}")

    # Generate version indexing for agent profiles
    agent_by_id = defaultdict(list)
    for r in agent_rows:
        agent_by_id[r["agent_id"]].append(r)

    processed_agent_rows = []
    for aid, rlist in agent_by_id.items():
        # Sort by updated_at if possible
        sorted_list = sorted(rlist, key=lambda x: x["updated_at"])
        for idx, r in enumerate(sorted_list, 1):
            arow = dict(r)
            arow["profile_version"] = idx
            arow["total_versions_for_agent"] = len(rlist)
            processed_agent_rows.append(arow)

    agents_clean_path = os.path.join(PROCESSED_DIR, "agents_profile_log.csv")
    fieldnames_agent = list(processed_agent_rows[0].keys())
    with open(agents_clean_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_agent)
        writer.writeheader()
        writer.writerows(processed_agent_rows)
    print(f"Wrote profiled agent logs to {agents_clean_path} ({len(processed_agent_rows)} rows)")

    # Save summary JSON
    summary_json_path = os.path.join(REPORTS_DIR, "cleaning_summary.json")
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary_metrics, f, indent=2)
    print(f"\nWrote cleaning summary JSON to {summary_json_path}")

    return summary_metrics

if __name__ == "__main__":
    execute_cleaning_pipeline()
