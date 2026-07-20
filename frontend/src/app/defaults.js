export const DEFAULT_FORM = {
  query:
    "请完成结构化数据分析：先清洗数据，再给出关键变量、统计检验、图表解释和可复现结论。",
  qualityMode: "standard",
  latencyMode: "auto",
  visionReviewMode: "auto",
  maxSteps: 6,
  maxReviews: 1,
  visionMaxImages: 3,
  visionMaxImageSide: 1024,
  outputDir: "outputs",
  agentName: "Advanced Data Analyst",
  envFile: "",
  sessionLabel: "",
  useRag: true,
  useMemory: true,
  memoryScopeLabel: "",
};
