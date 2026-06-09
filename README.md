<div align="center">

# 🔬 Academic-Data-Agent

**An auditable data-analysis agent workspace for structured research datasets.**

<p>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Data-CSV%20%7C%20XLS%20%7C%20XLSX-0F766E?style=flat-square&logo=microsoftexcel&logoColor=white" />
  <img src="https://img.shields.io/badge/RAG-enabled-16A34A?style=flat-square" />
  <img src="https://img.shields.io/badge/Workflow-auditable-7C3AED?style=flat-square" />
  <img src="https://img.shields.io/badge/UI-Gradio-F97316?style=flat-square" />
</p>

🧭 [Overview](#overview) · ✨ [Features](#features) · ⚡ [Quick Start](#quick-start) · 📊 [Evaluation](#evaluation) · 🗂️ [Structure](#structure)

</div>

<a id="overview"></a>

## 🔎 Overview

Academic-Data-Agent is a research-oriented agent system for structured tabular data. It is not a general chat agent. It turns a data-analysis task into an inspectable workflow: read the dataset, build data context, run Python analysis, generate charts and reports, and save traces for later review.

It is designed for:

| Use case | What it supports |
|---|---|
| 📈 Academic data analysis | Cleaning, statistics, plotting, and reporting for `csv / xls / xlsx` files |
| 🧾 Reproducible runs | Saved traces, reviews, run summaries, and lineage records |
| 🧪 Benchmark evaluation | Local DABench / DataSciBench-style evaluation and ablation workflows |
| 💬 History Q&A | Follow-up questions over previous run artifacts without restarting from scratch |

<a id="features"></a>

## ✨ Features

| Feature | Purpose |
|---|---|
| 🧭 Controlled ReAct loop | Runs Python tools for cleaning, statistics, plotting, and reporting instead of producing unverifiable conclusions |
| 🛡️ Execution audit | Checks whether formal analysis is based on the full cleaned dataset |
| 📑 Report contract | Constrains report structure, statistical interpretation, chart evidence, and output artifacts |
| 🔎 RAG and memory | Retrieves external references, successful patterns, and failure lessons |
| 🕸️ Lineage DAG | Records relationships among raw data, cleaned data, Python steps, figures, reports, and metrics |
| 📊 Local evaluation | Provides regression harness, DABench, DataSciBench, and symbolic ablation entry points |

## 🧭 Workflow

```text
Upload table
      ↓
Build data context
      ↓
Retrieve references and memory
      ↓
Run controlled Python analysis
      ↓
Audit, review, and validate artifacts
      ↓
Save report, charts, trace, and lineage
```

<a id="quick-start"></a>

## ⚡ Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure `.env`

```env
LLM_MODEL_ID=your_model
LLM_BASE_URL=https://your-llm-endpoint
LLM_API_KEY=your_api_key
LLM_TIMEOUT=120

# optional
TAVILY_API_KEY=your_tavily_api_key
EMBEDDING_MODEL_ID=text-embedding-3-small
EMBEDDING_API_KEY=your_embedding_key
```

### 3. Run from CLI

```bash
python main.py --data data/simple_data.xlsx
```

### 4. Launch the Web workspace

```bash
python gradio_app.py
```

## 🧰 Common Options

| Option | Meaning |
|---|---|
| `--data` | Input table path |
| `--output-dir` | Output directory |
| `--query` | User analysis question |
| `--quality-mode` | `draft / standard / publication` |
| `--latency-mode` | `auto / quality / fast` |
| `--vision-review-mode` | `off / auto / on` |

## 🧪 Python API

```python
from pathlib import Path
from data_analysis_agent.agent_runner import run_analysis

result = run_analysis(
    Path("data/simple_data.xlsx"),
    quality_mode="standard",
    latency_mode="auto",
    use_rag=True,
    use_memory=True,
)

print(result.report_path)
print(result.trace_path)
print(result.review_status)
```

<a id="evaluation"></a>

## 📊 Evaluation

> These are local reproduction results, not official leaderboard submissions, official rankings, or SOTA claims.

| Benchmark | Setting | Metric | Result |
|---|---|---|---:|
| Local regression `seed_v5` | 10 tasks | accepted | 10/10 |
| DABench closed-form dev | 257 tasks | official-style accuracy | 85.60%-85.94% |
| DABench closed-form dev | 257 tasks | compatible exact match | 87.16% |
| DataSciBench full local reproduction | 222 tasks | official CR | 66.27% |
| DataSciBench clean ablation `full` | 60 tasks | official CR | 53.12% |

Detailed reports:

- [DABench public benchmark report](./docs/dabench_public_benchmark_report.md)
- [DataSciBench formal comparison](./docs/datascibench_formal_comparison_local_reproduction.md)
- [DataSciBench clean ablation report](./docs/datascibench_clean_ablation_20260520.md)
- [DataSciBench scorer readiness notes](./docs/datascibench_official_eval_readiness.md)

<a id="structure"></a>

## 🗂️ Structure

```text
.
├── src/data_analysis_agent/   # Core agent workflow
├── eval/                      # Evaluation scripts and tasks
├── docs/                      # Reports, notes, and benchmark writeups
├── diagrams/                  # Diagram prompts and notes
├── data/                      # Example and external data
├── memory/                    # Stored experience and history
├── main.py                    # CLI entrypoint
└── gradio_app.py              # Web workspace
```

## 📚 Documentation

- [Agent runner reading map](./docs/agent_runner_reading_map.md)
- [DABench public benchmark report](./docs/dabench_public_benchmark_report.md)
- [DataSciBench formal comparison](./docs/datascibench_formal_comparison_local_reproduction.md)

---

<div align="center">
  <sub>Focused on data-analysis agents that run real code, leave evidence, and make results easier to review.</sub>
</div>
