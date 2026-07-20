"""FastAPI application for the React web workspace."""

from __future__ import annotations

import asyncio
import json
import queue
import re
import shutil
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Any, Literal
from urllib.parse import urlencode

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, SecretStr

from ..agent_runner import run_analysis
from ..history_qa import answer_history_question
from ..memory import derive_memory_scope_key
from ..modeling_workspace import ModelingWorkspace, ModelingWorkspaceError
from .history import RunHistoryEntry, find_run_history, scan_run_history
from .model_settings import (
    ModelSettingsInput,
    ModelSettingsStore,
    redact_sensitive_text,
    test_model_connection,
    validate_model_settings,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = "outputs"
DEFAULT_HISTORY_LIMIT = 100
DEFAULT_KNOWLEDGE_BASE_DIR = Path("memory") / "knowledge_base"
ALLOWED_DATA_SUFFIXES = {".csv", ".xls", ".xlsx"}
ALLOWED_KNOWLEDGE_SUFFIXES = {".txt", ".md", ".pdf"}
ALLOWED_MODELING_PROBLEM_SUFFIXES = {".txt", ".md", ".pdf"}
ALLOWED_MODELING_ATTACHMENT_SUFFIXES = {
    ".txt", ".md", ".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".csv", ".xls", ".xlsx"
}

WEB_ANALYSIS_STRATEGIES: dict[str, dict[str, object]] = {
    "general": {
        "quality_mode": "standard",
        "latency_mode": "auto",
        "vision_review_mode": "auto",
        "max_steps": 6,
        "max_reviews": 1,
        "vision_max_images": 3,
        "vision_max_image_side": 1024,
        "use_rag": True,
        "use_memory": True,
        "task_type": "general_analysis",
        "task_expectations": (
            "inspect data quality before analysis",
            "select methods that match the user's question and data",
            "report validated findings, limitations, and reproducible evidence",
        ),
    },
    "modeling": {
        "quality_mode": "publication",
        "latency_mode": "quality",
        "vision_review_mode": "auto",
        "max_steps": 10,
        "max_reviews": 2,
        "vision_max_images": 4,
        "vision_max_image_side": 1280,
        "use_rag": True,
        "use_memory": True,
        "task_type": "mathematical_modeling",
        "task_expectations": (
            "state objectives, constraints, variables, and assumptions",
            "compare suitable models using only the current task data",
            "validate the selected model and perform sensitivity analysis",
            "produce reproducible code, figures, limitations, and report-ready materials",
        ),
    },
}


def resolve_web_analysis_strategy(scenario: str) -> dict[str, object] | None:
    """Return the server-owned runtime strategy for a Web task scenario."""

    normalized = str(scenario or "").strip().lower()
    strategy = WEB_ANALYSIS_STRATEGIES.get(normalized)
    return dict(strategy) if strategy is not None else None


class HistoryQuestionRequest(BaseModel):
    question: str
    selectedRunIds: list[str] = []
    mode: str = "single"
    outputDir: str = DEFAULT_OUTPUT_DIR
    envFile: str = ""


class ModelSettingsRequest(BaseModel):
    modelId: str
    baseUrl: str
    apiKey: SecretStr
    timeout: int = 120

    def to_settings_input(self) -> ModelSettingsInput:
        return ModelSettingsInput(
            model_id=self.modelId,
            base_url=self.baseUrl,
            api_key=self.apiKey.get_secret_value(),
            timeout=self.timeout,
        )


class ModelingPackageUpdateRequest(BaseModel):
    primaryTableId: str | None = None
    tableLabels: dict[str, str] | None = None
    relationships: list[dict[str, Any]] | None = None
    relationshipNotes: str | None = None
    confirmed: bool | None = None


def _json_default(value: object) -> object:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _sse(event: str, payload: dict[str, object]) -> str:
    data = json.dumps(payload, ensure_ascii=False, default=_json_default)
    return f"event: {event}\ndata: {data}\n\n"


def build_session_id(session_label: str | None = None) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(session_label or "").strip()).strip("-")
    return f"{(normalized[:32] or 'session')}-{uuid.uuid4().hex[:8]}"


def create_run_bundle(run_dir: str | Path) -> Path:
    run_path = Path(run_dir)
    archive_base = run_path.parent / f"{run_path.name}_artifacts"
    archive_path = shutil.make_archive(
        str(archive_base),
        "zip",
        root_dir=run_path.parent,
        base_dir=run_path.name,
    )
    return Path(archive_path)


