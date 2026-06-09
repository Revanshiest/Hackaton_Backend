"""Собрать demoSnapshot.json для фронтенда из report.json.

Примеры:
  python scripts/build_demo_snapshot.py
  python scripts/build_demo_snapshot.py --job 04e00ce4
  python scripts/build_demo_snapshot.py --report cache/jobs/04e00ce4/output/report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.demo_snapshot import build_demo_snapshot, find_fullest_report, find_latest_report  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Собрать demoSnapshot.json для demo-режима фронтенда")
    parser.add_argument("--latest", action="store_true", help="Последний по времени report (по умолчанию — с max МО)")
    parser.add_argument("--job", help="ID задачи (cache/jobs/<job>/output/report.json)")
    parser.add_argument("--report", type=Path, help="Путь к report.json")
    args = parser.parse_args()

    if args.job and args.report:
        raise SystemExit("Укажите либо --job, либо --report, не оба")

    report_path = args.report
    if report_path is None and args.job is None:
        if args.latest:
            report_path = find_latest_report()
            print(f"Последний report: {report_path}")
        else:
            report_path = find_fullest_report()
            print(f"Самый полный report: {report_path}")

    out = build_demo_snapshot(job_id=args.job, report_path=args.report)
    meta = json.loads(out.read_text(encoding="utf-8"))["meta"]
    print(
        f"Wrote {out} ({out.stat().st_size // 1024} KB) "
        f"from job {meta['source_job']} · {meta['municipalities']} МО"
    )


if __name__ == "__main__":
    main()
