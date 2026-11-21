"""Orchestrator chạy toàn bộ pipeline xử lý dữ liệu Airbnb Porto.

Ví dụ:
    python run_pipeline.py                          # chạy qa -> kpi -> reviews -> viz
    python run_pipeline.py --with-filter            # chạy thêm filter_all + check_counts
    python run_pipeline.py --steps kpi viz          # chỉ chạy lại KPI và vẽ biểu đồ
    python run_pipeline.py --skip-llm               # bỏ qua bước gọi LLM K07
    python run_pipeline.py --dry-run                # chỉ in lệnh, không thực thi
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent


def run_step(label, cmd, dry_run=False):
    cmd_str = " ".join(str(c) for c in cmd)
    print(f"\n[STEP] {label}\n  $ {cmd_str}")
    if dry_run:
        return
    t0 = time.perf_counter()
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else str(ROOT)
    subprocess.run([str(c) for c in cmd], cwd=ROOT, env=env, check=True)
    print(f"[DONE] {label} ({time.perf_counter() - t0:.2f}s)")


def main():
    ap = argparse.ArgumentParser(description="Chạy pipeline dữ liệu Airbnb Porto (QA -> KPI -> Reviews/LLM -> Viz)")
    ap.add_argument("--config", default="configs/porto.yaml", help="Đường dẫn file cấu hình YAML")
    ap.add_argument(
        "--steps",
        nargs="+",
        default=["qa", "kpi", "reviews", "viz"],
        choices=["prep", "qa", "kpi", "reviews", "viz"],
        help="Các giai đoạn cần chạy theo thứ tự",
    )
    ap.add_argument("--with-filter", action="store_true", help="Chạy thêm bước lọc dữ liệu thô (prep) trước qa")
    ap.add_argument("--skip-llm", action="store_true", help="Bỏ qua bước gắn nhãn LLM / K07")
    ap.add_argument("--dry-run", action="store_true", help="Chỉ in ra các lệnh sẽ chạy mà không thực thi")
    args = ap.parse_args()

    cfg_path = ROOT / args.config
    cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))
    proc_dir = cfg["paths"]["processed"]
    labels_path = cfg["kpi"]["k7"]["llm"]["labels_path"]
    py = sys.executable

    steps = list(args.steps)
    if args.with_filter and "prep" not in steps:
        steps.insert(0, "prep")

    t_start = time.perf_counter()

    if "prep" in steps:
        run_step("Filter raw data to interim", [py, "src/filter_all.py", "--config", args.config], args.dry_run)
        run_step("Check filtered row counts", [py, "src/check_counts.py", "--config", args.config], args.dry_run)

    if "qa" in steps:
        for label, script in [
            ("QA host & locations", "src/flag_host_locations.py"),
            ("QA price & calendar", "src/flag_price_calendar.py"),
            ("QA property cross-checks", "src/flag_property_cross.py"),
            ("QA reviews", "src/flag_reviews.py"),
        ]:
            run_step(label, [py, script, "--config", args.config], args.dry_run)
        run_step("Audit QA flags", [py, "run_audits.py", "--config", args.config], args.dry_run)

    if "kpi" in steps:
        for label, script in [
            ("K01 area listing share", "src/kpi_k1_area_share.py"),
            ("K02 multi-host listing share", "src/kpi_k2_multi_host_share.py"),
            ("K03 entire home share", "src/kpi_k3_entire_home_share.py"),
            ("K04 supply change", "src/kpi_k4_supply_change.py"),
            ("K05 revenue & tourist tax", "src/kpi_k5_revenue_tax.py"),
            ("K06 commercial share", "src/kpi_k6_commercial_share.py"),
        ]:
            run_step(label, [py, script, "--config", args.config], args.dry_run)

    if "reviews" in steps:
        valid_csv = f"{proc_dir}/reviews_valid.csv"
        k07_csv = f"{proc_dir}/kpi_k07_community_complaint.csv"
        run_step("K08 data reliability (pass 1)", [py, "src/kpi_k8_data_reliability.py", args.config, proc_dir], args.dry_run)
        run_step(
            "Baseline NLP (language & sentiment)",
            [py, "src/baseline.py", "--config", args.config, "--input", valid_csv, "--output", f"{proc_dir}/baseline_reviews.csv"],
            args.dry_run,
        )
        if not args.skip_llm:
            run_step("K07 community complaint (LLM)", [py, "src/kpi_k7_community_complaint.py", args.config, valid_csv, proc_dir], args.dry_run)
            run_step(
                "K08 data reliability (pass 2)",
                [py, "src/kpi_k8_data_reliability.py", args.config, proc_dir, labels_path, k07_csv],
                args.dry_run,
            )
        else:
            print("\n[SKIP] Bỏ qua K07 LLM và K08 pass 2 theo cờ --skip-llm.")
        run_step("Evaluate Baseline & LLM", [py, "src/evaluate.py", "--config", args.config], args.dry_run)

    if any(s in steps for s in ("qa", "kpi", "reviews")):
        run_step("Build consolidated QA report", [py, "src/qa_report.py", "--config", args.config], args.dry_run)

    if "viz" in steps:
        run_step("Generate figures", [py, "src/viz.py", "--config", args.config, "--out", "figures"], args.dry_run)

    print(f"\n[PIPELINE COMPLETE] Tổng thời gian: {time.perf_counter() - t_start:.2f}s")


if __name__ == "__main__":
    main()