def _event_payload_text(payload: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def format_event_line(event_type: str, payload: dict[str, object]) -> str:
    if event_type == "config_loading":
        return "正在加载运行配置。"
    if event_type == "config_loaded":
        model_id = payload.get("model_id", "unknown")
        tavily = "已配置" if payload.get("tavily_configured") else "未配置"
        embedding = "已配置" if payload.get("embedding_configured") else "未配置"
        vision = "已配置" if payload.get("vision_configured") else "未配置"
        return f"模型：{model_id} | Tavily：{tavily} | Embedding：{embedding} | 视觉检查：{vision}"
    if event_type == "run_directory_created":
        return f"已创建运行目录：{payload.get('run_dir', '')}"
    if event_type == "document_ingestion_started":
        return f"开始准备输入数据：{payload.get('input_kind', 'tabular')}"
    if event_type == "document_ingestion_completed":
        return f"输入数据准备完成：{payload.get('summary') or payload.get('status', 'completed')}"
    if event_type == "document_ingestion_skipped":
        return "输入数据无需额外解析。"
    if event_type == "data_context_ready":
        shape = payload.get("shape", ("?", "?"))
        rows = cols = "?"
        if isinstance(shape, (list, tuple)) and len(shape) >= 2:
            rows, cols = shape[0], shape[1]
        return f"数据上下文已准备：{rows} 行 x {cols} 列"
    if event_type == "search_planning_completed":
        return str(payload.get("reason") or "联网搜索需求已评估。")
    if event_type == "knowledge_indexing_started":
        return f"正在写入参考资料：{payload.get('file_count', 0)} 个文件"
    if event_type == "knowledge_indexing_completed":
        return f"参考资料已入库：{payload.get('indexed_count', 0)} 个文件"
    if event_type == "knowledge_indexing_skipped":
        return f"参考资料入库已跳过：{payload.get('reason', '')}"
    if event_type == "knowledge_structured_chunking_completed":
        return f"结构化切块完成：{payload.get('chunk_count', 0)} 个片段"
    if event_type == "knowledge_retrieval_completed":
        return f"参考资料检索完成：命中 {payload.get('match_count', 0)} 条"
    if event_type == "knowledge_retrieval_skipped":
        return f"参考资料检索已跳过：{payload.get('reason', '')}"
    if event_type == "memory_retrieval_completed":
        return f"历史经验检索完成：命中 {payload.get('match_count', 0)} 条"
    if event_type == "memory_retrieval_skipped":
        return f"历史经验检索已跳过：{payload.get('reason', '')}"
    if event_type == "tool_registry_ready":
        return f"分析工具已就绪：{payload.get('tool_count', 0)} 个"
    if event_type == "analysis_started":
        return f"开始分析：最多 {payload.get('max_steps', '?')} 步"
    if event_type == "step_started":
        return f"执行第 {payload.get('step_index', '?')} 步"
    if event_type == "tool_call_started":
        return f"调用工具：{payload.get('tool_name', 'unknown')}"
    if event_type == "tool_call_completed":
        return f"工具完成：{payload.get('tool_name', 'unknown')} | {payload.get('tool_status', 'unknown')}"
    if event_type == "report_saved":
        return f"报告已保存：{payload.get('report_path', '')}"
    if event_type == "artifact_validation_completed":
        status = "通过" if payload.get("workflow_complete") else "需检查"
        return f"工件校验完成：{status}"
    if event_type == "review_started":
        return f"开始第 {payload.get('review_round', '?')} 轮可信度检查"
    if event_type == "review_completed":
        return f"可信度检查完成：{payload.get('decision', payload.get('status', 'unknown'))}"
    if event_type == "vision_review_started":
        return "开始图表视觉检查。"
    if event_type == "vision_review_completed":
        return f"图表视觉检查完成：{payload.get('status', 'completed')}"
    if event_type == "analysis_finished":
        return "分析流程已完成。"
    if event_type == "analysis_max_steps":
        return "已达到最大分析步数。"

    detail = _event_payload_text(payload, "summary", "message", "status")
    if detail:
        return f"{event_type}: {detail}"
    return f"{event_type}: {json.dumps(payload, ensure_ascii=False, default=_json_default)}"


def _resolve_project_path(value: str | Path, *, base: Path = PROJECT_ROOT) -> Path:
    path = Path(value or DEFAULT_OUTPUT_DIR)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _safe_upload_name(filename: str | None, fallback: str) -> str:
    name = Path(filename or fallback).name.strip() or fallback
    cleaned = "".join(char if char.isalnum() or char in {".", "-", "_", " "} else "_" for char in name)
    return cleaned.strip(" .") or fallback


def _relative_to_outputs(path: Path) -> bool:
    outputs_root = (PROJECT_ROOT / "outputs").resolve()
    try:
        path.resolve().relative_to(outputs_root)
    except ValueError:
        return False
    return True


def _file_url(path: str | Path | None) -> str:
    if not path:
        return ""
    resolved = _resolve_project_path(path)
    if not _relative_to_outputs(resolved):
        return ""
    return f"/api/files?{urlencode({'path': resolved.as_posix()})}"


def _file_payload(path: str | Path | None, *, label: str = "") -> dict[str, object] | None:
    if not path:
        return None
    resolved = _resolve_project_path(path)
    if not resolved.exists():
        return None
    return {
        "name": label or resolved.name,
        "path": resolved.as_posix(),
        "url": _file_url(resolved),
        "size": resolved.stat().st_size,
    }


def _rewrite_markdown_file_links(markdown: str, *, base_dir: Path | None = None) -> str:
    """Rewrite local image targets in markdown to the guarded file endpoint."""

    import re

    def replace_image(match: re.Match[str]) -> str:
        alt_text = match.group(1)
        raw_target = match.group(2).strip()
        if raw_target.startswith(("http://", "https://", "data:", "/api/files")):
            return match.group(0)
        candidate = Path(raw_target)
        if not candidate.is_absolute():
            candidates = []
            if base_dir is not None:
                candidates.append((base_dir / candidate).resolve())
            candidates.append((PROJECT_ROOT / candidate).resolve())
            candidate = next((item for item in candidates if item.exists()), candidates[0])
        if not candidate.exists() or not _relative_to_outputs(candidate):
            return match.group(0)
        return f"![{alt_text}]({_file_url(candidate)})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_image, markdown or "")


def _read_markdown_file(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return _rewrite_markdown_file_links(path.read_text(encoding="utf-8"), base_dir=path.parent)


def _read_trace_payload(path: Path | None) -> dict[str, object]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_json_payload(path: Path | None) -> dict[str, object]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _serialize_lineage(run_dir: Path) -> dict[str, object]:
    lineage_path = run_dir / "logs" / "lineage.json"
    mermaid_path = run_dir / "logs" / "lineage.mmd"
    if not lineage_path.exists():
        return {
            "available": False,
            "summary": {},
            "nodes": [],
            "edges": [],
            "downloads": [],
        }

    try:
        payload = json.loads(lineage_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    allowed_types = {
        "figure",
        "dataset_snapshot",
        "source_code",
        "report_block",
        "source_field",
        "derived_field",
        "python_step",
        "execution_evidence",
        "report_claim",
    }
    nodes = [
        dict(node)
        for node in payload.get("nodes", [])
        if isinstance(node, dict) and str(node.get("type", "")) in allowed_types
    ]
    node_ids = {str(node.get("id", "")) for node in nodes}
    edges = [
        dict(edge)
        for edge in payload.get("edges", [])
        if (
            isinstance(edge, dict)
            and str(edge.get("source", "")) in node_ids
            and str(edge.get("target", "")) in node_ids
        )
    ]
    summary = payload.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}

    return {
        "available": bool(nodes),
        "version": payload.get("version", 0),
        "status": payload.get("status", "unknown"),
        "summary": summary,
        "nodes": nodes,
        "edges": edges,
        "downloads": [
            item
            for item in (
                _file_payload(lineage_path, label="lineage.json"),
                _file_payload(mermaid_path, label="lineage.mmd"),
            )
            if item is not None
        ],
    }


def _interactive_report_paths(run_dir: Path) -> dict[str, Path]:
    logs_dir = run_dir / "logs"
    return {
        "manifest": logs_dir / "interactive_report_manifest.json",
        "snapshot": logs_dir / "interactive_report_snapshot.json",
        "sourceMap": logs_dir / "source_map.json",
    }


def _interactive_report_summary(run_dir: Path) -> dict[str, object]:
    paths = _interactive_report_paths(run_dir)
    manifest = _read_json_payload(paths["manifest"])
    summary = manifest.get("summary", {}) if isinstance(manifest, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    return {
        "available": bool(manifest),
        "manifest": _file_payload(paths["manifest"], label="interactive_report_manifest.json"),
        "snapshot": _file_payload(paths["snapshot"], label="interactive_report_snapshot.json"),
        "sourceMap": _file_payload(paths["sourceMap"], label="source_map.json"),
        "summary": summary,
    }


def _hydrate_interactive_report_payload(run_dir: Path) -> dict[str, object]:
    paths = _interactive_report_paths(run_dir)
    manifest = _read_json_payload(paths["manifest"])
    snapshot = _read_json_payload(paths["snapshot"])
    source_map = _read_json_payload(paths["sourceMap"])
    if not manifest:
        return {
            "available": False,
            "manifest": {},
            "snapshot": {},
            "sourceMap": {},
            "lineage": _serialize_lineage(run_dir),
            "downloads": [],
        }

    for figure in manifest.get("figures", []) if isinstance(manifest.get("figures", []), list) else []:
        if not isinstance(figure, dict):
            continue
        file_payload = _file_payload(figure.get("path"), label=str(figure.get("name") or "figure"))
        if file_payload:
            figure["file"] = file_payload
            figure["url"] = file_payload.get("url", "")
    for dataset in (snapshot.get("datasets", {}) if isinstance(snapshot.get("datasets", {}), dict) else {}).values():
        if not isinstance(dataset, dict):
            continue
        source_payload = _file_payload(dataset.get("sourcePath"), label=Path(str(dataset.get("sourcePath", "data"))).name)
        if source_payload:
            dataset["sourceFile"] = source_payload

    return {
        "available": True,
        "manifest": manifest,
        "snapshot": snapshot,
        "sourceMap": source_map,
        "lineage": _serialize_lineage(run_dir),
        "downloads": [
            item
            for item in (
                _file_payload(paths["manifest"], label="interactive_report_manifest.json"),
                _file_payload(paths["snapshot"], label="interactive_report_snapshot.json"),
                _file_payload(paths["sourceMap"], label="source_map.json"),
            )
            if item is not None
        ],
    }


def _serialize_history_entry(entry: RunHistoryEntry) -> dict[str, object]:
    interactive = _interactive_report_summary(entry.run_dir)
    return {
        "runId": entry.run_dir.name,
        "runDir": entry.run_dir.as_posix(),
        "timestamp": entry.timestamp,
        "domain": entry.domain,
        "qualityMode": entry.quality_mode,
        "latencyMode": entry.latency_mode,
        "inputKind": entry.input_kind,
        "reviewStatus": entry.review_status,
        "visionReviewStatus": entry.vision_review_status,
        "workflowComplete": entry.workflow_complete,
        "report": _file_payload(entry.report_path, label="final_report.md"),
        "trace": _file_payload(entry.trace_path, label="agent_trace.json"),
        "cleanedData": _file_payload(entry.cleaned_data_path, label="cleaned_data.csv"),
        "figureCount": len(entry.figure_paths),
        "lineageAvailable": (entry.run_dir / "logs" / "lineage.json").exists(),
        "interactiveReportAvailable": bool(interactive["available"]),
        "interactiveReportSummary": interactive["summary"],
    }


def _serialize_history_detail(entry: RunHistoryEntry) -> dict[str, object]:
    trace_payload = _read_trace_payload(entry.trace_path)
    figures = [
        payload
        for payload in (_file_payload(path, label=path.name) for path in entry.figure_paths)
        if payload is not None
    ]
    stage_contract = trace_payload.get("artifact_validation", {})
    if not isinstance(stage_contract, dict):
        stage_contract = {}
    return {
        **_serialize_history_entry(entry),
        "reportMarkdown": _read_markdown_file(entry.report_path)
        or "## 历史报告\n\n当前运行没有可预览的报告。",
        "figures": figures,
        "tracePayload": trace_payload,
        "lineage": _serialize_lineage(entry.run_dir),
        "diagnostics": {
            "stageContractStatus": entry.stage_contract_status,
            "stageContractPassed": entry.stage_contract_passed,
            "stageContractFindings": list(entry.stage_contract_findings),
            "documentIngestionStatus": entry.document_ingestion_status,
            "documentIngestionSummary": entry.document_ingestion_summary,
            "candidateTableCount": entry.candidate_table_count,
            "selectedTableId": entry.selected_table_id,
            "selectedTableShape": entry.selected_table_shape,
            "visionReviewSummary": entry.vision_review_summary,
            "warnings": stage_contract.get("warnings", []),
        },
        "downloads": [
            item
            for item in (
                _file_payload(entry.report_path, label="final_report.md"),
                _file_payload(entry.trace_path, label="agent_trace.json"),
                _file_payload(entry.cleaned_data_path, label="cleaned_data.csv"),
            )
            if item is not None
        ],
    }


def _find_history_entry(run_id: str, outputs_root: str | Path) -> RunHistoryEntry:
    entry = find_run_history(run_id, outputs_root)
    if entry is not None:
        return entry
    raise HTTPException(status_code=404, detail=f"History run not found: {run_id}")


def _knowledge_base_status(knowledge_base_dir: str | Path | None = None) -> dict[str, object]:
    resolved_dir = _resolve_project_path(knowledge_base_dir or DEFAULT_KNOWLEDGE_BASE_DIR)
    files_dir = resolved_dir / "files"
    keyword_index_path = resolved_dir / "keyword_index.json"
    chroma_dir = resolved_dir / "chroma"

    indexed_files = sorted(
        [path for path in files_dir.glob("*") if path.is_file()] if files_dir.exists() else [],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    chunk_count = 0
    if keyword_index_path.exists():
        try:
            payload = json.loads(keyword_index_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        chunks = payload.get("chunks", []) if isinstance(payload, dict) else []
        chunk_count = len(chunks) if isinstance(chunks, list) else 0

    vector_ready = chroma_dir.exists() and any(chroma_dir.rglob("*"))
    return {
        "path": resolved_dir.as_posix(),
        "indexedFileCount": len(indexed_files),
        "chunkCount": chunk_count,
        "vectorStatus": "ready" if vector_ready else "empty",
        "recentFiles": [
            {
                "name": path.name,
                "path": path.as_posix(),
                "modifiedAt": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="minutes"),
                "size": path.stat().st_size,
            }
            for path in indexed_files[:8]
        ],
    }


def _history_qa_run_choices(entries: list[RunHistoryEntry]) -> list[dict[str, str]]:
    return [
        {
            "runId": entry.run_dir.name,
            "label": f"{entry.run_dir.name} | {entry.domain} | {entry.review_status} | {entry.timestamp}",
            "domain": entry.domain,
            "reviewStatus": entry.review_status,
            "timestamp": entry.timestamp,
        }
        for entry in entries
    ]


def _serialize_workspace(output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> dict[str, object]:
    entries = scan_run_history(output_dir, limit=DEFAULT_HISTORY_LIMIT)
    history_runs = [_serialize_history_entry(entry) for entry in entries]
    return {
        "outputDir": str(output_dir or DEFAULT_OUTPUT_DIR),
        "historyRuns": history_runs,
        "selectedRunId": history_runs[0]["runId"] if history_runs else "",
        "historyQaRuns": _history_qa_run_choices(entries),
        "knowledgeBase": _knowledge_base_status(),
    }


def _serialize_step_trace(trace: object) -> dict[str, object]:
    return {
        "stepIndex": getattr(trace, "step_index", None),
        "toolName": getattr(trace, "tool_name", "") or getattr(trace, "action", ""),
        "toolStatus": getattr(trace, "tool_status", "unknown"),
        "decision": getattr(trace, "decision", "") or getattr(trace, "action", ""),
        "summary": getattr(trace, "summary", "") or getattr(trace, "observation_preview", ""),
        "llmDurationMs": getattr(trace, "llm_duration_ms", 0),
        "toolDurationMs": getattr(trace, "tool_duration_ms", 0),
    }


def _serialize_analysis_result(result: object, bundle_path: Path | None = None) -> dict[str, object]:
    run_dir = _resolve_project_path(getattr(result, "run_dir", ""))
    report_path = _resolve_project_path(getattr(result, "report_path", run_dir / "final_report.md"))
    trace_path = _resolve_project_path(getattr(result, "trace_path", run_dir / "logs" / "agent_trace.json"))
    cleaned_data_path = _resolve_project_path(
        getattr(result, "cleaned_data_path", run_dir / "data" / "cleaned_data.csv")
    )
    figures = [
        payload
        for payload in (
            _file_payload(path, label=Path(path).name)
            for path in getattr(getattr(result, "telemetry", None), "figures_generated", ())
        )
        if payload is not None
    ]
    downloads = [
        item
        for item in (
            _file_payload(report_path, label="final_report.md"),
            _file_payload(trace_path, label="agent_trace.json"),
            _file_payload(bundle_path, label="artifacts.zip"),
            _file_payload(cleaned_data_path, label="cleaned_data.csv"),
        )
        if item is not None
    ]
    report_markdown = getattr(result, "report_markdown", "") or _read_markdown_file(report_path)
    lineage = _serialize_lineage(run_dir)
    interactive = _interactive_report_summary(run_dir)
    return {
        "runId": run_dir.name,
        "runDir": run_dir.as_posix(),
        "status": "success" if getattr(result, "workflow_complete", False) else "warning",
        "workflowComplete": bool(getattr(result, "workflow_complete", False)),
        "qualityMode": getattr(result, "quality_mode", "standard"),
        "latencyMode": getattr(result, "latency_mode", "auto"),
        "detectedDomain": getattr(result, "detected_domain", "unknown"),
        "inputKind": getattr(result, "input_kind", "tabular"),
        "reviewStatus": getattr(result, "review_status", "unknown"),
        "visionReviewStatus": getattr(result, "vision_review_status", "skipped"),
        "ragStatus": getattr(result, "rag_status", "disabled"),
        "ragMatchCount": getattr(result, "rag_match_count", 0),
        "memoryWritebackStatus": getattr(result, "memory_writeback_status", "disabled"),
        "reviewRoundsUsed": getattr(result, "review_rounds_used", 0),
        "totalDurationMs": getattr(result, "total_duration_ms", 0),
        "methodsUsed": list(getattr(result, "methods_used", ()) or ()),
        "toolsUsed": list(getattr(result, "tools_used", ()) or ()),
        "searchStatus": getattr(result, "search_status", "not_used"),
        "searchNotes": getattr(result, "search_notes", ""),
        "searchSources": [dict(source) for source in (getattr(result, "search_sources", ()) or ())],
        "workflowWarnings": list(getattr(result, "workflow_warnings", ()) or ()),
        "executionAudit": {
            "status": getattr(result, "execution_audit_status", "not_checked"),
            "passed": bool(getattr(result, "execution_audit_passed", False)),
            "findings": list(getattr(result, "execution_audit_findings", ()) or ()),
        },
        "review": {
            "critique": getattr(result, "review_critique", ""),
            "visionSummary": getattr(result, "vision_review_summary", ""),
        },
        "reportMarkdown": _rewrite_markdown_file_links(report_markdown, base_dir=report_path.parent),
        "figures": figures,
        "downloads": downloads,
        "trace": [_serialize_step_trace(trace) for trace in getattr(result, "step_traces", ())],
        "lineage": lineage,
        "interactiveReportAvailable": bool(interactive["available"]),
        "interactiveReportSummary": interactive["summary"],
    }


async def _save_upload(upload: UploadFile, destination: Path, allowed_suffixes: set[str]) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in allowed_suffixes:
        allowed = ", ".join(sorted(allowed_suffixes))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {allowed}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    await upload.close()
    return destination


def create_app(project_root: Path | None = None) -> FastAPI:
    root = (project_root or PROJECT_ROOT).resolve()
    app = FastAPI(title="Academic Data Agent React API", version="1.0.0")
    app.state.model_settings = ModelSettingsStore(root / ".env")
    app.state.modeling_workspace = ModelingWorkspace(root / "outputs" / "modeling_packages")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        dist_dir = root / "frontend" / "dist"
        return {
            "ok": True,
            "service": "academic-data-agent-web",
            "frontendBuilt": (dist_dir / "index.html").exists(),
            "projectRoot": root.as_posix(),
        }

    @app.get("/api/workspace")
    async def workspace(output_dir: str = Query(DEFAULT_OUTPUT_DIR)) -> dict[str, object]:
        return _serialize_workspace(output_dir or DEFAULT_OUTPUT_DIR)

    @app.get("/api/settings/model")
    async def model_settings_status() -> dict[str, object]:
        return app.state.model_settings.public_status()

    @app.put("/api/settings/model")
    async def save_model_settings(payload: ModelSettingsRequest) -> dict[str, object]:
        try:
            return app.state.model_settings.save(payload.to_settings_input())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.delete("/api/settings/model")
    async def clear_model_settings() -> dict[str, object]:
        return app.state.model_settings.clear()

    @app.post("/api/settings/model/test")
    async def test_saved_model_connection(payload: ModelSettingsRequest | None = None) -> dict[str, object]:
        config = None
        try:
            if payload is not None:
                config = validate_model_settings(payload.to_settings_input(), env_file=root / ".env")
            else:
                config = app.state.model_settings.runtime_config()
                if config is None:
                    raise ValueError("请先填写模型配置，或保存后再测试连接。")
            message = await asyncio.to_thread(test_model_connection, config)
        except ValueError as exc:
            message = str(exc)
            if config is not None:
                app.state.model_settings.record_connection_result(
                    config,
                    succeeded=False,
                    message=message,
                )
            raise HTTPException(status_code=400, detail=message) from None

        app.state.model_settings.record_connection_result(config, succeeded=True, message=message)
        return {"ok": True, "message": message}

    @app.get("/api/history/runs")
    async def history_runs(
        output_dir: str = Query(DEFAULT_OUTPUT_DIR),
        limit: int = Query(DEFAULT_HISTORY_LIMIT, ge=1, le=500),
    ) -> dict[str, object]:
        runs = [
            _serialize_history_entry(entry)
            for entry in scan_run_history(output_dir or DEFAULT_OUTPUT_DIR, limit=limit)
        ]
        return {"runs": runs}

    @app.get("/api/history/runs/{run_id}")
    async def history_run_detail(
        run_id: str,
        output_dir: str = Query(DEFAULT_OUTPUT_DIR),
    ) -> dict[str, object]:
        return _serialize_history_detail(_find_history_entry(run_id, output_dir or DEFAULT_OUTPUT_DIR))

    @app.get("/api/history/runs/{run_id}/interactive-report")
    async def history_run_interactive_report(
        run_id: str,
        output_dir: str = Query(DEFAULT_OUTPUT_DIR),
    ) -> dict[str, object]:
        entry = _find_history_entry(run_id, output_dir or DEFAULT_OUTPUT_DIR)
        return _hydrate_interactive_report_payload(entry.run_dir)

    @app.post("/api/history/question")
    async def history_question(payload: HistoryQuestionRequest) -> dict[str, object]:
        question = payload.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="question is required")
        result = answer_history_question(
            question,
            run_ids=payload.selectedRunIds,
            mode=payload.mode,
            outputs_root=payload.outputDir or DEFAULT_OUTPUT_DIR,
            env_file=payload.envFile or None,
            runtime_config_override=app.state.model_settings.runtime_config(payload.envFile or None),
        )
        return {
            "answerMarkdown": result.answer_markdown,
            "sources": list(result.sources),
            "warnings": list(result.warnings),
        }

    @app.get("/api/files")
    async def files(path: str = Query(...)) -> FileResponse:
        resolved = _resolve_project_path(path)
        if not _relative_to_outputs(resolved):
            raise HTTPException(status_code=403, detail="Only files under project outputs/ can be served")
        if not resolved.exists() or not resolved.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(resolved, filename=resolved.name)

    @app.post("/api/modeling/packages")
    async def create_modeling_package(
        problem_file: UploadFile = File(...),
        data_files: list[UploadFile] = File(...),
        attachments: list[UploadFile] | None = File(None),
    ) -> dict[str, object]:
        package_id = build_session_id("modeling")
        uploads_root = root / "outputs" / "modeling_packages" / package_id / "uploads"
        try:
            problem_path = await _save_upload(
                problem_file,
                uploads_root / "problem" / _safe_upload_name(problem_file.filename, "problem.md"),
                ALLOWED_MODELING_PROBLEM_SUFFIXES,
            )
            saved_data_paths: list[Path] = []
            for index, upload in enumerate(data_files, start=1):
                if not upload.filename:
                    continue
                safe_name = _safe_upload_name(upload.filename, f"data-{index}.csv")
                saved_data_paths.append(
                    await _save_upload(upload, uploads_root / "data" / f"{index:02d}" / safe_name, ALLOWED_DATA_SUFFIXES)
                )
            saved_attachment_paths: list[Path] = []
            for index, upload in enumerate(attachments or [], start=1):
                if not upload.filename:
                    continue
                safe_name = _safe_upload_name(upload.filename, f"attachment-{index}.pdf")
                saved_attachment_paths.append(
                    await _save_upload(
                        upload,
                        uploads_root / "attachments" / f"{index:02d}" / safe_name,
                        ALLOWED_MODELING_ATTACHMENT_SUFFIXES,
                    )
                )
            return app.state.modeling_workspace.create(
                package_id,
                problem_path=problem_path,
                data_paths=saved_data_paths,
                attachment_paths=saved_attachment_paths,
            )
        except (HTTPException, ModelingWorkspaceError) as exc:
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            raise HTTPException(status_code=400, detail=detail) from None

    @app.get("/api/modeling/packages/{package_id}")
    async def get_modeling_package(package_id: str) -> dict[str, object]:
        try:
            return app.state.modeling_workspace.load(package_id)
        except ModelingWorkspaceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None

    @app.patch("/api/modeling/packages/{package_id}")
    async def update_modeling_package(
        package_id: str,
        payload: ModelingPackageUpdateRequest,
    ) -> dict[str, object]:
        try:
            return app.state.modeling_workspace.update(package_id, payload.model_dump(exclude_none=True))
        except ModelingWorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.post("/api/analysis/runs")
    async def analysis_runs(
        data_file: UploadFile = File(...),
        scenario: Literal["", "general", "modeling"] = Form(""),
        query: str = Form(""),
        quality_mode: str = Form("standard"),
        latency_mode: str = Form("auto"),
        vision_review_mode: str = Form("auto"),
        max_steps: int = Form(6),
        max_reviews: int | None = Form(None),
        vision_max_images: int = Form(3),
        vision_max_image_side: int = Form(1024),
        output_dir: str = Form(DEFAULT_OUTPUT_DIR),
        agent_name: str = Form("Advanced Data Analyst"),
        env_file: str = Form(""),
        session_label: str = Form(""),
        use_rag: str = Form("true"),
        use_memory: str = Form("true"),
        memory_scope_label: str = Form(""),
        knowledge_uploads: list[UploadFile] | None = File(None),
    ) -> StreamingResponse:
        runtime_config_override = app.state.model_settings.runtime_config(env_file or None)
        web_strategy = resolve_web_analysis_strategy(scenario)
        if web_strategy:
            runtime_strategy = {
                "max_steps": int(web_strategy["max_steps"]),
                "max_reviews": int(web_strategy["max_reviews"]),
                "quality_mode": str(web_strategy["quality_mode"]),
                "latency_mode": str(web_strategy["latency_mode"]),
                "vision_review_mode": str(web_strategy["vision_review_mode"]),
                "vision_max_images": int(web_strategy["vision_max_images"]),
                "vision_max_image_side": int(web_strategy["vision_max_image_side"]),
                "use_rag": bool(web_strategy["use_rag"]),
                "use_memory": bool(web_strategy["use_memory"]),
                "task_type": str(web_strategy["task_type"]),
                "task_expectations": tuple(web_strategy["task_expectations"]),
            }
        else:
            runtime_strategy = {
                "max_steps": _safe_int(max_steps, 6),
                "max_reviews": max_reviews,
                "quality_mode": quality_mode or "standard",
                "latency_mode": latency_mode or "auto",
                "vision_review_mode": vision_review_mode or "auto",
                "vision_max_images": max(1, _safe_int(vision_max_images, 3)),
                "vision_max_image_side": max(256, min(_safe_int(vision_max_image_side, 1024), 2048)),
                "use_rag": _safe_bool(use_rag, True),
                "use_memory": _safe_bool(use_memory, True),
                "task_type": "",
                "task_expectations": (),
            }

        async def stream():
            logs: list[str] = []
            event_queue: queue.Queue[tuple[str, object]] = queue.Queue()
            session_id = build_session_id(session_label)
            uploads_root = _resolve_project_path(output_dir or DEFAULT_OUTPUT_DIR) / "web_uploads" / session_id

            try:
                data_destination = uploads_root / _safe_upload_name(data_file.filename, "data.csv")
                copied_file = await _save_upload(data_file, data_destination, ALLOWED_DATA_SUFFIXES)
                logs.append(f"上传文件已保存：{copied_file.as_posix()}")
                knowledge_paths: list[Path] = []
                for upload in knowledge_uploads or []:
                    if not upload.filename:
                        continue
                    target = uploads_root / "knowledge" / _safe_upload_name(upload.filename, "knowledge.md")
                    knowledge_paths.append(await _save_upload(upload, target, ALLOWED_KNOWLEDGE_SUFFIXES))
                if knowledge_paths:
                    logs.append(f"参考资料已准备：{len(knowledge_paths)} 个文件")
            except Exception as exc:
                detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
                yield _sse("error", {"message": detail, "logs": logs})
                return

            yield _sse(
                "status",
                {
                    "state": "starting",
                    "message": "文件已接收，正在启动分析任务。",
                    "logs": logs,
                },
            )

            memory_scope_key = derive_memory_scope_key(
                session_label=memory_scope_label or session_label,
                source_path=copied_file,
            )

            def handle_event(event_type: str, payload: dict[str, object]) -> None:
                event_queue.put(("event", {"eventType": event_type, "payload": payload}))

            def run_target() -> None:
                try:
                    result = run_analysis(
                        copied_file,
                        query=query,
                        output_dir=output_dir or DEFAULT_OUTPUT_DIR,
                        env_file=env_file or None,
                        agent_name=agent_name or "Advanced Data Analyst",
                        max_steps=runtime_strategy["max_steps"],
                        max_reviews=runtime_strategy["max_reviews"],
                        quality_mode=runtime_strategy["quality_mode"],
                        latency_mode=runtime_strategy["latency_mode"],
                        vision_review_mode=runtime_strategy["vision_review_mode"],
                        vision_max_images=runtime_strategy["vision_max_images"],
                        vision_max_image_side=runtime_strategy["vision_max_image_side"],
                        event_handler=handle_event,
                        knowledge_paths=tuple(knowledge_paths),
                        use_rag=runtime_strategy["use_rag"],
                        use_memory=runtime_strategy["use_memory"],
                        memory_scope_key=memory_scope_key,
                        task_type=runtime_strategy["task_type"],
                        task_expectations=runtime_strategy["task_expectations"],
                        runtime_config_override=runtime_config_override,
                    )
                    event_queue.put(("result", result))
                except Exception as exc:  # pragma: no cover - covered through API tests with mock
                    api_key = runtime_config_override.api_key if runtime_config_override else ""
                    event_queue.put(
                        (
                            "error",
                            {
                                "message": redact_sensitive_text(exc, api_key),
                                "traceback": redact_sensitive_text(traceback.format_exc(), api_key),
                            },
                        )
                    )

            worker = Thread(target=run_target, daemon=True)
            worker.start()

            while True:
                try:
                    kind, payload = event_queue.get(timeout=0.1)
                except queue.Empty:
                    if not worker.is_alive():
                        break
                    await asyncio.sleep(0.05)
                    continue

                if kind == "event":
                    event_type = str(payload["eventType"])
                    event_payload = payload["payload"]
                    line = format_event_line(event_type, event_payload)
                    logs.append(line)
                    yield _sse(
                        "log",
                        {
                            "eventType": event_type,
                            "message": line,
                            "logs": logs[-400:],
                        },
                    )
                    continue

                if kind == "error":
                    message = str(payload.get("message", "分析失败"))
                    logs.append(message)
                    if payload.get("traceback"):
                        logs.append(str(payload["traceback"]))
                    yield _sse("error", {"message": message, "logs": logs})
                    return

                if kind == "result":
                    result = payload
                    bundle_path = create_run_bundle(getattr(result, "run_dir"))
                    logs.append(f"工件压缩包已生成：{bundle_path.as_posix()}")
                    yield _sse(
                        "result",
                        {
                            "message": "分析完成。",
                            "logs": logs,
                            "result": _serialize_analysis_result(result, bundle_path),
                            "workspace": _serialize_workspace(getattr(result, "run_dir").parent),
                        },
                    )
                    return

            yield _sse("error", {"message": "分析任务意外结束，未生成结果。", "logs": logs})

        return StreamingResponse(stream(), media_type="text/event-stream")

    dist_dir = root / "frontend" / "dist"
    assets_dir = dist_dir / "assets"
    index_html = dist_dir / "index.html"
    if index_html.exists():
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

        @app.get("/")
        async def frontend_root() -> FileResponse:
            return FileResponse(index_html)

        @app.get("/{full_path:path}", response_model=None)
        async def frontend_spa(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            return FileResponse(index_html)

    return app


__all__ = [
    "create_app",
]
