import json
import os

NOTEBOOK_PATH = r"c:\Users\puram\Desktop\credresolve project\notebooks\credresolve_analysis.ipynb"

def create_notebook():
    cells = []

    def md_cell(source):
        return {
            "cell_type": "markdown",
            "metadata": {},
            "source": [line + "\n" for line in source.split("\n")]
        }

    def code_cell(source):
        return {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [line + "\n" for line in source.split("\n")]
        }

    # Cell 1: Title and Executive Intro
    cells.append(md_cell("""# CredResolve: Collections Performance Forensics
## Phase 3: Business Performance Analysis & Forensic Investigation

**Author**: Senior Forensic Data Analyst & Data Engineer  
**Dataset**: Golden Cleaned Dataset (`data/processed/`)  
**Scope**: 30,000 portfolio accounts, 24,986 clean payment records, 89,921 clean calls, 18,000 PTPs  
**Primary Objective**: Independently audit the reported **11% month-on-month recovery improvement**, calculate core portfolio performance metrics, evaluate channel attribution, and assess strategic investment options.

---
### Key Executive Conclusions
1. **The 11% Claim is NOT Supported as a Sustainable Improvement**:
   - The reported "+11% MoM improvement" is a statistical artifact:
     - **Calendar Illusion**: March gross recovery grew +10.96% (~11%) over February, but February had 28 days and March had 31 days (+10.71% more calendar days). The **daily run-rate grew by only +0.2%** (₹6.07M/day in Feb vs ₹6.08M/day in March).
     - **Cumulative Confusion**: The cumulative net portfolio recovery rate reached **11.21% by July (11.63% by Aug 8)**, which was mistakenly conflated with a monthly growth velocity.
     - **Reversals Subtraction**: When accounting for reversals, March net growth was only +9.94%, and subsequent months fluctuated wildly (-7.21% in April, +6.03% in May, -5.34% in June, +5.95% in July).
2. **Operational Window Truncation**:
   - Collections operational data spans strictly from **January 1, 2026 to August 8, 2026 (7.25 months / 220 days)**. August is incomplete (only 8 days), and months 9-12 are completely missing.
3. **Channel Performance**:
   - WhatsApp and Digital SMS deliver the highest recovery per operational dollar, whereas Field Visits are cost-prohibitive for pre-NPA buckets.
"""))

    # Cell 2: Imports & Environment Setup
    cells.append(code_cell("""import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Set visual styles
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
pd.set_option('display.float_format', lambda x: f'₹{x:,.2f}' if abs(x) > 100 else f'{x:,.2f}')

BASE_DIR = os.path.abspath('..') if os.path.exists(os.path.join('..', 'data', 'processed')) else (os.path.abspath('.') if os.path.exists(os.path.join('.', 'data', 'processed')) else r"c:\\Users\\puram\\Desktop\\credresolve project")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")

print(f"Environment configured successfully. Base dir: {BASE_DIR}")"""))

    # Cell 3: Load Datasets
    cells.append(code_cell("""# Load Golden Datasets
accounts = pd.read_csv(os.path.join(PROCESSED_DIR, "accounts_clean.csv"))
payments = pd.read_csv(os.path.join(PROCESSED_DIR, "payments_clean.csv"))
calls = pd.read_csv(os.path.join(PROCESSED_DIR, "calls_clean.csv"))
ptp = pd.read_csv(os.path.join(PROCESSED_DIR, "ptp_clean.csv"))

print(f"Loaded Accounts: {len(accounts):,} records")
print(f"Loaded Payments: {len(payments):,} records")
print(f"Loaded Calls: {len(calls):,} records")
print(f"Loaded PTP: {len(ptp):,} records")

total_outstanding = accounts['outstanding_amount'].sum()
total_principal = accounts['principal_amount'].sum()
print(f"Total Portfolio Outstanding Book: ₹{total_outstanding:,.2f}")
print(f"Total Portfolio Principal: ₹{total_principal:,.2f}")"""))

    # Cell 4: Section 1 - Monthly Recovery Analysis Table
    cells.append(md_cell("""## 1. Monthly Recovery Performance & Run-Rate Analysis
We analyze monthly cash inflows, reversal clawbacks, net realized recovery, and daily run-rates across the 2026 operating timeline."""))

    cells.append(code_cell("""# Extract year-month
payments['month'] = payments['event_at'].str[:7]

# Aggregate monthly metrics
monthly = payments.groupby('month').apply(lambda g: pd.Series({
    'gross_success_amt': g[g['payment_status'] == 'SUCCESS']['amount'].sum(),
    'success_txns': (g['payment_status'] == 'SUCCESS').sum(),
    'reversed_amt': g[g['payment_status'] == 'REVERSED']['amount'].sum(),
    'reversed_txns': (g['payment_status'] == 'REVERSED').sum(),
    'net_recovery': g[g['payment_status'] == 'SUCCESS']['amount'].sum() - g[g['payment_status'] == 'REVERSED']['amount'].sum(),
    'failed_amt': g[g['payment_status'] == 'FAILED']['amount'].sum(),
    'pending_amt': g[g['payment_status'] == 'PENDING']['amount'].sum(),
    'paying_accounts': g[g['payment_status'] == 'SUCCESS']['account_id'].nunique()
})).reset_index()

# Calendar days mapping
days_map = {'2026-01': 31, '2026-02': 28, '2026-03': 31, '2026-04': 30, '2026-05': 31, '2026-06': 30, '2026-07': 31, '2026-08': 8}
monthly['days'] = monthly['month'].map(days_map)
monthly['status_coverage'] = monthly['month'].apply(lambda x: 'INCOMPLETE (8 days)' if x == '2026-08' else 'FULL_MONTH')

# Growth and run-rate metrics
monthly['gross_mom_pct'] = monthly['gross_success_amt'].pct_change() * 100
monthly['net_mom_pct'] = monthly['net_recovery'].pct_change() * 100
monthly['daily_gross_run_rate'] = monthly['gross_success_amt'] / monthly['days']
monthly['daily_net_run_rate'] = monthly['net_recovery'] / monthly['days']
monthly['monthly_recovery_rate_pct'] = (monthly['net_recovery'] / total_outstanding) * 100
monthly['cumulative_net_recovery'] = monthly['net_recovery'].cumsum()
monthly['cumulative_recovery_rate_pct'] = (monthly['cumulative_net_recovery'] / total_outstanding) * 100

monthly[['month', 'status_coverage', 'gross_success_amt', 'reversed_amt', 'net_recovery', 'net_mom_pct', 'daily_net_run_rate', 'cumulative_recovery_rate_pct']]"""))

    # Cell 5: Plotting Monthly Net Recovery
    cells.append(code_cell("""fig, ax = plt.subplots(figsize=(10, 5))
colors = ['#1f77b4' if s == 'FULL_MONTH' else '#d62728' for s in monthly['status_coverage']]
bars = ax.bar(monthly['month'], monthly['net_recovery'] / 1e6, color=colors, edgecolor='black', alpha=0.85)
ax.set_title("Monthly Net Realized Recovery (Jan 2026 - Aug 2026)", fontsize=14, fontweight='bold', pad=15)
ax.set_xlabel("Month", fontsize=11)
ax.set_ylabel("Net Realized Recovery (INR Millions)", fontsize=11)
for bar in bars:
    y = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, y + 2, f"₹{y:.1f}M", ha='center', va='bottom', fontsize=9, fontweight='bold')
plt.tight_layout()
plt.show()"""))

    # Cell 6: Section 2 - Recovery by DPD Bucket & Risk Segment
    cells.append(md_cell("""## 2. Portfolio Stratification: Recovery by DPD Bucket & Risk Segment"""))

    cells.append(code_cell("""# Merge accounts with payments
acc_pay = payments[payments['payment_status'] == 'SUCCESS'].groupby('account_id')['amount'].sum().reset_index()
acc_pay.rename(columns={'amount': 'recovered_amount'}, inplace=True)
acc_full = accounts.merge(acc_pay, on='account_id', how='left')
acc_full['recovered_amount'] = acc_full['recovered_amount'].fillna(0.0)

# DPD Summary
dpd_summary = acc_full.groupby('dpd').agg(
    accounts=('account_id', 'count'),
    total_outstanding=('outstanding_amount', 'sum'),
    total_recovered=('recovered_amount', 'sum'),
    paying_accounts=('recovered_amount', lambda x: (x > 0).sum())
).reset_index()
dpd_summary['recovery_rate_pct'] = (dpd_summary['total_recovered'] / dpd_summary['total_outstanding']) * 100
dpd_summary['account_paying_rate_pct'] = (dpd_summary['paying_accounts'] / dpd_summary['accounts']) * 100

print("--- RECOVERY BY DPD BUCKET ---")
dpd_summary"""))

    # Cell 7: Plotting Recovery by DPD
    cells.append(code_cell("""fig, ax = plt.subplots(figsize=(10, 5))
bars = ax.bar([f"DPD {d}" for d in dpd_summary['dpd']], dpd_summary['recovery_rate_pct'], color='#3b528b', edgecolor='black', alpha=0.85)
ax.set_title("Net Recovery Rate (%) by DPD Bucket", fontsize=14, fontweight='bold', pad=15)
ax.set_xlabel("Delinquency (DPD)", fontsize=11)
ax.set_ylabel("Recovery Rate (%)", fontsize=11)
for bar in bars:
    y = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, y + 0.15, f"{y:.2f}%", ha='center', va='bottom', fontsize=9, fontweight='bold')
plt.tight_layout()
plt.show()"""))

    # Cell 8: Section 3 - Multi-Touch Channel Attribution
    cells.append(md_cell("""## 3. Channel Analysis & Multi-Touch Attribution (48-Hour Lookback)"""))

    cells.append(code_cell("""channel_analysis_df = pd.read_csv(os.path.join(REPORTS_DIR, "channel_analysis.csv"))
channel_analysis_df[['channel', 'total_outreach_events', 'attributed_payments_48h_last_touch', 'attributed_amount_48h_inr', 'share_of_attributed_amount_48h_pct', 'channel_cost_profile']]"""))

    # Cell 9: Plotting Channel Attribution
    cells.append(code_cell("""fig, ax = plt.subplots(figsize=(10, 5))
sub_chan = channel_analysis_df[channel_analysis_df['channel'] != 'ORGANIC / UNATTRIBUTED (No touch in 48h)']
bars = ax.bar(sub_chan['channel'], sub_chan['attributed_amount_48h_inr'] / 1e6, color=['#1f77b4', '#2ca02c', '#ff7f0e', '#9467bd'], edgecolor='black', alpha=0.85)
ax.set_title("48-Hour Last-Touch Attributed Recovery by Channel (INR Millions)", fontsize=14, fontweight='bold', pad=15)
ax.set_xlabel("Channel", fontsize=11)
ax.set_ylabel("Attributed Recovery (INR Millions)", fontsize=11)
for bar in bars:
    y = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, y + 5, f"₹{y:.1f}M", ha='center', va='bottom', fontsize=9, fontweight='bold')
plt.tight_layout()
plt.show()"""))

    # Cell 10: Section 4 - PTP Performance
    cells.append(md_cell("""## 4. Promises-to-Pay (PTP) Conversion Analysis"""))

    cells.append(code_cell("""ptp_summary = ptp.groupby('status').agg(
    count=('ptp_id', 'count'),
    total_promised_amt=('promised_amount', 'sum')
).reset_index()
ptp_summary['pct_of_count'] = (ptp_summary['count'] / ptp_summary['count'].sum()) * 100
ptp_summary['pct_of_volume'] = (ptp_summary['total_promised_amt'] / ptp_summary['total_promised_amt'].sum()) * 100
ptp_summary"""))

    # Cell 11: Section 5 - Deconstructing the 11% Claim
    cells.append(md_cell("""## 5. Forensic Audit: Deconstructing the "11% Improvement" Claim

### The Evidence:
1. **Calendar Length Discrepancy**:
   - Gross success recovery in February 2026: **₹170,005,292.55** (28 days).
   - Gross success recovery in March 2026: **₹188,634,421.46** (31 days).
   - Nominal Gross Growth = $\frac{₹188.63M - ₹170.01M}{₹170.01M} = \mathbf{+10.96\% \approx 11.0\%}$.
   - However, March had **10.71% more calendar days** than February ($31 / 28 = 1.1071$).
   - Normalized Daily Run-Rate:
     - February daily gross: $\frac{₹170.01M}{28} = \mathbf{₹6.07M / day}$.
     - March daily gross: $\frac{₹188.63M}{31} = \mathbf{₹6.08M / day}$.
     - **True operational growth on a daily normalized basis was only +0.2%**!
2. **Reversal Leakage**:
   - Reversals surged in March (₹14.36M vs ₹11.48M in Feb).
   - Net realized MoM growth was only **+9.94%**, not 11%.
3. **Cumulative Recovery Conflation**:
   - By the end of July 2026, cumulative net recovery reached **₹1,175.88M**, which is **11.21% of the ₹10.49B outstanding portfolio**.
   - Management / reporting presentations frequently confuse a **11% cumulative recovery ratio** with an ongoing **11% MoM velocity improvement**.
4. **Subsequent Performance Collapse**:
   - In April 2026, net recovery dropped by **-7.21%**.
   - In June 2026, net recovery dropped by **-5.34%**.
   - Claiming a persistent "11% month-on-month improvement" is completely refuted by the data.
"""))

    # Cell 12: Section 6 - Counterfactual Framework
    cells.append(md_cell("""## 6. Counterfactual Methodology Design
To estimate what recovery would have looked like without the targeting strategy change:
- **Treatment vs Control**: In `daily_targeting.csv` and `campaigns.csv`, strategies `v1`, `v2`, `v3`, and `legacy` were deployed concurrently across identical risk profiles.
- **Methodology**: Difference-in-Differences (DiD) and Propensity Score Matching (PSM) controlling for DPD, principal balance, and risk segment.
- **Empirical Finding**: As documented in the analysis, conversion rates across all four strategy versions were identical (~44.2% to 44.5%), indicating that the targeting strategy change produced negligible incremental treatment effect."""))

    # Cell 13: Section 7 - Strategic Investment Options
    cells.append(md_cell("""## 7. Strategic Investment Recommendations
Evaluation of the six investment options:
1. **Voice AI Conversational Bot**: Recommended pilot for early DPD (1-30) to automate low-duration calls and eliminate dialer latency.
2. **WhatsApp Business API**: **PRIMARY RECOMMENDATION**. Highest ROI per rupee spent. High reach, frictionless payment link integration, lowest dispute rate.
3. **Field Collection Expansion**: NOT recommended for general portfolio; cost-prohibitive. Restrict strictly to high-value NPA write-offs (>₹200k).
4. **Bulk SMS**: Maintain as passive hygiene notification, but cap investment due to low click-through engagement.
5. **ML Targeting Engine**: Refine propensity scoring to identify self-cure accounts and suppress unnecessary touches.
6. **Agent Upskilling**: Focus on dispute resolution and compliance to reduce the 5.04% reversal rate."""))

    notebook_content = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "codemirror_mode": {"name": "ipython", "version": 3},
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.12.0"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }

    with open(NOTEBOOK_PATH, "w", encoding="utf-8") as f:
        json.dump(notebook_content, f, indent=2)
    print(f"Created notebook at {NOTEBOOK_PATH}")

if __name__ == "__main__":
    create_notebook()
