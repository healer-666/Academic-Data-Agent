"""Tool registry construction and execution helpers."""

from __future__ import annotations

import contextlib
import io
import json
import time
from typing import Any
from urllib.parse import urlparse

from .compat import ToolRegistry
from .reporting import ReportTelemetry
from .runtime_models import AgentStepTrace, ToolExecutionRecord
from .tools.python_interpreter import PythonInterpreterTool
from .tools.tavily_search import TavilySearchTool


def build_tool_registry(*, enable_search: bool = True, tavily_api_key: str | None = None) -> ToolRegistry:
    tool_registry = ToolRegistry()
    for deprecated_tool_name in ("DataCleaningTool", "DataStatisticsTool", "python_interpreter_tool"):
        tool_registry._tools.pop(deprecated_tool_name, None)
        tool_registry._functions.pop(deprecated_tool_name, None)

    with contextlib.redirect_stdout(io.StringIO()):
        tool_registry.register_tool(PythonInterpreterTool())
        if enable_search:
            tool_registry.register_tool(TavilySearchTool(api_key=tavily_api_key))
    return tool_registry


def parse_tool_observation(observation: str) -> tuple[str, str]:
    try:
        payload = json.loads(observation)
    except Exception:
        preview = " ".join(observation.split())
        return "unknown", preview[:220]

    status = str(payload.get("status", "unknown")).strip() or "unknown"
    preview = " ".join(str(payload.get("text", "")).split())
    return status, preview[:220]


def execute_tool_call(
    *,
    tool_registry: Any,
    tool_name: str,
    tool_input: str,
    available_tools: set[str] | None = None,
) -> ToolExecutionRecord:
    available = available_tools or set(tool_registry.list_tools())
    if tool_name not in available:
        observation = json.dumps(
            {
                "status": "error",
                "text": f"Tool '{tool_name}' is not registered.",
                "available_tools": sorted(available),
            },
            ensure_ascii=False,
            indent=2,
        )
        tool_status, observation_preview = parse_tool_observation(observation)
        return ToolExecutionRecord(
            tool_name=tool_name,
            tool_input=tool_input,
            tool_status=tool_status,
            observation=observation,
            observation_preview=observation_preview,
            duration_ms=0,
        )

    started_at = time.perf_counter()
    observation = tool_registry.execute_tool(tool_name, tool_input)
    duration_ms = int(round((time.perf_counter() - started_at) * 1000))
    tool_status, observation_preview = parse_tool_observation(observation)
    return ToolExecutionRecord(
        tool_name=tool_name,
        tool_input=tool_input,
        tool_status=tool_status,
        observation=observation,
        observation_preview=observation_preview,
        duration_ms=duration_ms,
    )


def determine_search_status(
    step_traces: tuple[AgentStepTrace, ...],
    telemetry: ReportTelemetry,
    *,
    search_requested: bool = False,
    search_configured: bool = True,
) -> tuple[str, str]:
    tavily_steps = [trace for trace in step_traces if trace.tool_name == "TavilySearchTool"]
    if telemetry.valid and telemetry.search_used:
        return "used", telemetry.search_notes
    if not tavily_steps:
        if search_requested and not search_configured:
            return (
                "unavailable",
                "任务需要外部资料，但未配置 Tavily 搜索服务；已继续完成本地分析。",
            )
        if search_requested:
            return "not_used", "系统已评估联网需求，但本次分析未采用外部搜索结果。"
        if telemetry.valid and telemetry.search_notes != "unknown":
            return "not_used", telemetry.search_notes
        return "not_used", "当前任务不需要外部资料，未触发联网搜索。"

    combined_preview = " ".join(trace.observation_preview for trace in tavily_steps).lower()
    if "no tavily search credential" in combined_preview:
        return "skipped", "Tavily credential is not configured, so online search was skipped."
    if "temporarily unavailable" in combined_preview or "dependency is unavailable" in combined_preview:
        return "unavailable", "Online retrieval was unavailable; the agent fell back to local analysis."
    if any(trace.tool_status == "success" for trace in tavily_steps):
        return "used", telemetry.search_notes if telemetry.search_notes != "unknown" else "Online search results were incorporated."
    return "attempted", telemetry.search_notes if telemetry.search_notes != "unknown" else "Online search was attempted but did not yield stable results."


def collect_search_sources(step_traces: tuple[AgentStepTrace, ...]) -> tuple[dict[str, str], ...]:
    """Extract a compact, deduplicated source list from successful search traces."""

    sources: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for trace in step_traces:
        if trace.tool_name != "TavilySearchTool" or not trace.observation:
            continue
        try:
            payload = json.loads(trace.observation)
        except Exception:
            continue
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        results = data.get("results", []) if isinstance(data, dict) else []
        query = str(data.get("query", trace.tool_input) or trace.tool_input).strip()
        for item in results if isinstance(results, list) else []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or url in seen_urls:
                continue
            seen_urls.add(url)
            sources.append(
                {
                    "title": str(item.get("title", "Untitled source")).strip() or "Untitled source",
                    "url": url,
                    "snippet": " ".join(str(item.get("content", "")).split())[:500],
                    "query": query,
                }
            )
            if len(sources) >= 12:
                return tuple(sources)
    return tuple(sources)


def append_search_disclosure(
    report_markdown: str,
    *,
    search_status: str,
    search_notes: str,
    search_sources: tuple[dict[str, str], ...],
) -> str:
    """Append a deterministic report section for search provenance or degradation."""

    marker = "<!-- web-search-provenance -->"
    base_report = str(report_markdown or "").partition(marker)[0].rstrip()
    if search_status == "not_used" and not search_sources:
        return base_report

    lines = [base_report, "", marker, "", "## 联网搜索与外部来源", "", search_notes]
    if search_sources:
        lines.extend(["", "外部资料仅用于背景、定义和方法参考；当前任务结论仍来自本次上传的数据与重新计算。", ""])
        for source in search_sources:
            title = source["title"].replace("[", "（").replace("]", "）")
            safe_url = source["url"].replace(">", "%3E")
            lines.append(f"- [{title}](<{safe_url}>)")
    elif search_status == "unavailable":
        lines.extend(["", "本次报告未使用外部搜索结果；这不会阻断本地数据分析，但相关背景信息可能不完整。"])
    return "\n".join(lines).strip() + "\n"


def collect_tools_used(step_traces: tuple[AgentStepTrace, ...], telemetry: ReportTelemetry) -> tuple[str, ...]:
    if telemetry.tools_used:
        return telemetry.tools_used
    tool_names: list[str] = []
    for trace in step_traces:
        if trace.tool_name and trace.tool_name not in tool_names:
            tool_names.append(trace.tool_name)
    return tuple(tool_names)
