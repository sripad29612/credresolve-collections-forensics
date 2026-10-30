import os
import csv
import json
import re
from datetime import datetime
from collections import Counter, defaultdict

DATASET_DIR = r"c:\Users\puram\Desktop\credresolve project\collections_30k_dataset (1)"

def is_null_val(val):
    if val is None:
        return True
    s = str(val).strip()
    return s == "" or s.lower() in ("null", "none", "nan", "na", "\\n")

def parse_iso_date(val):
    if is_null_val(val):
        return None
    s = str(val).strip()
    # Try different date formats
    for fmt in (
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%Y/%m/%d"
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    # Regex fallback for ISO with timezone offset like +05:30 or +00:00 or Z
    # Handle fractional seconds and TZ
    clean_s = re.sub(r'(\.\d+)', '', s)
    clean_s = clean_s.replace('Z', '+0000')
    if '+' in clean_s or '-' in clean_s[10:]:
        # Remove colon in timezone +05:30 -> +0530
        clean_s = re.sub(r'([+-]\d{2}):(\d{2})$', r'\1\2', clean_s)
    for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(clean_s, fmt)
        except ValueError:
            pass
    return None

def inspect_dataset():
    files = [f for f in os.listdir(DATASET_DIR) if f.endswith(".csv")]
    print(f"Found {len(files)} CSV files in {DATASET_DIR}")
    
    # Read data dictionary first
    data_dict = defaultdict(dict)
    dd_path = os.path.join(DATASET_DIR, "data_dictionary.csv")
    if os.path.exists(dd_path):
        with open(dd_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                data_dict[row["dataset"]][row["column"]] = row["dtype"]

    report_data = {
        "tables": {},
        "fk_checks": {},
        "overall_summary": {}
    }

    table_pks = {
        "borrowers": "borrower_id",
        "accounts": "account_id",
        "agents": "agent_id",
        "agent_sessions": "session_id",
        "campaigns": "campaign_id",
        "daily_targeting": "target_id",
        "calls": "call_id",
        "call_attempts": "attempt_id",
        "call_dispositions": "disposition_id",
        "whatsapp_events": "whatsapp_event_id",
        "sms_events": "sms_event_id",
        "field_visits": "visit_id",
        "promises_to_pay": "ptp_id",
        "payments": "payment_id",
        "vendor_telephony": "vendor_id",
        "complaints": "complaint_id",
        "account_status_history": "history_id"
    }

    # Store sets of IDs for FK checking
    id_store = defaultdict(set)

    for fname in sorted(files):
        tname = fname[:-4]
        fpath = os.path.join(DATASET_DIR, fname)
        print(f"\n--- Processing {fname} ---")

        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                report_data["tables"][tname] = {"rows": 0, "cols": 0, "columns": []}
                continue

            num_cols = len(header)
            row_count = 0
            null_counts = [0] * num_cols
            col_samples = [set() for _ in range(num_cols)]
            id_counts = Counter()
            row_hashes = set()
            exact_duplicate_rows = 0

            # Date tracking
            date_col_indices = []
            for idx, cname in enumerate(header):
                expected_type = data_dict.get(tname, {}).get(cname, "")
                if "datetime" in expected_type or "date" in cname.lower() or cname.endswith("_at"):
                    date_col_indices.append(idx)

            date_min_max = {idx: {"min": None, "max": None, "valid_count": 0, "invalid_count": 0, "month_counts": Counter()} for idx in date_col_indices}

            pk_col = table_pks.get(tname)
            pk_idx = header.index(pk_col) if pk_col in header else -1

            for row in reader:
                row_count += 1
                row_tuple = tuple(row)
                if row_tuple in row_hashes:
                    exact_duplicate_rows += 1
                else:
                    if len(row_hashes) < 500000:
                        row_hashes.add(row_tuple)

                # PK tracking
                if pk_idx >= 0 and pk_idx < len(row):
                    pk_val = row[pk_idx].strip()
                    id_counts[pk_val] += 1
                    id_store[f"{tname}.{pk_col}"].add(pk_val)

                # Null & sample tracking
                for idx, val in enumerate(row):
                    if idx >= num_cols:
                        continue
                    if is_null_val(val):
                        null_counts[idx] += 1
                    else:
                        if len(col_samples[idx]) < 10:
                            col_samples[idx].add(val.strip())

                # Date parsing
                for idx in date_col_indices:
                    if idx < len(row):
                        raw_date = row[idx]
                        dt = parse_iso_date(raw_date)
                        if dt is not None:
                            # Standardize to naive UTC for min/max
                            if dt.tzinfo is not None:
                                dt_naive = dt.replace(tzinfo=None)
                            else:
                                dt_naive = dt
                            curr_min = date_min_max[idx]["min"]
                            curr_max = date_min_max[idx]["max"]
                            if curr_min is None or dt_naive < curr_min:
                                date_min_max[idx]["min"] = dt_naive
                            if curr_max is None or dt_naive > curr_max:
                                date_min_max[idx]["max"] = dt_naive
                            date_min_max[idx]["valid_count"] += 1
                            month_key = dt_naive.strftime("%Y-%m")
                            date_min_max[idx]["month_counts"][month_key] += 1
                        else:
                            if not is_null_val(raw_date):
                                date_min_max[idx]["invalid_count"] += 1

            # PK analysis
            unique_pks = len(id_counts)
            dup_pk_count = sum(1 for v in id_counts.values() if v > 1)
            dup_pk_examples = [k for k, v in id_counts.items() if v > 1][:5]

            # Columns detail
            cols_info = []
            for idx, cname in enumerate(header):
                c_nulls = null_counts[idx]
                c_null_pct = round((c_nulls / row_count * 100), 2) if row_count > 0 else 0
                c_dict_type = data_dict.get(tname, {}).get(cname, "unknown")
                c_samples = list(col_samples[idx])[:5]

                c_info = {
                    "name": cname,
                    "expected_type": c_dict_type,
                    "null_count": c_nulls,
                    "null_pct": c_null_pct,
                    "samples": c_samples
                }

                if idx in date_min_max:
                    dmm = date_min_max[idx]
                    c_info["date_stats"] = {
                        "min": dmm["min"].isoformat() if dmm["min"] else None,
                        "max": dmm["max"].isoformat() if dmm["max"] else None,
                        "valid_dates": dmm["valid_count"],
                        "invalid_dates": dmm["invalid_count"],
                        "month_distribution": dict(sorted(dmm["month_counts"].items()))
                    }

                cols_info.append(c_info)

            table_report = {
                "file_name": fname,
                "row_count": row_count,
                "col_count": num_cols,
                "exact_duplicate_rows": exact_duplicate_rows,
                "pk_column": pk_col,
                "unique_pks": unique_pks,
                "duplicate_pk_count": dup_pk_count,
                "duplicate_pk_examples": dup_pk_examples,
                "columns": cols_info
            }
            report_data["tables"][tname] = table_report
            print(f"Done {tname}: {row_count} rows, {num_cols} cols, {exact_duplicate_rows} exact dup rows, {dup_pk_count} dup PKs")

    # Second pass for FK checking on key relationships
    print("\n--- Performing Foreign Key Checks ---")
    fk_pairs = [
        ("accounts", "borrower_id", "borrowers", "borrower_id"),
        ("calls", "account_id", "accounts", "account_id"),
        ("calls", "borrower_id", "borrowers", "borrower_id"),
        ("calls", "agent_id", "agents", "agent_id"),
        ("calls", "campaign_id", "campaigns", "campaign_id"),
        ("call_attempts", "call_id", "calls", "call_id"),
        ("call_attempts", "account_id", "accounts", "account_id"),
        ("call_dispositions", "call_id", "calls", "call_id"),
        ("call_dispositions", "account_id", "accounts", "account_id"),
        ("whatsapp_events", "account_id", "accounts", "account_id"),
        ("sms_events", "account_id", "accounts", "account_id"),
        ("field_visits", "account_id", "accounts", "account_id"),
        ("field_visits", "agent_id", "agents", "agent_id"),
        ("promises_to_pay", "account_id", "accounts", "account_id"),
        ("payments", "account_id", "accounts", "account_id"),
        ("payments", "borrower_id", "borrowers", "borrower_id"),
        ("complaints", "account_id", "accounts", "account_id"),
        ("daily_targeting", "account_id", "accounts", "account_id"),
        ("daily_targeting", "campaign_id", "campaigns", "campaign_id"),
        ("agent_sessions", "agent_id", "agents", "agent_id"),
        ("agents", "vendor_id", "vendor_telephony", "vendor_id"),
        ("account_status_history", "account_id", "accounts", "account_id")
    ]

    for child_t, child_col, parent_t, parent_col in fk_pairs:
        fpath = os.path.join(DATASET_DIR, f"{child_t}.csv")
        if not os.path.exists(fpath):
            continue
        parent_pk_set = id_store[f"{parent_t}.{parent_col}"]
        missing_fk_count = 0
        null_fk_count = 0
        total_child_rows = 0
        orphans_examples = set()

        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            header = next(reader)
            if child_col not in header:
                continue
            c_idx = header.index(child_col)
            for row in reader:
                total_child_rows += 1
                if c_idx >= len(row):
                    continue
                val = row[c_idx].strip()
                if is_null_val(val):
                    null_fk_count += 1
                elif val not in parent_pk_set:
                    missing_fk_count += 1
                    if len(orphans_examples) < 5:
                        orphans_examples.add(val)

        fk_key = f"{child_t}.{child_col} -> {parent_t}.{parent_col}"
        report_data["fk_checks"][fk_key] = {
            "total_records": total_child_rows,
            "null_fk_count": null_fk_count,
            "missing_fk_count": missing_fk_count,
            "orphans_examples": list(orphans_examples)
        }
        print(f"FK check {fk_key}: {missing_fk_count} missing, {null_fk_count} null out of {total_child_rows}")

    # Specific Forensic Checks:
    print("\n--- Additional Forensics Checks ---")
    # 1. payments duplicate payment references
    payments_path = os.path.join(DATASET_DIR, "payments.csv")
    pay_ref_counts = Counter()
    pay_statuses = Counter()
    pay_amounts = []
    with open(payments_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for r in reader:
            pay_ref_counts[r["payment_reference"].strip()] += 1
            pay_statuses[r["payment_status"].strip()] += 1
            try:
                pay_amounts.append(float(r["amount"]))
            except:
                pass
    dup_refs = sum(1 for v in pay_ref_counts.values() if v > 1)
    report_data["payments_forensics"] = {
        "unique_references": len(pay_ref_counts),
        "dup_references_count": dup_refs,
        "status_distribution": dict(pay_statuses),
        "min_amount": min(pay_amounts) if pay_amounts else None,
        "max_amount": max(pay_amounts) if pay_amounts else None,
        "negative_amounts": sum(1 for a in pay_amounts if a < 0),
        "zero_amounts": sum(1 for a in pay_amounts if a == 0)
    }

    # 2. promises_to_pay status
    ptp_path = os.path.join(DATASET_DIR, "promises_to_pay.csv")
    ptp_statuses = Counter()
    ptp_sources = Counter()
    with open(ptp_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ptp_statuses[r["status"].strip()] += 1
            ptp_sources[r["source"].strip()] += 1
    report_data["ptp_forensics"] = {
        "status_distribution": dict(ptp_statuses),
        "source_distribution": dict(ptp_sources)
    }

    # 3. account status and dpd in accounts.csv
    accounts_path = os.path.join(DATASET_DIR, "accounts.csv")
    acc_statuses = Counter()
    acc_risk = Counter()
    acc_timezones = Counter()
    acc_schemas = Counter()
    with open(accounts_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for r in reader:
            acc_statuses[r["status"].strip()] += 1
            acc_risk[r["risk_segment"].strip()] += 1
            acc_timezones[r["timezone"].strip()] += 1
            acc_schemas[r["schema_version"].strip()] += 1
    report_data["accounts_forensics"] = {
        "status_distribution": dict(acc_statuses),
        "risk_distribution": dict(acc_risk),
        "timezone_distribution": dict(acc_timezones),
        "schema_version_distribution": dict(acc_schemas)
    }

    # Save raw json output
    os.makedirs(r"c:\Users\puram\Desktop\credresolve project\scratch", exist_ok=True)
    out_json_path = r"c:\Users\puram\Desktop\credresolve project\scratch\inspection_results.json"
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, default=str)
    print(f"\nWrote full inspection results to {out_json_path}")

if __name__ == "__main__":
    inspect_dataset()
