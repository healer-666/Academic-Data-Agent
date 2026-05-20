from __future__ import annotations

import sys
import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_PATH = PROJECT_ROOT / "eval" / "scripts"
if str(SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_PATH))

import run_datascibench_ablation as ablation  # noqa: E402
from run_datascibench import DataSciBenchTask  # noqa: E402


def _task(task_id: str, group: str) -> DataSciBenchTask:
    return DataSciBenchTask(
        task_id=task_id,
        prompt="prompt",
        data_source_type="1",
        task_group=group,
        prompt_path=Path("data") / task_id / "prompt.json",
        raw_prompt={},
    )


class DataSciBenchAblationTests(unittest.TestCase):
    def test_select_weak_plus_controls_smoke_is_stratified(self):
        tasks = tuple(
            [
                *[_task(f"csv_excel_{index}", "csv_excel") for index in range(5)],
                *[_task(f"human_{index}", "human") for index in range(5)],
                *[
                    DataSciBenchTask(
                        task_id=f"bcb{index}",
                        prompt="prompt",
                        data_source_type="1",
                        task_group="bcb",
                        prompt_path=Path("data") / f"bcb{index}" / "prompt.json",
                        raw_prompt={},
                    )
                    for index in range(6)
                ],
                *[_task(f"dl_{index}", "dl") for index in range(5)],
            ]
        )

        selected = ablation.select_weak_plus_controls(tasks, seed=20260519, smoke=True)
        groups = {task.task_group for task in selected}

        self.assertEqual(groups, {"csv_excel", "human", "bcb", "dl"})
        self.assertEqual(len(selected), 12)

    def test_build_ablation_summary_computes_paired_delta(self):
        profile_runs = {
            profile: {"summary_path": (PROJECT_ROOT / "tool-output" / "missing.json").as_posix()}
            for profile in ablation.PROFILES
        }
        tmp = PROJECT_ROOT / "tool-output" / "test-temp" / "ablation_summary_runner.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(
            '{"completed_rate": 1.0, "run_error_count": 0, "format_failure_count": 0, "artifact_contract_pass_rate": 1.0}',
            encoding="utf-8",
        )
        for value in profile_runs.values():
            value["summary_path"] = tmp.as_posix()
        official_summaries = {
            "full": {"scored_count": 2, "results": [{"id": "a", "official_score_status": "scored", "official_cr": 1.0}, {"id": "b", "official_score_status": "scored", "official_cr": 0.5}]},
            "prompt_only": {"scored_count": 2, "results": [{"id": "a", "official_score_status": "scored", "official_cr": 0.5}, {"id": "b", "official_score_status": "scored", "official_cr": 0.5}]},
            "none": {"scored_count": 2, "results": [{"id": "a", "official_score_status": "scored", "official_cr": 0.0}, {"id": "b", "official_score_status": "scored", "official_cr": 0.5}]},
        }

        summary = ablation.build_ablation_summary(
            profile_runs=profile_runs,
            official_summaries=official_summaries,
            task_ids=["a", "b"],
            seed=20260519,
            smoke=True,
            report_dir=tmp.parent,
        )

        self.assertEqual(summary["profile_metrics"]["full"]["mean_official_cr"], 0.75)
        self.assertEqual(summary["paired_comparisons"]["full_minus_prompt_only"]["mean_delta_cr"], 0.25)
        self.assertIn("full", summary["failure_analysis"])

    def test_build_failure_analysis_groups_failure_reasons(self):
        tmp = PROJECT_ROOT / "tool-output" / "test-temp" / "ablation_failure_runner.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "id": "csv_excel_1",
                            "task_group": "csv_excel",
                            "status": "completed",
                            "format_compliant": True,
                            "required_artifact_count": 1,
                            "artifact_contract_passed": False,
                        },
                        {
                            "id": "human_1",
                            "task_group": "human",
                            "status": "failed",
                            "error": "Task human_1 exceeded timeout of 1 seconds",
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        profile_runs = {"full": {"summary_path": tmp.as_posix()}}
        official_summaries = {
            "full": {
                "results": [
                    {"id": "csv_excel_1", "official_score_status": "scored", "official_cr": 0.0},
                    {"id": "human_1", "official_score_status": "scored", "official_cr": 0.0},
                ]
            }
        }

        analysis = ablation.build_failure_analysis(profile_runs, official_summaries)

        self.assertEqual(analysis["full"]["by_group"]["csv_excel"]["artifact_missing"], 1)
        self.assertEqual(analysis["full"]["by_group"]["human"]["task_timeout"], 1)


if __name__ == "__main__":
    unittest.main()
