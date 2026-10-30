import os
import csv
from collections import defaultdict

DATASET_DIR = r"c:\Users\puram\Desktop\credresolve project\collections_30k_dataset (1)"

def audit_finances():
    p_path = os.path.join(DATASET_DIR, "payments.csv")
    with open(p_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Raw rows: {len(rows)}")
    raw_status_counts = defaultdict(int)
    raw_status_amounts = defaultdict(float)
    for r in rows:
        st = r["payment_status"]
        amt = float(r["amount"])
        raw_status_counts[st] += 1
        raw_status_amounts[st] += amt

    print("\n--- RAW TOTALS ---")
    for st in sorted(raw_status_counts.keys()):
        print(f"{st}: {raw_status_counts[st]} rows, INR {raw_status_amounts[st]:,.2f}")
    total_raw_amt = sum(raw_status_amounts.values())
    print(f"Total Raw Amount: INR {total_raw_amt:,.2f}")

    # Identify exact duplicates and conflicts
    p_by_id = defaultdict(list)
    for r in rows:
        p_by_id[r["payment_id"]].append(r)

    exact_dup_rows = []
    conflict_rows = []
    clean_rows = []

    seen_exact = set()

    for pid, rlist in p_by_id.items():
        if len(rlist) == 1:
            clean_rows.append(rlist[0])
        else:
            first_t = tuple(rlist[0].items())
            all_identical = all(tuple(r.items()) == first_t for r in rlist)
            if all_identical:
                # Keep 1, others are exact dups
                clean_rows.append(rlist[0])
                exact_dup_rows.extend(rlist[1:])
            else:
                conflict_rows.extend(rlist)

    print("\n--- DEDUPLICATION & QUARANTINE BREAKDOWN ---")
    print(f"Clean rows: {len(clean_rows)}")
    print(f"Exact duplicate rows removed: {len(exact_dup_rows)}")
    print(f"Conflicting rows quarantined: {len(conflict_rows)}")
    print(f"Sum check: {len(clean_rows)} + {len(exact_dup_rows)} + {len(conflict_rows)} = {len(clean_rows) + len(exact_dup_rows) + len(conflict_rows)}")

    # Exact dups financial breakdown
    ed_counts = defaultdict(int)
    ed_amts = defaultdict(float)
    for r in exact_dup_rows:
        st = r["payment_status"]
        amt = float(r["amount"])
        ed_counts[st] += 1
        ed_amts[st] += amt
    print("\nRemoved Exact Duplicates Breakdown:")
    for st in sorted(ed_counts.keys()):
        print(f"  {st}: {ed_counts[st]} rows, INR {ed_amts[st]:,.2f}")

    # Conflict rows financial breakdown
    cf_counts = defaultdict(int)
    cf_amts = defaultdict(float)
    for r in conflict_rows:
        st = r["payment_status"]
        amt = float(r["amount"])
        cf_counts[st] += 1
        cf_amts[st] += amt
    print("\nQuarantined Conflicts Breakdown:")
    for st in sorted(cf_counts.keys()):
        print(f"  {st}: {cf_counts[st]} rows, INR {cf_amts[st]:,.2f}")

    # Clean rows financial breakdown
    cl_counts = defaultdict(int)
    cl_amts = defaultdict(float)
    for r in clean_rows:
        st = r["payment_status"]
        amt = float(r["amount"])
        cl_counts[st] += 1
        cl_amts[st] += amt
    print("\nClean Payments Breakdown:")
    for st in sorted(cl_counts.keys()):
        print(f"  {st}: {cl_counts[st]} rows, INR {cl_amts[st]:,.2f}")
    total_cl_amt = sum(cl_amts.values())
    print(f"Total Clean Amount: INR {total_cl_amt:,.2f}")

    # Realized Recovery: SUCCESS minus REVERSED
    net_realized_raw = raw_status_amounts["SUCCESS"] - raw_status_amounts["REVERSED"]
    net_realized_clean = cl_amts["SUCCESS"] - cl_amts["REVERSED"]
    gross_recovery_clean = cl_amts["SUCCESS"]
    print(f"\nNet Realized Recovery (SUCCESS - REVERSED):")
    print(f"  Raw (uncleaned): INR {net_realized_raw:,.2f}")
    print(f"  Clean (analytical layer): INR {net_realized_clean:,.2f}")
    print(f"  Gross Success Recovery (Clean): INR {gross_recovery_clean:,.2f}")

if __name__ == "__main__":
    audit_finances()
