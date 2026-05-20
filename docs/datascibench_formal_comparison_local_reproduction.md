# DataSciBench Formal Comparison

**Scope:** local reproduction, not leaderboard.

This report uses a clean local DataSciBench run produced on 2026-05-17/18. It should not be described as an official leaderboard submission because the run uses the local Academic-Data-Agent harness, local environment fixes, and retry repair for transient HTTPS EOF failures.

Update on 2026-05-20: a separate clean 60-task `full / prompt_only / none` ablation was completed in `.conda-datascibench-repro` with task-level package installation blocked. That ablation is not a replacement for the 222-task headline run; it is the mechanism-comparison experiment used to support claims about metric-aware contracts and symbolic profiles. See `docs/datascibench_clean_ablation_20260520.md`.

## Run Summary

| Item | Value |
| --- | ---: |
| Benchmark | DataSciBench |
| Task count | 222 |
| Base clean one-shot runner | 203 completed / 19 failed |
| Retry repair on failed tasks | 16 recovered / 3 still failed |
| Merged runner result used for scoring | 219 completed / 3 failed |
| Official scorer prepared | 222 |
| Official scorer scored | 222 |
| Unsupported | 0 |
| Evaluator failed | 0 |
| Mean official CR | **66.27%** |
| CR = 1.0 count | 128 / 222 |
| CR >= 0.5 count | 150 / 222 |

Source artifacts:

- Runner summary: `eval/reports/datascibench_clean_merged/20260517_final_plus_retry/eval_datascibench_summary.json`
- Official scorer summary: `eval/reports/datascibench_official_clean_retry_v6/20260518_030837/official_eval_summary.json`
- Progress helper: `eval/scripts/show_datascibench_progress.py`

## Capability Breakdown

| Task group | Count | Mean CR | CR = 1.0 | CR >= 0.5 |
| --- | ---: | ---: | ---: | ---: |
| bcb | 167 | **76.20%** | 122 | 129 |
| csv_excel | 20 | 41.76% | 3 | 9 |
| dl | 10 | 31.67% | 0 | 4 |
| human | 25 | 33.40% | 3 | 8 |

Interpretation: the current project is strongest on BigCodeBench-style code/function tasks. The main weakness is non-code data science workflow execution, especially human-written open-ended tasks and deep-learning tasks.

## Public Comparison

| System / model | Reported DataSciBench CR | Source / status |
| --- | ---: | --- |
| GPT-4o-2024-05-13 | 68.44% | DataSciBench paper/public table |
| **Academic-Data-Agent** | **66.27%** | **local reproduction, not leaderboard** |
| DeepAnalyze-8B | 66.24% | DeepAnalyze public summary |
| Deepseek-Coder-33B-Instruct | 61.23% | DataSciBench paper/public table |
| GPT-4-Turbo | 58.87% | DataSciBench paper/public table |
| Claude-3.5-Sonnet | 58.11% | DataSciBench paper/public table |
| GPT-4o-mini | 57.78% | DataSciBench paper/public table |
| Qwen2.5-Coder-7B-Instruct | 53.11% | DataSciBench paper/public table |
| Qwen2.5-7B-Instruct | 50.74% | DataSciBench paper/public table |
| o1-mini | 45.26% | DataSciBench paper/public table |

Sources:

- DataSciBench paper/public table: https://openreview.net/forum?id=BltaWJZMeR and https://arxiv.org/abs/2502.13897
- DataSciBench GitHub: https://github.com/THUDM/DataSciBench
- DeepAnalyze summary: https://www.aimodels.fyi/papers/arxiv/deepanalyze-agentic-large-language-models-autonomous-data

## Method Notes

The formal number above is **66.27% CR**. A previous intermediate scorer run produced **69.74% CR**, but that number is discarded because the adapter searched globally under the workspace and could copy stale artifacts from old runs into failed tasks. The scorer was fixed to use only the current record's `run_dir`, `raw_report_path`, and `trace_path`, and stale official result files are deleted before each per-task scoring call.

The agent run itself used a clean conda environment before scorer-specific MetaGPT dependencies were installed. MetaGPT was installed only for the official TFC evaluator, because the official evaluator imports `metagpt` even when no LLM call is needed.

## Bottom Line

The result is competitive with published DataSciBench baselines, roughly between GPT-4o and DeepAnalyze-8B on overall CR, but it is not a leaderboard claim. The score is carried by strong BCB performance; improving `csv_excel`, `human`, and `dl` execution should be the next optimization target.

## Clean 60-Task Ablation Addendum

The clean ablation uses a fixed 60-task subset (`csv_excel=20`, `human=25`, `bcb=10`, `dl=5`) and compares three symbolic profiles under the same clean environment.

| Profile | Mean CR | 95% CI | Official scored | Contract pass | Run errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| `full` | **53.12%** | 43.32%-63.13% | 60/60 | 97.73% | 1 |
| `prompt_only` | 50.81% | 40.89%-60.57% | 60/60 | 97.73% | 1 |
| `none` | 50.17% | 40.87%-59.95% | 59/60 | 100.00% | 1 |

Paired deltas:

| Comparison | Paired tasks | Mean delta CR | Bootstrap 95% CI |
| --- | ---: | ---: | ---: |
| `full - prompt_only` | 60 | +2.32 pts | -3.60 to +7.98 pts |
| `full - none` | 59 | +2.16 pts | -1.11 to +5.37 pts |

Interpretation: `full` is the best profile in the clean run, but the confidence intervals cross zero. This should be described as a positive trend, not a statistically significant improvement. Failure analysis shows that the dominant remaining failure type is `calculation_error`, not artifact missing or format failure.
