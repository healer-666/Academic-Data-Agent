from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.web.history import find_run_history, scan_run_history


class HistoryTests(unittest.TestCase):
    def _workspace_case_dir(self) -> Path:
        base_dir = PROJECT_ROOT / "tool-output" / "test-temp"
        base_dir.mkdir(parents=True, exist_ok=True)
        case_dir = base_dir / f"history_case_{uuid.uuid4().hex}"
        case_dir.mkdir(parents=True, exist_ok=True)
        return case_dir

    def _create_run_dir(
        self,
        root: Path,
        name: str,
        *,
        timestamp: str | None = None,
        with_trace: bool = True,
    ) -> Path:
        run_dir = root / name
        (run_dir / "logs").mkdir(parents=True, exist_ok=True)
        (run_dir / "data").mkdir(parents=True, exist_ok=True)
        (run_dir / "figures" / "review_round_1").mkdir(parents=True, exist_ok=True)
        (run_dir / "data" / "cleaned_data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        (run_dir / "figures" / "review_round_1" / "chart.png").write_text("fake-image", encoding="utf-8")
        (run_dir / "logs" / "document_ingestion.json").write_text("{}", encoding="utf-8")
        (run_dir / "final_report.md").write_text(
            "# Report\n\n![chart](outputs/{}/figures/review_round_1/chart.png)".format(name),
            encoding="utf-8",
        )
        if with_trace:
            figure_path = run_dir / "figures" / "review_round_1" / "chart.png"
            payload = {
                "run_metadata": {
                    "timestamp": timestamp or "2026-03-16T10:00:00",
                    "quality_mode": "standard",
                    "latency_mode": "auto",
                    "input_kind": "pdf",
                },
                "document_ingestion": {
                    "input_kind": "pdf",
                    "status": "completed",
                    "summary": "PDF table selected.",
                    "candidate_table_count": 2,
                    "selected_table_id": "table_01",
                    "selected_table_shape": [7, 5],
                    "pdf_multi_table_mode": True,
                },
                "telemetry": {
                    "domain": "finance",
                    "figures_generated": [figure_path.resolve().as_posix()],
                },
                "artifact_validation": {
                    "workflow_complete": True,
                    "warnings": [],
                    "stage_contract_status": "failed",
                    "stage_contract_findings": ["No later Python step explicitly reloaded cleaned_data.csv."],
                    "stage_contract_passed": False,
                },
                "review_status": "accepted",
                "vision_review_history": [
                    {
                        "status": "completed",
                        "summary": "Chart layout is clear.",
                    }
                ],
                "step_traces": [
                    {
                        "step_index": 1,
                        "tool_name": "PythonInterpreterTool",
                        "summary": "Local Python execution",
                    }
                ],
            }
            (run_dir / "logs" / "agent_trace.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return run_dir

    def test_scan_run_history_sorts_newest_first(self):
        case_dir = self._workspace_case_dir()
        self._create_run_dir(case_dir, "run_20260316_090000", timestamp="2026-03-16T09:00:00")
        self._create_run_dir(case_dir, "run_20260316_110000", timestamp="2026-03-16T11:00:00")

        entries = scan_run_history(case_dir)

        self.assertEqual(entries[0].run_dir.name, "run_20260316_110000")
        self.assertEqual(entries[1].run_dir.name, "run_20260316_090000")

    def test_scan_run_history_falls_back_when_trace_missing(self):
        case_dir = self._workspace_case_dir()
        self._create_run_dir(case_dir, "run_20260316_120000", with_trace=False)

        entries = scan_run_history(case_dir)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].report_path.name, "final_report.md")
        self.assertIsNone(entries[0].trace_path)

    def test_scan_run_history_supports_empty_state(self):
        case_dir = self._workspace_case_dir()

        entries = scan_run_history(case_dir)

        self.assertEqual(entries, [])

    def test_scan_run_history_reads_report_figures_and_table_metadata(self):
        case_dir = self._workspace_case_dir()
        run_dir = self._create_run_dir(case_dir, "run_20260316_130000", timestamp="2026-03-16T13:00:00")

        entries = scan_run_history(case_dir)
        entry = entries[0]

        self.assertEqual(entry.run_dir, run_dir.resolve())
        self.assertEqual(len(entry.figure_paths), 1)
        self.assertEqual(entry.selected_table_id, "table_01")
        self.assertEqual(entry.selected_table_shape, (7, 5))
        self.assertTrue(entry.pdf_multi_table_mode)
        self.assertEqual(entry.stage_contract_status, "failed")
        self.assertIn("No later Python step explicitly reloaded cleaned_data.csv.", entry.stage_contract_findings)
        self.assertTrue(str(entry.report_path).endswith("final_report.md"))
        self.assertTrue(str(entry.trace_path).endswith("agent_trace.json"))
        self.assertTrue(str(entry.cleaned_data_path).endswith("cleaned_data.csv"))

    def test_scan_run_history_limit_and_direct_lookup(self):
        case_dir = self._workspace_case_dir()
        self._create_run_dir(case_dir, "run_20260316_140000", timestamp="2026-03-16T14:00:00")
        second = self._create_run_dir(case_dir, "run_20260316_150000", timestamp="2026-03-16T15:00:00")
        os.utime(second, (second.stat().st_atime, second.stat().st_mtime + 10))

        entries = scan_run_history(case_dir, limit=1)
        direct = find_run_history(second.name, case_dir)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].run_dir.name, second.name)
        self.assertEqual(direct.run_dir.name, second.name)
        self.assertIsNone(find_run_history("../outside", case_dir))


if __name__ == "__main__":
    unittest.main()
