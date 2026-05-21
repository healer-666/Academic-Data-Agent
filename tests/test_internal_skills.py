from __future__ import annotations

import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.skills import SkillContext, SkillValidationContext, resolve_analysis_skills  # noqa: E402
from data_analysis_agent.skills.datascibench_artifact import (  # noqa: E402
    DataSciBenchArtifactSkill,
    load_artifact_contract,
)
from data_analysis_agent.skills.lineage_audit import LineageAuditSkill  # noqa: E402
from data_analysis_agent.skills.statistical_analysis import StatisticalAnalysisSkill  # noqa: E402


class InternalSkillTests(unittest.TestCase):
    def _case_dir(self) -> Path:
        base_dir = PROJECT_ROOT / "tool-output" / "test-temp"
        base_dir.mkdir(parents=True, exist_ok=True)
        case_dir = base_dir / f"skill_case_{uuid.uuid4().hex}"
        case_dir.mkdir(parents=True, exist_ok=True)
        return case_dir

    def test_auto_profile_enables_default_runtime_skills(self):
        skills = resolve_analysis_skills(SkillContext(task_type=""))

        self.assertEqual([skill.name for skill in skills], ["statistical_analysis", "lineage_audit"])

    def test_datascibench_context_enables_artifact_and_benchmark_skills(self):
        skills = resolve_analysis_skills(SkillContext(task_type="datascibench"))

        self.assertEqual(
            [skill.name for skill in skills],
            ["statistical_analysis", "lineage_audit", "datascibench_artifact", "benchmark_run"],
        )

    def test_explicit_enabled_skills_override_defaults(self):
        skills = resolve_analysis_skills(SkillContext(task_type="datascibench", enabled_skills=("lineage_audit",)))

        self.assertEqual([skill.name for skill in skills], ["lineage_audit"])

    def test_datascibench_artifact_skill_validates_required_output(self):
        root = self._case_dir()
        metric_dir = root / "metric" / "csv_excel_1"
        metric_dir.mkdir(parents=True)
        (metric_dir / "metric.yaml").write_text(
            """
"TMC-list":
- code: "output = pd.read_csv('output.csv')"
  metric: "Completeness"
""",
            encoding="utf-8",
        )
        contract = load_artifact_contract(data_root=root, task_id="csv_excel_1")
        run_dir = root / "run"
        run_dir.mkdir()
        (run_dir / "output.csv").write_text("value\n1\n", encoding="utf-8")

        result = DataSciBenchArtifactSkill().post_run_validate(
            SkillValidationContext(
                run_context=SimpleNamespace(run_dir=run_dir),
                report_markdown="",
                lineage_contract=contract.to_dict(),
            )
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.details["found_artifact_count"], 1)

    def test_statistical_skill_detects_successful_python_and_results(self):
        run_context = SimpleNamespace(cleaned_data_path=Path("cleaned_data.csv"))
        trace = SimpleNamespace(
            tool_name="PythonInterpreterTool",
            tool_status="success",
            tool_input="df = pd.read_csv('cleaned_data.csv')",
            observation="mean=1.2, p-value=0.03, 95% CI [0.1, 0.3]",
        )

        result = StatisticalAnalysisSkill().post_run_validate(
            SkillValidationContext(
                run_context=run_context,
                report_markdown=(
                    "The analysis reloaded cleaned_data.csv and computed descriptive statistics. "
                    "The mean difference had p-value 0.03 and 95% CI. "
                    "The report explains that all numerical claims came from the successful Python observation "
                    "and does not add unsupported manual calculations."
                ),
                step_traces=(trace,),
            )
        )

        self.assertTrue(result.passed)
        self.assertTrue(result.details["has_cleaned_reload_evidence"])

    def test_lineage_skill_summarizes_generated_payload(self):
        result = LineageAuditSkill().post_run_validate(
            SkillValidationContext(
                run_context=SimpleNamespace(),
                report_markdown="",
                lineage_payload={
                    "status": "generated",
                    "json_path": "logs/lineage.json",
                    "mermaid_path": "logs/lineage.mmd",
                    "node_count": 4,
                    "edge_count": 3,
                    "missing_artifact_count": 0,
                },
            )
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.details["node_count"], 4)


if __name__ == "__main__":
    unittest.main()
