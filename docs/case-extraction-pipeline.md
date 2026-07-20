# 往届竞赛案例提炼流水线

这条流程只供项目维护者离线生产竞赛经验库。普通用户不需要、也不应该上传往届赛题、往届数据或论文原文。普通用户最终只会接触已审核的结构化案例卡片和来源引用。

## 产物状态

```text
私有来源清单 → 草稿 revision-001 → 人工审核/修正 → approved → 公开案例卡片
                         ↘ rejected → 修改清单或提示后重新生成 revision-002
```

- `drafts/`：不可变的模型提炼草稿。每次生成都会增加 revision，旧稿保留。
- `reviews/`：审核记录。审核者可用 JSON 修正提炼字段，再选择 `approved` 或 `rejected`。
- 发布目录：只包含通过审核的结构化字段、来源元数据、哈希和引用地址。
- 原始文件：始终留在清单指定的位置，不复制到工作区，也不进入发布产物。

## 1. 准备私有清单

复制 [`examples/modeling_cases/manifest.example.yaml`](../examples/modeling_cases/manifest.example.yaml)，填写比赛、年份、题号、赛题标题和三类必需来源：

- `problem_statement`：官方赛题；
- `dataset`：官方数据；
- `paper`：经过选择的高水平论文或解题报告。

每条来源必须有稳定 id、标题、本地路径、来源地址和许可说明。默认 `distribution: metadata_only`。本地路径只用于维护者提炼，不会发布。

## 2. 生成或重新生成草稿

使用当前模型配置：

```powershell
python case_pipeline.py generate `
  --manifest path/to/manifest.yaml `
  --workspace tool-output/case-maintenance `
  --env-file .env
```

若已经人工准备或修正了模型返回的结构化 JSON，可使用固定输入，不发起模型请求：

```powershell
python case_pipeline.py generate `
  --manifest path/to/manifest.yaml `
  --workspace tool-output/case-maintenance `
  --extraction-json path/to/extraction.json
```

`regenerate` 与 `generate` 接受相同参数，但表达“基于新提示、来源或修正意见重跑”的维护动作。两者都会创建新的不可变 revision。

草稿会检查：

- 比赛、年份、题号、标题是否齐全；
- 赛题、数据、论文三类来源是否齐全且文件存在；
- 数据操作、模型、验证方法、图表和主要结论是否均已提取；
- 每条提炼内容引用的 source id 是否真实存在；
- 输入文件 SHA-256 是否记录，便于确认重跑时来源是否变化。

## 3. 人工审核与修正

修正文件是一个 JSON 对象，可只写需要替换的提炼字段。例如：

```json
{
  "problem_summary": "审核后修正的赛题摘要",
  "limitations": ["该历史方法依赖时间序列平稳性，应用到新数据前必须重新检验。"]
}
```

审核通过：

```powershell
python case_pipeline.py review `
  --draft tool-output/case-maintenance/drafts/competition-2024-a/revision-001.json `
  --workspace tool-output/case-maintenance `
  --decision approved `
  --reviewer maintainer-name `
  --notes "已逐项核对来源" `
  --corrections path/to/corrections.json
```

若存在无法直接修正的问题，将 decision 改为 `rejected`，再调整来源、提示或固定 extraction JSON 后运行 `regenerate`。审核动作不会改写原始草稿。

## 4. 发布结构化结果

```powershell
python case_pipeline.py publish `
  --reviewed tool-output/case-maintenance/reviews/competition-2024-a/revision-001-review-001.json `
  --workspace tool-output/case-maintenance `
  --output-dir memory/modeling_cases
```

发布有硬性门禁：只有 `approved` 审核产物能发布。发布文件不包含本地路径、清单路径、原文摘录、原始表格或原始附件；即使来源许可允许再分发，本流水线默认仍只发布结构化提炼结果与引用。若未来需要分发原文，应另行建立显式的许可审核流程。

## 使用约束

- 案例卡片只提供历史启发，不能把历史数值结果当成当前赛题的结果。
- 当前数据违反历史模型假设时，分析流程必须拒绝机械复用。
- 没有高相关案例时应回退到通用分析与联网研究，不能伪造匹配。
- 通用数据分析流程不依赖本流水线或竞赛经验库；经验库不可用时仍应正常运行。
