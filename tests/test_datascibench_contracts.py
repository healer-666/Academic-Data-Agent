from __future__ import annotations

import sys
import unittest
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_PATH = PROJECT_ROOT / "eval" / "scripts"
if str(SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_PATH))

from datascibench_contracts import load_artifact_contract, validate_artifact_contract  # noqa: E402


class DataSciBenchContractTests(unittest.TestCase):
    def _case_dir(self) -> Path:
        base_dir = PROJECT_ROOT / "tool-output" / "test-temp"
        base_dir.mkdir(parents=True, exist_ok=True)
        case_dir = base_dir / f"datascibench_contract_case_{uuid.uuid4().hex}"
        case_dir.mkdir(parents=True, exist_ok=True)
        return case_dir

    def test_load_contract_extracts_output_files_and_metrics(self):
        root = self._case_dir()
        metric_dir = root / "metric" / "csv_excel_1"
        metric_dir.mkdir(parents=True)
        (metric_dir / "metric.yaml").write_text(
            """
"TMC-list":
- "code": |-
    def check(ground_truth):
        import pandas as pd
        output = pd.read_excel("target.xlsx", sheet_name="sheet1")
        return len(output) > 0
  "function": |-
    Data Quality Score
  "metric": |-
    Filter Efficiency
  "task_name": |-
    Data cleaning and preprocessing
  ground_truth: "target.xlsx"
- "code": |-
    def check_csv(ground_truth):
        import pandas as pd
        output = pd.read_csv("output.csv")
        return bool(len(output))
  "metric": "CSV Completeness"
  ground_truth: "output.csv"
""",
            encoding="utf-8",
        )

        contract = load_artifact_contract(data_root=root, task_id="csv_excel_1")

        self.assertEqual(contract.status, "available")
        self.assertEqual(contract.required_artifacts, ("target.xlsx", "output.csv"))
        self.assertEqual(contract.metrics[0].metric, "Filter Efficiency")
        self.assertIn("target.xlsx", contract.to_prompt_block())

    def test_missing_metric_yaml_is_unavailable(self):
        root = self._case_dir()

        contract = load_artifact_contract(data_root=root, task_id="human_0")

        self.assertEqual(contract.status, "contract_unavailable")
        self.assertFalse(contract.available)

    def test_contract_off_disables_parsing(self):
        root = self._case_dir()

        contract = load_artifact_contract(data_root=root, task_id="csv_excel_1", contract_mode="off")

        self.assertEqual(contract.status, "disabled")

    def test_validate_artifact_contract_finds_required_files(self):
        root = self._case_dir()
        metric_dir = root / "metric" / "human_0"
        metric_dir.mkdir(parents=True)
        (metric_dir / "metric.yaml").write_text(
            """
"TMC-list":
- code: "output = pd.read_csv('most_corr_output.csv')"
  metric: "Model Accuracy"
  ground_truth: "most_corr_output.csv"
""",
            encoding="utf-8",
        )
        run_dir = root / "run"
        run_dir.mkdir()
        (run_dir / "most_corr_output.csv").write_text("Ticker 1,Ticker 2\nFB,MSFT\n", encoding="utf-8")
        contract = load_artifact_contract(data_root=root, task_id="human_0")

        result = validate_artifact_contract(contract, run_dir=run_dir, report_markdown="")

        self.assertTrue(result["artifact_contract_passed"])
        self.assertEqual(result["found_artifact_count"], 1)
        self.assertEqual(result["missing_required_artifacts"], [])

    def test_validate_artifact_contract_reports_missing_files(self):
        root = self._case_dir()
        metric_dir = root / "metric" / "csv_excel_3"
        metric_dir.mkdir(parents=True)
        (metric_dir / "metric.yaml").write_text(
            """
"TMC-list":
- code: "output = pd.read_csv('output.csv')"
  metric: "Data Completeness"
""",
            encoding="utf-8",
        )
        contract = load_artifact_contract(data_root=root, task_id="csv_excel_3")

        result = validate_artifact_contract(contract, run_dir=root / "missing", report_markdown="")

        self.assertFalse(result["artifact_contract_passed"])
        self.assertEqual(result["missing_required_artifacts"], ["output.csv"])


if __name__ == "__main__":
    unittest.main()
