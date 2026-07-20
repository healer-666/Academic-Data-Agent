from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.modeling_skills import (
    DEFAULT_CATALOG_PATH,
    SKILL_CATEGORIES,
    ModelingSkillBuilder,
    ModelingSkillCatalog,
    ModelingSkillError,
    ModelingTaskProfile,
    load_runtime_modeling_skills,
)


class ModelingSkillTests(unittest.TestCase):
    def _temp_dir(self) -> Path:
        path = PROJECT_ROOT / "tool-output" / "test-temp" / f"modeling_skills_{uuid.uuid4().hex}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _case_card(self, directory: Path, case_id: str, method: str) -> Path:
        path = directory / f"{case_id}.json"
        payload = {
            "schema_version": "1.0",
            "library_version": f"{case_id}-r001",
            "published_at": "2026-07-20T00:00:00Z",
            "case": {
                "id": case_id,
                "competition": "Representative Modeling Contest",
                "year": 2025,
                "problem_number": "A",
                "title": "Representative task",
                "locale": "en",
            },
            "sources": [],
            "extraction": {
                "problem_summary": "A representative capacity and risk modeling task.",
                "data_operations": [{"name": "Audit", "purpose": "Check grain", "evidence_source_ids": ["paper"]}],
                "models": [{"name": method, "purpose": "Model outcome", "assumptions": [], "evidence_source_ids": ["paper"]}],
                "validation_methods": [{"name": "Backtest", "purpose": "Validate", "evidence_source_ids": ["paper"]}],
                "charts": [{"name": "Residuals", "purpose": "Diagnose", "evidence_source_ids": ["paper"]}],
                "key_findings": [{"statement": "Use structured validation.", "evidence_source_ids": ["paper"]}],
                "limitations": ["Representative fixture only."],
            },
            "review": {"status": "approved", "reviewer": "maintainer"},
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def _skills(self, case_ids: list[str]) -> dict[str, object]:
        skills = []
        for category in SKILL_CATEGORIES:
            skills.append(
                {
                    "id": f"representative-{category}",
                    "name": category.replace("_", " ").title(),
                    "category": category,
                    "description": f"Reusable {category} method.",
                    "applicability": {
                        "task_types": ["mathematical_modeling"],
                        "characteristics_any": [],
                        "characteristics_all": [],
                        "query_terms_any": [],
                        "exclusions": [],
                    },
                    "inputs": [{"name": "Data", "description": "Audited input data.", "required": True}],
                    "procedure": [{"action": "Apply method", "purpose": "Produce an auditable result."}],
                    "outputs": [{"name": "Result", "description": "A structured result."}],
                    "validation_requirements": [
                        {"name": "Holdout check", "description": "Verify on held-out data.", "required": True}
                    ],
                    "source_case_ids": case_ids,
                }
            )
        return {"skills": skills}

    def test_representative_time_series_task_selects_core_cross_case_skills(self):
        catalog = ModelingSkillCatalog.load(DEFAULT_CATALOG_PATH)
        profile = ModelingTaskProfile.from_task(
            task_type="mathematical_modeling",
            query="Forecast regional demand and optimize capacity with sensitivity scenarios.",
            columns=("region", "month", "demand", "capacity"),
            shape=(240, 4),
        )

        selected = catalog.select(profile)
        selected_ids = {item.skill_id for item in selected}

        self.assertEqual({item.category for item in selected}, set(SKILL_CATEGORIES))
        self.assertIn("time-aware-feature-engineering", selected_ids)
        self.assertIn("structure-preserving-validation", selected_ids)
        self.assertTrue(all(len(item.skill["source_case_ids"]) >= 2 for item in selected))
        prompt = catalog.render_for_prompt(selected)
        self.assertIn("Validation requirements", prompt)
        self.assertIn("never as evidence or results", prompt)

    def test_general_analysis_does_not_load_or_select_modeling_skills(self):
        catalog, selected = load_runtime_modeling_skills(
            task_type="two_group_small_sample",
            query="Compare the groups",
            columns=("group", "value"),
            shape=(20, 2),
            catalog_path=self._temp_dir() / "missing.json",
        )
        self.assertIsNone(catalog)
        self.assertEqual(selected, ())

    def test_builder_requires_approved_cross_case_evidence_and_all_categories(self):
        directory = self._temp_dir()
        first = self._case_card(directory, "case-a", "Rolling forecast")
        second = self._case_card(directory, "case-b", "Robust optimization")
        captured_prompt: list[str] = []

        def extractor(prompt: str):
            captured_prompt.append(prompt)
            return self._skills(["case-a", "case-b"])

        destination = ModelingSkillBuilder().build([first, second], extractor, directory / "catalog.json")
        catalog = ModelingSkillCatalog.load(destination)

        self.assertEqual(len(catalog.skills), 6)
        self.assertIn("Organize by reusable method", captured_prompt[0])
        self.assertIn("case-a", captured_prompt[0])
        self.assertIn("case-b", captured_prompt[0])

    def test_builder_rejects_a_skill_derived_from_one_paper(self):
        directory = self._temp_dir()
        first = self._case_card(directory, "case-a", "Rolling forecast")
        second = self._case_card(directory, "case-b", "Robust optimization")
        payload = self._skills(["case-a", "case-b"])
        payload["skills"][0]["source_case_ids"] = ["case-a"]

        with self.assertRaisesRegex(ModelingSkillError, "at least two distinct source cases"):
            ModelingSkillBuilder().build([first, second], lambda _prompt: payload, directory / "catalog.json")

    def test_builder_rejects_unapproved_case_cards(self):
        directory = self._temp_dir()
        first = self._case_card(directory, "case-a", "Rolling forecast")
        second = self._case_card(directory, "case-b", "Robust optimization")
        payload = json.loads(second.read_text(encoding="utf-8"))
        payload["review"]["status"] = "pending"
        second.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaisesRegex(ModelingSkillError, "approved and published"):
            ModelingSkillBuilder().build(
                [first, second],
                lambda _prompt: self._skills(["case-a", "case-b"]),
                directory / "catalog.json",
            )


if __name__ == "__main__":
    unittest.main()
