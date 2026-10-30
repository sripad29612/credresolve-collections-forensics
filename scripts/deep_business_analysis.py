import os
import csv
import json
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

BASE_DIR = r"c:\Users\puram\Desktop\credresolve project"
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
RAW_DIR = os.path.join(BASE_DIR, "collections_30k_dataset (1)")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")
NOTEBOOKS_DIR = os.path.join(BASE_DIR, "notebooks")

os.makedirs(CHARTS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(NOTEBOOKS_DIR, exist_ok=True)

def parse_iso(dt_str):
    if not dt_str or dt_str.strip() in ("", "NULL", "None"):
        return None
    s = dt_str.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None

def run_business_analysis():
    print("=== STARTING COMPREHENSIVE BUSINESS PERFORMANCE ANALYSIS ===")

    # 1. Load Clean Accounts
    print("\n1. Loading accounts_clean.csv...")
    acc_path = os.path.join(PROCESSED_DIR, "accounts_clean.csv")
    with open(acc_path, "r", encoding="utf-8") as f:
        accounts = list(csv.DictReader(f))
    account_dict = {a["account_id"]: a for a in accounts}
    total_accounts = len(accounts)
    total_outstanding_portfolio = sum(float(a["outstanding_amount"]) for a in accounts)
    total_principal_portfolio = sum(float(a["principal_amount"]) for a in accounts)
    print(f"Total Accounts: {total_accounts:,}, Total Outstanding: INR {total_outstanding_portfolio:,.2f}")

    # 2. Load Clean Payments
    print("\n2. Loading payments_clean.csv...")
    pay_path = os.path.join(PROCESSED_DIR, "payments_clean.csv")
    with open(pay_path, "r", encoding="utf-8") as f:
        payments = list(csv.DictReader(f))
    print(f"Total Clean Payments: {len(payments):,}")

    # 3. Monthly Recovery Analysis
    print("\n3. Computing Monthly Recovery Analysis...")
    monthly_data = defaultdict(lambda: {
        "success_amt": 0.0, "success_txns": 0,
        "reversed_amt": 0.0, "reversed_txns": 0,
        "failed_amt": 0.0, "failed_txns": 0,
        "pending_amt": 0.0, "pending_txns": 0,
        "paying_accounts": set(),
        "days_in_month": 0,
        "is_incomplete": False
    })

    # Days in month mapping for 2026
    month_days = {
        "2026-01": 31, "2026-02": 28, "2026-03": 31,
        "2026-04": 30, "2026-05": 31, "2026-06": 30,
        "2026-07": 31, "2026-08": 8 # Incomplete! Only Aug 1 to Aug 8
    }

    for p in payments:
        m = p["event_at"][:7]
        st = p["payment_status"]
        amt = float(p["amount"])
        aid = p["account_id"]
        
        monthly_data[m]["days_in_month"] = month_days.get(m, 30)
        if m == "2026-08":
            monthly_data[m]["is_incomplete"] = True

        if st == "SUCCESS":
            monthly_data[m]["success_amt"] += amt
            monthly_data[m]["success_txns"] += 1
            monthly_data[m]["paying_accounts"].add(aid)
        elif st == "REVERSED":
            monthly_data[m]["reversed_amt"] += amt
            monthly_data[m]["reversed_txns"] += 1
        elif st == "FAILED":
            monthly_data[m]["failed_amt"] += amt
            monthly_data[m]["failed_txns"] += 1
        elif st == "PENDING":
            monthly_data[m]["pending_amt"] += amt
            monthly_data[m]["pending_txns"] += 1

    sorted_months = sorted(monthly_data.keys())
    monthly_report_rows = []
    prev_net = None
    prev_gross = None
    cumulative_net = 0.0

    for m in sorted_months:
        d = monthly_data[m]
        g_amt = d["success_amt"]
        r_amt = d["reversed_amt"]
        net_amt = g_amt - r_amt
        cumulative_net += net_amt
        days = d["days_in_month"]
        daily_gross = g_amt / days if days > 0 else 0
        daily_net = net_amt / days if days > 0 else 0
        paying_accs = len(d["paying_accounts"])
        
        # Growth calculations
        if prev_net is not None and prev_net > 0:
            net_mom_pct = ((net_amt - prev_net) / prev_net) * 100.0
            net_abs_change = net_amt - prev_net
        else:
            net_mom_pct = None
            net_abs_change = 0.0

        if prev_gross is not None and prev_gross > 0:
            gross_mom_pct = ((g_amt - prev_gross) / prev_gross) * 100.0
        else:
            gross_mom_pct = None

        recovery_rate_pct = (net_amt / total_outstanding_portfolio) * 100.0
        cumulative_recovery_rate_pct = (cumulative_net / total_outstanding_portfolio) * 100.0

        row = {
            "month": m,
            "status_coverage": "INCOMPLETE (8 days)" if d["is_incomplete"] else "FULL_MONTH",
            "days_recorded": days,
            "gross_success_amount": round(g_amt, 2),
            "success_transactions": d["success_txns"],
            "reversed_amount": round(r_amt, 2),
            "reversed_transactions": d["reversed_txns"],
            "net_realized_recovery": round(net_amt, 2),
            "net_abs_change_inr": round(net_abs_change, 2),
            "gross_mom_growth_pct": round(gross_mom_pct, 2) if gross_mom_pct is not None else "N/A (Base)",
            "net_mom_growth_pct": round(net_mom_pct, 2) if net_mom_pct is not None else "N/A (Base)",
            "daily_net_run_rate_inr": round(daily_net, 2),
            "daily_gross_run_rate_inr": round(daily_gross, 2),
            "distinct_paying_accounts": paying_accs,
            "portfolio_outstanding_denominator": round(total_outstanding_portfolio, 2),
            "monthly_recovery_rate_pct": round(recovery_rate_pct, 4),
            "cumulative_net_recovery_inr": round(cumulative_net, 2),
            "cumulative_recovery_rate_pct": round(cumulative_recovery_rate_pct, 2)
        }
        monthly_report_rows.append(row)
        prev_net = net_amt
        prev_gross = g_amt

    monthly_csv_path = os.path.join(REPORTS_DIR, "monthly_recovery_analysis.csv")
    with open(monthly_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(monthly_report_rows[0].keys()))
        writer.writeheader()
        writer.writerows(monthly_report_rows)
    print(f"Wrote monthly recovery analysis to {monthly_csv_path}")

    # 4. Recovery Metrics by DPD & Risk Segment
    print("\n4. Computing Recovery Metrics by DPD Bucket & Risk Segment...")
    
    # Account-level financial summary
    acc_recovery = defaultdict(lambda: {"gross_recovery": 0.0, "reversals": 0.0, "net_recovery": 0.0, "success_txns": 0})
    for p in payments:
        aid = p["account_id"]
        st = p["payment_status"]
        amt = float(p["amount"])
        if st == "SUCCESS":
            acc_recovery[aid]["gross_recovery"] += amt
            acc_recovery[aid]["net_recovery"] += amt
            acc_recovery[aid]["success_txns"] += 1
        elif st == "REVERSED":
            acc_recovery[aid]["reversals"] += amt
            acc_recovery[aid]["net_recovery"] -= amt

    # DPD breakdown
    dpd_stats = defaultdict(lambda: {
        "account_count": 0, "total_principal": 0.0, "total_outstanding": 0.0,
        "gross_recovery": 0.0, "reversals": 0.0, "net_recovery": 0.0, "paying_accounts": 0
    })
    
    # Risk segment breakdown
    risk_stats = defaultdict(lambda: {
        "account_count": 0, "total_principal": 0.0, "total_outstanding": 0.0,
        "gross_recovery": 0.0, "reversals": 0.0, "net_recovery": 0.0, "paying_accounts": 0
    })

    # Loan type breakdown
    loan_stats = defaultdict(lambda: {
        "account_count": 0, "total_principal": 0.0, "total_outstanding": 0.0,
        "gross_recovery": 0.0, "reversals": 0.0, "net_recovery": 0.0, "paying_accounts": 0
    })

    for a in accounts:
        aid = a["account_id"]
        dpd = int(a["dpd"])
        risk = a["risk_segment"]
        ltype = a["loan_type"]
        p_amt = float(a["principal_amount"])
        o_amt = float(a["outstanding_amount"])

        rec = acc_recovery[aid]
        has_paid = 1 if rec["success_txns"] > 0 else 0

        # DPD
        dpd_stats[dpd]["account_count"] += 1
        dpd_stats[dpd]["total_principal"] += p_amt
        dpd_stats[dpd]["total_outstanding"] += o_amt
        dpd_stats[dpd]["gross_recovery"] += rec["gross_recovery"]
        dpd_stats[dpd]["reversals"] += rec["reversals"]
        dpd_stats[dpd]["net_recovery"] += rec["net_recovery"]
        dpd_stats[dpd]["paying_accounts"] += has_paid

        # Risk
        risk_stats[risk]["account_count"] += 1
        risk_stats[risk]["total_principal"] += p_amt
        risk_stats[risk]["total_outstanding"] += o_amt
        risk_stats[risk]["gross_recovery"] += rec["gross_recovery"]
        risk_stats[risk]["reversals"] += rec["reversals"]
        risk_stats[risk]["net_recovery"] += rec["net_recovery"]
        risk_stats[risk]["paying_accounts"] += has_paid

        # Loan type
        loan_stats[ltype]["account_count"] += 1
        loan_stats[ltype]["total_principal"] += p_amt
        loan_stats[ltype]["total_outstanding"] += o_amt
        loan_stats[ltype]["gross_recovery"] += rec["gross_recovery"]
        loan_stats[ltype]["reversals"] += rec["reversals"]
        loan_stats[ltype]["net_recovery"] += rec["net_recovery"]
        loan_stats[ltype]["paying_accounts"] += has_paid

    recovery_metrics_rows = []
    
    for dpd in sorted(dpd_stats.keys()):
        s = dpd_stats[dpd]
        rate = (s["net_recovery"] / s["total_outstanding"] * 100) if s["total_outstanding"] > 0 else 0
        recovery_metrics_rows.append({
            "dimension": "DPD_BUCKET",
            "segment_value": f"DPD_{dpd}",
            "accounts_count": s["account_count"],
            "total_outstanding_inr": round(s["total_outstanding"], 2),
            "gross_recovery_inr": round(s["gross_recovery"], 2),
            "reversals_inr": round(s["reversals"], 2),
            "net_recovery_inr": round(s["net_recovery"], 2),
            "net_recovery_rate_pct": round(rate, 2),
            "paying_accounts_count": s["paying_accounts"],
            "account_paying_rate_pct": round((s["paying_accounts"] / s["account_count"] * 100), 2),
            "net_recovery_per_account_inr": round(s["net_recovery"] / s["account_count"], 2)
        })

    for risk in sorted(risk_stats.keys()):
        s = risk_stats[risk]
        rate = (s["net_recovery"] / s["total_outstanding"] * 100) if s["total_outstanding"] > 0 else 0
        recovery_metrics_rows.append({
            "dimension": "RISK_SEGMENT",
            "segment_value": risk,
            "accounts_count": s["account_count"],
            "total_outstanding_inr": round(s["total_outstanding"], 2),
            "gross_recovery_inr": round(s["gross_recovery"], 2),
            "reversals_inr": round(s["reversals"], 2),
            "net_recovery_inr": round(s["net_recovery"], 2),
            "net_recovery_rate_pct": round(rate, 2),
            "paying_accounts_count": s["paying_accounts"],
            "account_paying_rate_pct": round((s["paying_accounts"] / s["account_count"] * 100), 2),
            "net_recovery_per_account_inr": round(s["net_recovery"] / s["account_count"], 2)
        })

    for ltype in sorted(loan_stats.keys()):
        s = loan_stats[ltype]
        rate = (s["net_recovery"] / s["total_outstanding"] * 100) if s["total_outstanding"] > 0 else 0
        recovery_metrics_rows.append({
            "dimension": "LOAN_TYPE",
            "segment_value": ltype,
            "accounts_count": s["account_count"],
            "total_outstanding_inr": round(s["total_outstanding"], 2),
            "gross_recovery_inr": round(s["gross_recovery"], 2),
            "reversals_inr": round(s["reversals"], 2),
            "net_recovery_inr": round(s["net_recovery"], 2),
            "net_recovery_rate_pct": round(rate, 2),
            "paying_accounts_count": s["paying_accounts"],
            "account_paying_rate_pct": round((s["paying_accounts"] / s["account_count"] * 100), 2),
            "net_recovery_per_account_inr": round(s["net_recovery"] / s["account_count"], 2)
        })

    recovery_metrics_csv_path = os.path.join(REPORTS_DIR, "recovery_metrics.csv")
    with open(recovery_metrics_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(recovery_metrics_rows[0].keys()))
        writer.writeheader()
        writer.writerows(recovery_metrics_rows)
    print(f"Wrote recovery metrics to {recovery_metrics_csv_path}")

    # 5. PTP Performance Analysis
    print("\n5. Computing PTP Performance Analysis...")
    ptp_path = os.path.join(PROCESSED_DIR, "ptp_clean.csv")
    with open(ptp_path, "r", encoding="utf-8") as f:
        ptps = list(csv.DictReader(f))

    ptp_monthly = defaultdict(lambda: Counter())
    ptp_amounts_by_status = defaultdict(float)
    ptp_by_source = defaultdict(lambda: Counter())

    for pt in ptps:
        m = pt["event_at"][:7]
        st = pt["status"]
        src = pt["source"]
        amt = float(pt["promised_amount"])
        ptp_monthly[m][st] += 1
        ptp_amounts_by_status[st] += amt
        ptp_by_source[src][st] += 1

    ptp_report_rows = []
    for m in sorted(ptp_monthly.keys()):
        c = ptp_monthly[m]
        tot = sum(c.values())
        kept = c["KEPT"]
        broken = c["BROKEN"]
        resolved = kept + broken
        ptp_report_rows.append({
            "month": m,
            "total_ptp_recorded": tot,
            "kept_count": kept,
            "broken_count": broken,
            "cancelled_count": c["CANCELLED"],
            "open_count": c["OPEN"],
            "ptp_kept_rate_of_total_pct": round((kept / tot * 100), 2) if tot > 0 else 0,
            "ptp_kept_rate_of_resolved_pct": round((kept / resolved * 100), 2) if resolved > 0 else 0,
            "ptp_broken_rate_of_resolved_pct": round((broken / resolved * 100), 2) if resolved > 0 else 0
        })

    ptp_csv_path = os.path.join(REPORTS_DIR, "ptp_analysis.csv")
    with open(ptp_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(ptp_report_rows[0].keys()))
        writer.writeheader()
        writer.writerows(ptp_report_rows)
    print(f"Wrote PTP analysis to {ptp_csv_path}")

    # 6. Channel Analysis & Multi-Touch Attribution
    print("\n6. Computing Channel Activity & Payment Attribution...")
    
    # Load channel activity
    # Calls
    call_path = os.path.join(PROCESSED_DIR, "calls_clean.csv")
    with open(call_path, "r", encoding="utf-8") as f:
        calls = list(csv.DictReader(f))
    print(f"Loaded {len(calls):,} clean calls")

    # WhatsApp
    wa_path = os.path.join(RAW_DIR, "whatsapp_events.csv")
    with open(wa_path, "r", encoding="utf-8") as f:
        wa_events = list(csv.DictReader(f))
    print(f"Loaded {len(wa_events):,} WhatsApp events")

    # SMS
    sms_path = os.path.join(RAW_DIR, "sms_events.csv")
    with open(sms_path, "r", encoding="utf-8") as f:
        sms_events = list(csv.DictReader(f))
    print(f"Loaded {len(sms_events):,} SMS events")

    # Field Visits
    fv_path = os.path.join(RAW_DIR, "field_visits.csv")
    with open(fv_path, "r", encoding="utf-8") as f:
        fv_events = list(csv.DictReader(f))
    print(f"Loaded {len(fv_events):,} Field Visits")

    # Group events by account_id and sort by event_at
    account_events = defaultdict(list)
    for c in calls:
        dt = parse_iso(c["event_at"])
        if dt:
            account_events[c["account_id"]].append((dt, "CALL", c["call_status"]))
    for w in wa_events:
        dt = parse_iso(w["event_at"])
        if dt:
            account_events[w["account_id"]].append((dt, "WHATSAPP", w["event_type"]))
    for s in sms_events:
        dt = parse_iso(s["event_at"])
        if dt:
            account_events[s["account_id"]].append((dt, "SMS", s["event_type"]))
    for v in fv_events:
        dt = parse_iso(v["event_at"])
        if dt:
            account_events[v["account_id"]].append((dt, "FIELD", v["outcome"]))

    for aid in account_events:
        account_events[aid].sort(key=lambda x: x[0])

    # Attribution Windows: 24h, 48h, 7d
    attributed_success_payments_48h = defaultdict(int)
    attributed_success_amount_48h = defaultdict(float)
    attributed_success_payments_7d = defaultdict(int)
    attributed_success_amount_7d = defaultdict(float)
    unattributed_payments_48h = 0
    unattributed_amount_48h = 0.0

    total_success_payments = 0
    total_success_amount = 0.0

    for p in payments:
        if p["payment_status"] != "SUCCESS":
            continue
        total_success_payments += 1
        p_amt = float(p["amount"])
        total_success_amount += p_amt
        p_dt = parse_iso(p["event_at"])
        aid = p["account_id"]
        evs = account_events.get(aid, [])

        # Look for interactions in preceding 48h and 7d
        prior_48h = [e for e in evs if timedelta(seconds=0) <= (p_dt - e[0]) <= timedelta(hours=48)]
        prior_7d = [e for e in evs if timedelta(seconds=0) <= (p_dt - e[0]) <= timedelta(days=7)]

        if prior_48h:
            # Last-touch attribution within 48h
            last_touch_channel = prior_48h[-1][1]
            attributed_success_payments_48h[last_touch_channel] += 1
            attributed_success_amount_48h[last_touch_channel] += p_amt
        else:
            unattributed_payments_48h += 1
            unattributed_amount_48h += p_amt

        if prior_7d:
            last_touch_channel_7d = prior_7d[-1][1]
            attributed_success_payments_7d[last_touch_channel_7d] += 1
            attributed_success_amount_7d[last_touch_channel_7d] += p_amt

    channel_rows = [
        {
            "channel": "CALLS (Voice)",
            "total_outreach_events": len(calls),
            "distinct_accounts_contacted": len(set(c["account_id"] for c in calls)),
            "attributed_payments_48h_last_touch": attributed_success_payments_48h["CALL"],
            "attributed_amount_48h_inr": round(attributed_success_amount_48h["CALL"], 2),
            "share_of_attributed_amount_48h_pct": round((attributed_success_amount_48h["CALL"] / total_success_amount * 100), 2),
            "attributed_payments_7d_last_touch": attributed_success_payments_7d["CALL"],
            "attributed_amount_7d_inr": round(attributed_success_amount_7d["CALL"], 2),
            "channel_cost_profile": "HIGH (Human Agent + Telephony Gateway)"
        },
        {
            "channel": "WHATSAPP",
            "total_outreach_events": len(wa_events),
            "distinct_accounts_contacted": len(set(w["account_id"] for w in wa_events)),
            "attributed_payments_48h_last_touch": attributed_success_payments_48h["WHATSAPP"],
            "attributed_amount_48h_inr": round(attributed_success_amount_48h["WHATSAPP"], 2),
            "share_of_attributed_amount_48h_pct": round((attributed_success_amount_48h["WHATSAPP"] / total_success_amount * 100), 2),
            "attributed_payments_7d_last_touch": attributed_success_payments_7d["WHATSAPP"],
            "attributed_amount_7d_inr": round(attributed_success_amount_7d["WHATSAPP"], 2),
            "channel_cost_profile": "LOW (Per-message BSP Gateway)"
        },
        {
            "channel": "SMS",
            "total_outreach_events": len(sms_events),
            "distinct_accounts_contacted": len(set(s["account_id"] for s in sms_events)),
            "attributed_payments_48h_last_touch": attributed_success_payments_48h["SMS"],
            "attributed_amount_48h_inr": round(attributed_success_amount_48h["SMS"], 2),
            "share_of_attributed_amount_48h_pct": round((attributed_success_amount_48h["SMS"] / total_success_amount * 100), 2),
            "attributed_payments_7d_last_touch": attributed_success_payments_7d["SMS"],
            "attributed_amount_7d_inr": round(attributed_success_amount_7d["SMS"], 2),
            "channel_cost_profile": "VERY LOW (Bulk Telco DLT)"
        },
        {
            "channel": "FIELD_VISITS",
            "total_outreach_events": len(fv_events),
            "distinct_accounts_contacted": len(set(v["account_id"] for v in fv_events)),
            "attributed_payments_48h_last_touch": attributed_success_payments_48h["FIELD"],
            "attributed_amount_48h_inr": round(attributed_success_amount_48h["FIELD"], 2),
            "share_of_attributed_amount_48h_pct": round((attributed_success_amount_48h["FIELD"] / total_success_amount * 100), 2),
            "attributed_payments_7d_last_touch": attributed_success_payments_7d["FIELD"],
            "attributed_amount_7d_inr": round(attributed_success_amount_7d["FIELD"], 2),
            "channel_cost_profile": "VERY HIGH (Feet-on-street Agency + Comm)"
        },
        {
            "channel": "ORGANIC / UNATTRIBUTED (No touch in 48h)",
            "total_outreach_events": 0,
            "distinct_accounts_contacted": 0,
            "attributed_payments_48h_last_touch": unattributed_payments_48h,
            "attributed_amount_48h_inr": round(unattributed_amount_48h, 2),
            "share_of_attributed_amount_48h_pct": round((unattributed_amount_48h / total_success_amount * 100), 2),
            "attributed_payments_7d_last_touch": total_success_payments - sum(attributed_success_payments_7d.values()),
            "attributed_amount_7d_inr": round(total_success_amount - sum(attributed_success_amount_7d.values()), 2),
            "channel_cost_profile": "ZERO (Self-cure / Direct Portal Settlement)"
        }
    ]

    channel_csv_path = os.path.join(REPORTS_DIR, "channel_analysis.csv")
    with open(channel_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(channel_rows[0].keys()))
        writer.writeheader()
        writer.writerows(channel_rows)
    print(f"Wrote channel analysis to {channel_csv_path}")

    # 7. Generate Data Visualizations
    print("\n7. Generating Data Visualizations (charts/)...")
    
    # Chart 1: Monthly Net Recovery & Run-rate
    plt.figure(figsize=(10, 6))
    months_plot = [r["month"] for r in monthly_report_rows]
    net_vals = [r["net_realized_recovery"] / 1e6 for r in monthly_report_rows] # in Millions
    colors = ['#1f77b4' if not r["status_coverage"].startswith("INCOMPLETE") else '#d62728' for r in monthly_report_rows]
    bars = plt.bar(months_plot, net_vals, color=colors, edgecolor='black', alpha=0.85)
    plt.title("Monthly Net Realized Recovery (Jan 2026 - Aug 2026)\n[CredResolve Collections Forensics]", fontsize=14, fontweight='bold', pad=15)
    plt.xlabel("Month", fontsize=12)
    plt.ylabel("Net Realized Recovery (INR Millions)", fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    for bar in bars:
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., h + 2, f"₹{h:.1f}M", ha='center', va='bottom', fontsize=9, fontweight='bold')
    plt.annotate('Incomplete Month\n(8 days only: ₹44.2M)', xy=(7, 44.15), xytext=(5.2, 80),
                 arrowprops=dict(facecolor='black', shrink=0.05, width=1.5, headwidth=8),
                 fontsize=10, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.6))
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, "01_monthly_net_recovery.png"), dpi=300)
    plt.close()

    # Chart 2: Gross Success vs Reversals
    plt.figure(figsize=(10, 6))
    gross_vals = [r["gross_success_amount"] / 1e6 for r in monthly_report_rows]
    rev_vals = [r["reversed_amount"] / 1e6 for r in monthly_report_rows]
    x = range(len(months_plot))
    width = 0.35
    plt.bar([i - width/2 for i in x], gross_vals, width=width, label='Gross Success Recovery', color='#2ca02c', edgecolor='black', alpha=0.85)
    plt.bar([i + width/2 for i in x], rev_vals, width=width, label='Reversals / Dishonored (Clawback)', color='#d62728', edgecolor='black', alpha=0.85)
    plt.xticks(x, months_plot)
    plt.title("Gross Success Payments vs. Reversals by Month", fontsize=14, fontweight='bold', pad=15)
    plt.xlabel("Month", fontsize=12)
    plt.ylabel("Amount (INR Millions)", fontsize=12)
    plt.legend(frameon=True, shadow=True)
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, "02_gross_vs_reversed_payments.png"), dpi=300)
    plt.close()

    # Chart 3: Recovery by DPD Bucket
    plt.figure(figsize=(10, 6))
    dpd_items = [r for r in recovery_metrics_rows if r["dimension"] == "DPD_BUCKET"]
    dpd_labels = [r["segment_value"] for r in dpd_items]
    dpd_rates = [r["net_recovery_rate_pct"] for r in dpd_items]
    bars = plt.bar(dpd_labels, dpd_rates, color='#3b528b', edgecolor='black', alpha=0.85)
    plt.title("Net Recovery Rate (%) by DPD Bucket", fontsize=14, fontweight='bold', pad=15)
    plt.xlabel("Delinquency (DPD Bucket)", fontsize=12)
    plt.ylabel("Net Recovery Rate (%)", fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    for bar in bars:
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., h + 0.15, f"{h:.2f}%", ha='center', va='bottom', fontsize=9, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, "03_recovery_by_dpd.png"), dpi=300)
    plt.close()

    # Chart 4: Channel Comparison (Attributed Recovery)
    plt.figure(figsize=(10, 6))
    chan_items = [c for c in channel_rows if c["channel"] != "ORGANIC / UNATTRIBUTED (No touch in 48h)"]
    chan_names = [c["channel"] for c in chan_items]
    chan_amts = [c["attributed_amount_48h_inr"] / 1e6 for c in chan_items]
    bars = plt.bar(chan_names, chan_amts, color=['#1f77b4', '#2ca02c', '#ff7f0e', '#9467bd'], edgecolor='black', alpha=0.85)
    plt.title("48-Hour Last-Touch Attributed Recovery by Channel (INR Millions)", fontsize=14, fontweight='bold', pad=15)
    plt.xlabel("Channel", fontsize=12)
    plt.ylabel("Attributed Amount (INR Millions)", fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    for bar in bars:
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., h + 5, f"₹{h:.1f}M", ha='center', va='bottom', fontsize=9, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, "04_channel_comparison.png"), dpi=300)
    plt.close()

    # Chart 5: PTP Performance Breakdown
    plt.figure(figsize=(8, 6))
    ptp_statuses = ["KEPT", "BROKEN", "CANCELLED", "OPEN"]
    ptp_counts = [ptp_amounts_by_status[st] / 1e6 for st in ptp_statuses]
    plt.pie(ptp_counts, labels=[f"{st}\n₹{ptp_amounts_by_status[st]/1e6:.1f}M" for st in ptp_statuses],
            autopct='%1.1f%%', startangle=140, colors=['#2ca02c', '#d62728', '#7f7f7f', '#1f77b4'],
            wedgeprops={'edgecolor': 'black'})
    plt.title("Promises-to-Pay (PTP) Commitment Volume Breakdown\nTotal Promised: ₹904.2M", fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, "05_ptp_performance.png"), dpi=300)
    plt.close()

    # Chart 6: MoM Growth Forensics (Uncovering the 11% Mystery)
    plt.figure(figsize=(10, 6))
    full_months = [r["month"] for r in monthly_report_rows[1:] if not r["status_coverage"].startswith("INCOMPLETE")] # Feb to Jul
    mom_growths = [float(r["net_mom_growth_pct"]) for r in monthly_report_rows[1:] if not r["status_coverage"].startswith("INCOMPLETE")]
    colors = ['#2ca02c' if g > 0 else '#d62728' for g in mom_growths]
    bars = plt.bar(full_months, mom_growths, color=colors, edgecolor='black', alpha=0.85)
    plt.axhline(0, color='black', linewidth=1)
    plt.axhline(11.0, color='blue', linestyle='--', linewidth=1.5, label='Claimed 11% MoM Baseline')
    plt.title("Actual Month-on-Month Net Recovery Growth Rate (%)\n[Forensic Audit of the Claimed 11% MoM Improvement]", fontsize=13, fontweight='bold', pad=15)
    plt.xlabel("Month", fontsize=12)
    plt.ylabel("MoM Growth Rate (%)", fontsize=12)
    plt.legend(frameon=True, shadow=True)
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    for bar in bars:
        h = bar.get_height()
        va = 'bottom' if h >= 0 else 'top'
        y_pos = h + 0.5 if h >= 0 else h - 1.2
        plt.text(bar.get_x() + bar.get_width()/2., y_pos, f"{h:+.2f}%", ha='center', va=va, fontsize=9, fontweight='bold')
    plt.annotate('March "Jump" (+9.9% Net / +11.0% Gross):\nFebruary had 28 days, March had 31 days (+10.7% days)!\nDaily run-rate change was +0.2%.',
                 xy=(1, 9.94), xytext=(1.2, 12.5),
                 arrowprops=dict(facecolor='black', shrink=0.05, width=1.5, headwidth=8),
                 fontsize=9.5, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="#ffecb3", alpha=0.9))
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, "06_mom_growth_forensics.png"), dpi=300)
    plt.close()

    print(f"Generated 6 forensic charts in {CHARTS_DIR}")

    return {
        "monthly_report": monthly_report_rows,
        "recovery_metrics": recovery_metrics_rows,
        "channel_analysis": channel_rows,
        "ptp_analysis": ptp_report_rows
    }

if __name__ == "__main__":
    run_business_analysis()
