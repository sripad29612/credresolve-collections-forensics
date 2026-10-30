import os
import shutil

src_dir = r"C:\Users\puram\.gemini\antigravity-ide\brain\cb0fe217-2ed2-4de7-a7bc-cfe6ebb40d0f"
dest_dir = r"c:\Users\puram\Desktop\credresolve project\reports\dashboard_screenshots"

os.makedirs(dest_dir, exist_ok=True)

files_map = {
    "homepage_overview_1793346182303.png": "01_homepage_overview.png",
    "tab1_monthly_recovery_1793346198682.png": "02_tab1_monthly_recovery.png",
    "tab2_audit_11_percent_1793346214653.png": "03_tab2_audit_11_percent.png",
    "tab2_mar_tooltip_1793346220994.png": "04_tab2_mar_tooltip.png",
    "tab3_channel_attribution_1793346255448.png": "05_tab3_channel_attribution.png",
    "tab4_dpd_risk_stratification_1793346271608.png": "06_tab4_dpd_risk_stratification.png",
    "tab5_rct_proposal_1793346287528.png": "07_tab5_rct_proposal.png",
}

for src_name, dest_name in files_map.items():
    src_path = os.path.join(src_dir, src_name)
    dest_path = os.path.join(dest_dir, dest_name)
    if os.path.exists(src_path):
        shutil.copyfile(src_path, dest_path)
        print(f"Copied {src_name} -> {dest_name}")
    else:
        print(f"File not found: {src_path}")

print("Done copying screenshots.")
