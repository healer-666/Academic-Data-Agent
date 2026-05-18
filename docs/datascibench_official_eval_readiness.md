# DataSciBench Official Evaluation Readiness

This note records the current state of the DataSciBench official scoring integration and the full local reproduction runs.

## What Is Integrated

- Official evaluator source: `data/external/datascibench_official/`
- Official prompt/metric layout: `data/{task_id}/prompt.json` and `metric/{task_id}/metric.yaml`
- Academic-Data-Agent output bridge:
  - BigCodeBench-style tasks (`bcb*`) are converted to `{model_id}_outputs.jsonl` and scored with `python -m experiments.evaluate_tmc`.
  - TFC artifact tasks (`csv_excel*`, `human*`, `dl*`) are staged into `data/{task_id}/{model_id}_{run_id}/` and scored with `python -m experiments.evaluate` when `data/{task_id}/gt/` exists.
  - Missing official GT is reported as unsupported, not scored with a custom substitute metric.
- Full-evaluation runner preparation:
  - `run_datascibench.py` now builds a task input manifest from official task files when present.
  - If no task files are available, it falls back to prompt-only execution.
- HuggingFace evaluation data:
  - `download_datascibench_hf.py` downloads `zd21/DataSciBench` into `data/external/datascibench_hf/`.
  - The helper extracts `DataSciBench_GroundTruth_Data.zip` into `data/external/datascibench_hf/extracted_ground_truth/`.
  - The official bridge syncs task source files and GT folders into the local official evaluator tree before scoring.

## Full Local Official Scoring Result

Source agent run:

`eval/reports/datascibench/20260511_131125/eval_datascibench_summary.json`

Official scoring bridge run:

`eval/reports/datascibench_official/20260511_195607/official_eval_summary.json`

| Metric | Value |
| --- | ---: |
| DataSciBench tasks attempted | 222 |
| Agent workflow completed | 221 |
| Agent run errors | 1 |
| Format failures | 0 |
| Average agent duration | 93.83s/task |
| Prepared for official evaluator | 209 |
| Officially scored | 209 |
| Unsupported by bridge | 13 |
| Official evaluator failures | 0 |
| Mean official CR over scored tasks | 0.6769 |
| CR = 1.0 tasks | 117 / 209 |
| CR >= 0.5 tasks | 151 / 209 |

Score breakdown by task family:

| Family | Scored tasks | Mean CR | CR = 1.0 | CR >= 0.5 |
| --- | ---: | ---: | ---: | ---: |
| `bcb` | 154 | 0.7413 | 111 | 116 |
| `csv_excel` | 20 | 0.5047 | 2 | 12 |
| `human` | 25 | 0.5103 | 4 | 16 |
| `dl` | 10 | 0.4458 | 0 | 7 |

Unsupported tasks:

| Reason | Count | Task ids |
| --- | ---: | --- |
| No extractable `task_func` in trace/report | 13 | `bcb102`, `bcb1063`, `bcb238`, `bcb304`, `bcb468`, `bcb527`, `bcb53`, `bcb622`, `bcb646`, `bcb664`, `bcb71`, `bcb891`, `bcb99` |

Interpretation: this is a stronger and more academic benchmark signal than the project-local evaluation set because it uses the public DataSciBench prompts plus official scorer. It is still a local reproduction run, not an official leaderboard submission, and the 13 unsupported tasks should be fixed before using the number as a headline score.

## Unsupported Remediation Result

The 13 unsupported BCB tasks from the first full run were re-run with a stricter BCB query contract that requires a final fenced Python code block containing a complete `def task_func(...):` implementation. The official bridge was also updated to recover `task_func` from later fenced code blocks and mixed trace text.

Source remediation run:

`eval/reports/datascibench/20260517_112847/eval_datascibench_summary.json`

Official remediation scoring run:

`eval/reports/datascibench_official/20260517_113925/official_eval_summary.json`

| Metric | Before remediation | After remediation |
| --- | ---: | ---: |
| DataSciBench tasks attempted | 222 | 222 |
| Officially scored | 209 | 222 |
| Unsupported | 13 | 0 |
| Official evaluator failures | 0 | 0 |
| Mean CR over scored tasks | 0.6769 over 209 | 0.6722 over 222 |
| Conservative full-222 CR | 0.6374 | 0.6722 |
| CR = 1.0 tasks | 117 / 209 | 124 / 222 |
| CR >= 0.5 tasks | 151 / 209 | 159 / 222 |

Remediated task scores:

| Task | Official CR |
| --- | ---: |
| `bcb102` | 1.00 |
| `bcb1063` | 1.00 |
| `bcb238` | 0.00 |
| `bcb304` | 0.00 |
| `bcb468` | 1.00 |
| `bcb527` | 0.75 |
| `bcb53` | 0.00 |
| `bcb622` | 1.00 |
| `bcb646` | 0.00 |
| `bcb664` | 1.00 |
| `bcb71` | 1.00 |
| `bcb891` | 1.00 |
| `bcb99` | 0.00 |

Interpretation: the remediation primarily improves official scoring coverage and the conservative full-set metric. The scored-only mean decreases slightly because the newly recovered tasks average 0.5962 CR, below the previous 209-task scored mean.

