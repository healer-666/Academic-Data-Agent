function plainText(value) {
  return String(value || "")
    .replace(/\*\*/g, "")
    .replace(/[`*_#]/g, "")
    .replace(/[：:，,。.!！?？\s]+/g, "")
    .toLowerCase();
}

export function stripResultEvidenceComments(value) {
  return String(value ?? "").replace(
    /<!--\s*result-evidence\s*:\s*(?:Python\s*)?step[_\s-]*\d+\s*-->/gi,
    "",
  );
}

export function figureFileKey(value) {
  const decoded = decodeURIComponent(String(value || ""));
  const pathMatch = decoded.match(/[?&]path=([^&]+)/i);
  const target = pathMatch ? decodeURIComponent(pathMatch[1]) : decoded.split("?")[0];
  return target.replace(/\\/g, "/").split("/").pop()?.toLowerCase() || "";
}

export function buildTraceSources(tracePayload) {
  const steps = Array.isArray(tracePayload?.step_traces) ? tracePayload.step_traces : [];
  return steps.map((step, index) => {
    const stepIndex = step.step_index || index + 1;
    const code = typeof step.tool_input === "string" ? step.tool_input : step.tool_input?.code || "";
    const decision = String(step.decision || step.summary || "").trim();
    return {
      id: `trace-step-${stepIndex}`,
      stepIndex,
      toolName: step.tool_name || (code ? "PythonInterpreterTool" : "分析工作流"),
      status: step.tool_status || step.status || "recorded",
      summary: decision || `完成第 ${stepIndex} 个分析步骤`,
      decision,
      code,
      stdout: step.observation_preview || step.stdout || "",
    };
  });
}

export function sourcesForFigure(figure, sources) {
  const codeSources = (sources || []).filter((source) => String(source.code || "").trim());
  if (!codeSources.length) return [];
  const key = figureFileKey(figure?.file?.url || figure?.url || figure?.file?.name || figure?.name || figure?.title);
  const stem = key.replace(/\.[^.]+$/, "");
  const matched = codeSources.filter((source) => {
    const code = String(source.code || "").toLowerCase();
    return (key && code.includes(key)) || (stem.length > 4 && code.includes(stem));
  });
  return matched.length ? matched : codeSources.slice(-1);
}

export function resolveEvidenceSources(sources, sourceIds = [], figure = null) {
  const allSources = sources || [];
  const mapped = sourceIds.length ? allSources.filter((source) => sourceIds.includes(source.id)) : [];
  if (!figure) return mapped;
  if (mapped.some((source) => String(source.code || "").trim())) return mapped;
  const relevant = sourcesForFigure(figure, allSources);
  const merged = [...mapped];
  relevant.forEach((source) => {
    if (!merged.some((item) => item.id === source.id)) merged.push(source);
  });
  return merged.length ? merged : allSources;
}

export function matchMarkdownClaim(markdownItem, claims = []) {
  const itemText = plainText(markdownItem);
  if (!itemText) return null;
  const matches = claims.filter((claim) => {
    const section = plainText(claim.section);
    const text = plainText(claim.text);
    return (section.length >= 4 && itemText.includes(section))
      || (text.length >= 10 && itemText.includes(text.slice(0, Math.min(24, text.length))));
  });
  matches.sort((left, right) => {
    const leftHasEvidence = Boolean(left.datasetId || left.sourceIds?.length);
    const rightHasEvidence = Boolean(right.datasetId || right.sourceIds?.length);
    if (leftHasEvidence !== rightHasEvidence) return rightHasEvidence ? 1 : -1;
    return plainText(right.text).length - plainText(left.text).length;
  });
  return matches[0] || null;
}
