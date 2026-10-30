import os
import csv
from collections import defaultdict

BASE_DIR = r"c:\Users\puram\Desktop\credresolve project"
PAY_PATH = os.path.join(BASE_DIR, "data", "processed", "payments_clean.csv")

def check_monthly():
    with open(PAY_PATH, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    months = sorted(list(set(r["event_at"][:7] for r in rows)))
    print("Months present in payments_clean:", months)

    monthly_stats = defaultdict(lambda: {
        "success_amt": 0.0, "success_txns": 0,
        "reversed_amt": 0.0, "reversed_txns": 0,
        "failed_amt": 0.0, "failed_txns": 0,
        "pending_amt": 0.0, "pending_txns": 0,
        "paying_accounts": set()
    })

    for r in rows:
        m = r["event_at"][:7]
        st = r["payment_status"]
        amt = float(r["amount"])
        aid = r["account_id"]
        if st == "SUCCESS":
            monthly_stats[m]["success_amt"] += amt
            monthly_stats[m]["success_txns"] += 1
            monthly_stats[m]["paying_accounts"].add(aid)
        elif st == "REVERSED":
            monthly_stats[m]["reversed_amt"] += amt
            monthly_stats[m]["reversed_txns"] += 1
        elif st == "FAILED":
            monthly_stats[m]["failed_amt"] += amt
            monthly_stats[m]["failed_txns"] += 1
        elif st == "PENDING":
            monthly_stats[m]["pending_amt"] += amt
            monthly_stats[m]["pending_txns"] += 1

    prev_net = None
    print("\n--- MONTHLY RECOVERY TABLE ---")
    print(f"{'Month':<10} | {'Gross Success (INR)':<20} | {'Reversals (INR)':<18} | {'Net Realized (INR)':<20} | {'MoM Growth %':<14} | {'Paying Accs':<12}")
    print("-" * 95)
    for m in months:
        s_amt = monthly_stats[m]["success_amt"]
        r_amt = monthly_stats[m]["reversed_amt"]
        net = s_amt - r_amt
        acc_cnt = len(monthly_stats[m]["paying_accounts"])
        if prev_net is not None and prev_net > 0:
            growth = ((net - prev_net) / prev_net) * 100
            growth_str = f"{growth:+.2f}%"
        else:
            growth_str = "N/A (Base)"
        print(f"{m:<10} | {s_amt:>18,.2f}  | {r_amt:>16,.2f}  | {net:>18,.2f}  | {growth_str:>12} | {acc_cnt:>10}")
        prev_net = net

if __name__ == "__main__":
    check_monthly()
