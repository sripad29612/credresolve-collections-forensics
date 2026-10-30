import os
import csv
from collections import Counter, defaultdict

DATASET_DIR = r"c:\Users\puram\Desktop\credresolve project\collections_30k_dataset (1)"

def inspect_conflicts():
    print("=== INSPECTING PAYMENT DUPLICATES & CONFLICTS ===")
    p_path = os.path.join(DATASET_DIR, "payments.csv")
    with open(p_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)

    print(f"Total payment rows: {len(rows)}")
    p_by_id = defaultdict(list)
    for r in rows:
        p_by_id[r["payment_id"]].append(r)

    exact_dup_pids = []
    conflict_pids = []

    for pid, rlist in p_by_id.items():
        if len(rlist) > 1:
            # Check if all rows in rlist are identical
            first_tuple = tuple(rlist[0].items())
            all_identical = all(tuple(r.items()) == first_tuple for r in rlist)
            if all_identical:
                exact_dup_pids.append((pid, len(rlist)))
            else:
                conflict_pids.append((pid, len(rlist)))

    print(f"Payments with multiple rows: {len(exact_dup_pids) + len(conflict_pids)}")
    print(f"Exact duplicate payment IDs (all fields identical): {len(exact_dup_pids)} (total rows: {sum(x[1] for x in exact_dup_pids)})")
    print(f"Conflicting payment IDs (fields differ): {len(conflict_pids)} (total rows: {sum(x[1] for x in conflict_pids)})")

    if conflict_pids:
        print("\nSample conflicting payment ID:")
        sample_pid = conflict_pids[0][0]
        for r in p_by_id[sample_pid]:
            print("  ", r)

    print("\n=== INSPECTING CALL DUPLICATES & CONFLICTS ===")
    c_path = os.path.join(DATASET_DIR, "calls.csv")
    with open(c_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        c_rows = list(reader)

    print(f"Total call rows: {len(c_rows)}")
    c_by_id = defaultdict(list)
    for r in c_rows:
        c_by_id[r["call_id"]].append(r)

    exact_dup_cids = []
    conflict_cids = []

    for cid, rlist in c_by_id.items():
        if len(rlist) > 1:
            first_tuple = tuple(rlist[0].items())
            all_identical = all(tuple(r.items()) == first_tuple for r in rlist)
            if all_identical:
                exact_dup_cids.append((cid, len(rlist)))
            else:
                conflict_cids.append((cid, len(rlist)))

    print(f"Calls with multiple rows: {len(exact_dup_cids) + len(conflict_cids)}")
    print(f"Exact duplicate call IDs (all fields identical): {len(exact_dup_cids)} (total rows: {sum(x[1] for x in exact_dup_cids)})")
    print(f"Conflicting call IDs (fields differ): {len(conflict_cids)} (total rows: {sum(x[1] for x in conflict_cids)})")

    if conflict_cids:
        print("\nSample conflicting call ID:")
        sample_cid = conflict_cids[0][0]
        for r in c_by_id[sample_cid]:
            print("  ", r)

    print("\n=== INSPECTING PTP DATA ===")
    ptp_path = os.path.join(DATASET_DIR, "promises_to_pay.csv")
    with open(ptp_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        ptp_rows = list(reader)
    print(f"Total PTP rows: {len(ptp_rows)}")
    ptp_by_id = defaultdict(list)
    for r in ptp_rows:
        ptp_by_id[r["ptp_id"]].append(r)
    ptp_dups = [k for k, v in ptp_by_id.items() if len(v) > 1]
    print(f"PTP duplicate IDs: {len(ptp_dups)}")

    print("\n=== INSPECTING TIMEZONES IN CALLS & ACCOUNTS ===")
    call_tz = Counter(r.get("timezone", "") for r in c_rows)
    print(f"Calls timezones: {dict(call_tz)}")
    call_missing_tz = sum(1 for r in c_rows if not r.get("timezone"))
    print(f"Calls missing timezone: {call_missing_tz}")

if __name__ == "__main__":
    inspect_conflicts()
