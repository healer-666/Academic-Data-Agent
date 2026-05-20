"""Lightweight provenance DAG generation for analysis runs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .reporting import ReportTelemetry
from .runtime_models import AgentStepTrace, ArtifactValidationResult, RunContext


ARTIFACT_EXTENSIONS = {
    ".csv",
    ".tsv",
    ".xlsx",
    ".xls",
    ".json",
    ".jsonl",
    ".txt",
    ".md",
    ".png",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".html",
    ".parquet",
    ".pkl",
}


@dataclass(frozen=True)
class LineageArtifact:
    json_path: Path
    mermaid_path: Path
    status: str
    node_count: int
    edge_count: int
    missing_artifact_count: int

    def to_trace_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "json_path": self.json_path.as_posix(),
            "mermaid_path": self.mermaid_path.as_posix(),
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "missing_artifact_count": self.missing_artifact_count,
        }


def _stable_id(prefix: str, value: str, index: int) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", f"{prefix}_{index}_{Path(value).stem or value}")[:80]
    return cleaned.strip("_") or f"{prefix}_{index}"


def _path_payload(path: Path, node_type: str, *, status: str = "present", label: str | None = None) -> dict[str, Any]:
    return {
        "id": "",
        "type": node_type,
        "label": label or path.name,
        "path": path.as_posix(),
        "status": status,
        "exists": path.exists(),
    }


def _extract_artifact_names(text: str) -> tuple[str, ...]:
    names: list[str] = []
    for match in re.finditer(
        r"(?<![\w.-])([\w./\\:-]+\.(?:csv|tsv|xlsx|xls|json|jsonl|txt|md|png|jpg|jpeg|pdf|html|parquet|pkl))",
        str(text or ""),
        re.IGNORECASE,
    ):
        name = match.group(1).strip("`'\"),.;")
        if Path(name).suffix.lower() in ARTIFACT_EXTENSIONS and name not in names:
            names.append(name)
    return tuple(names)


def _add_node(nodes: list[dict[str, Any]], node: dict[str, Any], *, prefix: str) -> str:
    path = str(node.get("path", ""))
    label = str(node.get("label", ""))
    key = (node.get("type"), path, label)
    for existing in nodes:
        if (existing.get("type"), existing.get("path", ""), existing.get("label", "")) == key:
            return str(existing["id"])
    node_id = _stable_id(prefix, path or label, len(nodes) + 1)
    node["id"] = node_id
    nodes.append(node)
    return node_id


def _add_edge(edges: list[dict[str, str]], source: str, target: str, label: str) -> None:
    edge = {"source": source, "target": target, "label": label}
    if edge not in edges:
        edges.append(edge)


def _candidate_generated_paths(run_context: RunContext, telemetry: ReportTelemetry, traces: Iterable[AgentStepTrace]) -> list[Path]:
    paths: list[Path] = []
    for figure in telemetry.figures_generated:
        candidate = Path(str(figure))
        if not candidate.is_absolute():
            candidate = run_context.run_dir / candidate
        if candidate not in paths:
            paths.append(candidate)
    for trace in traces:
        combined = "\n".join([trace.tool_input or "", trace.observation or "", trace.observation_preview or ""])
        for candidate_text in _extract_artifact_names(combined):
            candidate = Path(candidate_text)
            if not candidate.is_absolute():
                candidate = run_context.run_dir / candidate
            if candidate.exists() and candidate not in paths and candidate != run_context.cleaned_data_path:
                try:
                    candidate.relative_to(run_context.run_dir)
                except ValueError:
                    continue
                paths.append(candidate)
    return paths


def _contract_required_artifacts(lineage_contract: dict[str, Any] | None) -> tuple[str, ...]:
    if not lineage_contract:
        return ()
    values = lineage_contract.get("required_artifacts") or []
    return tuple(str(item) for item in values if str(item).strip())


def _contract_metrics(lineage_contract: dict[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if not lineage_contract:
        return ()
    metrics = lineage_contract.get("metrics") or []
    return tuple(dict(item) for item in metrics if isinstance(item, dict))


def write_lineage_artifacts(
    *,
    run_context: RunContext,
    step_traces: tuple[AgentStepTrace, ...],
    telemetry: ReportTelemetry,
    artifact_validation: ArtifactValidationResult,
    lineage_contract: dict[str, Any] | None = None,
) -> LineageArtifact:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []

    raw_id = _add_node(nodes, _path_payload(run_context.source_path, "raw_data"), prefix="raw")
    clean_id = _add_node(
        nodes,
        _path_payload(
            run_context.cleaned_data_path,
            "cleaned_data",
            status="present" if run_context.cleaned_data_path.exists() else "missing",
        ),
        prefix="cleaned",
    )
    report_id = _add_node(
        nodes,
        _path_payload(
            run_context.report_path,
            "final_report",
            status="present" if run_context.report_path.exists() else "missing",
        ),
        prefix="report",
    )

    cleaning_step_id = ""
    analysis_step_ids: list[str] = []
    for trace in step_traces:
        if trace.tool_name != "PythonInterpreterTool":
            continue
        code = trace.tool_input or ""
        is_cleaning = run_context.cleaned_data_path.as_posix() in code or "cleaned_data.csv" in code
        node_id = _add_node(
            nodes,
            {
                "id": "",
                "type": "python_step",
                "label": f"Python step {trace.step_index}",
                "path": "",
                "status": trace.tool_status,
                "step_index": trace.step_index,
                "summary": trace.summary or trace.observation_preview,
            },
            prefix="python",
        )
        if is_cleaning and not cleaning_step_id:
            cleaning_step_id = node_id
        else:
            analysis_step_ids.append(node_id)

    if cleaning_step_id:
        _add_edge(edges, raw_id, cleaning_step_id, "read")
        _add_edge(edges, cleaning_step_id, clean_id, "writes")
    else:
        _add_edge(edges, raw_id, clean_id, "expected_cleaning")

    generated_paths = _candidate_generated_paths(run_context, telemetry, step_traces)
    latest_analysis_id = analysis_step_ids[-1] if analysis_step_ids else cleaning_step_id or clean_id
    if latest_analysis_id != clean_id:
        _add_edge(edges, clean_id, latest_analysis_id, "analyzes")
    generated_node_ids: dict[str, str] = {}
    for path in generated_paths:
        node_type = "figure" if path.suffix.lower() in {".png", ".jpg", ".jpeg"} else "generated_artifact"
        node_id = _add_node(
            nodes,
            _path_payload(path, node_type, status="present" if path.exists() else "missing"),
            prefix=node_type,
        )
        generated_node_ids[path.name] = node_id
        _add_edge(edges, latest_analysis_id, node_id, "creates")
        _add_edge(edges, node_id, report_id, "reported_in")

    required = _contract_required_artifacts(lineage_contract)
    metrics = _contract_metrics(lineage_contract)
    for name in required:
        path = run_context.run_dir / name
        node_id = generated_node_ids.get(name)
        if not node_id:
            matching = [path_item for path_item in generated_paths if path_item.name == name]
            path = matching[0] if matching else path
            node_id = _add_node(
                nodes,
                _path_payload(path, "generated_artifact", status="present" if path.exists() else "missing", label=name),
                prefix="contract_artifact",
            )
            _add_edge(edges, latest_analysis_id, node_id, "creates")
            _add_edge(edges, node_id, report_id, "reported_in")
        for index, metric in enumerate(metrics, start=1):
            if name not in set(metric.get("output_files") or []):
                continue
            metric_id = _add_node(
                nodes,
                {
                    "id": "",
                    "type": "contract_metric",
                    "label": str(metric.get("metric") or metric.get("function") or f"metric_{index}"),
                    "path": "",
                    "status": "expected",
                    "task_name": str(metric.get("task_name") or ""),
                },
                prefix="metric",
            )
            _add_edge(edges, node_id, metric_id, "scored_by")

    payload = {
        "version": 1,
        "run_id": run_context.run_id,
        "status": "generated",
        "nodes": nodes,
        "edges": edges,
        "artifact_validation": {
            "workflow_complete": artifact_validation.workflow_complete,
            "missing_artifacts": list(artifact_validation.missing_artifacts),
            "warnings": list(artifact_validation.warnings),
        },
    }
    json_path = run_context.logs_dir / "lineage.json"
    mermaid_path = run_context.logs_dir / "lineage.mmd"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    mermaid_path.write_text(render_mermaid(payload), encoding="utf-8")

    missing_count = sum(1 for node in nodes if node.get("status") == "missing" or node.get("exists") is False)
    return LineageArtifact(
        json_path=json_path,
        mermaid_path=mermaid_path,
        status="generated",
        node_count=len(nodes),
        edge_count=len(edges),
        missing_artifact_count=missing_count,
    )


def render_mermaid(payload: dict[str, Any]) -> str:
    lines = ["flowchart TD"]
    node_shapes = {
        "raw_data": ('[["', '"]]'),
        "cleaned_data": ('[["', '"]]'),
        "python_step": ('["', '"]'),
        "generated_artifact": ('[/"', '"/]'),
        "figure": ('[/"', '"/]'),
        "final_report": ('[["', '"]]'),
        "contract_metric": ('(("', '"))'),
    }
    for node in payload.get("nodes", []):
        node_id = str(node.get("id", "node"))
        label = str(node.get("label", node_id)).replace('"', "'")
        if node.get("status") == "missing":
            label = f"{label} (missing)"
        left, right = node_shapes.get(str(node.get("type")), ('["', '"]'))
        lines.append(f"  {node_id}{left}{label}{right}")
    for edge in payload.get("edges", []):
        label = str(edge.get("label", "")).replace('"', "'")
        lines.append(f"  {edge['source']} -->|{label}| {edge['target']}")
    return "\n".join(lines).strip() + "\n"
