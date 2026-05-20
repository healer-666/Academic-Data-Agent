<div align="center">
<h1>Academic-Data-Agent</h1>

**面向科研与学术场景的结构化数据分析 Agent 工作台**

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](#)

[特点](#-核心特点) · [图览](#-架构图览) · [架构](#-系统架构) · [评测](#公开评测结果) · [快速开始](#-快速开始) · [使用指南](#-使用指南) · [项目结构](#-项目结构)
</div>

## 项目简介

**Academic-Data-Agent** 是一个基于 `hello-agents` 二次开发的数据科学 Agent 项目，主线聚焦 **结构化表格数据分析、可审计报告生成、公开 benchmark 评测和历史结果追问**。

项目不是通用聊天 Agent，而是把科研数据分析流程拆成可运行、可追踪、可审计、可复现的工程闭环：

- 输入 `csv / xls / xlsx` 等结构化表格数据；
- 构建数据上下文，并按需接入 RAG、成功经验和失败教训；
- 通过受控 ReAct 循环调用 Python 完成清洗、统计、建模、绘图和报告；
- 用 execution audit、report contract、artifact validation 和 reviewer 约束输出质量；
- 为公开 benchmark 增加 metric-aware artifact contract，按官方 scorer 要求生成可评分文件；
- 每次运行保存报告、图表、trace、review、run summary 和数据血缘 DAG；
- 支持 DABench、DataSciBench、本地 harness 和 symbolic ablation 评测。

一句话概括：这是一个 **面向数据科学任务的可评分、可审计、可复现实验型 Agent 系统**。

## 公开评测结果

> 说明：DABench 与 DataSciBench 均为 **local reproduction, not leaderboard**。结果来自公开数据与官方或官方风格 scorer 的本地复现实验，不代表官方 leaderboard 提交、官方排名或 SOTA 声明。

| Benchmark | 任务数 | 指标 | 当前结果 | 说明 |
| --- | ---: | --- | ---: | --- |
| 自建回归评测 `seed_v5` | 10 | accepted | 10/10 | 日常回归稳定性检查，外部说服力有限 |
| DABench closed-form dev | 257 | official-style Accuracy by Question | 85.60%-85.94% | 当前公开文件为 257 题，不是网页旧口径 311 题 |
| DABench closed-form dev | 257 | local compatible exact match | 87.16% | 224/257，包含轻微格式归一化 |
| DataSciBench full local reproduction | 222 | official CR | **66.27%** | 官方 scorer 本地复现，222/222 scored，0 unsupported，0 evaluator failed |
| DataSciBench clean ablation `full` | 60 | official CR | **53.12%** | 干净环境固定 60 题消融，禁止任务内 `pip install` |

DataSciBench 222 题分项：

| Task group | Count | Mean CR | CR = 1.0 | CR >= 0.5 |
| --- | ---: | ---: | ---: | ---: |
| bcb | 167 | 76.20% | 122 | 129 |
| csv_excel | 20 | 41.76% | 3 | 9 |
| dl | 10 | 31.67% | 0 | 4 |
| human | 25 | 33.40% | 3 | 8 |

DataSciBench clean 60-task 消融：

| Profile | Mean CR | 95% CI | Scored | Contract pass | Run errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| `full` | **53.12%** | 43.32%-63.13% | 60/60 | 97.73% | 1 |
| `prompt_only` | 50.81% | 40.89%-60.57% | 60/60 | 97.73% | 1 |
| `none` | 50.17% | 40.87%-59.95% | 59/60 | 100.00% | 1 |

消融结论：`full` 相比 `prompt_only` 提升 2.32 个百分点，相比 `none` 提升 2.16 个百分点，但 bootstrap 95% CI 仍跨 0。因此当前应表述为“固定 60 题子集上的正向趋势”，不能表述为显著提升。失败分析显示主要瓶颈已从 artifact/格式问题转向 `calculation_error`。

DataSciBench 公开结果对比：

| System / model | DataSciBench CR | 状态 |
| --- | ---: | --- |
| GPT-4o-2024-05-13 | 68.44% | DataSciBench 公开结果 |
| Academic-Data-Agent | **66.27%** | local reproduction, not leaderboard |
| DeepAnalyze-8B | 66.24% | 公开结果 |
| Deepseek-Coder-33B-Instruct | 61.23% | DataSciBench 公开结果 |
| GPT-4-Turbo | 58.87% | DataSciBench 公开结果 |
| Claude-3.5-Sonnet | 58.11% | DataSciBench 公开结果 |

详细报告：

- [DABench public benchmark report](./docs/dabench_public_benchmark_report.md)
- [DataSciBench formal comparison](./docs/datascibench_formal_comparison_local_reproduction.md)
- [DataSciBench clean ablation report](./docs/datascibench_clean_ablation_20260520.md)
- [DataSciBench scorer readiness notes](./docs/datascibench_official_eval_readiness.md)

## 架构图览

以下图片位于 [`diagrams/`](./diagrams/) 目录，可在 GitHub README 中直接查看。

### 1. 总体六层架构

<img src="./diagrams/01_overall_architecture.png" alt="Academic-Data-Agent 总体六层架构" width="100%">

### 2. 主执行流水线

<img src="./diagrams/02_main_pipeline.png" alt="Academic-Data-Agent 主执行流水线" width="100%">

### 3. Neuro-Symbolic 治理架构

<img src="./diagrams/03_neuro_symbolic.png" alt="Academic-Data-Agent Neuro-Symbolic 治理架构" width="100%">

### 4. RAG 检索子系统

<img src="./diagrams/04_rag_subsystem.png" alt="Academic-Data-Agent RAG 检索子系统" width="100%">

### 5. 记忆子系统

<img src="./diagrams/05_memory_subsystem.png" alt="Academic-Data-Agent 记忆子系统" width="100%">

### 6. 审稿循环与质量模式

<img src="./diagrams/06_review_system.png" alt="Academic-Data-Agent 审稿循环与质量模式" width="100%">

### 7. 评测框架与消融实验

<img src="./diagrams/07_eval_harness.png" alt="Academic-Data-Agent 评测框架与消融实验" width="100%">

### 适用场景

- 科研表格数据的自动清洗、统计分析、图表生成和报告撰写；
- 需要保留完整 trace、图表、审稿记录和运行工件的分析任务；
- 需要围绕历史分析结果继续追问、对比和复盘的项目；
- 需要用公开 benchmark 和固定 eval baseline 验证 Agent 能力的实验型工作。

---

## 核心特点

### 1. 受控 ReAct 分析循环

- analyst 按步骤调用 Python 工具，而不是直接生成不可验证结论；
- 每轮工具调用、观测结果、审稿意见和最终报告都会写入 trace；
- 支持 `draft / standard / publication` 质量模式。

### 2. 面向科研报告的治理链路

- execution audit 检查正式分析是否基于清洗后的全量数据；
- report contract 检查报告结构、统计解释、图表证据和引用覆盖；
- reviewer 对结论边界、证据一致性和报告完整性做二次审查。

### 3. Metric-Aware Artifact Contract

- DataSciBench 适配器读取 `metric.yaml` 中的官方 scorer 需求；
- 对 `csv_excel / human` 任务注入 required artifact 文件名、字段和格式要求；
- 运行后验证 required artifact 是否真实生成，并优先复制给官方 evaluator。

### 4. 数据血缘 DAG

- 每次运行生成 `lineage.json` 和 Mermaid `lineage.mmd`；
- 追踪 raw data、cleaned data、Python step、generated artifact、figure、final report 和 contract metric；
- 适合用于审计、展示和技术报告。

### 5. RAG、Memory 与历史追问

- RAG 提供外部参考资料和证据片段；
- Memory 分层保存成功经验和失败教训；
- History QA 读取历史工件回答追问，不重新执行新的数据分析。

### 6. 评测与消融

- 本地 harness 使用固定 10 题 `seed_v5` 做回归；
- DABench 用于表格数据分析 closed-form 公共评测；
- DataSciBench 接入 HuggingFace GT 与官方 scorer；
- 支持 `full / prompt_only / none` 三组 symbolic profile 消融。

---

## 系统架构

当前系统可理解为六层：

1. **输入与数据上下文层**：读取表格，生成字段、类型、规模、样例和数据质量摘要。
2. **检索与记忆层**：检索外部资料、成功经验和失败教训。
3. **分析执行层**：通过 `run_analysis(...)` 编排 ReAct loop 和 Python 工具。
4. **治理与审计层**：执行 audit、report contract、reviewer、artifact validation 和 lineage。
5. **评测层**：运行本地 harness、DABench、DataSciBench 和 ablation。
6. **展示与追问层**：保存运行工件，并支持历史记录浏览和结果追问。

---

## 快速开始

### 环境要求

- Python 3.10+
- 建议使用虚拟环境

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

在项目根目录创建 `.env` 文件：

```env
LLM_MODEL_ID=mimo-v2.5
LLM_BASE_URL=https://your-llm-endpoint/anthropic
LLM_API_KEY=your_api_key_here
LLM_TIMEOUT=120

# 可选：联网搜索
TAVILY_API_KEY=your_tavily_api_key_here

# 可选：向量检索
EMBEDDING_MODEL_ID=text-embedding-3-small
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=your_embedding_api_key
EMBEDDING_TIMEOUT=120

# 可选：视觉审稿
VISION_LLM_MODEL_ID=your_vision_model
VISION_LLM_BASE_URL=https://your-vision-endpoint/v1
VISION_LLM_API_KEY=your_vision_api_key
VISION_LLM_TIMEOUT=120
```

### 命令行运行

```bash
python main.py --data data/simple_data.xlsx
```

### 启动 Web 工作台

```bash
python gradio_app.py
```

---

## 使用指南

### CLI 常用参数

- `--data`：输入表格路径
- `--output-dir`：运行工件输出目录
- `--query`：用户分析问题
- `--quality-mode`：`draft / standard / publication`
- `--latency-mode`：`auto / quality / fast`
- `--vision-review-mode`：`off / auto / on`

### Python API

```python
from pathlib import Path

from data_analysis_agent.agent_runner import run_analysis

result = run_analysis(
    Path("data/simple_data.xlsx"),
    quality_mode="standard",
    latency_mode="auto",
    use_rag=True,
    use_memory=True,
    memory_scope_key="demo-project",
)

print(result.report_path)
print(result.trace_path)
print(result.review_status)
print(result.lineage_mermaid_path)
```

### 常用评测命令

本地 10 题回归：

```bash
python eval/scripts/run_eval.py --tasks eval/tasks --env-file .env
```

DABench：

```bash
python eval/scripts/run_dabench.py --full-validation --dabench-mode --env-file .env --vision-review-mode off
```

DataSciBench clean 60-task ablation：

```bash
python eval/scripts/run_datascibench_ablation.py \
  --data-root data/external/datascibench_official \
  --hf-root data/external/datascibench_hf \
  --official-root data/external/datascibench_official \
  --run-official-eval \
  --env-file .env \
  --seed 20260519 \
  --max-steps 16 \
  --task-timeout-seconds 900 \
  --block-pip-install
```

### 文档索引

- [DABench public benchmark report](./docs/dabench_public_benchmark_report.md)
- [DataSciBench formal comparison](./docs/datascibench_formal_comparison_local_reproduction.md)
- [DataSciBench clean ablation report](./docs/datascibench_clean_ablation_20260520.md)
- [DataSciBench scorer readiness notes](./docs/datascibench_official_eval_readiness.md)
- [核心代码学习手册](./docs/核心代码学习手册.md)
- [项目主链路拆解](./docs/项目主链路拆解.md)
- [项目改进路线图](./docs/项目改进路线图.md)

---

## 项目结构

```text
.
├── data/                         示例数据与外部 benchmark 数据目录
├── docs/                         技术说明、评测报告与复盘文档
├── eval/                         本地 harness、DABench、DataSciBench 与消融脚本
├── memory/                       外部参考资料、成功经验与失败教训
├── outputs/                      每次分析运行的报告、图表、trace 和 lineage
├── src/
│   └── data_analysis_agent/
│       ├── agent_runner.py       主分析流程与编排入口
│       ├── artifact_service.py   工件落盘与 trace 保存
│       ├── data_context.py       数据上下文构建
│       ├── execution_audit.py    全量数据使用审计
│       ├── lineage.py            数据血缘 DAG 生成
│       ├── report_contract.py    报告契约与返修 brief
│       ├── reporting.py          报告解析与证据覆盖分析
│       ├── rag/                  外部资料检索
│       ├── memory/               成功经验与失败教训
│       └── web/                  Web 工作台相关代码
├── tests/                        单元测试
├── main.py                       CLI 入口
└── README.md
```

---

## 运行产物

每次 `run_analysis(...)` 会在 `outputs/run_YYYYMMDD_HHMMSS/` 下生成独立工件：

```text
outputs/run_YYYYMMDD_HHMMSS/
├── data/
│   └── cleaned_data.csv
├── figures/
├── logs/
│   ├── agent_trace.json
│   ├── lineage.json
│   └── lineage.mmd
├── review_round_1_report.md
└── final_report.md
```

核心可审计信息：

- analyst 每步工具调用与 observation；
- execution audit 与 report contract 结果；
- RAG / memory 检索和写回状态；
- generated artifacts、figures 与 final report；
- lineage DAG 的节点、边和缺失 artifact 统计。

---

## Eval 基线

当前本地 harness 固定 10 个任务：

```text
before_after_paired_measure
correlation_without_causality
memory_constrained_repeat_task
missing_values_by_group
mixed_units_and_dirty_headers
multi_group_with_variance_shift
outlier_sensitive_measurement
reference_guideline_lookup
time_series_trend_clean
two_group_small_sample
```

当前稳定基线：

```text
baseline: seed_v5
task_count: 10
accepted: 10/10
workflow_complete_rate: 1.0
execution_audit_pass_rate: 1.0
review_reject_rate: 0.0
```

---

## 当前边界

- 默认正式输入主线是结构化表格数据，不把 PDF 作为当前主入口；
- 公开 benchmark 结果均为本地复现，不是官方 leaderboard 提交；
- DataSciBench 总分主要由 BCB 代码类任务拉动，`csv_excel / human / dl` 仍是主要改进方向；
- clean ablation 显示 `full` 有正向趋势，但统计显著性不足；
- 当前主要瓶颈是 `calculation_error`，下一步更适合做 metric-aware self-check / retry，而不是继续扩大 prompt 面积。
