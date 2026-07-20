from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.modeling_workspace import ModelingWorkspace, ModelingWorkspaceError

try:
    from fastapi.testclient import TestClient
    from data_analysis_agent.web.api import create_app
except ModuleNotFoundError:  # pragma: no cover - dependencies are declared by the project
    TestClient = None
    create_app = None


class ModelingWorkspaceTests(unittest.TestCase):
    def _fixture(self) -> tuple[Path, Path, Path, Path, Path]:
        root = PROJECT_ROOT / "tool-output" / "test-temp" / f"modeling_workspace_{uuid.uuid4().hex}"
        root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        problem = root / "problem.md"
        problem.write_text("# Problem A\nAnalyze linked customer and order tables.", encoding="utf-8")
        customers = root / "customers.csv"
        customers.write_text("customer_id,region,segment\n1,East,A\n2,West,B\n3,,B\n", encoding="utf-8")
        orders = root / "orders.csv"
        orders.write_text("order_id,customer_id,amount\n10,1,5\n11,1,8\n12,2,13\n", encoding="utf-8")
        attachment = root / "constraints.pdf"
        attachment.write_bytes(b"placeholder")
        return root, problem, customers, orders, attachment

    def test_create_inspects_fields_quality_and_relationships(self):
        root, problem, customers, orders, attachment = self._fixture()
        workspace = ModelingWorkspace(root / "packages")

        package = workspace.create(
            "demo-package",
            problem_path=problem,
            data_paths=[customers, orders],
            attachment_paths=[attachment],
        )

        self.assertEqual(package["status"], "needs_review")
        self.assertEqual(package["summary"]["tableCount"], 2)
        self.assertEqual(package["summary"]["fieldCount"], 6)
        self.assertGreater(package["summary"]["qualityWarningCount"], 0)
        self.assertEqual(package["problem"]["name"], "problem.md")
        self.assertEqual(package["attachments"][0]["name"], "constraints.pdf")
        self.assertNotIn("_private", package)
        relationship = package["relationships"][0]
        self.assertEqual(relationship["leftColumn"], "customer_id")
        self.assertEqual(relationship["rightColumn"], "customer_id")
        self.assertEqual(relationship["kind"], "one_to_many")
        self.assertEqual(relationship["status"], "inferred")

        customer_table = next(table for table in package["tables"] if table["sourceFileName"] == "customers.csv")
        region = next(field for field in customer_table["fields"] if field["name"] == "region")
        self.assertEqual(region["missingCount"], 1)
        self.assertIn("East", region["sampleValues"])

    def test_excel_sheets_are_exposed_as_individual_tables(self):
        root, problem, _customers, _orders, _attachment = self._fixture()
        workbook = root / "multi.xlsx"
        with pd.ExcelWriter(workbook) as writer:
            pd.DataFrame({"id": [1, 2], "value": [3, 4]}).to_excel(writer, sheet_name="Input", index=False)
            pd.DataFrame({"id": [1, 2], "score": [8, 9]}).to_excel(writer, sheet_name="Score", index=False)

        package = ModelingWorkspace(root / "packages").create(
            "excel-package",
            problem_path=problem,
            data_paths=[workbook],
        )

        self.assertEqual(package["summary"]["tableCount"], 2)
        self.assertEqual({table["sheetName"] for table in package["tables"]}, {"Input", "Score"})

    def test_update_persists_human_corrections_and_confirmation(self):
        root, problem, customers, orders, _attachment = self._fixture()
        workspace = ModelingWorkspace(root / "packages")
        package = workspace.create("review-package", problem_path=problem, data_paths=[customers, orders])
        relationship = dict(package["relationships"][0])
        relationship["status"] = "confirmed"
        relationship["reason"] = "Maintainer verified the customer key."

        updated = workspace.update(
            package["packageId"],
            {
                "primaryTableId": package["tables"][1]["id"],
                "tableLabels": {package["tables"][0]["id"]: "客户主表"},
                "relationships": [relationship],
                "relationshipNotes": "已核对字段定义。",
                "confirmed": True,
            },
        )

        self.assertEqual(updated["status"], "confirmed")
        self.assertTrue(updated["review"]["confirmed"])
        self.assertEqual(updated["review"]["tableLabels"][package["tables"][0]["id"]], "客户主表")
        self.assertEqual(updated["relationships"][0]["status"], "confirmed")
        self.assertEqual(workspace.load(package["packageId"])["primaryTableId"], package["tables"][1]["id"])

        reopened = workspace.update(package["packageId"], {"confirmed": False})
        self.assertEqual(reopened["review"]["tableLabels"][package["tables"][0]["id"]], "客户主表")
        self.assertEqual(reopened["review"]["relationshipNotes"], "已核对字段定义。")
        self.assertEqual(reopened["relationships"][0]["status"], "confirmed")

    def test_low_confidence_relationship_is_marked_uncertain(self):
        root, problem, _customers, _orders, _attachment = self._fixture()
        left = root / "left.csv"
        right = root / "right.csv"
        left.write_text("shared_id,value\n1,a\n2,b\n3,c\n4,d\n", encoding="utf-8")
        right.write_text("shared_id,score\n1,8\n2,7\n9,6\n10,5\n", encoding="utf-8")

        package = ModelingWorkspace(root / "packages").create(
            "uncertain-package",
            problem_path=problem,
            data_paths=[left, right],
        )

        self.assertEqual(package["relationships"][0]["status"], "uncertain")
        self.assertEqual(package["summary"]["uncertainRelationshipCount"], 1)

    def test_update_rejects_unknown_relationship_fields(self):
        root, problem, customers, orders, _attachment = self._fixture()
        workspace = ModelingWorkspace(root / "packages")
        package = workspace.create("invalid-package", problem_path=problem, data_paths=[customers, orders])
        relationship = dict(package["relationships"][0])
        relationship["leftColumn"] = "not_a_field"

        with self.assertRaisesRegex(ModelingWorkspaceError, "unknown table or field"):
            workspace.update(
                package["packageId"],
                {
                    "primaryTableId": package["primaryTableId"],
                    "relationships": [relationship],
                },
            )


