from __future__ import annotations

import json
import unittest
import uuid
from pathlib import Path

from data_analysis_agent.lineage import write_lineage_artifacts
from data_analysis_agent.reporting import ReportTelemetry
from data_analysis_agent.runtime_models import AgentStepTrace, ArtifactValidationResult, RunContext


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LineageTests(unittest.TestCase):
    def _run_context(self) -> RunContext:
        base_dir = PROJECT_ROOT / "tool-output" / "test-temp" / f"lineage_case_{uuid.uuid4().hex}"
        data_dir = base_dir / "data"
        figures_dir = base_dir / "figures"
        logs_dir = base_dir / "logs"
        for directory in (data_dir, figures_dir, logs_dir):
            directory.mkdir(parents=True, exist_ok=True)
        source = base_dir / "source.csv"
        source.write_text("x\n1\n", encoding="utf-8")
        report = base_dir / "final_report.md"
        report.write_text("# Report\n", encoding="utf-8")
        cleaned = data_dir / "cleaned_data.csv"
        cleaned.write_text("x\n1\n", encoding="utf-8")
        return RunContext(
            run_id=base_dir.name,
            session_id=base_dir.name,
            source_path=source,
            output_root=base_dir.parent,
            run_dir=base_dir,
            data_dir=data_dir,
            figures_dir=figures_dir,
            logs_dir=logs_dir,
            cleaned_data_path=cleaned,
            report_path=report,
            trace_path=logs_dir / "agent_trace.json",
            quality_mode="draft",
            latency_mode="quality",
            vision_review_mode="off",
            document_ingestion_mode="tabular_only",
        )

    def test_write_lineage_artifacts_generates_json_and_mermaid(self):
        context = self._run_context()
        output = context.run_dir / "output.csv"
        output.write_text("y\n2\n", encoding="utf-8")
        traces = (
            AgentStepTrace(
                step_index=1,
                raw_response="",
                action="call_tool",
                tool_name="PythonInterpreterTool",
                tool_input=f"pd.read_csv('{context.source_path.as_posix()}').to_csv('{context.cleaned_data_path.as_posix()}')",
                tool_status="success",
            ),
            AgentStepTrace(
                step_index=2,
                raw_response="",
                action="call_tool",
                tool_name="PythonInterpreterTool",
                tool_input=f"pd.read_csv('{context.cleaned_data_path.as_posix()}').to_csv('{output.as_posix()}')",
                tool_status="success",
                observation=f"Saved {output.as_posix()}",
            ),
        )
        telemetry = ReportTelemetry(valid=True, figures_generated=())
        validation = ArtifactValidationResult(
            workflow_complete=True,
            missing_artifacts=(),
            warnings=(),
            cleaned_data_exists=True,
            report_exists=True,
            trace_exists=True,
        )

        artifact = write_lineage_artifacts(
            run_context=context,
            step_traces=traces,
            telemetry=telemetry,
            artifact_validation=validation,
            lineage_contract={
                "required_artifacts": ["output.csv"],
                "metrics": [{"metric": "Data Completeness", "output_files": ["output.csv"]}],
            },
        )

        payload = json.loads(artifact.json_path.read_text(encoding="utf-8"))
        mermaid = artifact.mermaid_path.read_text(encoding="utf-8")

        self.assertEqual(payload["status"], "generated")
        self.assertIn("contract_metric", {node["type"] for node in payload["nodes"]})
        self.assertIn("flowchart TD", mermaid)
        self.assertGreaterEqual(artifact.node_count, 5)

    def test_missing_cleaned_data_is_marked_missing(self):
        context = self._run_context()
        context.cleaned_data_path.unlink()

        artifact = write_lineage_artifacts(
            run_context=context,
            step_traces=(),
            telemetry=ReportTelemetry(valid=False),
            artifact_validation=ArtifactValidationResult(
                workflow_complete=False,
                missing_artifacts=(context.cleaned_data_path.as_posix(),),
                warnings=("missing cleaned data",),
                cleaned_data_exists=False,
                report_exists=True,
                trace_exists=False,
            ),
        )

        payload = json.loads(artifact.json_path.read_text(encoding="utf-8"))
        cleaned_nodes = [node for node in payload["nodes"] if node["type"] == "cleaned_data"]

        self.assertEqual(cleaned_nodes[0]["status"], "missing")
        self.assertGreaterEqual(artifact.missing_artifact_count, 1)


if __name__ == "__main__":
    unittest.main()
