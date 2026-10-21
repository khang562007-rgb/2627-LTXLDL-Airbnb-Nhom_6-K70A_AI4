from pathlib import Path
import requests
ROOT = Path(__file__).parent.parent          # file nằm trong src/ -> gốc dự án là thư mục cha
RAW = ROOT / "data" / "raw"

SNAPSHOTS = ["2025-09-21", "2025-12-25", "2026-03-26", "2026-06-23"]
BASE = "https://data.insideairbnb.com/portugal/norte/porto"
FILES = ["listings.csv.gz", "calendar.csv.gz", "reviews.csv.gz"]

for snap in SNAPSHOTS:
    folder = RAW / snap
    folder.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        path = folder / name
        if path.exists():
            print("đã có, bỏ qua:", path.relative_to(ROOT))
            continue

        # tải từng khối vào file tạm, xong mới đổi tên (tránh để lại file hỏng nếu bị ngắt giữa chừng)
        tmp = path.with_name(name + ".part")
        with requests.get(f"{BASE}/{snap}/data/{name}", stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
        tmp.rename(path)
        print("đã tải:", path.relative_to(ROOT), f"({path.stat().st_size / 1e6:.1f} MB)")