@unittest.skipIf(TestClient is None, "fastapi is not installed in this environment")
class ModelingWorkspaceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app(PROJECT_ROOT))
        self.package_dirs: list[Path] = []

    def tearDown(self) -> None:
        for path in self.package_dirs:
            shutil.rmtree(path, ignore_errors=True)

    def test_create_review_and_reload_modeling_package(self):
        files = [
            ("problem_file", ("problem.md", b"# Problem\nBuild a linked model.", "text/markdown")),
            ("data_files", ("customers.csv", b"customer_id,region\n1,East\n2,West\n", "text/csv")),
            ("data_files", ("orders.csv", b"order_id,customer_id\n10,1\n11,1\n12,2\n", "text/csv")),
            ("attachments", ("notes.txt", b"Constraint notes", "text/plain")),
        ]
        response = self.client.post("/api/modeling/packages", files=files)

        self.assertEqual(response.status_code, 200)
        package = response.json()
        package_dir = PROJECT_ROOT / "outputs" / "modeling_packages" / package["packageId"]
        self.package_dirs.append(package_dir)
        self.assertEqual(package["summary"]["tableCount"], 2)
        self.assertNotIn("_private", response.text)

        relationship = dict(package["relationships"][0])
        relationship["status"] = "confirmed"
        update = {
            "primaryTableId": package["primaryTableId"],
            "tableLabels": {package["primaryTableId"]: "主分析表"},
            "relationships": [relationship],
            "relationshipNotes": "人工确认",
            "confirmed": True,
        }
        updated_response = self.client.patch(f"/api/modeling/packages/{package['packageId']}", json=update)
        self.assertEqual(updated_response.status_code, 200)
        self.assertEqual(updated_response.json()["status"], "confirmed")

        loaded = self.client.get(f"/api/modeling/packages/{package['packageId']}")
        self.assertEqual(loaded.status_code, 200)
        self.assertEqual(loaded.json()["review"]["relationshipNotes"], "人工确认")


if __name__ == "__main__":
    unittest.main()
