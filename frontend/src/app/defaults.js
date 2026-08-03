export const ANALYSIS_SCENARIOS = {
  general: {
    id: "general",
    label: "通用数据分析",
    shortLabel: "通用分析",
  },
  modeling: {
    id: "modeling",
    label: "数学建模项目",
    shortLabel: "数学建模",
  },
};

export function getAnalysisScenario(scenarioId) {
  return ANALYSIS_SCENARIOS[scenarioId] || ANALYSIS_SCENARIOS.general;
}

export function selectAnalysisScenario(current, scenarioId) {
  const next = getAnalysisScenario(scenarioId);

  return {
    ...current,
    scenario: next.id,
  };
}

export const DEFAULT_FORM = {
  scenario: "general",
  query: "",
  outputDir: "outputs",
  agentName: "Advanced Data Analyst",
  envFile: "",
  sessionLabel: "",
  memoryScopeLabel: "",
};
