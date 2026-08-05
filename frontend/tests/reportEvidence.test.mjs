import test from "node:test";
import assert from "node:assert/strict";

import {
  buildTraceSources,
  matchMarkdownClaim,
  resolveEvidenceSources,
  stripResultEvidenceComments,
} from "../src/utils/reportEvidence.js";

test("hidden result evidence markers remain available to matching but are not displayed", () => {
  const reportText = "销售额同比增长 12%。 <!-- result-evidence: step_3 -->";

  assert.equal(stripResultEvidenceComments(reportText), "销售额同比增长 12%。 ");
  assert.equal(reportText.includes("step_3"), true);
});

test("a chart resolves to the Python step that generated it, not an empty final step", () => {
  const tracePayload = {
    step_traces: [
      {
        step_index: 5,
        tool_name: "PythonInterpreterTool",
        tool_status: "success",
        decision: "生成分类分布图并保存",
        tool_input: "save_figure('fig1_category_distribution.png')",
        observation_preview: "Saved fig1_category_distribution.png (48213 bytes)",
      },
      {
        step_index: 7,
        tool_status: "success",
        decision: "完成最终报告",
        tool_input: "",
        observation_preview: "",
      },
    ],
  };
  const sources = buildTraceSources(tracePayload);
  const resolved = resolveEvidenceSources(
    sources,
    ["trace-step-7"],
    { name: "fig1_category_distribution.png" },
  );

  assert.equal(resolved.some((source) => source.id === "trace-step-5"), true);
  assert.equal(resolved.find((source) => source.id === "trace-step-5").code.includes("save_figure"), true);
  assert.equal(resolved.find((source) => source.id === "trace-step-5").stdout.includes("48213 bytes"), true);
  assert.equal(resolved.find((source) => source.id === "trace-step-5").toolName, "PythonInterpreterTool");
});

test("a Markdown conclusion item matches its interactive claim in place", () => {
  const claims = [{
    id: "report-claim-1",
    section: "分类分布高度不均衡",
    text: "花叶类和食用菌占据了近 70% 的品类。",
  }];
  const item = "**分类分布高度不均衡：** 花叶类和食用菌占据了近 70% 的品类。";

  assert.equal(matchMarkdownClaim(item, claims)?.id, "report-claim-1");
  assert.equal(matchMarkdownClaim("普通列表项", claims), null);
});

test("a multi-sentence conclusion prefers the claim with reviewable evidence", () => {
  const claims = [
    { id: "summary", text: "分类分布高度不均衡，类别差异很大。", sourceIds: [] },
    { id: "stat", text: "这种分布显著偏离均匀分布，卡方统计量为 171.99。", datasetId: "category-data", sourceIds: ["step-6"] },
  ];
  const item = "分类分布高度不均衡，类别差异很大。这种分布显著偏离均匀分布，卡方统计量为 171.99。";

  assert.equal(matchMarkdownClaim(item, claims)?.id, "stat");
});

test("an unmapped conclusion never receives every run source as a fallback", () => {
  const sources = [{ id: "step-1", code: "print(1)" }, { id: "step-2", code: "print(2)" }];
  assert.deepEqual(resolveEvidenceSources(sources, [], null), []);
});
