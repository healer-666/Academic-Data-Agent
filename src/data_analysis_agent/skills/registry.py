from __future__ import annotations

from typing import Any

from .base import AnalysisSkill, SkillContext, normalize_skill_names
from .benchmark_run import BenchmarkRunSkill
from .datascibench_artifact import DataSciBenchArtifactSkill
from .lineage_audit import LineageAuditSkill
from .statistical_analysis import StatisticalAnalysisSkill


SKILL_FACTORIES = {
    "statistical_analysis": StatisticalAnalysisSkill,
    "lineage_audit": LineageAuditSkill,
    "datascibench_artifact": DataSciBenchArtifactSkill,
    "benchmark_run": BenchmarkRunSkill,
}


def _default_skill_names(context: SkillContext) -> tuple[str, ...]:
    task_type = str(context.task_type or "").strip().lower()
    names = ["statistical_analysis", "lineage_audit"]
    if task_type == "datascibench" or context.lineage_contract:
        names.append("datascibench_artifact")
    if task_type in {"datascibench", "dabench", "benchmark"}:
        names.append("benchmark_run")
    return tuple(names)


def resolve_analysis_skills(context: SkillContext) -> tuple[AnalysisSkill, ...]:
    profile = str(context.skill_profile or "auto").strip().lower()
    explicit_names = normalize_skill_names(context.enabled_skills)
    if explicit_names is not None:
        names = explicit_names
    elif profile in {"off", "none"}:
        names = ()
    else:
        names = _default_skill_names(context)

    skills: list[AnalysisSkill] = []
    for name in names:
        factory = SKILL_FACTORIES.get(name)
        if factory is None:
            continue
        skill = factory()
        if skill.applies(context):
            skills.append(skill)
    return tuple(skills)


def build_skills_trace(
    *,
    skills: tuple[AnalysisSkill, ...],
    prompt_blocks: dict[str, str],
    validation_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "enabled": [skill.name for skill in skills],
        "prompt_blocks": {
            name: {"injected": bool(block), "char_count": len(block)}
            for name, block in prompt_blocks.items()
        },
        "validations": dict(validation_results or {}),
    }
