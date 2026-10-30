import os
import csv
from collections import defaultdict, Counter

BASE_DIR = r"c:\Users\puram\Desktop\credresolve project"
RAW_DIR = os.path.join(BASE_DIR, "collections_30k_dataset (1)")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

def inspect_campaigns_and_targeting():
    print("=== INSPECTING CAMPAIGNS & TARGETING ===")
    
    # Load campaigns
    camp_path = os.path.join(RAW_DIR, "campaigns.csv")
    with open(camp_path, "r", encoding="utf-8") as f:
        campaigns = list(csv.DictReader(f))
    print(f"Total campaigns: {len(campaigns)}")
    camp_dict = {c["campaign_id"]: c for c in campaigns}
    strat_counts = Counter(c["strategy_version"] for c in campaigns)
    print("Campaign strategy versions:", dict(strat_counts))

    # Load daily_targeting
    tgt_path = os.path.join(RAW_DIR, "daily_targeting.csv")
    with open(tgt_path, "r", encoding="utf-8") as f:
        targeting = list(csv.DictReader(f))
    print(f"Total targeting records: {len(targeting)}")

    # Load payments
    pay_path = os.path.join(PROCESSED_DIR, "payments_clean.csv")
    with open(pay_path, "r", encoding="utf-8") as f:
        payments = list(csv.DictReader(f))
    
    # Payments by account
    acc_success_pay = defaultdict(float)
    for p in payments:
        if p["payment_status"] == "SUCCESS":
            acc_success_pay[p["account_id"]] += float(p["amount"])

    # Targeting strategy performance
    strat_accounts = defaultdict(set)
    strat_target_counts = Counter()
    strat_channels = defaultdict(Counter)

    for t in targeting:
        cid = t["campaign_id"]
        aid = t["account_id"]
        strat = camp_dict.get(cid, {}).get("strategy_version", "UNKNOWN")
        strat_accounts[strat].add(aid)
        strat_target_counts[strat] += 1
        strat_channels[strat][t["recommended_channel"]] += 1

    print("\n--- TARGETING BY STRATEGY VERSION ---")
    for st in sorted(strat_accounts.keys()):
        acc_set = strat_accounts[st]
        tot_recovered = sum(acc_success_pay.get(aid, 0.0) for aid in acc_set)
        paying_accs = sum(1 for aid in acc_set if acc_success_pay.get(aid, 0.0) > 0)
        conversion_rate = (paying_accs / len(acc_set) * 100) if acc_set else 0
        avg_recovery = (tot_recovered / len(acc_set)) if acc_set else 0
        print(f"Strategy {st:<10}: {len(acc_set):>6} accounts, {strat_target_counts[st]:>6} target rows, {paying_accs:>5} paying accs ({conversion_rate:.2f}%), Total Rec: INR {tot_recovered:>14,.2f}, Avg Rec/Acc: INR {avg_recovery:>10,.2f}")
        print(f"   Channels: {dict(strat_channels[st])}")

    # Monthly strategy targeting roll-out
    strat_monthly = defaultdict(lambda: Counter())
    for t in targeting:
        m = t["target_date"][:7]
        cid = t["campaign_id"]
        strat = camp_dict.get(cid, {}).get("strategy_version", "UNKNOWN")
        strat_monthly[m][strat] += 1

    print("\n--- STRATEGY ROLLOUT BY MONTH (Targeting Counts) ---")
    all_strats = sorted(list(strat_counts.keys()))
    print(f"{'Month':<10} | " + " | ".join(f"{s:<10}" for s in all_strats))
    print("-" * 65)
    for m in sorted(strat_monthly.keys()):
        row_str = f"{m:<10} | " + " | ".join(f"{strat_monthly[m][s]:>10}" for s in all_strats)
        print(row_str)

if __name__ == "__main__":
    inspect_campaigns_and_targeting()
