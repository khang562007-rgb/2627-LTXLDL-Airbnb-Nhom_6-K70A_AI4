import pandas as pd
snaps = ["2025-09-21", "2025-12-25", "2026-03-26", "2026-06-23"]
for s in snaps:
    d = pd.read_csv(f"data/raw/{s}/listings.csv.gz", low_memory=False)
    print(s, d.shape, "| cot rong hoan toan:", d.columns[d.isna().all()].tolist())