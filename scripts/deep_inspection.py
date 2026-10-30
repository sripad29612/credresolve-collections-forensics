import os
import json
import csv
from datetime import datetime
from collections import Counter, defaultdict

SCRATCH_JSON = r"c:\Users\puram\Desktop\credresolve project\scratch\inspection_results.json"
DATASET_DIR = r"c:\Users\puram\Desktop\credresolve project\collections_30k_dataset (1)"
REPORT_PATH = r"c:\Users\puram\Desktop\credresolve project\reports\dataset_inspection.md"

def load_data():
    with open(SCRATCH_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def run_deep_analysis():
    data = load_data()
    tables = data["tables"]
    fk_checks = data["fk_checks"]

    print("=== DEEP ANALYSIS OF DATASET ===")

    # 1. Date ranges across all tables
    print("\n--- Date Columns and Ranges ---")
    date_summary = {}
    all_months = Counter()
    for tname, tinfo in tables.items():
        for col in tinfo["columns"]:
            if "date_stats" in col:
                dstats = col["date_stats"]
                date_summary[f"{tname}.{col['name']}"] = dstats
                print(f"{tname}.{col['name']}: Min={dstats['min']}, Max={dstats['max']}, Valid={dstats['valid_dates']}, Months={list(dstats['month_distribution'].keys())}")
                if "event_at" in col["name"] or "target_date" in col["name"] or "login_at" in col["name"]:
                    for m, c in dstats["month_distribution"].items():
                        all_months[m] += c

    print("\n--- Aggregate Monthly Event Distribution ---")
    for m in sorted(all_months.keys()):
        print(f"  {m}: {all_months[m]} events")

    # Check claimed 12 months
    print(f"\nTotal distinct months in operational/event tables: {len(all_months)} -> {sorted(all_months.keys())}")

    # 2. Table row counts, duplicate rows, duplicate PKs
    print("\n--- Table Integrity & Duplicates ---")
    for tname, tinfo in sorted(tables.items()):
        print(f"{tname}: Rows={tinfo['row_count']}, Cols={tinfo['col_count']}, ExactDupRows={tinfo['exact_duplicate_rows']}, PK={tinfo['pk_column']}, DupPKs={tinfo['duplicate_pk_count']}")

    # 3. Missing values analysis
    print("\n--- Columns with Missing / Null Values ---")
    null_cols = []
    for tname, tinfo in sorted(tables.items()):
        for col in tinfo["columns"]:
            if col["null_count"] > 0:
                print(f"{tname}.{col['name']}: {col['null_count']} nulls ({col['null_pct']}%)")
                null_cols.append((tname, col['name'], col['null_count'], col['null_pct']))

    # 4. Check agents duplicate PKs and multiple agent identifiers
    print("\n--- Agent Table Deep Dive ---")
    agents_path = os.path.join(DATASET_DIR, "agents.csv")
    agent_id_counts = Counter()
    emp_code_counts = Counter()
    agent_id_to_emp = defaultdict(set)
    emp_to_agent_id = defaultdict(set)
    with open(agents_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for r in reader:
            aid = r["agent_id"]
            ecode = r["employee_code"]
            agent_id_counts[aid] += 1
            emp_code_counts[ecode] += 1
            agent_id_to_emp[aid].add(ecode)
            emp_to_agent_id[ecode].add(aid)
    dup_agent_ids = sum(1 for v in agent_id_counts.values() if v > 1)
    dup_emp_codes = sum(1 for v in emp_code_counts.values() if v > 1)
    multi_emp_for_aid = sum(1 for v in agent_id_to_emp.values() if len(v) > 1)
    multi_aid_for_emp = sum(1 for v in emp_to_agent_id.values() if len(v) > 1)
    print(f"Agents total: 30000 rows. Unique agent_ids: {len(agent_id_counts)} (Dup IDs: {dup_agent_ids}). Unique employee_codes: {len(emp_code_counts)} (Dup codes: {dup_emp_codes}).")
    print(f"agent_ids with multiple employee_codes: {multi_emp_for_aid}, employee_codes with multiple agent_ids: {multi_aid_for_emp}")

    # 5. Check Borrowers duplicate PKs
    print("\n--- Borrowers Table Deep Dive ---")
    borrowers_path = os.path.join(DATASET_DIR, "borrowers.csv")
    brw_id_counts = Counter()
    brw_rows = []
    with open(borrowers_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for r in reader:
            brw_id_counts[r["borrower_id"]] += 1
    dup_brw_ids = sum(1 for v in brw_id_counts.values() if v > 1)
    print(f"Borrowers total: 30600 rows. Unique borrower_ids: {len(brw_id_counts)}. Duplicate borrower_ids: {dup_brw_ids}")

    # 6. Check Call Dispositions and legacy codes
    print("\n--- Call Dispositions Deep Dive ---")
    disp_path = os.path.join(DATASET_DIR, "call_dispositions.csv")
    disp_codes = Counter()
    disp_versions = Counter()
    with open(disp_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for r in reader:
            disp_codes[r["disposition_code"]] += 1
            disp_versions[r["disposition_version"]] += 1
    print(f"Disposition versions: {dict(disp_versions)}")
    print(f"Disposition codes: {dict(disp_codes)}")

    # 7. Check Payments Forensics
    print("\n--- Payments Deep Dive ---")
    pay_path = os.path.join(DATASET_DIR, "payments.csv")
    pay_methods = Counter()
    pay_providers = Counter()
    pay_statuses = Counter()
    pay_ref_counts = Counter()
    pay_by_status_amount = defaultdict(float)
    total_payments = 0
    with open(pay_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for r in reader:
            total_payments += 1
            st = r["payment_status"]
            pay_statuses[st] += 1
            pay_methods[r["payment_method"]] += 1
            pay_providers[r["provider_id"]] += 1
            pay_ref_counts[r["payment_reference"]] += 1
            try:
                pay_by_status_amount[st] += float(r["amount"])
            except:
                pass
    print(f"Payment Statuses: {dict(pay_statuses)}")
    print(f"Payment Amounts by Status: {dict(pay_by_status_amount)}")
    print(f"Payment Methods: {dict(pay_methods)}")
    print(f"Unique payment references: {len(pay_ref_counts)}, duplicate references: {sum(1 for v in pay_ref_counts.values() if v > 1)}")

    # 8. Check Accounts Forensics
    print("\n--- Accounts Deep Dive ---")
    acc_path = os.path.join(DATASET_DIR, "accounts.csv")
    acc_tz = Counter()
    acc_sv = Counter()
    acc_loan_types = Counter()
    acc_status = Counter()
    acc_risk = Counter()
    total_principal = 0.0
    total_outstanding = 0.0
    with open(acc_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for r in reader:
            acc_tz[r["timezone"]] += 1
            acc_sv[r["schema_version"]] += 1
            acc_loan_types[r["loan_type"]] += 1
            acc_status[r["status"]] += 1
            acc_risk[r["risk_segment"]] += 1
            total_principal += float(r["principal_amount"])
            total_outstanding += float(r["outstanding_amount"])
    print(f"Timezones: {dict(acc_tz)}")
    print(f"Schema versions: {dict(acc_sv)}")
    print(f"Statuses: {dict(acc_status)}")
    print(f"Risk segments: {dict(acc_risk)}")
    print(f"Total principal: {total_principal:,.2f}, Total outstanding: {total_outstanding:,.2f}")

    # 9. Check Campaigns
    print("\n--- Campaigns Deep Dive ---")
    camp_path = os.path.join(DATASET_DIR, "campaigns.csv")
    camp_strat = Counter()
    camp_chan = Counter()
    camp_dates = []
    with open(camp_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for r in reader:
            camp_strat[r["strategy_version"]] += 1
            camp_chan[r["channel"]] += 1
    print(f"Campaign Strategy versions: {dict(camp_strat)}")
    print(f"Campaign Channels: {dict(camp_chan)}")

    # 10. Check account_status_history
    print("\n--- Account Status History Deep Dive ---")
    ash_path = os.path.join(DATASET_DIR, "account_status_history.csv")
    ash_sources = Counter()
    ash_statuses = Counter()
    ash_changed_by = Counter()
    with open(ash_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ash_sources[r["source"]] += 1
            ash_statuses[r["status"]] += 1
            ash_changed_by[r["changed_by"][:3]] += 1
    print(f"Status History Sources: {dict(ash_sources)}")
    print(f"Status History Statuses: {dict(ash_statuses)}")
    print(f"Status History Changed By prefixes: {dict(ash_changed_by)}")

    # 11. Vendor Telephony
    print("\n--- Vendor Telephony Deep Dive ---")
    vt_path = os.path.join(DATASET_DIR, "vendor_telephony.csv")
    with open(vt_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for r in reader:
            print(f"  {r}")

if __name__ == "__main__":
    run_deep_analysis()
