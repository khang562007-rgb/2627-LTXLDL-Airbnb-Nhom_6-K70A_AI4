from pathlib import Path
import sys
import pandas as pd
import yaml

from src import flag_host_locations, flag_price_calendar, flag_property_cross, flag_reviews

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
cfg = yaml.safe_load((ROOT / "configs" / "porto.yaml").open(encoding="utf-8"))

ids_path = ROOT / cfg["sample"]["listing_ids_path"]
ids = set(pd.read_csv(ids_path, dtype=str)["listing_id"])
print("so id doc duoc:", len(ids))

for name, mod in [
    ("flag_host_locations", flag_host_locations),
    ("flag_price_calendar", flag_price_calendar),
    ("flag_property_cross", flag_property_cross),
    ("flag_reviews", flag_reviews),
]:
    print(f"\n=== Chay {name} ===")
    sys.argv = [name, "--config", "configs/porto.yaml"]
    mod.main()