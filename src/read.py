import argparse
from pathlib import Path
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser(description="Kiểm tra nhanh kích thước và cột rỗng của listings thô")
    ap.add_argument("--config", default="configs/porto.yaml", help="Đường dẫn file cấu hình YAML")
    args = ap.parse_args()
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    cfg = yaml.safe_load(cfg_path.open(encoding="utf-8"))
    snaps = cfg["snapshots"]
    raw_root = ROOT / cfg["paths"]["raw_root"]

    for s in snaps:
        d = pd.read_csv(raw_root / str(s) / "listings.csv.gz", low_memory=False)
        print(s, d.shape, "| cot rong hoan toan:", d.columns[d.isna().all()].tolist())


if __name__ == "__main__":
    main()