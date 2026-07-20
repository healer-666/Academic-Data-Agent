export const ANALYSIS_SCENARIOS = {
  general: {
    id: "general",
    label: "通用数据分析",
    shortLabel: "通用分析",
    description: "面向科研、业务和日常表格任务，快速形成可复现的数据结论。",
    inputHint: "上传一份主要 CSV 或 Excel 数据；可补充方法说明、字段文档或参考资料。",
    queryPlaceholder: "例如：哪些变量最重要？组间差异是否显著？需要哪些图表支持结论？",
    defaultQuery:
      "请基于当前数据完成结构化分析：检查数据质量，回答核心问题，并给出统计验证、图表解释、限制和可复现结论。",
    strategyTitle: "标准研究分析",
    strategySummary: [
      "自动完成数据质量检查与探索",
      "按问题选择统计检验或建模方法",
      "保留引用、图表、代码和审计记录",
    ],
    deliverable: "可复现分析报告与完整产物包",
  },
  modeling: {
    id: "modeling",
    label: "数学建模项目",
    shortLabel: "数学建模",
    description: "面向数据密集型竞赛题，强化模型假设、验证、敏感性分析和材料组织。",
    inputHint: "上传赛题说明、多份 CSV 或 Excel 数据和必要附件；系统会先形成可检查的资料包。",
    queryPlaceholder: "例如：赛题目标和约束是什么？需要建立哪些模型？如何验证并分析方案稳定性？",
    defaultQuery:
      "请围绕赛题目标分析当前数据：说明假设与数据操作，建立并比较适用模型，完成验证和敏感性分析，给出限制及可复现材料。",
    strategyTitle: "竞赛建模增强",
    strategySummary: [
      "优先梳理目标、约束、变量和表关系",
      "加强模型比较、验证与敏感性分析",
      "组织报告、图表、代码和竞赛材料",
    ],
    deliverable: "可编辑建模报告草稿与竞赛分析材料包",
    boundary: "首版适合结构化表格为主的数据密集型赛题；纯机理推导、复杂微分方程和图像题暂不属于首版承诺范围。",
  },
};

export function getAnalysisScenario(scenarioId) {
  return ANALYSIS_SCENARIOS[scenarioId] || ANALYSIS_SCENARIOS.general;
}

export function selectAnalysisScenario(current, scenarioId) {
  const previous = getAnalysisScenario(current.scenario);
  const next = getAnalysisScenario(scenarioId);
  const queryIsDefault = !current.query.trim() || current.query === previous.defaultQuery;

  return {
    ...current,
    scenario: next.id,
    query: queryIsDefault ? next.defaultQuery : current.query,
  };
}

export const DEFAULT_FORM = {
  scenario: "general",
  query: ANALYSIS_SCENARIOS.general.defaultQuery,
  outputDir: "outputs",
  agentName: "Advanced Data Analyst",
  envFile: "",
  sessionLabel: "",
  memoryScopeLabel: "",
};
