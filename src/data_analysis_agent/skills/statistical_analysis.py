from __future__ import annotations

import re
from typing import Any

from .base import SkillContext, SkillValidationContext, SkillValidationResult


STATISTICAL_PROMPT_BLOCK = """<Skill: statistical_analysis>
Use this statistical-analysis skill when the task asks for tabular data analysis.
- Save a cleaned dataset, then reload the cleaned dataset before formal analysis.
- Prefer descriptive statistics before modeling or inference.
- For group comparison, correlation, regression, or classification, compute results with Python rather than guessing.
- If a hypothesis test is used, report the test statistic, p-value, effect size, and 95% CI together.
- If pairwise comparisons across more than two groups are used, apply and name a multiple-comparison correction.
- Do not invent numeric findings. Every statistical claim must be grounded in successful tool observations.
</Skill: statistical_analysis>
"""


class StatisticalAnalysisSkill:
    name = "statistical_analysis"

    def applies(self, context: SkillContext) -> bool:
        return str(context.skill_profile or "auto").strip().lower() != "off"

    def build_prompt_block(self, context: SkillContext) -> str:
        return STATISTICAL_PROMPT_BLOCK

    def post_run_validate(self, context: SkillValidationContext) -> SkillValidationResult:
        successful_python_steps = [
            trace
            for trace in context.step_traces
            if getattr(trace, "tool_name", "") == "PythonInterpreterTool"
            and str(getattr(trace, "tool_status", "")).lower() != "error"
        ]
        cleaned_path = getattr(context.run_context, "cleaned_data_path", None)
        cleaned_name = "cleaned_data.csv"
        if cleaned_path is not None:
            cleaned_name = getattr(cleaned_path, "name", cleaned_name)
        combined_trace_text = "\n".join(
            str(getattr(trace, "tool_input", "") or "") + "\n" + str(getattr(trace, "observation", "") or "")
            for trace in context.step_traces
        )
        report_text = str(context.report_markdown or "")
        has_cleaned_reload_evidence = bool(successful_python_steps) and cleaned_name in combined_trace_text
        has_statistical_result = bool(
            re.search(
                r"\b(p[- ]?value|confidence interval|95% CI|effect size|correlation|regression|accuracy|mean|median|std)\b",
                report_text + "\n" + combined_trace_text,
                flags=re.IGNORECASE,
            )
        )
        empty_report_risk = len(report_text.strip()) < 200 or not successful_python_steps
        warnings: list[str] = []
        if not successful_python_steps:
            warnings.append("No successful PythonInterpreterTool analysis step was detected.")
        if not has_cleaned_reload_evidence:
            warnings.append("No clear cleaned-data reload evidence was detected in the trace.")
        if not has_statistical_result:
            warnings.append("No obvious statistical result keyword was detected in report or trace.")
        if empty_report_risk:
            warnings.append("Report may be empty or insufficiently grounded in tool observations.")
        return SkillValidationResult(
            name=self.name,
            status="checked",
            passed=not warnings,
            warnings=tuple(warnings),
            details={
                "successful_python_step_count": len(successful_python_steps),
                "has_cleaned_reload_evidence": has_cleaned_reload_evidence,
                "has_statistical_result": has_statistical_result,
                "empty_report_risk": empty_report_risk,
            },
        )

    def to_trace_dict(self) -> dict[str, Any]:
        return {"name": self.name}
