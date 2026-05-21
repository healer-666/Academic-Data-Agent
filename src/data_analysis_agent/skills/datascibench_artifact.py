from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from .base import SkillContext, SkillValidationContext, SkillValidationResult


ARTIFACT_EXTENSIONS = {
    ".csv",
    ".tsv",
    ".xlsx",
    ".xls",
    ".json",
    ".jsonl",
    ".txt",
    ".md",
    ".png",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".html",
    ".parquet",
    ".pkl",
}

CONTRACT_GROUPS = {"csv_excel", "human"}
ARTIFACT_LITERAL_RE = re.compile(
    r"""['"]([^'"]+\.(?:csv|tsv|xlsx|xls|json|jsonl|txt|md|png|jpg|jpeg|pdf|html|parquet|pkl))['"]""",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DataSciBenchMetricSpec:
    metric: str = ""
    function: str = ""
    task_name: str = ""
    ground_truth: str = ""
    code: str = ""
    output_files: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "function": self.function,
            "task_name": self.task_name,
            "ground_truth": self.ground_truth,
            "output_files": list(self.output_files),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DataSciBenchMetricSpec":
        return cls(
            metric=str(payload.get("metric", "") or ""),
            function=str(payload.get("function", "") or ""),
            task_name=str(payload.get("task_name", "") or ""),
            ground_truth=str(payload.get("ground_truth", "") or ""),
            code=str(payload.get("code", "") or ""),
            output_files=tuple(str(item) for item in payload.get("output_files", ()) if str(item).strip()),
        )


@dataclass(frozen=True)
class DataSciBenchArtifactContract:
    task_id: str
    task_group: str
    status: str
    metric_path: str = ""
    required_artifacts: tuple[str, ...] = ()
    metrics: tuple[DataSciBenchMetricSpec, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def available(self) -> bool:
        return self.status == "available" and bool(self.required_artifacts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_group": self.task_group,
            "status": self.status,
            "metric_path": self.metric_path,
            "required_artifacts": list(self.required_artifacts),
            "metrics": [metric.to_dict() for metric in self.metrics],
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "DataSciBenchArtifactContract | None":
        if not payload:
            return None
        return cls(
            task_id=str(payload.get("task_id", "") or ""),
            task_group=str(payload.get("task_group", "") or ""),
            status=str(payload.get("status", "") or ""),
            metric_path=str(payload.get("metric_path", "") or ""),
            required_artifacts=tuple(str(item) for item in payload.get("required_artifacts", ()) if str(item).strip()),
            metrics=tuple(
                DataSciBenchMetricSpec.from_dict(dict(item))
                for item in payload.get("metrics", ())
                if isinstance(item, dict)
            ),
            warnings=tuple(str(item) for item in payload.get("warnings", ()) if str(item).strip()),
        )

    def to_prompt_block(self) -> str:
        if not self.available:
            return ""
        metric_lines = []
        for metric in self.metrics:
            outputs = ", ".join(metric.output_files) if metric.output_files else "n/a"
            metric_lines.append(
                f"- {metric.metric or metric.function or 'metric'} | task={metric.task_name or 'unknown'} | output_files={outputs}"
            )
        required = "\n".join(f"- {name}" for name in self.required_artifacts)
        metrics_text = "\n".join(metric_lines)
        return (
            "<Skill: datascibench_artifact>\n"
            "Metric-aware artifact contract:\n"
            "The official DataSciBench scorer will look for exact artifact filenames. Treat these as mandatory outputs.\n"
            f"Required artifact filenames:\n{required}\n"
            f"Official metric checks:\n{metrics_text}\n"
            "Rules:\n"
            "- Create every required artifact with the exact filename shown above.\n"
            "- Save artifacts inside the current run directory whenever possible.\n"
            "- In the final report, list each required artifact with its absolute path and generation status.\n"
            "- Do not report a custom substitute score as if it were the official DataSciBench score.\n"
            "</Skill: datascibench_artifact>\n\n"
        )


def task_group_from_id(task_id: str) -> str:
    match = re.match(r"([A-Za-z_]+)", str(task_id))
    return match.group(1).rstrip("_") if match else "unknown"


def should_apply_contract(task_id: str, *, contract_mode: str = "auto") -> bool:
    mode = str(contract_mode or "auto").strip().lower()
    if mode == "off":
        return False
    return task_group_from_id(task_id) in CONTRACT_GROUPS


def _extract_artifact_literals(code: str) -> tuple[str, ...]:
    names: list[str] = []
    for match in ARTIFACT_LITERAL_RE.finditer(str(code or "")):
        name = Path(match.group(1).strip()).name
        if Path(name).suffix.lower() in ARTIFACT_EXTENSIONS and name not in names:
            names.append(name)
    return tuple(names)


def _normalise_yaml_item(item: Any) -> dict[str, Any]:
    return dict(item) if isinstance(item, dict) else {}


def load_artifact_contract(
    *,
    data_root: Path,
    task_id: str,
    contract_mode: str = "auto",
) -> DataSciBenchArtifactContract:
    task_group = task_group_from_id(task_id)
    if not should_apply_contract(task_id, contract_mode=contract_mode):
        return DataSciBenchArtifactContract(task_id=task_id, task_group=task_group, status="disabled")

    metric_path = data_root / "metric" / task_id / "metric.yaml"
    if not metric_path.exists():
        return DataSciBenchArtifactContract(
            task_id=task_id,
            task_group=task_group,
            status="contract_unavailable",
            metric_path=metric_path.as_posix(),
            warnings=(f"Missing metric.yaml for {task_id}",),
        )

    try:
        payload = yaml.safe_load(metric_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return DataSciBenchArtifactContract(
            task_id=task_id,
            task_group=task_group,
            status="contract_unavailable",
            metric_path=metric_path.as_posix(),
            warnings=(f"Unable to parse metric.yaml: {exc}",),
        )

    metric_items = payload.get("TMC-list") or payload.get("TMC_list") or []
    metrics: list[DataSciBenchMetricSpec] = []
    required: list[str] = []
    for raw_item in metric_items:
        item = _normalise_yaml_item(raw_item)
        code = str(item.get("code", "") or "")
        outputs = _extract_artifact_literals(code)
        ground_truth = str(item.get("ground_truth", "") or "").strip()
        if ground_truth:
            gt_name = Path(ground_truth).name
            if Path(gt_name).suffix.lower() in ARTIFACT_EXTENSIONS and gt_name not in outputs:
                outputs = (*outputs, gt_name)
        for output in outputs:
            if output not in required:
                required.append(output)
        metrics.append(
            DataSciBenchMetricSpec(
                metric=str(item.get("metric", "") or "").strip(),
                function=str(item.get("function", "") or "").strip(),
                task_name=str(item.get("task_name", "") or "").strip(),
                ground_truth=ground_truth,
                code=code,
                output_files=outputs,
            )
        )

    status = "available" if required else "contract_unavailable"
    warnings = () if required else ("No required artifact filenames could be extracted from metric.yaml.",)
    return DataSciBenchArtifactContract(
        task_id=task_id,
        task_group=task_group,
        status=status,
        metric_path=metric_path.as_posix(),
        required_artifacts=tuple(required),
        metrics=tuple(metrics),
        warnings=warnings,
    )


def _iter_report_paths(report_markdown: str) -> Iterable[str]:
    for match in re.finditer(r"([A-Za-z]:[/\\][^\s`'\"<>]+\.[A-Za-z0-9]+|[/\\][^\s`'\"<>]+\.[A-Za-z0-9]+)", str(report_markdown or "")):
        yield match.group(1).strip("`'\"),.;")


def _find_required_artifact(*, name: str, run_dir: Path | None, report_markdown: str) -> Path | None:
    if run_dir is not None and run_dir.exists():
        direct_matches = [
            run_dir / name,
            run_dir / "data" / name,
            run_dir / "figures" / name,
        ]
        for candidate in direct_matches:
            if candidate.exists() and candidate.is_file():
                return candidate
        for candidate in run_dir.rglob(name):
            if candidate.exists() and candidate.is_file():
                return candidate
    for candidate_text in _iter_report_paths(report_markdown):
        candidate = Path(candidate_text)
        if candidate.name == name and candidate.exists() and candidate.is_file():
            return candidate
    return None


def validate_artifact_contract(
    contract: DataSciBenchArtifactContract,
    *,
    run_dir: str | Path | None,
    report_markdown: str,
) -> dict[str, Any]:
    if not contract.available:
        return {
            "status": contract.status,
            "artifact_contract_passed": False,
            "required_artifact_count": 0,
            "found_artifact_count": 0,
            "required_artifacts": [],
            "found_artifacts": [],
            "missing_required_artifacts": [],
            "contract": contract.to_dict(),
        }

    active_run_dir = Path(run_dir) if run_dir else None
    found: list[dict[str, str]] = []
    missing: list[str] = []
    for name in contract.required_artifacts:
        artifact = _find_required_artifact(name=name, run_dir=active_run_dir, report_markdown=report_markdown)
        if artifact is None:
            missing.append(name)
        else:
            found.append({"name": name, "path": artifact.as_posix()})
    return {
        "status": "checked",
        "artifact_contract_passed": not missing,
        "required_artifact_count": len(contract.required_artifacts),
        "found_artifact_count": len(found),
        "required_artifacts": list(contract.required_artifacts),
        "found_artifacts": found,
        "missing_required_artifacts": missing,
        "contract": contract.to_dict(),
    }


def render_contract_summary(contract: DataSciBenchArtifactContract) -> str:
    return json.dumps(contract.to_dict(), ensure_ascii=False, indent=2)


class DataSciBenchArtifactSkill:
    name = "datascibench_artifact"

    def _contract_from_context(self, context: SkillContext) -> DataSciBenchArtifactContract | None:
        return DataSciBenchArtifactContract.from_dict(context.lineage_contract)

    def applies(self, context: SkillContext) -> bool:
        if str(context.task_type or "").strip().lower() == "datascibench":
            return True
        return self._contract_from_context(context) is not None

    def build_prompt_block(self, context: SkillContext) -> str:
        contract = self._contract_from_context(context)
        return contract.to_prompt_block() if contract is not None and contract.available else ""

    def post_run_validate(self, context: SkillValidationContext) -> SkillValidationResult:
        active_contract = DataSciBenchArtifactContract.from_dict(context.lineage_contract)
        if active_contract is None:
            return SkillValidationResult(name=self.name, status="contract_unavailable", passed=None)
        result = validate_artifact_contract(
            active_contract,
            run_dir=context.run_context.run_dir,
            report_markdown=context.report_markdown,
        )
        found = tuple(str(item.get("path", "")) for item in result.get("found_artifacts", ()) if isinstance(item, dict))
        return SkillValidationResult(
            name=self.name,
            status=str(result.get("status", "checked")),
            passed=bool(result.get("artifact_contract_passed", False)),
            missing_artifacts=tuple(str(item) for item in result.get("missing_required_artifacts", ()) if str(item).strip()),
            generated_outputs=found,
            details=result,
        )

    def to_trace_dict(self) -> dict[str, Any]:
        return {"name": self.name}
