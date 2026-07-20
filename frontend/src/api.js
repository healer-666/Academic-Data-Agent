const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

function apiUrl(path) {
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function readJson(response) {
  const contentType = response.headers.get("content-type") || "";
  const text = await response.text();
  if (!text) return {};
  const trimmed = text.trimStart();
  if (contentType.includes("text/html") || trimmed.startsWith("<!DOCTYPE") || trimmed.startsWith("<html")) {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

function normalizeWorkspace(payload = {}, outputDir = "outputs") {
  return {
    outputDir,
    historyRuns: [],
    selectedRunId: "",
    historyQaRuns: [],
    knowledgeBase: {
      indexedFileCount: 0,
      chunkCount: 0,
      vectorStatus: "empty",
      recentFiles: [],
    },
    ...payload,
  };
}

export async function fetchWorkspace(outputDir = "outputs") {
  const response = await fetch(apiUrl(`/api/workspace?output_dir=${encodeURIComponent(outputDir)}`), {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = await readJson(response);
    throw new Error(payload.detail || payload.message || `工作台加载失败：${response.status}`);
  }
  return normalizeWorkspace(await readJson(response), outputDir);
}

export async function fetchModelSettings() {
  const response = await fetch(apiUrl("/api/settings/model"), {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  const payload = await readJson(response);
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || `模型配置加载失败：${response.status}`);
  }
  return payload;
}

export async function saveModelSettings(settings) {
  const response = await fetch(apiUrl("/api/settings/model"), {
    method: "PUT",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  const payload = await readJson(response);
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || `模型配置保存失败：${response.status}`);
  }
  return payload;
}

export async function clearModelSettings() {
  const response = await fetch(apiUrl("/api/settings/model"), {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
  const payload = await readJson(response);
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || `模型配置清除失败：${response.status}`);
  }
  return payload;
}

export async function testModelConnection(settings) {
  const options = {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
  };
  if (settings) options.body = JSON.stringify(settings);
  const response = await fetch(apiUrl("/api/settings/model/test"), options);
  const payload = await readJson(response);
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || `模型连接测试失败：${response.status}`);
  }
  return payload;
}

export async function fetchHistoryRun(runId, outputDir = "outputs") {
  const response = await fetch(
    apiUrl(`/api/history/runs/${encodeURIComponent(runId)}?output_dir=${encodeURIComponent(outputDir)}`),
    {
      headers: { Accept: "application/json" },
      cache: "no-store",
    },
  );
  if (!response.ok) {
    const payload = await readJson(response);
    throw new Error(payload.detail || payload.message || `历史记录加载失败：${response.status}`);
  }
  return readJson(response);
}

export async function fetchInteractiveReport(runId, outputDir = "outputs") {
  const response = await fetch(
    apiUrl(`/api/history/runs/${encodeURIComponent(runId)}/interactive-report?output_dir=${encodeURIComponent(outputDir)}`),
    {
      headers: { Accept: "application/json" },
      cache: "no-store",
    },
  );
  if (!response.ok) {
    const payload = await readJson(response);
    throw new Error(payload.detail || payload.message || `交互报告加载失败：${response.status}`);
  }
  return readJson(response);
}

export async function askHistoryQuestion({ question, selectedRunIds, mode, outputDir, envFile }) {
  const response = await fetch(apiUrl("/api/history/question"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question, selectedRunIds, mode, outputDir, envFile }),
  });
  const payload = await readJson(response);
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || `历史追问失败：${response.status}`);
  }
  return payload;
}

function parseSseChunk(rawBlock) {
  const lines = rawBlock.split(/\r?\n/);
  let event = "message";
  const dataLines = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim() || "message";
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return { event, data: { message: dataLines.join("\n") } };
  }
}

export async function startAnalysis(formData, onEvent) {
  const response = await fetch(apiUrl("/api/analysis/runs"), {
    method: "POST",
    headers: { Accept: "text/event-stream" },
    body: formData,
  });

  if (!response.ok) {
    const payload = await readJson(response);
    throw new Error(payload.detail || payload.message || `分析任务启动失败：${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("分析接口没有返回可读取的事件流。");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";

    for (const block of blocks) {
      const event = parseSseChunk(block);
      if (event) onEvent?.(event);
    }

    if (done) break;
  }

  if (buffer.trim()) {
    const event = parseSseChunk(buffer);
    if (event) onEvent?.(event);
  }
}

export async function createModelingPackage(formData) {
  const response = await fetch(apiUrl("/api/modeling/packages"), {
    method: "POST",
    headers: { Accept: "application/json" },
    body: formData,
  });
  const payload = await readJson(response);
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || `赛题资料识别失败：${response.status}`);
  }
  return payload;
}

export async function updateModelingPackage(packageId, corrections) {
  const response = await fetch(apiUrl(`/api/modeling/packages/${encodeURIComponent(packageId)}`), {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(corrections),
  });
  const payload = await readJson(response);
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || `资料包修正保存失败：${response.status}`);
  }
  return payload;
}

export function toAbsoluteFileUrl(url) {
  if (!url) return "";
  if (/^https?:\/\//i.test(url) || url.startsWith("data:")) return url;
  return apiUrl(url);
}
