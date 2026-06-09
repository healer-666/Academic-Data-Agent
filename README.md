<div align="center">

# 🔬 Academic-Data-Agent

**面向科研与学术场景的结构化数据分析 Agent 工作台**

<p>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Data-CSV%20%7C%20XLS%20%7C%20XLSX-0F766E?style=flat-square&logo=microsoftexcel&logoColor=white" />
  <img src="https://img.shields.io/badge/RAG-enabled-16A34A?style=flat-square" />
  <img src="https://img.shields.io/badge/Workflow-auditable-7C3AED?style=flat-square" />
  <img src="https://img.shields.io/badge/UI-Gradio-F97316?style=flat-square" />
</p>

🧭 [项目简介](#overview) · ✨ [核心能力](#features) · ⚡ [快速开始](#quick-start) · 📊 [评测结果](#evaluation) · 🗂️ [项目结构](#structure)

</div>

<a id="overview"></a>

## 🔎 项目简介

Academic-Data-Agent 是一个面向结构化表格数据的科研分析 Agent。它不是通用聊天机器人，而是把一次数据分析拆成可执行、可追踪、可审计的工程流程：读取数据、清洗统计、调用 Python、生成图表和报告，并留下运行轨迹与审稿记录。

适合用来做：

| 场景 | 说明 |
|---|---|
| 📈 学术数据分析 | 对 `csv / xls / xlsx` 表格做清洗、统计、绘图和报告 |
| 🧾 可复盘分析 | 保存 trace、review、run summary、lineage 等运行证据 |
| 🧪 Benchmark 评测 | 支持本地 DABench / DataSciBench 风格评测与消融 |
| 💬 历史追问 | 基于历史运行结果继续提问，避免每次从零分析 |

<p align="center">
  <img src="diagrams/01_overall_architecture.png" width="760" alt="Academic-Data-Agent architecture">
</p>

<a id="features"></a>

## ✨ 核心能力

| 能力 | 作用 |
|---|---|
| 🧭 受控 ReAct 分析循环 | 通过 Python 工具完成清洗、统计、绘图和报告，而不是直接生成不可验证结论 |
| 🛡️ 执行审计 | 检查正式分析是否基于全量清洗后数据，减少“只看摘要就下结论”的风险 |
| 📑 Report Contract | 约束报告结构、统计解释、图表证据和输出 artifact |
| 🔎 RAG 与 Memory | 检索外部资料、成功经验和失败教训，支持历史结果追问 |
| 🕸️ Lineage DAG | 记录 raw data、cleaned data、Python steps、figures、reports 和 metrics 的关系 |
| 📊 本地评测 | 提供 regression harness、DABench、DataSciBench 和 symbolic ablation 入口 |

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

## ⚡ 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 `.env`

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

### 3. 命令行运行

```bash
python main.py --data data/simple_data.xlsx
```

### 4. 启动 Web 工作台

```bash
python gradio_app.py
```

## 🧰 常用参数

| 参数 | 说明 |
|---|---|
| `--data` | 输入表格路径 |
| `--output-dir` | 输出目录 |
| `--query` | 用户分析问题 |
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

## 📊 评测结果

> 说明：以下结果为 local reproduction，不代表官方 leaderboard 提交、官方排名或 SOTA 声明。

| Benchmark | 设置 | 指标 | 结果 |
|---|---|---|---:|
| Local regression `seed_v5` | 10 tasks | accepted | 10/10 |
| DABench closed-form dev | 257 tasks | official-style accuracy | 85.60%-85.94% |
| DABench closed-form dev | 257 tasks | compatible exact match | 87.16% |
| DataSciBench full local reproduction | 222 tasks | official CR | 66.27% |
| DataSciBench clean ablation `full` | 60 tasks | official CR | 53.12% |

更多细节：

- [DABench public benchmark report](./docs/dabench_public_benchmark_report.md)
- [DataSciBench formal comparison](./docs/datascibench_formal_comparison_local_reproduction.md)
- [DataSciBench clean ablation report](./docs/datascibench_clean_ablation_20260520.md)
- [DataSciBench scorer readiness notes](./docs/datascibench_official_eval_readiness.md)

<a id="structure"></a>

## 🗂️ 项目结构

```text
.
├── src/data_analysis_agent/   # Core agent workflow
├── eval/                      # Evaluation scripts and tasks
├── docs/                      # Reports, notes, and benchmark writeups
├── diagrams/                  # Architecture diagrams
├── data/                      # Example and external data
├── memory/                    # Stored experience and history
├── main.py                    # CLI entrypoint
└── gradio_app.py              # Web workspace
```

## 📚 相关文档

- [核心代码学习手册](./docs/核心代码学习手册.md)
- [项目主链路拆解](./docs/项目主链路拆解.md)
- [项目改进路线图](./docs/项目改进路线图.md)

---

<div align="center">
  <sub>Focused on data-analysis agents that run real code, leave evidence, and make results easier to review.</sub>
</div>
