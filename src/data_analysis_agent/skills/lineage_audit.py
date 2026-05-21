from __future__ import annotations

from typing import Any

from .base import SkillContext, SkillValidationContext, SkillValidationResult


class LineageAuditSkill:
    name = "lineage_audit"

    def applies(self, context: SkillContext) -> bool:
        return str(context.skill_profile or "auto").strip().lower() != "off"

    def build_prompt_block(self, context: SkillContext) -> str:
        return ""

    def post_run_validate(self, context: SkillValidationContext) -> SkillValidationResult:
        payload = dict(context.lineage_payload or {})
        status = str(payload.get("status", "not_generated"))
        passed = status == "generated"
        warnings: list[str] = []
        if not passed:
            warnings.append(str(payload.get("error") or "Lineage artifacts were not generated."))
        return SkillValidationResult(
            name=self.name,
            status=status,
            passed=passed,
            warnings=tuple(warnings),
            details={
                "json_path": payload.get("json_path", ""),
                "mermaid_path": payload.get("mermaid_path", ""),
                "node_count": int(payload.get("node_count", 0) or 0),
                "edge_count": int(payload.get("edge_count", 0) or 0),
                "missing_artifact_count": int(payload.get("missing_artifact_count", 0) or 0),
            },
        )

    def to_trace_dict(self) -> dict[str, Any]:
        return {"name": self.name}
