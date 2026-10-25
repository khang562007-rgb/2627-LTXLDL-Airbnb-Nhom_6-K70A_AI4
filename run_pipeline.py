"""Run each pipeline stage in order from the repository root."""
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
STAGES = (
    "src/filter_all.py",
    "src/qa.py",
    "src/flag_property_cross.py",
)


def main():
    for stage in STAGES:
        print(f"\n=== Running {stage} ===", flush=True)
        subprocess.run([sys.executable, str(ROOT / stage)], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
