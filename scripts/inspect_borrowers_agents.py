import os
import csv
from collections import Counter, defaultdict

DATASET_DIR = r"c:\Users\puram\Desktop\credresolve project\collections_30k_dataset (1)"

def inspect_borrowers_agents():
    print("=== INSPECTING BORROWERS ===")
    b_path = os.path.join(DATASET_DIR, "borrowers.csv")
    with open(b_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        b_rows = list(reader)

    print(f"Total borrower rows: {len(b_rows)}")
    b_by_id = defaultdict(list)
    for r in b_rows:
        b_by_id[r["borrower_id"]].append(r)

    print(f"Unique borrower_ids: {len(b_by_id)}")
    
    b_conflicts = []
    b_exact_dups = []
    b_singletons = []

    for bid, rlist in b_by_id.items():
        if len(rlist) == 1:
            b_singletons.append(bid)
        else:
            first_t = tuple(rlist[0].items())
            if all(tuple(r.items()) == first_t for r in rlist):
                b_exact_dups.append((bid, len(rlist)))
            else:
                b_conflicts.append((bid, len(rlist)))

    print(f"Singletons: {len(b_singletons)}")
    print(f"Exact duplicate ID groups: {len(b_exact_dups)} (total rows: {sum(x[1] for x in b_exact_dups)})")
    print(f"Conflicting ID groups: {len(b_conflicts)} (total rows: {sum(x[1] for x in b_conflicts)})")

    # Check agents
    print("\n=== INSPECTING AGENTS ===")
    a_path = os.path.join(DATASET_DIR, "agents.csv")
    with open(a_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        a_rows = list(reader)
    print(f"Total agent rows: {len(a_rows)}")
    a_by_id = defaultdict(list)
    for r in a_rows:
        a_by_id[r["agent_id"]].append(r)
    print(f"Unique agent_ids: {len(a_by_id)}")
    print(f"Rows per agent_id: min={min(len(v) for v in a_by_id.values())}, max={max(len(v) for v in a_by_id.values())}, avg={len(a_rows)/len(a_by_id):.1f}")
    
    # Check what fields vary across rows for a single agent_id
    varying_fields = Counter()
    for aid, rlist in a_by_id.items():
        for field in reader.fieldnames:
            vals = set(r[field] for r in rlist)
            if len(vals) > 1:
                varying_fields[field] += 1
    print(f"Fields that vary across rows for the same agent_id: {dict(varying_fields)}")

if __name__ == "__main__":
    inspect_borrowers_agents()
