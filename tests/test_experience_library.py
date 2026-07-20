from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.experience_library import (
    DEFAULT_BUNDLED_ROOT,
    ExperienceLibraryError,
    ExperienceLibraryManager,
    build_experience_package,
)


class ExperienceLibraryTests(unittest.TestCase):
    def _temp_dir(self) -> Path:
        path = PROJECT_ROOT / "tool-output" / "test-temp" / f"experience_library_{uuid.uuid4().hex}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _content(self, root: Path, *, include_case: bool = False) -> Path:
        content = root / "content"
        (content / "skills").mkdir(parents=True)
        (content / "indexes").mkdir(parents=True)
        shutil.copy2(PROJECT_ROOT / "data" / "modeling_skills" / "catalog.json", content / "skills" / "catalog.json")
        (content / "indexes" / "keyword_index.json").write_text('{"chunks": []}\n', encoding="utf-8")
        if include_case:
            (content / "cases").mkdir(parents=True)
            (content / "cases" / "case-a.json").write_text('{"case": {"id": "case-a"}}\n', encoding="utf-8")
        return content

    def _sources(self) -> list[dict[str, str]]:
        return [
            {
                "id": "fixture-a",
                "title": "Reviewed representative fixture",
                "kind": "case_card",
                "license": "test-only",
                "uri": "https://example.test/case-a",
            }
        ]

    def _package(self, root: Path, version: str, *, status: str = "preview", include_case: bool = False) -> Path:
        return build_experience_package(
            self._content(root, include_case=include_case),
            root / f"experience-{version}.zip",
            version=version,
            content_status=status,
            sources=self._sources(),
            published_at="2026-07-20T00:00:00Z",
        )

    def test_bundled_preview_is_available_without_user_import(self):
        resolution = ExperienceLibraryManager(self._temp_dir() / "install", DEFAULT_BUNDLED_ROOT).resolve()

        self.assertEqual(resolution.status, "bundled")
        self.assertEqual(resolution.version, "0.1.0-preview")
        self.assertEqual(resolution.content_status, "preview")
        self.assertTrue(resolution.skill_catalog_path.is_file())
        self.assertTrue(resolution.keyword_index_path.is_file())
        self.assertEqual(resolution.case_card_paths, ())

    def test_install_upgrade_and_rollback_preserve_versions_and_user_data(self):
        root = self._temp_dir()
        install_root = root / "builtin-library"
        user_knowledge = root / "user-knowledge" / "notes.md"
        user_knowledge.parent.mkdir(parents=True)
        user_knowledge.write_text("my private notes", encoding="utf-8")
        first = self._package(root / "first", "1.0.0", status="curated", include_case=True)
        second = self._package(root / "second", "1.1.0", status="curated", include_case=True)
        manager = ExperienceLibraryManager(install_root, bundled_root=None)

        manager.install(first)
        upgraded = manager.install(second)

        self.assertEqual(upgraded.version, "1.1.0")
        self.assertEqual(manager.installed_versions(), ("1.1.0", "1.0.0"))
        rolled_back = manager.activate("1.0.0")
        self.assertEqual(rolled_back.version, "1.0.0")
        self.assertEqual(manager.resolve().version, "1.0.0")
        self.assertEqual(user_knowledge.read_text(encoding="utf-8"), "my private notes")

    def test_corrupted_active_version_degrades_without_raising(self):
        root = self._temp_dir()
        manager = ExperienceLibraryManager(root / "install", bundled_root=None)
        installed = manager.install(self._package(root / "package", "1.0.0"))
        installed.skill_catalog_path.write_text("corrupted", encoding="utf-8")

        resolution = manager.resolve()

        self.assertEqual(resolution.status, "degraded")
        self.assertFalse(resolution.usable)
        self.assertIn("integrity check", resolution.warnings[0])

    def test_missing_library_degrades_to_general_analysis(self):
        resolution = ExperienceLibraryManager(self._temp_dir() / "missing", bundled_root=None).resolve()
        self.assertEqual(resolution.status, "degraded")
        self.assertIsNone(resolution.skill_catalog_path)
        self.assertIn("general analysis", resolution.warnings[0])

    def test_curated_package_requires_at_least_one_case_card(self):
        root = self._temp_dir()
        with self.assertRaisesRegex(ExperienceLibraryError, "case_card"):
            self._package(root, "1.0.0", status="curated", include_case=False)

    def test_install_rejects_archive_path_traversal(self):
        root = self._temp_dir()
        package = root / "unsafe.zip"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("../outside.txt", "unsafe")

        with self.assertRaisesRegex(ExperienceLibraryError, "Unsafe"):
            ExperienceLibraryManager(root / "install", bundled_root=None).install(package)
        self.assertFalse((root / "outside.txt").exists())


if __name__ == "__main__":
    unittest.main()
