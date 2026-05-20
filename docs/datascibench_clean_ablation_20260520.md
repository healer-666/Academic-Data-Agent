# DataSciBench Clean 60-Task Ablation

**Scope:** local reproduction, not leaderboard.

This report records the clean-environment DataSciBench ablation run completed on 2026-05-20. The goal was not to chase a higher headline score, but to produce a reproducible and citable comparison of `full`, `prompt_only`, and `none` symbolic profiles under one fixed environment.

## Run Configuration

| Item | Value |
| --- | --- |
| Benchmark | DataSciBench |
| Task subset | 60 fixed tasks |
| Subset composition | `csv_excel=20`, `human=25`, `bcb=10`, `dl=5` |
| Seed | `20260519` |
| Profiles | `full`, `prompt_only`, `none` |
| Runtime environment | `.conda-datascibench-repro` |
| LLM timeout | `600s` |
| Per-task timeout | `900s` |
| Task-level package install | blocked |
| RAG / memory | disabled |
| Official scorer | enabled |

Source artifacts:

- Ablation summary: `eval/reports/datascibench_clean_ablation/20260520_105932/ablation_summary.json`
- Markdown summary: `eval/reports/datascibench_clean_ablation/20260520_105932/ablation_summary.md`
- Progress log: `eval/reports/datascibench_clean_ablation/20260520_105932/progress.log`

## Main Result

| Profile | Mean CR | 95% CI | Official scored | Contract pass | Run errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| `full` | **53.12%** | 43.32%-63.13% | 60/60 | 97.73% | 1 |
| `prompt_only` | 50.81% | 40.89%-60.57% | 60/60 | 97.73% | 1 |
| `none` | 50.17% | 40.87%-59.95% | 59/60 | 100.00% | 1 |

Paired comparison:

| Comparison | Paired tasks | Mean delta CR | Bootstrap 95% CI |
| --- | ---: | ---: | ---: |
| `full - prompt_only` | 60 | +2.32 pts | -3.60 to +7.98 pts |
| `full - none` | 59 | +2.16 pts | -1.11 to +5.37 pts |

Interpretation: the `full` profile is consistently the best profile in this clean run, but the confidence intervals still cross zero. The correct claim is therefore a positive trend on the fixed 60-task subset, not a statistically significant improvement.

## Failure Analysis

The clean run indicates that the main remaining bottleneck is calculation correctness, not artifact availability or answer formatting.

### `full`

| Group | ok | calculation_error | artifact_missing | format_failure | task_timeout | dependency_error | blocked_pip_install | run_error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `bcb` | 7 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| `csv_excel` | 14 | 5 | 0 | 0 | 0 | 1 | 0 | 0 |
| `dl` | 4 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| `human` | 19 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |

### `prompt_only`

| Group | ok | calculation_error | artifact_missing | format_failure | task_timeout | dependency_error | blocked_pip_install | run_error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `bcb` | 7 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| `csv_excel` | 15 | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| `dl` | 4 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| `human` | 18 | 6 | 0 | 0 | 1 | 0 | 0 | 0 |

### `none`

| Group | ok | calculation_error | artifact_missing | format_failure | task_timeout | dependency_error | blocked_pip_install | run_error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `bcb` | 6 | 3 | 0 | 0 | 1 | 0 | 0 | 0 |
| `csv_excel` | 16 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| `dl` | 4 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| `human` | 20 | 5 | 0 | 0 | 0 | 0 | 0 | 0 |

## Method Notes

- This run used the local official DataSciBench scorer and HuggingFace GT data.
- Task-level package installation was blocked through `ADA_BENCHMARK_BLOCK_PIP_INSTALL=1`.
- The run preserved progress logs, per-profile summaries, official scorer outputs, raw reports, traces, and failure tables under the ignored `eval/reports/` directory.
- Raw benchmark data and generated task artifacts are intentionally not committed.

## Bottom Line

The clean ablation makes the mechanism story more defensible: metric-aware contracts make artifacts highly scorable, while `full` shows a small positive trend over weaker profiles. The current score bottleneck is calculation correctness, so the next technical improvement should focus on metric-aware self-check and retry rather than more prompt formatting.
