from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.skills.benchmark_run import (  # noqa: E402
    CLEAN_ABLATION_PROFILES,
    CLEAN_ABLATION_SEED,
    CLEAN_ABLATION_TASK_TIMEOUT_SECONDS,
    append_progress,
)
from prepare_datascibench_official_eval import OfficialEvalConfig, prepare_and_optionally_score  # noqa: E402
from run_datascibench import (  # noqa: E402
    DataSciBenchRunConfig,
    DataSciBenchTask,
    load_datascibench_tasks,
    run_datascibench_sample,
)


PROFILES = CLEAN_ABLATION_PROFILES


def _resolve_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else PROJECT_ROOT / value


def _group_tasks(tasks: tuple[DataSciBenchTask, ...], group: str) -> list[DataSciBenchTask]:
    return [task for task in tasks if task.task_group == group]


def select_weak_plus_controls(
    tasks: tuple[DataSciBenchTask, ...],
    *,
    seed: int,
    smoke: bool = False,
) -> tuple[DataSciBenchTask, ...]:
    rng = random.Random(seed)
    csv_excel = sorted(_group_tasks(tasks, "csv_excel"), key=lambda task: task.task_id)
    human = sorted(_group_tasks(tasks, "human"), key=lambda task: task.task_id)
    bcb = sorted(_group_tasks(tasks, "bcb"), key=lambda task: task.task_id)
    dl = sorted(_group_tasks(tasks, "dl"), key=lambda task: task.task_id)
    if smoke:
        selected = [
            *csv_excel[:3],
            *human[:3],
            *rng.sample(bcb, min(3, len(bcb))),
            *dl[:3],
        ]
    else:
        selected = [
            *csv_excel,
            *human,
            *rng.sample(bcb, min(10, len(bcb))),
            *rng.sample(dl, min(5, len(dl))),
        ]
    return tuple(sorted({task.task_id: task for task in selected}.values(), key=lambda task: task.task_id))


def _append_progress(path: Path, message: str) -> None:
    append_progress(path, message)


