from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.interactive_report import build_interactive_report_artifacts
from data_analysis_agent.lineage_detail import extract_report_claims
from data_analysis_agent.reporting import ReportTelemetry
from data_analysis_agent.runtime_models import AgentStepTrace, RunContext


class InteractiveReportEvidenceTests(unittest.TestCase):
    def _context(self) -> RunContext:
        run_dir = PROJECT_ROOT / "tool-output" / "test-temp" / f"result_evidence_{uuid.uuid4().hex}"
        data_dir = run_dir / "data"
        figures_dir = run_dir / "figures"
        logs_dir = run_dir / "logs"
        for directory in (data_dir, figures_dir, logs_dir):
            directory.mkdir(parents=True, exist_ok=True)
        source = run_dir / "source.xlsx"
        import pandas as pd

        frame = pd.DataFrame({
            "category": ["A", "A", "B", "B"],
            "product_name": ["a", "alphabet", "bee", "beta"],
            "amount": [10, 20, 30, 40],
        })
        frame.to_excel(source, index=False, sheet_name="原始数据")
        cleaned = data_dir / "cleaned_data.csv"
        frame.to_csv(cleaned, index=False)
        report = run_dir / "final_report.md"
        trace = logs_dir / "agent_trace.json"
        self.addCleanup(lambda: shutil.rmtree(run_dir, ignore_errors=True))
        return RunContext(
            run_id=run_dir.name,
            session_id=run_dir.name,
            source_path=source,
            output_root=run_dir.parent,
            run_dir=run_dir,
            data_dir=data_dir,
            figures_dir=figures_dir,
            logs_dir=logs_dir,
            cleaned_data_path=cleaned,
            report_path=report,
            trace_path=trace,
            quality_mode="standard",
            latency_mode="auto",
            vision_review_mode="off",
            document_ingestion_mode="tabular_only",
        )

    def test_figures_get_distinct_columns_rows_and_code_focus(self):
        context = self._context()
        category_figure = context.figures_dir / "category.png"
        length_figure = context.figures_dir / "length.png"
        category_figure.write_bytes(b"png")
        length_figure.write_bytes(b"png")
        code = (
            "df = pd.read_csv('data/cleaned_data.csv')\n"
            "category_counts = df['category'].value_counts()\n"
            "category_counts.plot.bar()\n"
            f"save_figure('{category_figure.as_posix()}')\n"
            "df['name_length'] = df['product_name'].str.len()\n"
            "df.plot.scatter(x='name_length', y='amount')\n"
            f"save_figure('{length_figure.as_posix()}')\n"
        )
        trace = AgentStepTrace(
            step_index=3,
            raw_response="",
            action="call_tool",
            decision="Generate two different charts",
            tool_name="PythonInterpreterTool",
            tool_input=code,
            tool_status="success",
            observation=json.dumps({"data": {"stdout": "category count 2; mean length 4"}}),
        )
        report = (
            "# Report\n\n## 主要统计结果\n"
            "分类 A 和 B 各有 2 条记录。\n"
            "产品名称平均长度为 4。\n\n"
            f"![分类]({category_figure.as_posix()})\n"
            f"![长度]({length_figure.as_posix()})"
        )
        artifact = build_interactive_report_artifacts(
            run_context=context,
            report_markdown=report,
            telemetry=ReportTelemetry(valid=True),
            step_traces=(trace,),
        )
        manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
        snapshot = json.loads(artifact.snapshot_path.read_text(encoding="utf-8"))
        source_map = json.loads(artifact.source_map_path.read_text(encoding="utf-8"))

        self.assertEqual(len(manifest["figures"]), 2)
        first, second = manifest["figures"]
        first_data = snapshot["datasets"][first["datasetId"]]
        second_data = snapshot["datasets"][second["datasetId"]]
        self.assertIn("category", first_data["locator"]["columns"])
        self.assertNotIn("amount", first_data["locator"]["columns"])
        self.assertIn("product_name", second_data["locator"]["columns"])
        self.assertIn("amount", second_data["locator"]["columns"])
        self.assertEqual(first_data["locator"]["sourceSheet"], "原始数据")
        self.assertEqual(first_data["locator"]["sourceRows"], "2–5")
        self.assertEqual(first_data["rows"][0]["__source_row__"], 2)
        self.assertNotEqual(
            source_map["figures"][first["id"]]["sourceIds"],
            source_map["figures"][second["id"]]["sourceIds"],
        )
        sources = {source["id"]: source for source in manifest["sources"]}
        self.assertNotEqual(sources[first["sourceId"]]["code"], sources[second["sourceId"]]["code"])

    def test_claims_have_separate_targeted_datasets(self):
        context = self._context()
        trace = AgentStepTrace(
            step_index=4,
            raw_response="",
            action="call_tool",
            decision="Compute category counts and name lengths",
            tool_name="PythonInterpreterTool",
            tool_input=(
                "df = pd.read_csv('data/cleaned_data.csv')\n"
                "df['name_length'] = df['product_name'].str.len()\n"
                "print(df['category'].value_counts())\n"
                "print(df.groupby('category')['name_length'].mean())\n"
            ),
            tool_status="success",
            observation=json.dumps({"data": {"stdout": "A 2 B 2; mean name length 4.0"}}),
        )
        report = (
            "# Report\n\n## 结论\n### 分类分布\n"
            "1. χ²(1) = 0.0，两个组各有 2 条记录。[证据: step_4]\n"
            "### 名称长度\n"
            "2. H(1) = 4.0，差异需要复核。[证据: step_4]\n"
        )
        artifact = build_interactive_report_artifacts(
            run_context=context,
            report_markdown=report,
            telemetry=ReportTelemetry(valid=True),
            step_traces=(trace,),
        )
        manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
        snapshot = json.loads(artifact.snapshot_path.read_text(encoding="utf-8"))
        claims = manifest["claims"]
        self.assertEqual(len(claims), 2)
        self.assertNotEqual(claims[0]["datasetId"], claims[1]["datasetId"])
        first_columns = snapshot["datasets"][claims[0]["datasetId"]]["locator"]["columns"]
        second_columns = snapshot["datasets"][claims[1]["datasetId"]]["locator"]["columns"]
        self.assertIn("category", first_columns)
        self.assertNotIn("amount", first_columns)
        self.assertIn("product_name", second_columns)
        self.assertIn("name_length", second_columns)
        self.assertNotEqual(claims[0]["sourceIds"], claims[1]["sourceIds"])

    def test_only_findings_or_explicit_hidden_evidence_become_interactive_claims(self):
        report = (
            "## 方法说明\n最多执行 6 个分析步骤。\n"
            "## 主要统计结果\n均值为 12.5，差异显著。\n"
            "## 数据清洗说明\n删除了 2 行。 <!-- result-evidence: step_1 -->\n"
        )
        claims = extract_report_claims(report)
        self.assertEqual(len(claims), 2)
        self.assertTrue(any("12.5" in claim.text for claim in claims))
        self.assertTrue(any(claim.explicit_step_indices == (1,) for claim in claims))


if __name__ == "__main__":
    unittest.main()
