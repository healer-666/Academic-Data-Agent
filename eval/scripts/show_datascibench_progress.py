from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
START_RE = re.compile(r"\[(?P<idx>\d+)/(?P<total>\d+)\] DataSciBench task (?P<task>\S+)")


def _resolve_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else PROJECT_ROOT / value


def _latest_run(reports_dir: Path) -> Path:
    candidates = [item for item in reports_dir.iterdir() if item.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"No report run directories found under {reports_dir}")
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _parse_time(line: str) -> datetime | None:
    if not line.startswith("["):
        return None
    token = line.split("]", 1)[0].strip("[")
    try:
        return datetime.fromisoformat(token)
    except ValueError:
        return None


def _progress_from_log(progress_log: Path) -> dict[str, Any]:
    if not progress_log.exists():
        return {}
    lines = [line.strip() for line in progress_log.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    started_at = _parse_time(lines[0]) if lines else None
    last_at = _parse_time(lines[-1]) if lines else None
    current_task = ""
    current_index = 0
    total = 0
    completed_events = 0
    failed_events = 0
    finished = any("run_finished" in line for line in lines)
    for line in lines:
        if "] done | status=completed" in line:
            completed_events += 1
        if "] done | status=failed" in line:
            failed_events += 1
        match = START_RE.search(line)
        if match:
            current_index = int(match.group("idx"))
            total = int(match.group("total"))
            current_task = match.group("task")
    return {
        "started_at": started_at,
        "last_at": last_at,
        "current_task": current_task,
        "current_index": current_index,
        "total": total,
        "completed_events": completed_events,
        "failed_events": failed_events,
        "finished": finished,
    }


def render_progress(run_dir: Path) -> str:
    summary = _load_json(run_dir / "eval_datascibench_summary.json")
    log_info = _progress_from_log(run_dir / "progress.log")
    total = int(summary.get("requested_sample_size") or log_info.get("total") or summary.get("sample_size") or 0)
    recorded = int(summary.get("sample_size") or log_info.get("completed_events", 0) + log_info.get("failed_events", 0))
    failed = int(summary.get("run_error_count") or log_info.get("failed_events") or 0)
    completed = max(0, recorded - failed)
    pct = (recorded / total * 100) if total else 0.0
    avg_duration = float(summary.get("avg_duration_seconds") or 0.0)
    remaining = max(0, total - recorded)
    eta_seconds = remaining * avg_duration if avg_duration > 0 else 0.0
    current_task = log_info.get("current_task") or ""
    state = "finished" if log_info.get("finished") else "running"
    lines = [
        f"run_dir: {run_dir}",
        f"state: {state}",
        f"progress: {recorded}/{total} ({pct:.1f}%)",
        f"completed: {completed}",
        f"failed: {failed}",
        f"current_task: {current_task}",
        f"avg_duration_seconds: {avg_duration:.1f}",
        f"eta_minutes: {eta_seconds / 60:.1f}" if eta_seconds else "eta_minutes: n/a",
    ]
    if log_info.get("started_at"):
        lines.append(f"started_at: {log_info['started_at'].isoformat(timespec='seconds')}")
    if log_info.get("last_at"):
        lines.append(f"last_update: {log_info['last_at'].isoformat(timespec='seconds')}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Show progress for a DataSciBench evaluation run.")
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--reports-dir", default="eval/reports/datascibench_clean_one_shot_final")
    args = parser.parse_args()
    run_dir = _resolve_path(args.run_dir) if args.run_dir else _latest_run(_resolve_path(args.reports_dir))
    print(render_progress(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
