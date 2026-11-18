from pathlib import Path
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
cfg = yaml.safe_load((ROOT / "configs" / "porto.yaml").open(encoding="utf-8"))
snaps = cfg["snapshots"]
raw_root = ROOT / cfg["paths"]["raw_root"]

for s in snaps:
    d = pd.read_csv(raw_root / s / "listings.csv.gz", low_memory=False)
    print(s, d.shape, "| cot rong hoan toan:", d.columns[d.isna().all()].tolist())