from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - dependency is declared in requirements.txt
    TestClient = None

if TestClient is not None:
    from data_analysis_agent.web.api import create_app, resolve_web_analysis_strategy
else:  # pragma: no cover
    create_app = None
    resolve_web_analysis_strategy = None


@unittest.skipIf(TestClient is None, "fastapi is not installed in this environment")
class ReactWebApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app(PROJECT_ROOT))

    def _make_outputs_run(self) -> Path:
        run_dir = PROJECT_ROOT / "outputs" / f"run_api_{uuid.uuid4().hex}"
        (run_dir / "logs").mkdir(parents=True, exist_ok=True)
        (run_dir / "data").mkdir(parents=True, exist_ok=True)
        (run_dir / "figures").mkdir(parents=True, exist_ok=True)
        (run_dir / "final_report.md").write_text("# Demo\n\nResult.", encoding="utf-8")
        (run_dir / "logs" / "agent_trace.json").write_text(
            json.dumps(
                {
                    "run_metadata": {
                        "timestamp": "2026-05-16T10:00:00",
                        "quality_mode": "standard",
                        "latency_mode": "auto",
                        "input_kind": "tabular",
                    },
                    "telemetry": {"domain": "demo-domain"},
                    "artifact_validation": {"workflow_complete": True, "stage_contract_passed": True},
                    "review_status": "accepted",
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "data" / "cleaned_data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        (run_dir / "figures" / "chart.png").write_bytes(b"fake")
        self._write_lineage(run_dir)
        self.addCleanup(lambda: shutil.rmtree(run_dir, ignore_errors=True))
        return run_dir

    def _write_lineage(self, run_dir: Path) -> None:
        lineage_payload = {
            "version": 2,
            "status": "generated",
            "summary": {
                "field_count": 1,
                "claim_count": 1,
                "supported_claim_count": 1,
                "unsupported_claim_count": 0,
                "claim_support_rate": 1.0,
            },
            "nodes": [
                {"id": "field_a", "type": "source_field", "label": "a", "status": "referenced"},
                {"id": "step_1", "type": "python_step", "label": "Python step 1", "status": "success"},
                {
                    "id": "evidence_1",
                    "type": "execution_evidence",
                    "label": "Evidence from step 1",
                    "status": "observed",
                },
                {
                    "id": "claim_1",
                    "type": "report_claim",
                    "label": "Claim 1",
                    "text": "The mean is 1.",
                    "status": "supported",
                },
                {"id": "raw_1", "type": "raw_data", "label": "source.csv", "status": "present"},
            ],
            "edges": [
                {"source": "field_a", "target": "step_1", "label": "used_by"},
                {"source": "step_1", "target": "evidence_1", "label": "produces_evidence"},
                {"source": "evidence_1", "target": "claim_1", "label": "supports:1.0:explicit"},
                {"source": "raw_1", "target": "field_a", "label": "contains_field"},
            ],
        }
        logs_dir = run_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "lineage.json").write_text(json.dumps(lineage_payload), encoding="utf-8")
        (logs_dir / "lineage.mmd").write_text("flowchart TD\n", encoding="utf-8")

    def _write_interactive_report(self, run_dir: Path) -> None:
        logs_dir = run_dir / "logs"
        figure_path = run_dir / "figures" / "chart.png"
        cleaned_path = run_dir / "data" / "cleaned_data.csv"
        logs_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "version": 1,
            "surface": "interactive_report",
            "runId": run_dir.name,
            "title": "Interactive report",
            "blocks": [{"id": "report_markdown", "type": "markdown", "markdown": "# Mock report"}],
            "figures": [
                {
                    "id": "figure_chart",
                    "type": "image",
                    "title": "chart",
                    "name": "chart.png",
                    "path": figure_path.as_posix(),
                    "datasetId": "dataset_figure_chart",
                    "sourceId": "source_1",
                    "lineageNodeIds": ["step_1"],
                }
            ],
            "claims": [],
            "sources": [
                {
                    "id": "source_1",
                    "type": "python",
                    "label": "Python step 1",
                    "stepIndex": 1,
                    "status": "success",
                    "code": "print('demo')",
                    "stdout": "demo",
                }
            ],
            "summary": {"figureCount": 1, "claimCount": 0, "datasetCount": 1, "sourceCount": 1},
        }
        snapshot = {
            "version": 1,
            "runId": run_dir.name,
            "datasets": {
                "dataset_figure_chart": {
                    "id": "dataset_figure_chart",
                    "label": "chart data",
                    "sourcePath": cleaned_path.as_posix(),
                    "rowCount": 1,
                    "sampleRowCount": 1,
                    "truncated": False,
                    "columns": [{"key": "a", "label": "a", "type": "int64"}],
                    "rows": [{"a": 1}],
                }
            },
        }
        source_map = {
            "version": 1,
            "runId": run_dir.name,
            "figures": {
                "figure_chart": {
                    "datasetId": "dataset_figure_chart",
                    "sourceId": "source_1",
                    "stepIndex": 1,
                    "filePath": figure_path.as_posix(),
                    "lineageNodeIds": ["step_1"],
                }
            },
            "claims": {},
            "tables": {},
        }
        (logs_dir / "interactive_report_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (logs_dir / "interactive_report_snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
        (logs_dir / "source_map.json").write_text(json.dumps(source_map), encoding="utf-8")

    def _fake_result(self, run_dir: Path) -> SimpleNamespace:
        report_path = run_dir / "final_report.md"
        trace_path = run_dir / "logs" / "agent_trace.json"
        cleaned_path = run_dir / "data" / "cleaned_data.csv"
        figure_path = run_dir / "figures" / "chart.png"
        for path in [report_path, trace_path, cleaned_path, figure_path]:
            path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("# Mock report\n\n![chart](figures/chart.png)", encoding="utf-8")
        trace_path.write_text("{}", encoding="utf-8")
        cleaned_path.write_text("a,b\n1,2\n", encoding="utf-8")
        figure_path.write_bytes(b"fake")
        self._write_lineage(run_dir)
        self._write_interactive_report(run_dir)
        return SimpleNamespace(
            run_dir=run_dir,
            report_path=report_path,
            trace_path=trace_path,
            cleaned_data_path=cleaned_path,
            workflow_complete=True,
            quality_mode="standard",
            latency_mode="auto",
            detected_domain="demo-domain",
            input_kind="tabular",
            review_status="accepted",
            vision_review_status="skipped",
            rag_status="retrieved",
            rag_match_count=1,
            memory_writeback_status="written",
            review_rounds_used=1,
            total_duration_ms=1200,
            methods_used=("descriptive statistics",),
            tools_used=("PythonInterpreterTool",),
            workflow_warnings=(),
            execution_audit_status="passed",
            execution_audit_passed=True,
            execution_audit_findings=(),
            review_critique="Accepted.",
            vision_review_summary="No visual review.",
            report_markdown="# Mock report\n\n![chart](figures/chart.png)",
            telemetry=SimpleNamespace(figures_generated=(figure_path.as_posix(),)),
            step_traces=(),
        )

    def test_health(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_web_scenario_strategies_are_server_owned(self):
        general = resolve_web_analysis_strategy("general")
        modeling = resolve_web_analysis_strategy("modeling")

        self.assertEqual(general["task_type"], "general_analysis")
        self.assertEqual(general["quality_mode"], "standard")
        self.assertEqual(general["max_reviews"], 1)
        self.assertEqual(modeling["task_type"], "mathematical_modeling")
        self.assertEqual(modeling["quality_mode"], "publication")
        self.assertEqual(modeling["latency_mode"], "quality")
        self.assertEqual(modeling["max_reviews"], 2)
        self.assertGreater(len(modeling["task_expectations"]), len(general["task_expectations"]))
        self.assertIsNone(resolve_web_analysis_strategy(""))

    def test_workspace_and_history_detail(self):
        run_dir = self._make_outputs_run()

        workspace = self.client.get("/api/workspace", params={"output_dir": "outputs"}).json()
        self.assertTrue(any(run["runId"] == run_dir.name for run in workspace["historyRuns"]))

        detail_response = self.client.get(f"/api/history/runs/{run_dir.name}", params={"output_dir": "outputs"})
        self.assertEqual(detail_response.status_code, 200)
        detail = detail_response.json()
        self.assertEqual(detail["runId"], run_dir.name)
        self.assertIn("Demo", detail["reportMarkdown"])
        self.assertTrue(detail["lineage"]["available"])
        self.assertEqual(detail["lineage"]["summary"]["supported_claim_count"], 1)
        self.assertEqual(
            {node["type"] for node in detail["lineage"]["nodes"]},
            {"source_field", "python_step", "execution_evidence", "report_claim"},
        )
        self.assertNotIn("raw_data", {node["type"] for node in detail["lineage"]["nodes"]})

    def test_files_endpoint_allows_only_project_outputs(self):
        run_dir = self._make_outputs_run()
        allowed = run_dir / "final_report.md"

        allowed_response = self.client.get("/api/files", params={"path": allowed.as_posix()})
        self.assertEqual(allowed_response.status_code, 200)

        outside = Path(tempfile.gettempdir()) / f"outside_{uuid.uuid4().hex}.txt"
        outside.write_text("blocked", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        denied_response = self.client.get("/api/files", params={"path": outside.as_posix()})
        self.assertEqual(denied_response.status_code, 403)

    def test_interactive_report_endpoint_and_legacy_fallback(self):
        run_dir = self._make_outputs_run()

        legacy_response = self.client.get(
            f"/api/history/runs/{run_dir.name}/interactive-report",
            params={"output_dir": "outputs"},
        )
        self.assertEqual(legacy_response.status_code, 200)
        self.assertFalse(legacy_response.json()["available"])

        self._write_interactive_report(run_dir)
        response = self.client.get(
            f"/api/history/runs/{run_dir.name}/interactive-report",
            params={"output_dir": "outputs"},
        )
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["available"])
        self.assertEqual(payload["manifest"]["summary"]["figureCount"], 1)
        self.assertIn("url", payload["manifest"]["figures"][0])
        self.assertEqual(payload["snapshot"]["datasets"]["dataset_figure_chart"]["rows"][0]["a"], 1)

    def test_analysis_run_streams_result_with_mocked_runner(self):
        output_dir = PROJECT_ROOT / "outputs"
        run_dir = output_dir / f"run_stream_{uuid.uuid4().hex}"
        self.addCleanup(lambda: shutil.rmtree(run_dir, ignore_errors=True))

        def fake_run_analysis(*args, **kwargs):
            kwargs["event_handler"]("analysis_started", {"analysis_round": 1, "max_steps": 6})
            return self._fake_result(run_dir)

        files = {
            "data_file": ("sample.csv", b"a,b\n1,2\n", "text/csv"),
            "knowledge_uploads": ("notes.md", b"# Notes", "text/markdown"),
        }
        data = {
            "query": "demo query",
            "quality_mode": "standard",
            "latency_mode": "auto",
            "vision_review_mode": "off",
            "max_steps": "6",
            "max_reviews": "1",
            "vision_max_images": "1",
            "vision_max_image_side": "512",
            "output_dir": "outputs",
            "agent_name": "Advanced Data Analyst",
            "use_rag": "true",
            "use_memory": "true",
        }
        with patch("data_analysis_agent.web.api.run_analysis", side_effect=fake_run_analysis):
            with self.client.stream("POST", "/api/analysis/runs", data=data, files=files) as response:
                payload = response.read().decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: log", payload)
        self.assertIn("event: result", payload)
        self.assertIn("demo-domain", payload)
        self.assertIn('"lineage"', payload)
        self.assertIn('"claim_support_rate": 1.0', payload)
        self.assertIn('"interactiveReportAvailable": true', payload)
        self.assertIn('"figureCount": 1', payload)

    def test_general_and_modeling_scenarios_submit_end_to_end(self):
        expectations = {
            "general": {
                "task_type": "general_analysis",
                "quality_mode": "standard",
                "latency_mode": "auto",
                "max_steps": 6,
                "max_reviews": 1,
            },
            "modeling": {
                "task_type": "mathematical_modeling",
                "quality_mode": "publication",
                "latency_mode": "quality",
                "max_steps": 10,
                "max_reviews": 2,
            },
        }

        for scenario, expected in expectations.items():
            with self.subTest(scenario=scenario):
                run_dir = PROJECT_ROOT / "outputs" / f"run_{scenario}_{uuid.uuid4().hex}"
                self.addCleanup(lambda path=run_dir: shutil.rmtree(path, ignore_errors=True))
                captured: dict[str, object] = {}

                def fake_run_analysis(*args, **kwargs):
                    captured.update(kwargs)
                    kwargs["event_handler"]("analysis_started", {"analysis_round": 1})
                    return self._fake_result(run_dir)

                files = {"data_file": ("sample.csv", b"a,b\n1,2\n", "text/csv")}
                data = {
                    "scenario": scenario,
                    "query": "demo query",
                    # These conflicting values verify that a Web scenario owns its runtime strategy.
                    "quality_mode": "draft",
                    "latency_mode": "fast",
                    "vision_review_mode": "off",
                    "max_steps": "2",
                    "max_reviews": "0",
                    "use_rag": "false",
                    "use_memory": "false",
                    "output_dir": "outputs",
                }
                with patch("data_analysis_agent.web.api.run_analysis", side_effect=fake_run_analysis):
                    with self.client.stream("POST", "/api/analysis/runs", data=data, files=files) as response:
                        payload = response.read().decode("utf-8")

                self.assertEqual(response.status_code, 200)
                self.assertIn("event: result", payload)
                for key, value in expected.items():
                    self.assertEqual(captured[key], value)
                self.assertTrue(captured["use_rag"])
                self.assertTrue(captured["use_memory"])
                self.assertTrue(captured["task_expectations"])


if __name__ == "__main__":
    unittest.main()
