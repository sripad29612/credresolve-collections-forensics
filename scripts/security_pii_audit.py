import os
import glob
import pandas as pd
import re

base_dir = r"c:\Users\puram\Desktop\credresolve project"

print("="*60)
print("1. SCANNING REPOSITORY FILES AND SIZES")
print("="*60)

for root, dirs, files in os.walk(base_dir):
    # Skip .git if exists
    if ".git" in root:
        continue
    for f in files:
        fpath = os.path.join(root, f)
        relpath = os.path.relpath(fpath, base_dir)
        size = os.path.getsize(fpath)
        if size > 1024 * 1024:  # > 1 MB
            print(f"LARGE FILE: {relpath} ({size / (1024*1024):.2f} MB)")

print("\n" + "="*60)
print("2. INSPECTING COLUMNS OF PROCESSED & QUARANTINE DATASETS")
print("="*60)

processed_files = glob.glob(os.path.join(base_dir, "data", "processed", "*.csv"))
for pf in processed_files:
    fname = os.path.basename(pf)
    df = pd.read_csv(pf, nrows=5)
    print(f"\nFile: data/processed/{fname} (Total cols: {len(df.columns)})")
    print(f"Columns: {list(df.columns)}")
    print(f"Sample row:\n{df.iloc[0].to_dict()}")

quarantine_files = glob.glob(os.path.join(base_dir, "data", "quarantine", "*.csv"))
for qf in quarantine_files:
    fname = os.path.basename(qf)
    df = pd.read_csv(qf, nrows=5)
    print(f"\nFile: data/quarantine/{fname} (Total cols: {len(df.columns)})")
    print(f"Columns: {list(df.columns)}")

print("\n" + "="*60)
print("3. INSPECTING REPORTS CSV FILES")
print("="*60)

report_files = glob.glob(os.path.join(base_dir, "reports", "*.csv"))
for rf in report_files:
    fname = os.path.basename(rf)
    df = pd.read_csv(rf, nrows=5)
    print(f"\nFile: reports/{fname} (Total cols: {len(df.columns)})")
    print(f"Columns: {list(df.columns)}")

print("\n" + "="*60)
print("4. CHECKING FOR POTENTIAL SECRETS / CREDENTIALS")
print("="*60)

secret_patterns = [
    re.compile(r'(?i)(api[_-]?key|secret|password|auth[_-]?token|private[_-]?key)[\s:=]+["\']?([a-zA-Z0-9_\-]{8,})'),
    re.compile(r'ghp_[a-zA-Z0-9]{36}'),  # GitHub PAT
    re.compile(r'-----BEGIN [A-Z]+ PRIVATE KEY-----')
]

for root, dirs, files in os.walk(base_dir):
    if "collections_30k_dataset" in root or ".git" in root or ".ipynb_checkpoints" in root:
        continue
    for f in files:
        if f.endswith(('.py', '.sql', '.html', '.md', '.json', '.txt', '.csv', '.env')):
            fpath = os.path.join(root, f)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as fp:
                    content = fp.read()
                    for pat in secret_patterns:
                        matches = pat.findall(content)
                        if matches:
                            print(f"POTENTIAL MATCH in {os.path.relpath(fpath, base_dir)}: {matches[:3]}")
            except Exception as e:
                pass

print("Security audit scan completed.")
