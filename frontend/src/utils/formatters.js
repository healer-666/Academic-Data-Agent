export const formatBytes = (bytes) => {
  const value = Number(bytes ?? 0);
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const sized = value / 1024 ** exponent;
  return `${sized >= 10 || exponent === 0 ? Math.round(sized) : sized.toFixed(1)} ${units[exponent]}`;
};

export const formatDuration = (durationMs) => {
  const value = Number(durationMs ?? 0);
  if (!Number.isFinite(value) || value <= 0) return "0.0s";
  return `${(value / 1000).toFixed(1)}s`;
};

const STATUS_LABELS = {
  unknown: "待识别",
  accepted: "已通过",
  completed: "已完成",
  failed: "失败",
  skipped: "已跳过",
  not_checked: "未检查",
  not_needed: "无需处理",
  unavailable: "不可用",
};

export const compactStatus = (value) => {
  const normalized = String(value || "unknown").trim().toLowerCase();
  return STATUS_LABELS[normalized] || normalized.replaceAll("_", " ");
};
