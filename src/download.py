import argparse
import csv
import gzip
from tempfile import NamedTemporaryFile
from pathlib import Path

import requests
import yaml


ROOT = Path(__file__).resolve().parent.parent
REQUIRED_KEY_COLS = {
    "listings.csv.gz": {"id"},
    "calendar.csv.gz": {"listing_id", "date"},
    "reviews.csv.gz": {"id", "listing_id"},
}


def verify_key_columns(path: Path, name: str) -> None:
    """Kiểm tra tệp tồn tại, khác rỗng và có đủ các cột khóa bắt buộc."""
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"Tệp không tồn tại hoặc rỗng: {path}")
    required = REQUIRED_KEY_COLS.get(name, set())
    if not required:
        return
    opener = gzip.open if name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace", newline="") as fh:
        header = next(csv.reader(fh), [])
    cols = {c.strip().lstrip("\ufeff") for c in header}
    missing = required - cols
    if missing:
        raise ValueError(f"Tệp {path} thiếu cột khóa bắt buộc: {sorted(missing)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Tải dữ liệu Inside Airbnb theo tệp cấu hình YAML")
    ap.add_argument("--config", default="configs/porto.yaml", help="Đường dẫn file cấu hình YAML")
    args = ap.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    with config_path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    raw_dir = ROOT / config["paths"]["raw_root"]
    snapshots = config["snapshots"]
    base_url = config["download"]["base_url"].rstrip("/")
    files = config["download"]["files"]
    chunk_size = config["download"]["stream_chunk_size"]
    timeout = config["download"]["timeout_seconds"]

    for snap in snapshots:
        folder = raw_dir / str(snap)
        folder.mkdir(parents=True, exist_ok=True)
        for name in files:
            path = folder / name
            if path.exists():
                verify_key_columns(path, name)
                print("đã có & hợp lệ, bỏ qua:", path)
                continue

            # Write to a temporary file and rename only after the download completes.
            with NamedTemporaryFile(dir=folder, prefix=name + ".", suffix=".part", delete=False) as staging:
                tmp = Path(staging.name)
            try:
                with requests.get(
                    f"{base_url}/{snap}/data/{name}",
                    stream=True,
                    timeout=timeout,
                ) as response:
                    response.raise_for_status()
                    with tmp.open("wb") as output_file:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                output_file.write(chunk)
                verify_key_columns(tmp, name)
                tmp.replace(path)
            except Exception:
                tmp.unlink(missing_ok=True)
                raise

            print(
                "đã tải & kiểm tra cột khóa:",
                path,
                f"({path.stat().st_size / 1e6:.1f} MB)",
            )


if __name__ == "__main__":
    main()