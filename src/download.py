import argparse
import csv
import gzip
import json
import tempfile
import zlib
from pathlib import Path

import requests
import yaml


ROOT = Path(__file__).resolve().parent.parent
REQUIRED_KEY_COLS = {
    "listings.csv.gz": {"id"},
    "calendar.csv.gz": {"listing_id", "date"},
    "reviews.csv.gz": {"id", "listing_id"},
}


def verify_key_columns(path: Path, name: str, *, check_full_stream: bool = False) -> None:
    """Kiểm tra tệp tồn tại, khác rỗng và có đủ các cột khóa bắt buộc."""
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"Tệp không tồn tại hoặc rỗng: {path}")
    if name == "neighbourhoods.geojson":
        with path.open(encoding="utf-8-sig") as fh:
            geo = json.load(fh)
        if not isinstance(geo, dict) or geo.get("type") != "FeatureCollection" or not geo.get("features"):
            raise ValueError(f"GeoJSON thiếu ranh giới khu vực: {path}")
        return
    required = REQUIRED_KEY_COLS.get(name, set())
    if not required:
        return
    opener = gzip.open if name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace", newline="") as fh:
        header = next(csv.reader(fh), [])
        if check_full_stream:
            # Đọc hết để gzip kiểm tra CRC và phát hiện tệp bị cắt giữa chừng.
            while fh.buffer.read(1024 * 1024):
                pass
    cols = {c.strip().lstrip("\ufeff") for c in header}
    missing = required - cols
    if missing:
        raise ValueError(f"Tệp {path.relative_to(ROOT)} thiếu cột khóa bắt buộc: {sorted(missing)}")


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
    dl = config["download"]
    base_url = (
        dl.get("base_url")
        or f"https://data.insideairbnb.com/{str(config['data_root']).strip('/')}"
    ).rstrip("/")
    files = dl.get("files", [])
    visualisations = dl.get("visualisations", [])
    chunk_size = dl["stream_chunk_size"]
    timeout = dl["timeout_seconds"]

    for snap in snapshots:
        folder = raw_dir / str(snap)
        targets = []
        for name in files:
            section = "visualisations" if name == "neighbourhoods.geojson" else "data"
            targets.append((name, section, folder / name))
        for name in visualisations:
            targets.append((name, "visualisations", folder / "visualisations" / name))

        for name, section, path in targets:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                try:
                    verify_key_columns(path, name, check_full_stream=True)
                except (OSError, EOFError, ValueError, RuntimeError, zlib.error) as error:
                    print(f"Tải lại {name} vì kiểm tra thất bại: {error}")
                else:
                    print("đã có & hợp lệ, bỏ qua:", path.relative_to(ROOT))
                    continue

            # Write to a temporary file and rename only after the download completes.
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".part", delete=False) as staging:
                tmp = Path(staging.name)
            try:
                with requests.get(
                    f"{base_url}/{snap}/{section}/{name}",
                    stream=True,
                    timeout=timeout,
                ) as response:
                    response.raise_for_status()
                    with tmp.open("wb") as output_file:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                output_file.write(chunk)
                verify_key_columns(tmp, name, check_full_stream=True)
                tmp.replace(path)
            finally:
                tmp.unlink(missing_ok=True)

            print(
                "đã tải & kiểm tra:",
                path.relative_to(ROOT),
                f"({path.stat().st_size / 1e6:.1f} MB)",
            )


if __name__ == "__main__":
    main()