def _latest_profile_report_dir(report_dir: Path, profile: str) -> Path | None:
    profile_root = report_dir / "runs" / profile
    if not profile_root.exists():
        return None
    candidates = [
        path
        for path in profile_root.iterdir()
        if path.is_dir() and (path / "responses.jsonl").exists()
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _cr_by_task(official_summary: dict[str, Any]) -> dict[str, float]:
    values: dict[str, float] = {}
    for record in official_summary.get("results", []):
        if record.get("official_score_status") == "scored":
            values[str(record.get("id"))] = float(record.get("official_cr", 0.0) or 0.0)
    return values


def _task_group(task_id: str) -> str:
    if task_id.startswith("csv_excel_"):
        return "csv_excel"
    if task_id.startswith("human_"):
        return "human"
    if task_id.startswith("bcb"):
        return "bcb"
    if task_id.startswith("dl_"):
        return "dl"
    return "unknown"


def _artifact_contract_applicable(record: dict[str, Any]) -> bool:
    return int(record.get("required_artifact_count", 0) or 0) > 0


def _classify_failure(record: dict[str, Any], official_cr: float | None) -> str:
    status = str(record.get("status", ""))
    error = str(record.get("error", "") or "").lower()
    if status == "failed":
        if "exceeded timeout" in error or "timeouterror" in error:
            return "task_timeout"
        if "pip_install_forbidden" in error or "forbids task-level package installation" in error:
            return "blocked_pip_install"
        if "modulenotfounderror" in error or "importerror" in error or "no module named" in error:
            return "dependency_error"
        return "run_error"
    if status == "completed" and not bool(record.get("format_compliant", False)):
        return "format_failure"
    if _artifact_contract_applicable(record) and not bool(record.get("artifact_contract_passed", False)):
        return "artifact_missing"
    if official_cr is not None and official_cr <= 0:
        return "calculation_error"
    return "ok"


def build_failure_analysis(profile_runs: dict[str, dict[str, Any]], official_summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    analysis: dict[str, Any] = {}
    for profile, run_info in profile_runs.items():
        runner_summary = _load_json(run_info["summary_path"])
        cr_map = _cr_by_task(official_summaries.get(profile, {}))
        by_group: dict[str, dict[str, int]] = {}
        by_reason: dict[str, int] = {}
        task_rows: list[dict[str, Any]] = []
        for record in runner_summary.get("results", []):
            task_id = str(record.get("id") or "")
            group = str(record.get("task_group") or _task_group(task_id))
            reason = _classify_failure(record, cr_map.get(task_id))
            by_group.setdefault(group, {})
            by_group[group][reason] = by_group[group].get(reason, 0) + 1
            by_reason[reason] = by_reason.get(reason, 0) + 1
            if reason != "ok":
                task_rows.append(
                    {
                        "id": task_id,
                        "group": group,
                        "reason": reason,
                        "status": record.get("status"),
                        "official_cr": cr_map.get(task_id),
                        "missing_required_artifacts": record.get("missing_required_artifacts", []),
                        "error_path": record.get("error_path", ""),
                        "raw_report_path": record.get("raw_report_path", ""),
                    }
                )
        analysis[profile] = {
            "by_group": by_group,
            "by_reason": by_reason,
            "tasks": task_rows,
        }
    return analysis


def _bootstrap_ci(values: list[float], *, seed: int, rounds: int = 2000) -> tuple[float, float] | None:
    if not values:
        return None
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(rounds):
        draw = [values[rng.randrange(len(values))] for _ in values]
        samples.append(mean(draw))
    samples.sort()
    lower = samples[int(0.025 * (len(samples) - 1))]
    upper = samples[int(0.975 * (len(samples) - 1))]
    return round(lower, 4), round(upper, 4)


def build_ablation_summary(
    *,
    profile_runs: dict[str, dict[str, Any]],
    official_summaries: dict[str, dict[str, Any]],
    task_ids: list[str],
    seed: int,
    smoke: bool,
    report_dir: Path,
) -> dict[str, Any]:
    profile_metrics: dict[str, Any] = {}
    cr_maps = {profile: _cr_by_task(summary) for profile, summary in official_summaries.items()}
    for profile, run_info in profile_runs.items():
        runner_summary = _load_json(run_info["summary_path"])
        official = official_summaries.get(profile, {})
        cr_values = list(cr_maps.get(profile, {}).values())
        profile_metrics[profile] = {
            "task_count": len(task_ids),
            "runner_completed_rate": runner_summary.get("completed_rate", 0.0),
            "run_error_count": runner_summary.get("run_error_count", 0),
            "format_failure_count": runner_summary.get("format_failure_count", 0),
            "artifact_contract_pass_rate": runner_summary.get("artifact_contract_pass_rate", 0.0),
            "official_scored_count": official.get("scored_count", 0),
            "official_unsupported_count": official.get("unsupported_count", 0),
            "official_evaluator_failed_count": official.get("evaluator_failed_count", 0),
            "mean_official_cr": round(mean(cr_values), 4) if cr_values else 0.0,
            "mean_official_cr_bootstrap_95ci": _bootstrap_ci(cr_values, seed=seed + len(profile)),
            "runner_summary_path": run_info["summary_path"],
            "official_summary_path": official.get("summary_path", ""),
        }

    paired: dict[str, Any] = {}
    full_map = cr_maps.get("full", {})
    for baseline in ("prompt_only", "none"):
        baseline_map = cr_maps.get(baseline, {})
        common = sorted(set(full_map) & set(baseline_map))
        diffs = [full_map[task_id] - baseline_map[task_id] for task_id in common]
        paired[f"full_minus_{baseline}"] = {
            "paired_task_count": len(common),
            "mean_delta_cr": round(mean(diffs), 4) if diffs else 0.0,
            "delta_bootstrap_95ci": _bootstrap_ci(diffs, seed=seed + len(baseline)),
            "interpretation": "exploratory_paired_comparison",
        }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "benchmark": "DataSciBench",
        "scope": "smoke" if smoke else "weak_plus_controls",
        "note": "local reproduction, not leaderboard",
        "profiles": list(PROFILES),
        "seed": seed,
        "task_ids": task_ids,
        "profile_metrics": profile_metrics,
        "paired_comparisons": paired,
        "failure_analysis": build_failure_analysis(profile_runs, official_summaries),
        "report_dir": report_dir.as_posix(),
    }


def render_ablation_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# DataSciBench Symbolic Ablation",
        "",
        "**Scope:** local reproduction, not leaderboard.",
        "",
        "| Profile | Mean CR | 95% CI | Scored | Contract pass | Run errors |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for profile in summary["profiles"]:
        item = summary["profile_metrics"].get(profile, {})
        ci = item.get("mean_official_cr_bootstrap_95ci")
        ci_text = f"{ci[0]:.4f}-{ci[1]:.4f}" if ci else "n/a"
        lines.append(
            "| {profile} | {cr:.4f} | {ci} | {scored} | {contract:.4f} | {errors} |".format(
                profile=profile,
                cr=float(item.get("mean_official_cr", 0.0) or 0.0),
                ci=ci_text,
                scored=item.get("official_scored_count", 0),
                contract=float(item.get("artifact_contract_pass_rate", 0.0) or 0.0),
                errors=item.get("run_error_count", 0),
            )
        )
    lines.extend(["", "## Paired Comparisons", "", "| Comparison | Tasks | Mean delta CR | 95% CI |", "| --- | ---: | ---: | --- |"])
    for name, item in summary["paired_comparisons"].items():
        ci = item.get("delta_bootstrap_95ci")
        ci_text = f"{ci[0]:.4f}-{ci[1]:.4f}" if ci else "n/a"
        lines.append(
            f"| {name} | {item.get('paired_task_count', 0)} | {float(item.get('mean_delta_cr', 0.0) or 0.0):.4f} | {ci_text} |"
        )
    lines.extend(["", "## Failure Analysis", ""])
    for profile in summary["profiles"]:
        lines.extend([f"### {profile}", "", "| Group | ok | calculation_error | artifact_missing | format_failure | task_timeout | dependency_error | blocked_pip_install | run_error |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
        groups = summary.get("failure_analysis", {}).get(profile, {}).get("by_group", {})
        for group, counts in sorted(groups.items()):
            lines.append(
                "| {group} | {ok} | {calc} | {artifact} | {format_failure} | {timeout} | {dependency} | {blocked} | {run_error} |".format(
                    group=group,
                    ok=counts.get("ok", 0),
                    calc=counts.get("calculation_error", 0),
                    artifact=counts.get("artifact_missing", 0),
                    format_failure=counts.get("format_failure", 0),
                    timeout=counts.get("task_timeout", 0),
                    dependency=counts.get("dependency_error", 0),
                    blocked=counts.get("blocked_pip_install", 0),
                    run_error=counts.get("run_error", 0),
                )
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run DataSciBench full/prompt_only/none ablations.")
    parser.add_argument("--data-root", default="data/external/datascibench_official")
    parser.add_argument("--hf-root", default="data/external/datascibench_hf")
    parser.add_argument("--official-root", default="data/external/datascibench_official")
    parser.add_argument("--reports-dir", default="eval/reports/datascibench_ablation")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--seed", type=int, default=CLEAN_ABLATION_SEED)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--run-official-eval", action="store_true")
    parser.add_argument("--max-steps", type=int, default=16)
    parser.add_argument("--task-timeout-seconds", type=int, default=CLEAN_ABLATION_TASK_TIMEOUT_SECONDS)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--block-pip-install", action="store_true", default=True)
    parser.add_argument("--resume-report-dir", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    data_root = _resolve_path(args.data_root).resolve()
    tasks = load_datascibench_tasks(data_root, allow_download=False)
    selected = select_weak_plus_controls(tasks, seed=args.seed, smoke=bool(args.smoke))
    task_ids = [task.task_id for task in selected]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = (
        _resolve_path(args.resume_report_dir)
        if args.resume_report_dir
        else (_resolve_path(args.reports_dir) / timestamp)
    ).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    progress_log = report_dir / "progress.log"
    profile_runs: dict[str, dict[str, Any]] = {}
    official_summaries: dict[str, dict[str, Any]] = {}

    (report_dir / "task_ids.json").write_text(json.dumps(task_ids, ensure_ascii=False, indent=2), encoding="utf-8")
    for profile in PROFILES:
        _append_progress(progress_log, f"profile_started profile={profile} task_count={len(task_ids)}")
        run_config = DataSciBenchRunConfig(
            data_root=data_root,
            reports_dir=report_dir / "runs" / profile,
            output_root=_resolve_path(args.output_root).resolve(),
            env_file=_resolve_path(args.env_file).resolve() if args.env_file else None,
            sample_size=0,
            seed=args.seed,
            task_ids=tuple(task_ids),
            allow_download=False,
            data_source_type="all",
            task_group="all",
            max_steps=args.max_steps,
            quality_mode="draft",
            latency_mode="quality",
            symbolic_profile=profile,
            vision_review_mode="off",
            task_retries=0,
            task_timeout_seconds=max(0, args.task_timeout_seconds),
            contract_mode="auto",
            block_pip_install=bool(args.block_pip_install),
            resume_report_dir=_latest_profile_report_dir(report_dir, profile) if args.resume_report_dir else None,
        )
        run_result = run_datascibench_sample(run_config)
        profile_runs[profile] = run_result
        official_config = OfficialEvalConfig(
            summary_path=Path(run_result["summary_path"]),
            official_root=_resolve_path(args.official_root).resolve(),
            reports_dir=report_dir / "official" / profile,
            hf_root=_resolve_path(args.hf_root).resolve() if args.hf_root else None,
            model_id=f"academic-data-agent-{profile}",
            run_id=timestamp,
            run_official_eval=bool(args.run_official_eval),
            python_executable=args.python_executable,
            timeout_seconds=args.timeout_seconds,
        )
        official_summary = prepare_and_optionally_score(official_config)
        official_summaries[profile] = official_summary
        _append_progress(progress_log, f"profile_finished profile={profile} summary={run_result['summary_path']}")

    summary = build_ablation_summary(
        profile_runs=profile_runs,
        official_summaries=official_summaries,
        task_ids=task_ids,
        seed=args.seed,
        smoke=bool(args.smoke),
        report_dir=report_dir,
    )
    summary["config"] = vars(args)
    summary["official_summaries"] = official_summaries
    summary_path = report_dir / "ablation_summary.json"
    markdown_path = report_dir / "ablation_summary.md"
    official_summary_path = report_dir / "official_eval_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_ablation_markdown(summary), encoding="utf-8")
    official_summary_path.write_text(json.dumps(official_summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    _append_progress(progress_log, f"ablation_finished summary={summary_path.as_posix()}")
    print(f"DataSciBench ablation report directory: {report_dir}")
    print(f"DataSciBench ablation summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