## Clean Full Reproduction Result

After the unsupported remediation, a cleaner full 222-task run was executed with explicit progress logging and timeout handling. The base run was interrupted by transient HTTPS EOF failures on 19 tasks, so only those failed tasks were retried and merged for scoring. This is the result currently used in the README and formal comparison report.

Source merged agent run:

`eval/reports/datascibench_clean_merged/20260517_final_plus_retry/eval_datascibench_summary.json`

Official scoring bridge run:

`eval/reports/datascibench_official_clean_retry_v6/20260518_030837/official_eval_summary.json`

| Metric | Value |
| --- | ---: |
| DataSciBench tasks attempted | 222 |
| Base clean one-shot runner | 203 completed / 19 failed |
| Retry repair on failed tasks | 16 recovered / 3 still failed |
| Merged runner result used for scoring | 219 completed / 3 failed |
| Officially scored | 222 |
| Unsupported by bridge | 0 |
| Official evaluator failures | 0 |
| Mean official CR | 0.6627 |
| CR = 1.0 tasks | 128 / 222 |
| CR >= 0.5 tasks | 150 / 222 |

Score breakdown by task family:

| Family | Scored tasks | Mean CR | CR = 1.0 | CR >= 0.5 |
| --- | ---: | ---: | ---: | ---: |
| `bcb` | 167 | 0.7620 | 122 | 129 |
| `csv_excel` | 20 | 0.4176 | 3 | 9 |
| `human` | 25 | 0.3340 | 3 | 8 |
| `dl` | 10 | 0.3167 | 0 | 4 |

Interpretation: this is the strongest current public-benchmark signal for the project. It is still a local reproduction, not a leaderboard submission, and should be reported with that caveat.

## Pilot Official Scoring Result

Source agent run:

`eval/reports/datascibench/20260511_111031/eval_datascibench_summary.json`

Official scoring bridge run:

`eval/reports/datascibench_official/20260511_115020/official_eval_summary.json`

| Metric | Value |
| --- | ---: |
| Pilot tasks | 10 |
| Prepared for official evaluator | 6 |
| Officially scored | 6 |
| Unsupported | 4 |
| Evaluator failures | 0 |

Scored `bcb*` task CR values:

| Task | Official evaluator | CR |
| --- | --- | ---: |
| `bcb198` | `evaluate_tmc` | 1.0 |
| `bcb42` | `evaluate_tmc` | 1.0 |
| `bcb50` | `evaluate_tmc` | 0.0 |
| `bcb646` | `evaluate_tmc` | 0.0 |
| `bcb690` | `evaluate_tmc` | 1.0 |
| `bcb983` | `evaluate_tmc` | 1.0 |

Unsupported pilot tasks:

| Task | Reason |
| --- | --- |
| `bcb579` | No extractable `task_func` implementation in trace/report |
| `csv_excel_1` | Missing HuggingFace `gt` directory |
| `csv_excel_41` | Missing HuggingFace `gt` directory |
| `dl_10` | Missing HuggingFace `gt` directory |

## HuggingFace Data

To score non-BCB TFC tasks, download the HuggingFace evaluation data into:

`data/external/datascibench_hf/`

Authenticated download helper:

```powershell
$env:HF_TOKEN = "<your HuggingFace token with dataset access>"
& 'D:\anaconda\envs\agent_env\python.exe' eval\scripts\download_datascibench_hf.py --output-dir data\external\datascibench_hf
```

The helper accepts either an interactive `huggingface-cli login` session or an explicit `HF_TOKEN`.

## Commands

Prepare or score an existing Academic-Data-Agent run:

```powershell
& 'D:\anaconda\envs\agent_env\python.exe' eval\scripts\prepare_datascibench_official_eval.py `
  --summary eval\reports\datascibench\20260511_131125\eval_datascibench_summary.json `
  --official-root data\external\datascibench_official `
  --hf-root data\external\datascibench_hf `
  --run-official-eval `
  --python-executable 'D:\anaconda\envs\agent_env\python.exe' `
  --timeout-seconds 300
```

Run the full 222-task DataSciBench set after official data is in place:

```powershell
& 'D:\anaconda\envs\agent_env\python.exe' eval\scripts\run_datascibench.py `
  --data-root data\external\datascibench_official `
  --sample-size 0 `
  --task-group all `
  --data-source-type all `
  --env-file .env `
  --task-retries 0 `
  --max-steps 16 `
  --quality-mode draft `
  --latency-mode quality `
  --vision-review-mode off
```

Then pass the generated `eval_datascibench_summary.json` into `prepare_datascibench_official_eval.py`.

## Full Evaluation Gate

Completed gates:

1. HuggingFace GT was downloaded with an authenticated CLI session.
2. A 10-task mixed pilot with official GT scored all selected `csv_excel`, `human`, and `dl` tasks.
3. The official bridge now scores 222/222 tasks with 0 unsupported and 0 evaluator failures.
4. The latest clean local reproduction reports 66.27% mean official CR.

Remaining cleanup before publishing:

1. Treat the current number as local reproduction, not leaderboard.
2. Investigate low-scoring `csv_excel`, `human`, and `dl` tasks before optimizing for another headline run.
3. Keep raw official data, raw reports, and generated task artifacts out of git.
