"""Chuẩn bị môi trường, tải dữ liệu Porto và chạy phân tích bằng một lệnh."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/porto.yaml")
    args = parser.parse_args()
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}
    python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        subprocess.run([sys.executable, "-m", "venv", ROOT / ".venv"], check=True, env=env)

    for command in (
        ["-m", "pip", "install", "--disable-pip-version-check", "-r", "requirements.txt"],
        ["src/download.py", "--config", args.config],
        ["run_pipeline.py", "--config", args.config, "--with-filter", "--skip-llm"],
    ):
        subprocess.run([python, *command], cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
