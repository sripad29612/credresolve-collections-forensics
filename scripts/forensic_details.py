import os
import csv
from collections import Counter, defaultdict

DATASET_DIR = r"c:\Users\puram\Desktop\credresolve project\collections_30k_dataset (1)"

def forensic_investigation():
    # 1. Investigate agents.csv
    print("--- 1. AGENTS FORENSICS ---")
    agents_path = os.path.join(DATASET_DIR, "agents.csv")
    with open(agents_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        sample_rows = []
        target_aid = "AGT0000001"
        for r in reader:
            if r["agent_id"] == target_aid:
                sample_rows.append(r)
            if len(sample_rows) >= 5:
                break
        print(f"Sample rows for {target_aid}:")
        for sr in sample_rows:
            print("  ", sr)

    # 2. Investigate borrowers.csv
    print("\n--- 2. BORROWERS FORENSICS ---")
    brw_path = os.path.join(DATASET_DIR, "borrowers.csv")
    with open(brw_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        target_bid = "BRW0000001"
        sample_b_rows = []
        for r in reader:
            if r["borrower_id"] == target_bid:
                sample_b_rows.append(r)
            if len(sample_b_rows) >= 5:
                break
        print(f"Sample rows for {target_bid}:")
        for sr in sample_b_rows:
            print("  ", sr)

    # 3. Investigate calls.csv duplicates
    print("\n--- 3. CALLS DUPLICATES FORENSICS ---")
    calls_path = os.path.join(DATASET_DIR, "calls.csv")
    with open(calls_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        target_cid = "CALL0000050"
        sample_c_rows = []
        for r in reader:
            if r["call_id"] == target_cid:
                sample_c_rows.append(r)
        print(f"Sample rows for {target_cid}:")
        for sr in sample_c_rows:
            print("  ", sr)

    # 4. Investigate payments.csv duplicates & payment_reference
    print("\n--- 4. PAYMENTS FORENSICS ---")
    payments_path = os.path.join(DATASET_DIR, "payments.csv")
    with open(payments_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        target_pid = "PAY0000050"
        sample_p_rows = []
        ref_samples = defaultdict(list)
        for r in reader:
            if r["payment_id"] == target_pid:
                sample_p_rows.append(r)
            ref_samples[r["payment_reference"]].append(r)
        print(f"Sample rows for {target_pid}:")
        for sr in sample_p_rows:
            print("  ", sr)
        
        # Look at multi-event payment references
        multi_refs = {k: v for k, v in ref_samples.items() if len(v) > 1 and k != ""}
        print(f"Total multi-event payment references: {len(multi_refs)}")
        sample_multi_ref = list(multi_refs.keys())[0]
        print(f"Sample multi-event reference {sample_multi_ref}:")
        for r in multi_refs[sample_multi_ref]:
            print("  ", r)

    # 5. Complaints resolution_at stats
    print("\n--- 5. COMPLAINTS RESOLUTION_AT ---")
    comp_path = os.path.join(DATASET_DIR, "complaints.csv")
    with open(comp_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        res_nulls = 0
        total_comps = 0
        statuses = Counter()
        types = Counter()
        severities = Counter()
        for r in reader:
            total_comps += 1
            statuses[r["status"]] += 1
            types[r["complaint_type"]] += 1
            severities[r["severity"]] += 1
            if r["resolution_at"].strip() == "" or r["resolution_at"].lower() in ("null", "none"):
                res_nulls += 1
        print(f"Total complaints: {total_comps}, resolution_at nulls: {res_nulls} ({res_nulls/total_comps*100:.2f}%)")
        print(f"Statuses: {dict(statuses)}")
        print(f"Types: {dict(types)}")
        print(f"Severities: {dict(severities)}")

    # 6. Promises to Pay Statuses & Amounts
    print("\n--- 6. PROMISES TO PAY STATS ---")
    ptp_path = os.path.join(DATASET_DIR, "promises_to_pay.csv")
    with open(ptp_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        ptp_stats = Counter()
        ptp_amounts = defaultdict(float)
        for r in reader:
            st = r["status"]
            ptp_stats[st] += 1
            try:
                ptp_amounts[st] += float(r["promised_amount"])
            except:
                pass
        print(f"PTP Statuses: {dict(ptp_stats)}")
        print(f"PTP Amounts by status: {dict(ptp_amounts)}")

if __name__ == "__main__":
    forensic_investigation()
