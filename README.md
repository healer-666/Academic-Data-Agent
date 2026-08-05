<div align="center">

# 🔬 Academic-Data-Agent

**Upload data, ask a question, and receive a report whose results can be checked.**

<p>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Data-CSV%20%7C%20Excel%20%7C%20PDF-0F766E?style=flat-square&logo=microsoftexcel&logoColor=white" />
  <img src="https://img.shields.io/badge/Reports-reviewable-16A34A?style=flat-square" />
  <img src="https://img.shields.io/badge/Cases-modeling%20ready-7C3AED?style=flat-square" />
  <img src="https://img.shields.io/badge/Use-Web%20workspace-F97316?style=flat-square" />
</p>

🧭 [Overview](#overview) · ✨ [Features](#features) · ⚡ [Quick Start](#quick-start) · 📊 [Evaluation](#evaluation) · 🗂️ [Structure](#structure)

</div>

<a id="overview"></a>

## 🔎 Overview

Academic-Data-Agent helps you analyze spreadsheet data without assembling the whole workflow by hand. Upload a file, describe what you want to learn, and the system produces a structured report with charts and conclusions.

The report is designed for review, not just reading. Supported charts and conclusions can be opened to inspect the data used, the calculation process, and the evidence behind the result. Previous reports stay in the sidebar so you can reopen, continue asking questions, or export them later.

It is designed for:

| Use case | What it supports |
|---|---|
| 📈 General data analysis | Upload a `csv / xls / xlsx` file and ask for cleaning, statistics, comparisons, charts, or a written summary |
| 🧩 Mathematical modeling | Upload a problem statement and one or more data files, review the detected tables, and receive a case-inspired analysis plan for confirmation |
| 🔍 Result checking | Open a chart or supported conclusion to see which data and calculation steps produced it |
| 📚 Reference materials | Browse general local materials and reviewed competition cases in one resource library |
| 💬 Previous reports | Reopen earlier analyses, continue asking questions, and export reports as Markdown or PDF |

<a id="features"></a>

## ✨ Features

| Feature | Purpose |
|---|---|
| 💬 Ask in natural language | Describe the analysis goal instead of writing a complete analysis script yourself |
| 📊 Reports with charts | Receive a structured report containing the important findings, methods, limitations, and figures |
| 🔍 Check results in place | Use the menu on a chart or conclusion to enlarge it, locate its data, review how it was produced, or download it |
| 🧩 Prepare modeling work | Review multiple tables and their relationships before accepting a suggested modeling plan |
| 📚 Learn from reviewed cases | See relevant historical cases, why they were selected, and which ideas may be useful for the current problem |
| 🕘 Continue previous work | Open a past report directly from the sidebar without starting the analysis again |
| 📤 Export reports | Download the final report as Markdown or PDF |
| 🔐 Configure your own model | Save and test a compatible model connection from the Web workspace before running an analysis |

## 🧭 Workflow

```text
Configure and test a model connection once
      ↓
Choose general analysis or mathematical modeling
      ↓
Upload the requested files and describe your goal
      ↓
Review the detected data or suggested plan when prompted
      ↓
Start the analysis and wait for the report
      ↓
Check important results in the report and export when ready
```

<a id="quick-start"></a>

## ⚡ Quick Start

### 1. Install dependencies

Clone the repository, then install the Python and Web workspace dependencies:

You need Python 3.10 or newer, plus Node.js and npm.

```bash
git clone https://github.com/healer-666/Academic-Data-Agent.git
cd Academic-Data-Agent
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

### 2. Configure a model

If you plan to use the Web workspace, you can skip the `.env` file: complete Step 4, open **Model Settings**, and enter:

- the model name;
- the service Base URL;
- your API key;
- the request timeout.

Click **Test connection** before starting an analysis. You only need to do this again when the model connection changes.

If you prefer an environment file, create `.env` in the repository root:

```env
LLM_MODEL_ID=your_model
LLM_BASE_URL=https://your-llm-endpoint
LLM_API_KEY=your_api_key
LLM_TIMEOUT=120
```

Do not commit `.env` or share your API key.

### 3. Run from CLI

This step is optional. Use it when you prefer the command line:

```bash
python main.py --data data/simple_data.xlsx --query "Summarize the main patterns and verify the important differences."
```

### 4. Launch the Web workspace

For most users, this is the recommended way to use the project:

```bash
cd frontend
npm run build
cd ..
python web_app.py --host 127.0.0.1 --port 8010
```

Open `http://127.0.0.1:8010` in your browser.

After opening the page:

1. Check the model status in the top-right corner.
2. Choose **General data analysis** or **Mathematical modeling**.
3. Upload the requested files and enter your question.
4. Review any data package or analysis plan shown by the system.
5. Start the analysis, then inspect or export the generated report.

## 🧰 Common Options

| Option | Meaning |
|---|---|
| `--data` | Input table path |
| `--output-dir` | Output directory |
| `--query` | User analysis question |
| `--quality-mode` | Choose a quick draft, a balanced standard report, or a more thoroughly reviewed publication report |
| `--latency-mode` | Let the system balance speed and quality, or explicitly prefer one of them |
| `--vision-review-mode` | Turn visual chart review off, on, or let the system decide |

## 🧪 Python API

Python users can call the analysis workflow directly:

```python
import sys
from pathlib import Path

sys.path.insert(0, "src")
from data_analysis_agent.agent_runner import run_analysis

result = run_analysis(
    Path("data/simple_data.xlsx"),
    query="Summarize the main patterns and verify the important differences.",
    quality_mode="standard",
)

print(result.report_path)
print(result.workflow_complete)
```

Each run is saved under `outputs/run_*/`. This folder contains the report, cleaned data, generated charts, and the information required to review the results later.

<a id="evaluation"></a>

## 📊 Evaluation

> These are local reproduction results, not official leaderboard submissions, official rankings, or SOTA claims.
> You do not need these benchmark datasets for normal use.

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

<a id="structure"></a>

## 🗂️ Structure

```text
.
├── data/                      # Example data and bundled competition cases
├── docs/                      # User guides and evaluation reports
├── frontend/                  # Web workspace
├── memory/                    # Local materials and saved experience
├── outputs/                   # Generated reports, charts, and analysis files
├── main.py                    # Command-line start
└── web_app.py                 # Web workspace start
```

## 📚 Documentation

- [Competition experience library](./docs/competition-experience-library.md)
- [Mathematical modeling problem workspace](./docs/modeling-problem-workspace.md)
- [Modeling skills](./docs/modeling-skills.md)
- [DABench public benchmark report](./docs/dabench_public_benchmark_report.md)
- [DataSciBench formal comparison](./docs/datascibench_formal_comparison_local_reproduction.md)

---

<div align="center">
  <sub>Focused on data-analysis agents that run real code, leave evidence, and make results easier to review.</sub>
</div>
