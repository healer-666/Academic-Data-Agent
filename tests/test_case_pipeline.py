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

from data_analysis_agent.case_pipeline import CasePipeline, CasePipelineError


class CasePipelineTests(unittest.TestCase):
    def _case_dir(self) -> Path:
        path = PROJECT_ROOT / "tool-output" / "test-temp" / f"case_pipeline_{uuid.uuid4().hex}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _fixture(self) -> tuple[Path, dict[str, object]]:
        case_dir = self._case_dir()
        (case_dir / "problem.md").write_text(
            "# Problem A\nForecast demand and optimize capacity from the supplied tables.",
            encoding="utf-8",
        )
        (case_dir / "data.csv").write_text("month,demand\n1,10\n2,13\n3,15\n", encoding="utf-8")
        (case_dir / "paper.md").write_text(
            "# Methods\nA high-quality prior solution used rolling validation and residual plots.",
            encoding="utf-8",
        )
        manifest = case_dir / "manifest.yaml"
        manifest.write_text(
            """schema_version: "1.0"
case:
  id: demo-2024-a
  competition: Demo Modeling Contest
  year: 2024
  problem_number: A
  title: Demand and capacity planning
sources:
  - id: problem
    role: problem_statement
    title: Official problem A
    path: problem.md
    url: https://example.test/problem
    license: citation-only
  - id: data
    role: dataset
    title: Official data
    path: data.csv
    url: https://example.test/data
    license: citation-only
  - id: paper
    role: paper
    title: Reviewed solution
    path: paper.md
    url: https://example.test/paper
    license: citation-only
""",
            encoding="utf-8",
        )
        extraction: dict[str, object] = {
            "problem_summary": "Forecast demand and choose capacity using the provided time-indexed data.",
            "data_operations": [
                {"name": "Time ordering", "purpose": "Build a chronological series.", "evidence_source_ids": ["data"]}
            ],
            "models": [
                {
                    "name": "Forecast model",
                    "purpose": "Estimate future demand.",
                    "assumptions": ["Past structure remains informative."],
                    "evidence_source_ids": ["paper", "data"],
                }
            ],
            "validation_methods": [
                {"name": "Rolling validation", "purpose": "Respect temporal order.", "evidence_source_ids": ["paper"]}
            ],
            "charts": [
                {"name": "Residual plot", "purpose": "Inspect model error.", "evidence_source_ids": ["paper"]}
            ],
            "key_findings": [
                {
                    "statement": "The historical solution recommends time-aware validation.",
                    "evidence_source_ids": ["paper"],
                    "raw_excerpt": "This field must never cross the structured interface.",
                }
            ],
            "limitations": ["Historical findings must not be reused as current results."],
        }
        return manifest, extraction

    def test_generate_links_required_sources_and_keeps_raw_paths_private(self):
        manifest, extraction = self._fixture()
        captured_prompt: list[str] = []

        def extractor(prompt: str):
            captured_prompt.append(prompt)
            return extraction

        result = CasePipeline(manifest.parent / "workspace").generate(manifest, extractor)
        payload = json.loads(result.artifact_path.read_text(encoding="utf-8"))

        self.assertEqual(result.status, "draft")
        self.assertEqual(payload["case"]["competition"], "Demo Modeling Contest")
        self.assertEqual(payload["case"]["year"], 2024)
        self.assertEqual(payload["case"]["problem_number"], "A")
        self.assertEqual({source["role"] for source in payload["sources"]}, {"problem_statement", "dataset", "paper"})
        self.assertTrue(all("path" not in source for source in payload["sources"]))
        self.assertEqual(len(payload["_private_provenance"]["local_sources"]), 3)
        self.assertIn("<source id=\"paper\">", captured_prompt[0])

    def test_review_applies_correction_and_publish_removes_private_provenance(self):
        manifest, extraction = self._fixture()
        pipeline = CasePipeline(manifest.parent / "workspace")
        draft = pipeline.generate(manifest, lambda _prompt: extraction)
        reviewed = pipeline.review(
            draft.artifact_path,
            decision="approved",
            reviewer="maintainer-a",
            notes="Checked against the cited source.",
            corrections={"problem_summary": "Corrected, concise problem summary."},
        )
        published = pipeline.publish(reviewed.artifact_path, manifest.parent / "library")
        payload = json.loads(published.artifact_path.read_text(encoding="utf-8"))
        serialized = published.artifact_path.read_text(encoding="utf-8")

        self.assertEqual(payload["extraction"]["problem_summary"], "Corrected, concise problem summary.")
        self.assertEqual(payload["review"]["status"], "approved")
        self.assertNotIn("_private_provenance", payload)
        self.assertNotIn(manifest.parent.as_posix(), serialized)
        self.assertNotIn("Forecast demand and optimize capacity", serialized)
        self.assertNotIn("raw_excerpt", serialized)
        self.assertEqual(payload["sources"][0]["distribution"], "metadata_only")

    def test_regeneration_is_immutable_and_increments_revision(self):
        manifest, extraction = self._fixture()
        pipeline = CasePipeline(manifest.parent / "workspace")
        first = pipeline.generate(manifest, lambda _prompt: extraction)
        second = pipeline.generate(manifest, lambda _prompt: extraction)

        self.assertEqual(first.revision, 1)
        self.assertEqual(second.revision, 2)
        self.assertTrue(first.artifact_path.exists())
        second_payload = json.loads(second.artifact_path.read_text(encoding="utf-8"))
        self.assertEqual(second_payload["previous_revision"], 1)

    def test_publish_rejects_unreviewed_or_rejected_artifacts(self):
        manifest, extraction = self._fixture()
        pipeline = CasePipeline(manifest.parent / "workspace")
        draft = pipeline.generate(manifest, lambda _prompt: extraction)
        rejected = pipeline.review(draft.artifact_path, decision="rejected", reviewer="maintainer-a")

        with self.assertRaises(CasePipelineError):
            pipeline.publish(draft.artifact_path, manifest.parent / "library")
        with self.assertRaises(CasePipelineError):
            pipeline.publish(rejected.artifact_path, manifest.parent / "library")

    def test_unknown_evidence_source_is_rejected(self):
        manifest, extraction = self._fixture()
        extraction["charts"][0]["evidence_source_ids"] = ["invented-source"]

        with self.assertRaisesRegex(CasePipelineError, "unknown sources"):
            CasePipeline(manifest.parent / "workspace").generate(manifest, lambda _prompt: extraction)

    def test_manifest_requires_problem_data_and_paper_sources(self):
        manifest, extraction = self._fixture()
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(text.replace("role: paper", "role: note"), encoding="utf-8")

        with self.assertRaisesRegex(CasePipelineError, "paper"):
            CasePipeline(manifest.parent / "workspace").generate(manifest, lambda _prompt: extraction)

    def test_manifest_requires_explicit_citation_and_license(self):
        manifest, extraction = self._fixture()
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(text.replace("    url: https://example.test/problem\n", ""), encoding="utf-8")

        with self.assertRaisesRegex(CasePipelineError, "url"):
            CasePipeline(manifest.parent / "workspace").generate(manifest, lambda _prompt: extraction)


if __name__ == "__main__":
    unittest.main()
