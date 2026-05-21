from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import SkillContext, SkillValidationContext, SkillValidationResult


CLEAN_ABLATION_PROFILES = ("full", "prompt_only", "none")
CLEAN_ABLATION_SEED = 20260519
CLEAN_ABLATION_TASK_COUNTS = {"csv_excel": 20, "human": 25, "bcb": 10, "dl": 5}
CLEAN_ABLATION_TASK_TIMEOUT_SECONDS = 900


@dataclass(frozen=True)
class BenchmarkRunDefaults:
    profiles: tuple[str, ...] = CLEAN_ABLATION_PROFILES
    seed: int = CLEAN_ABLATION_SEED
    task_counts: dict[str, int] | None = None
    block_pip_install: bool = True
    run_official_eval: bool = True
    task_timeout_seconds: int = CLEAN_ABLATION_TASK_TIMEOUT_SECONDS

    def to_dict(self) -> dict[str, Any]:
        return {
            "profiles": list(self.profiles),
            "seed": self.seed,
            "task_counts": dict(self.task_counts or CLEAN_ABLATION_TASK_COUNTS),
            "block_pip_install": self.block_pip_install,
            "run_official_eval": self.run_official_eval,
            "task_timeout_seconds": self.task_timeout_seconds,
        }


def append_progress(path: Path, message: str) -> None:
    from datetime import datetime

    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


class BenchmarkRunSkill:
    name = "benchmark_run"

    def applies(self, context: SkillContext) -> bool:
        return str(context.task_type or "").strip().lower() in {"datascibench", "dabench", "benchmark"}

    def build_prompt_block(self, context: SkillContext) -> str:
        return ""

    def post_run_validate(self, context: SkillValidationContext) -> SkillValidationResult:
        return SkillValidationResult(
            name=self.name,
            status="recorded",
            passed=None,
            details={"task_type": "benchmark", "defaults": BenchmarkRunDefaults().to_dict()},
        )

    def to_trace_dict(self) -> dict[str, Any]:
        return {"name": self.name, "defaults": BenchmarkRunDefaults().to_dict()}
