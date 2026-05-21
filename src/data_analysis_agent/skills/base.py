from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class SkillContext:
    """Static context available before the analyst prompt is built."""

    task_type: str = ""
    task_expectations: tuple[str, ...] = ()
    skill_profile: str = "auto"
    enabled_skills: tuple[str, ...] | None = None
    run_context: Any | None = None
    data_context: Any | None = None
    lineage_contract: dict[str, Any] | None = None


@dataclass(frozen=True)
class SkillValidationContext:
    """Post-run context used by skills to emit auditable validation facts."""

    run_context: Any
    report_markdown: str
    step_traces: tuple[Any, ...] = ()
    telemetry: Any | None = None
    artifact_validation: Any | None = None
    lineage_payload: dict[str, Any] | None = None
    lineage_contract: dict[str, Any] | None = None


@dataclass(frozen=True)
class SkillValidationResult:
    name: str
    status: str
    passed: bool | None = None
    warnings: tuple[str, ...] = ()
    missing_artifacts: tuple[str, ...] = ()
    generated_outputs: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def to_trace_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "passed": self.passed,
            "warnings": list(self.warnings),
            "missing_artifacts": list(self.missing_artifacts),
            "generated_outputs": list(self.generated_outputs),
            "details": self.details,
        }


class AnalysisSkill:
    name: str

    def applies(self, context: SkillContext) -> bool:
        raise NotImplementedError

    def build_prompt_block(self, context: SkillContext) -> str:
        raise NotImplementedError

    def post_run_validate(self, context: SkillValidationContext) -> SkillValidationResult:
        raise NotImplementedError

    def to_trace_dict(self) -> dict[str, Any]:
        raise NotImplementedError


def normalize_skill_names(values: Iterable[str] | None) -> tuple[str, ...] | None:
    if values is None:
        return None
    if isinstance(values, str):
        return (values.strip(),) if values.strip() else ()
    names = tuple(str(item).strip() for item in values if str(item).strip())
    return names


def path_to_str(path: Path | str | None) -> str:
    if path is None:
        return ""
    return path.as_posix() if hasattr(path, "as_posix") else str(path)
