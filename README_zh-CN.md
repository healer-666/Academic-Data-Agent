<div align="center">

# 🔬 Academic-Data-Agent

[English](./README.md) | 简体中文

**上传数据、提出问题，获得一份可以复核的分析报告。**

<p>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Data-CSV%20%7C%20Excel%20%7C%20PDF-0F766E?style=flat-square&logo=microsoftexcel&logoColor=white" />
  <img src="https://img.shields.io/badge/Reports-reviewable-16A34A?style=flat-square" />
  <img src="https://img.shields.io/badge/Cases-modeling%20ready-7C3AED?style=flat-square" />
  <img src="https://img.shields.io/badge/Use-Web%20workspace-F97316?style=flat-square" />
</p>

🧭 [项目简介](#overview) · ✨ [主要功能](#features) · ⚡ [快速开始](#quick-start) · 📊 [评测结果](#evaluation) · 🗂️ [目录说明](#structure)

</div>

<a id="overview"></a>

## 🔎 项目简介

Academic-Data-Agent 可以帮助你分析表格数据，而不必自己从头编写完整的分析流程。上传文件并说明你想了解的问题，系统会生成包含图表和结论的结构化报告。

报告不仅可以阅读，也可以复核。对于支持交互的图表和结论，你可以直接查看使用了哪些数据、经过了什么计算，以及结果背后的证据。历史报告会保留在侧边栏中，方便重新打开、继续追问或导出。

适合以下场景：

| 使用场景 | 可以完成什么 |
|---|---|
| 📈 通用数据分析 | 上传 `csv / xls / xlsx` 文件，进行数据清洗、统计、比较、绘图或总结 |
| 🧩 数学建模 | 上传赛题说明和一个或多个数据文件，核对识别出的数据表，并获得参考历史案例的分析方案 |
| 🔍 结果复核 | 从图表或结论直接查看它使用的数据及计算过程 |
| 📚 资料参考 | 在同一个资料库中查看通用本地资料和已经审核的竞赛案例 |
| 💬 历史报告 | 重新打开往期分析、继续追问，并将报告导出为 Markdown 或 PDF |

<a id="features"></a>

## ✨ 主要功能

| 功能 | 作用 |
|---|---|
| 💬 自然语言提问 | 直接描述分析目标，不必先写好完整分析脚本 |
| 📊 图文分析报告 | 获得包含重要发现、分析方法、局限和图表的结构化报告 |
| 🔍 就地复核结果 | 从图表或结论菜单中放大内容、定位数据、查看生成过程或下载图表 |
| 🧩 准备建模工作 | 在确认分析方案前，核对多张数据表及表间关系 |
| 📚 参考已审核案例 | 查看系统匹配了哪些历史案例、为什么匹配，以及可以借鉴哪些思路 |
| 🕘 继续历史任务 | 直接从侧边栏打开往期报告，不必重新运行原分析 |
| 📤 导出报告 | 将最终报告下载为 Markdown 或 PDF |
| 🔐 使用自己的模型 | 在网页中保存并测试兼容的模型连接，然后再开始分析 |

## 🧭 使用流程

```text
首次使用时配置并测试模型连接
      ↓
选择通用数据分析或数学建模
      ↓
上传所需文件并说明分析目标
      ↓
根据页面提示核对数据或分析方案
      ↓
开始分析并等待报告生成
      ↓
复核重要结果并按需导出报告
```

<a id="quick-start"></a>

## ⚡ 快速开始

### 1. 安装依赖

需要准备 Python 3.10 或更高版本，以及 Node.js 和 npm。

克隆仓库并安装 Python 与网页工作区依赖：

```bash
git clone https://github.com/healer-666/Academic-Data-Agent.git
cd Academic-Data-Agent
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

### 2. 配置模型

如果准备使用网页工作区，可以暂时跳过 `.env` 文件：先完成第 4 步，打开网页中的 **模型设置**，然后填写：

- 模型名称；
- 服务 Base URL；
- API Key；
- 请求超时时间。

开始分析前请点击 **测试连接**。只有模型连接发生变化时，才需要重新配置。

如果更习惯使用环境文件，可以在项目根目录创建 `.env`：

```env
LLM_MODEL_ID=your_model
LLM_BASE_URL=https://your-llm-endpoint
LLM_API_KEY=your_api_key
LLM_TIMEOUT=120
```

请勿提交 `.env` 文件，也不要向他人泄露 API Key。

### 3. 从命令行运行

此步骤为可选项，适合希望通过命令行使用的用户：

```bash
python main.py --data data/simple_data.xlsx --query "总结主要规律，并验证重要差异。"
```

### 4. 启动网页工作区

推荐大多数用户使用网页工作区：

```bash
cd frontend
npm run build
cd ..
python web_app.py --host 127.0.0.1 --port 8010
```

在浏览器中打开 `http://127.0.0.1:8010`。

打开页面后：

1. 查看右上角的模型连接状态。
2. 选择 **通用数据分析** 或 **数学建模**。
3. 上传页面要求的文件并输入问题。
4. 核对系统展示的数据资料包或分析方案。
5. 开始分析，然后复核或导出生成的报告。

## 🧰 常用命令行参数

| 参数 | 含义 |
|---|---|
| `--data` | 输入表格文件路径 |
| `--output-dir` | 结果保存目录 |
| `--query` | 希望系统完成的分析问题 |
| `--quality-mode` | 选择快速草稿、均衡的标准报告或经过更多检查的发布级报告 |
| `--latency-mode` | 让系统自动平衡速度和质量，或明确优先其中一项 |
| `--vision-review-mode` | 关闭、开启或自动决定是否检查图表视觉质量 |

## 🧪 Python 调用（可选）

Python 用户也可以直接调用分析流程：

```python
import sys
from pathlib import Path

sys.path.insert(0, "src")
from data_analysis_agent.agent_runner import run_analysis

result = run_analysis(
    Path("data/simple_data.xlsx"),
    query="总结主要规律，并验证重要差异。",
    quality_mode="standard",
)

print(result.report_path)
print(result.workflow_complete)
```

每次运行的结果会保存在 `outputs/run_*/` 下，其中包含报告、清洗后的数据、生成的图表，以及后续复核结果所需的信息。

<a id="evaluation"></a>

## 📊 评测结果

> 以下结果来自本地复现，不代表官方榜单提交、官方排名或 SOTA 声明。
> 日常使用本项目不需要下载这些评测数据集。

| 评测 | 设置 | 指标 | 结果 |
|---|---|---|---:|
| 本地回归 `seed_v5` | 10 个任务 | 通过数 | 10/10 |
| DABench closed-form dev | 257 个任务 | official-style accuracy | 85.60%-85.94% |
| DABench closed-form dev | 257 个任务 | compatible exact match | 87.16% |
| DataSciBench 完整本地复现 | 222 个任务 | official CR | 66.27% |
| DataSciBench clean ablation `full` | 60 个任务 | official CR | 53.12% |

详细报告：

- [DABench 公开评测报告](./docs/dabench_public_benchmark_report.md)
- [DataSciBench 正式对比](./docs/datascibench_formal_comparison_local_reproduction.md)
- [DataSciBench clean ablation 报告](./docs/datascibench_clean_ablation_20260520.md)

<a id="structure"></a>

## 🗂️ 目录说明

```text
.
├── data/                      # 示例数据和项目自带的竞赛案例
├── docs/                      # 使用说明和评测报告
├── frontend/                  # 网页工作区
├── memory/                    # 本地资料和保存的经验
├── outputs/                   # 生成的报告、图表和分析文件
├── main.py                    # 命令行启动入口
└── web_app.py                 # 网页工作区启动入口
```

## 📚 相关文档

- [竞赛经验库](./docs/competition-experience-library.md)
- [数学建模赛题资料工作区](./docs/modeling-problem-workspace.md)
- [数学建模技能](./docs/modeling-skills.md)
- [DABench 公开评测报告](./docs/dabench_public_benchmark_report.md)
- [DataSciBench 正式对比](./docs/datascibench_formal_comparison_local_reproduction.md)

---

<div align="center">
  <sub>让数据分析真正运行、留下证据，并使结果更容易复核。</sub>
</div>
