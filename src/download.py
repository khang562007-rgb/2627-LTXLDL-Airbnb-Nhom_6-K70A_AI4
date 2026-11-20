from pathlib import Path

import requests
import yaml


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "configs" / "porto.yaml"

with CONFIG_PATH.open(encoding="utf-8") as config_file:
    CONFIG = yaml.safe_load(config_file)

RAW = ROOT / CONFIG["paths"]["raw_root"]
SNAPSHOTS = CONFIG["snapshots"]
BASE = CONFIG["download"]["base_url"].rstrip("/")
FILES = CONFIG["download"]["files"]
CHUNK_SIZE = CONFIG["download"]["stream_chunk_size"]
TIMEOUT = CONFIG["download"]["timeout_seconds"]


for snap in SNAPSHOTS:
    folder = RAW / snap
    folder.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        path = folder / name
        if path.exists():
            print("đã có, bỏ qua:", path.relative_to(ROOT))
            continue

        # Write to a temporary file and rename only after the download completes.
        tmp = path.with_name(name + ".part")
        try:
            with requests.get(
                f"{BASE}/{snap}/data/{name}",
                stream=True,
                timeout=TIMEOUT,
            ) as response:
                response.raise_for_status()
                with tmp.open("wb") as output_file:
                    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            output_file.write(chunk)
            tmp.replace(path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

        print(
            "đã tải:",
            path.relative_to(ROOT),
            f"({path.stat().st_size / 1e6:.1f} MB)",
        )