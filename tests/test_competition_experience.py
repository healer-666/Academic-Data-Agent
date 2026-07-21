from __future__ import annotations

import sys
import unittest
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.experience_library import (
    CompetitionExperienceError,
    CompetitionExperienceLibrary,
    ExperienceLibraryManager,
)


class CompetitionExperienceTests(unittest.TestCase):
    def _library(self, *, bundled_root: Path | None = None) -> CompetitionExperienceLibrary:
        install_root = PROJECT_ROOT / "tool-output" / "test-temp" / f"case_browser_{uuid.uuid4().hex}"
        self.addCleanup(lambda: __import__("shutil").rmtree(install_root, ignore_errors=True))
        return CompetitionExperienceLibrary(
            ExperienceLibraryManager(
                install_root=install_root,
                bundled_root=bundled_root
                if bundled_root is not None
                else PROJECT_ROOT / "data" / "competition_experience" / "bundled" / "1.0.0",
            )
        )

    def _context(self, query: str) -> dict[str, object]:
        return {
            "packageId": "modeling-demo",
            "packageStatus": "confirmed",
            "query": query,
            "problemText": query,
            "problemWarnings": [],
            "tables": [
                {
                    "id": "table-1",
                    "name": "化学成分",
                    "sourceFileName": "附件.xlsx",
                    "rowCount": 69,
                    "columnCount": 15,
                    "fields": [
                        {"name": "文物编号"},
                        {"name": "SiO2"},
                        {"name": "PbO"},
                        {"name": "表面风化"},
                    ],
                    "quality": {"warnings": ["存在未检测成分"]},
                }
            ],
            "relationships": [],
            "summary": {"tableCount": 1, "rowCount": 69, "fieldCount": 15},
        }

    def test_browse_and_get_only_return_approved_public_case_fields(self):
        library = self._library()

        snapshot = library.browse()
        detail = library.get("cumcm-2022-c")

        self.assertTrue(snapshot["usable"])
        self.assertEqual(snapshot["version"], "1.0.0")
        self.assertEqual(len(snapshot["cases"]), 1)
        self.assertEqual(snapshot["cases"][0]["reviewStatus"], "approved")
        self.assertEqual(detail["case"]["id"], "cumcm-2022-c")
        self.assertTrue(detail["models"])
        self.assertTrue(detail["limitations"])
        self.assertTrue(all(source["distribution"] == "metadata_only" for source in detail["sources"]))
        self.assertNotIn("sha256", str(detail))
        self.assertNotIn("_private", str(detail))

        with self.assertRaises(CompetitionExperienceError):
            library.get("missing-case")

    def test_matching_selects_relevant_case_and_skills_with_audit_record(self):
        library = self._library()

        plan = library.build_plan(
            self._context("分析古代玻璃风化与化学成分，分类高钾玻璃和铅钡玻璃并做敏感性分析")
        )

        self.assertEqual(plan["status"], "needs_confirmation")
        self.assertEqual(plan["caseMatches"][0]["caseId"], "cumcm-2022-c")
        self.assertGreaterEqual(plan["caseMatches"][0]["score"], 0.6)
        self.assertTrue(plan["selectedSkills"])
        self.assertIn("cumcm-2022-c", plan["audit"]["selectedCaseIds"])
        self.assertTrue(any(model["referenceOnly"] for model in plan["models"]))

    def test_low_relevance_case_is_not_forced_into_plan(self):
        library = self._library()
        context = self._context("优化城市公交车辆排班和充电站容量")
        context["problemText"] = "公交车辆排班与充电容量优化"
        context["tables"][0]["name"] = "车辆班次"
        context["tables"][0]["sourceFileName"] = "schedule.csv"
        context["tables"][0]["fields"] = [{"name": "vehicle_id"}, {"name": "departure_time"}]

        plan = library.build_plan(context)

        self.assertEqual(plan["caseMatches"], [])
        self.assertTrue(plan["selectedSkills"])
        self.assertTrue(any("不强行套用" in warning for warning in plan["warnings"]))
        self.assertEqual(plan["audit"]["selectedCaseIds"], [])

    def test_missing_library_degrades_browse_and_keeps_general_plan(self):
        missing = PROJECT_ROOT / "tool-output" / "test-temp" / f"missing_{uuid.uuid4().hex}"
        library = self._library(bundled_root=missing)

        snapshot = library.browse()
        plan = library.build_plan(self._context("任意数学建模问题"))

        self.assertFalse(snapshot["usable"])
        self.assertEqual(snapshot["cases"], [])
        self.assertEqual(plan["caseMatches"], [])
        self.assertTrue(plan["dataOperations"])


if __name__ == "__main__":
    unittest.main()
