"""Generate result-level interactive report evidence for new and historical runs."""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .lineage_detail import (
    ArtifactSemantics,
    DerivedField,
    ReportClaim,
    StepSemantics,
    extract_report_claims,
    extract_step_semantics,
    fields_for_claim,
    match_claim_to_steps,
    unwrap_python_code,
)
from .reporting import ReportTelemetry
from .runtime_models import AgentStepTrace, RunContext


MANIFEST_FILENAME = "interactive_report_manifest.json"
SNAPSHOT_FILENAME = "interactive_report_snapshot.json"
SOURCE_MAP_FILENAME = "source_map.json"
GENERATOR_VERSION = 9
_MAX_SNAPSHOT_ROWS = 200
_ARTIFACT_EXTENSIONS = (".csv", ".tsv", ".xlsx", ".xls", ".json", ".png", ".jpg", ".jpeg")


@dataclass(frozen=True)
class InteractiveReportArtifact:
    manifest_path: Path
    snapshot_path: Path
    source_map_path: Path
    status: str
    figure_count: int
    claim_count: int
    dataset_count: int
    source_count: int
    unmatched_figure_count: int = 0
    unmatched_claim_count: int = 0
    warnings: tuple[str, ...] = ()

    def to_trace_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "manifest_path": self.manifest_path.as_posix(),
            "snapshot_path": self.snapshot_path.as_posix(),
            "source_map_path": self.source_map_path.as_posix(),
            "figure_count": self.figure_count,
            "claim_count": self.claim_count,
            "dataset_count": self.dataset_count,
            "source_count": self.source_count,
            "reviewable_figure_count": self.figure_count - self.unmatched_figure_count,
            "reviewable_claim_count": self.claim_count - self.unmatched_claim_count,
            "unmatched_figure_count": self.unmatched_figure_count,
            "unmatched_claim_count": self.unmatched_claim_count,
            "warnings": list(self.warnings),
        }


def _stable_id(prefix: str, value: str, index: int) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\u3400-\u9fff]+", "_", f"{prefix}_{index}_{value}")[:100]
    return cleaned.strip("_") or f"{prefix}_{index}"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_lineage(run_context: RunContext) -> dict[str, Any]:
    return _load_json(run_context.logs_dir / "lineage.json")


def _tool_stdout(trace: AgentStepTrace) -> str:
    raw = str(trace.observation or "")
    try:
        payload = json.loads(raw)
    except Exception:
        payload = {}
    if isinstance(payload, dict):
        data = payload.get("data", {})
        if isinstance(data, dict) and str(data.get("stdout", "")).strip():
            return str(data["stdout"]).strip()
        if str(payload.get("text", "")).strip():
            return str(payload["text"]).strip()
    return str(trace.observation_preview or trace.summary or "").strip()


def _report_figure_paths(run_context: RunContext, report_markdown: str, telemetry: ReportTelemetry) -> tuple[Path, ...]:
    candidates: list[Path] = []
    for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", report_markdown or ""):
        raw = match.group(1).strip()
        if raw.startswith(("http://", "https://", "/api/files")):
            continue
        candidates.append(Path(raw))
    candidates.extend(Path(str(value)) for value in telemetry.figures_generated)
    if not candidates and run_context.figures_dir.exists():
        candidates.extend(
            path for path in sorted(run_context.figures_dir.rglob("*"))
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
        )
    paths: list[Path] = []
    for candidate in candidates:
        if not candidate.is_absolute():
            options = ((Path.cwd() / candidate).resolve(), (run_context.run_dir / candidate).resolve())
            candidate = next((path for path in options if path.exists()), options[0])
        else:
            candidate = candidate.resolve()
        if candidate.exists() and candidate.suffix.lower() in {".png", ".jpg", ".jpeg"} and candidate not in paths:
            paths.append(candidate)
    return tuple(paths)


def _read_table(path: Path) -> tuple[pd.DataFrame | None, str]:
    try:
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path), ""
        if path.suffix.lower() in {".xlsx", ".xls"}:
            with pd.ExcelFile(path) as book:
                sheet = str(book.sheet_names[0]) if book.sheet_names else ""
                return pd.read_excel(book, sheet_name=sheet or 0), sheet
    except Exception:
        return None, ""
    return None, ""


def _normalized(value: Any) -> str:
    if pd.isna(value):
        return "<NA>"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _json_scalar(value: Any) -> Any:
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def _source_row_mapping(cleaned: pd.DataFrame, source: pd.DataFrame | None) -> list[int | None]:
    if source is None:
        return [None] * len(cleaned)
    shared = [column for column in cleaned.columns if column in source.columns]
    if not shared:
        return [None] * len(cleaned)
    positions: dict[tuple[str, ...], deque[int]] = defaultdict(deque)
    for position, row in source[shared].iterrows():
        positions[tuple(_normalized(row[column]) for column in shared)].append(int(position) + 2)
    mapped: list[int | None] = []
    for _, row in cleaned[shared].iterrows():
        key = tuple(_normalized(row[column]) for column in shared)
        mapped.append(positions[key].popleft() if positions[key] else None)
    return mapped


def _compact_ranges(values: Iterable[int]) -> str:
    numbers = sorted(set(int(value) for value in values))
    if not numbers:
        return "未能精确定位"
    ranges: list[str] = []
    start = previous = numbers[0]
    for value in numbers[1:]:
        if value == previous + 1:
            previous = value
            continue
        ranges.append(str(start) if start == previous else f"{start}–{previous}")
        start = previous = value
    ranges.append(str(start) if start == previous else f"{start}–{previous}")
    return "、".join(ranges)


def _derived_definition(field: str, semantics: StepSemantics | None) -> DerivedField | None:
    if semantics is None:
        return None
    return next((item for item in semantics.derived_fields if item.name == field), None)


def _materialize_derived(frame: pd.DataFrame, fields: Iterable[str], semantics: StepSemantics | None) -> pd.DataFrame:
    result = frame.copy()
    for field in fields:
        if field in result.columns:
            continue
        definition = _derived_definition(field, semantics)
        if definition and definition.operation == "string_length" and definition.source_fields:
            source = definition.source_fields[0]
            if source in result.columns:
                result[field] = result[source].astype(str).str.len()
    return result


def _dataset_snapshot(
    *,
    dataset_id: str,
    label: str,
    run_context: RunContext,
    fields: Iterable[str],
    semantics: StepSemantics | None,
    row_selector: str,
    filter_conditions: Iterable[str],
    step_index: int | None,
    code_lines: tuple[int, int] | None,
    confidence: float | str,
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    cleaned, _ = _read_table(run_context.cleaned_data_path)
    if cleaned is None:
        return None, ("cleaned_data_unreadable",)
    source, sheet = _read_table(run_context.source_path)
    source_rows = _source_row_mapping(cleaned, source)
    requested = [field for field in dict.fromkeys(str(field).strip() for field in fields) if field]
    materialized = _materialize_derived(cleaned, requested, semantics)
    selected = [field for field in requested if field in materialized.columns]
    warnings: list[str] = []
    if not selected:
        warnings.append("result_columns_unresolved")
    view = materialized[selected].head(_MAX_SNAPSHOT_ROWS) if selected else materialized.head(min(30, _MAX_SNAPSHOT_ROWS))
    rows: list[dict[str, Any]] = []
    for output_index, (cleaned_index, row) in enumerate(view.iterrows(), start=1):
        payload = {column: _json_scalar(row[column]) for column in view.columns}
        payload["__cleaned_row__"] = int(cleaned_index) + 1
        payload["__source_row__"] = source_rows[int(cleaned_index)] if int(cleaned_index) < len(source_rows) else None
        rows.append(payload)
    derived = [
        {
            "name": field,
            "sourceFields": list(definition.source_fields),
            "operation": definition.operation,
            "expression": definition.expression,
        }
        for field in selected
        if (definition := _derived_definition(field, semantics)) is not None
    ]
    mapped_source_rows = [value for value in source_rows if value is not None]
    source_row_label = _compact_ranges(mapped_source_rows)
    cleaned_row_label = _compact_ranges(range(1, len(cleaned) + 1))
    locator = {
        "sourcePath": run_context.source_path.as_posix(),
        "sourceSheet": sheet,
        "sourceRows": source_row_label,
        "cleanedPath": run_context.cleaned_data_path.as_posix(),
        "cleanedRows": cleaned_row_label,
        "columns": selected,
        "rowSelector": row_selector,
        "filterConditions": list(filter_conditions),
        "derivedFields": derived,
        "stepIndex": step_index,
        "codeLineStart": code_lines[0] if code_lines else None,
        "codeLineEnd": code_lines[1] if code_lines else None,
        "confidence": confidence,
        "sourceRowMappingCoverage": round(len(mapped_source_rows) / len(cleaned), 4) if len(cleaned) else 1.0,
    }
    columns = [
        {"key": "__cleaned_row__", "label": "清洗后行号", "type": "integer"},
        {"key": "__source_row__", "label": "原始文件行号", "type": "integer"},
        *[
            {"key": str(column), "label": str(column), "type": str(view[column].dtype)}
            for column in view.columns
        ],
    ]
    return {
        "id": dataset_id,
        "label": label,
        "sourcePath": run_context.cleaned_data_path.as_posix(),
        "rowCount": int(len(cleaned)),
        "sampleRowCount": len(rows),
        "truncated": len(cleaned) > len(rows),
        "columns": columns,
        "rows": rows,
        "locator": locator,
    }, tuple(warnings)


def _lineage_ids_for_step(lineage: dict[str, Any], step_index: int | None) -> tuple[str, ...]:
    if step_index is None:
        return ()
    return tuple(
        str(node.get("id")) for node in lineage.get("nodes", [])
        if isinstance(node, dict)
        and (node.get("step_index") == step_index or node.get("label") == f"Python step {step_index}")
        and node.get("id")
    )


def _artifact_match(
    path: Path,
    traces: tuple[AgentStepTrace, ...],
    semantics: tuple[StepSemantics, ...],
) -> tuple[AgentStepTrace | None, StepSemantics | None, ArtifactSemantics | None, str]:
    semantics_by_step = {item.step_index: item for item in semantics}
    successful = [
        trace for trace in traces
        if trace.tool_name == "PythonInterpreterTool" and str(trace.tool_status).lower() in {"success", "partial"}
    ]
    for trace in successful:
        step = semantics_by_step.get(trace.step_index)
        artifact = next((item for item in (step.artifacts if step else ()) if item.artifact_name == path.name), None)
        if artifact:
            return trace, step, artifact, "exact_artifact"
        if path.name in str(trace.tool_input or "") or path.name in str(trace.observation or ""):
            return trace, step, None, "step_artifact"
    return None, None, None, "unmatched"


def _fields_for_artifact(artifact: ArtifactSemantics | None, step: StepSemantics | None, figure_name: str) -> tuple[str, ...]:
    if step is None:
        return ()
    fields = list(artifact.fields if artifact else step.read_fields)
    normalized_name = figure_name.lower().replace("-", "_")
    category_fields = [
        field for field in (*step.read_fields, *step.written_fields)
        if any(token in field.lower() for token in ("分类", "类别", "category", "group"))
    ]
    if any(token in normalized_name for token in ("category", "group", "class", "分类", "pie", "distribution")):
        fields = category_fields
    for derived in step.derived_fields:
        derived_key = derived.name.lower().replace("-", "_")
        if derived_key in normalized_name or ("length" in normalized_name and "length" in derived_key):
            fields.extend((derived.name, *derived.source_fields))
            fields.extend(category_fields)
    if "count" in normalized_name or "distribution" in normalized_name:
        identifier = next(
            (field for field in step.read_fields if any(token in field.lower() for token in ("编码", "id", "code"))),
            "",
        )
        if identifier:
            fields.append(identifier)
    return tuple(dict.fromkeys(field for field in fields if field))


def _source_entry(
    *,
    source_id: str,
    trace: AgentStepTrace,
    code: str,
    summary: str,
    confidence: float | str,
    reason: str,
    lineage_ids: Iterable[str],
    code_lines: tuple[int, int] | None = None,
) -> dict[str, Any]:
    reason_labels = {
        "explicit_reference": "报告中保存了该计算步骤的明确引用",
        "numeric_overlap": "报告数值与该步骤运行输出一致",
        "field_overlap": "报告字段与该步骤读取字段一致",
        "statistical_keyword_overlap": "统计方法与该步骤运行记录一致",
    }
    readable_reason = "、".join(
        reason_labels.get(part, part) for part in str(reason or "").split("+") if part
    )
    return {
        "id": source_id,
        "type": "python",
        "label": f"Python step {trace.step_index}",
        "stepIndex": trace.step_index,
        "toolName": trace.tool_name or "PythonInterpreterTool",
        "status": trace.tool_status,
        "code": code,
        "stdout": _tool_stdout(trace),
        "summary": summary or trace.decision or trace.summary or trace.observation_preview or "",
        "confidence": confidence,
        "matchReason": readable_reason or "依据结果与运行记录的对应关系定位",
        "codeLineStart": code_lines[0] if code_lines else None,
        "codeLineEnd": code_lines[1] if code_lines else None,
        "lineageNodeIds": list(lineage_ids),
    }


def _claim_code(code: str, fields: Iterable[str], claim: ReportClaim) -> tuple[str, tuple[int, int] | None]:
    lines = code.splitlines()
    needles = [field.lower() for field in fields if field]
    needles.extend(keyword.lower() for keyword in claim.keyword_tokens)
    claim_text = f"{claim.section} {claim.text}".lower()
    if "χ" in claim_text or "卡方" in claim_text or "chi-square" in claim_text:
        needles.extend(("chisquare", "chi2", "cramer"))
    if "kruskal" in claim_text or re.search(r"\bh\s*\(", claim_text):
        needles.extend(("kruskal", "h_stat", "eps_"))
    if "mann" in claim_text or "u =" in claim_text or "事后" in claim_text:
        needles.extend(("mannwhitney", "u_stat", "p_bonf"))
    matched = [index for index, line in enumerate(lines) if any(needle in line.lower() for needle in needles)]
    if not matched:
        preview = "\n".join(lines[:80])
        return preview, (1, min(len(lines), 80)) if lines else None
    intervals: list[list[int]] = []
    for index in matched:
        start, end = max(0, index - 1), min(len(lines), index + 2)
        if intervals and start <= intervals[-1][1] + 1:
            intervals[-1][1] = max(intervals[-1][1], end)
        else:
            intervals.append([start, end])
    intervals = intervals[:10]
    snippets = [
        f"# 原代码第 {start + 1}–{end} 行\n" + "\n".join(lines[start:end])
        for start, end in intervals
    ]
    return "\n\n".join(snippets), (intervals[0][0] + 1, intervals[-1][1])


def build_interactive_report_artifacts(
    *,
    run_context: RunContext,
    report_markdown: str,
    telemetry: ReportTelemetry,
    step_traces: tuple[AgentStepTrace, ...],
) -> InteractiveReportArtifact:
    run_context.logs_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_context.logs_dir / MANIFEST_FILENAME
    snapshot_path = run_context.logs_dir / SNAPSHOT_FILENAME
    source_map_path = run_context.logs_dir / SOURCE_MAP_FILENAME
    warnings: list[str] = []
    lineage = _load_lineage(run_context)
    semantics = extract_step_semantics(step_traces, artifact_extensions=_ARTIFACT_EXTENSIONS)
    semantics_by_step = {item.step_index: item for item in semantics}
    source_entries: dict[str, dict[str, Any]] = {}
    dataset_entries: dict[str, dict[str, Any]] = {}
    source_map: dict[str, Any] = {"version": 2, "runId": run_context.run_id, "figures": {}, "claims": {}, "tables": {}}
    figures: list[dict[str, Any]] = []

    for index, figure_path in enumerate(_report_figure_paths(run_context, report_markdown, telemetry), start=1):
        figure_id = _stable_id("figure", figure_path.stem, index)
        trace, step, artifact, confidence = _artifact_match(figure_path, step_traces, semantics)
        source_id = f"source_{trace.step_index}_{figure_id}" if trace else ""
        dataset_id = f"dataset_{figure_id}"
        fields = _fields_for_artifact(artifact, step, figure_path.name)
        row_selector = artifact.row_selector if artifact else "该步骤读取的数据行；未能进一步解析图表筛选条件"
        filters = artifact.filter_conditions if artifact else ()
        code_lines = (artifact.code_line_start, artifact.code_line_end) if artifact else None
        dataset, dataset_warnings = _dataset_snapshot(
            dataset_id=dataset_id,
            label=f"{figure_path.name} 使用的数据",
            run_context=run_context,
            fields=fields,
            semantics=step,
            row_selector=row_selector,
            filter_conditions=filters,
            step_index=trace.step_index if trace else None,
            code_lines=code_lines,
            confidence=confidence,
        )
        warnings.extend(dataset_warnings)
        if dataset:
            dataset_entries[dataset_id] = dataset
        lineage_ids = _lineage_ids_for_step(lineage, trace.step_index if trace else None)
        if trace:
            source_entries[source_id] = _source_entry(
                source_id=source_id,
                trace=trace,
                code=artifact.focused_code if artifact else unwrap_python_code(trace.tool_input or ""),
                summary=f"生成图表：{figure_path.name}",
                confidence=confidence,
                reason="按图表文件名定位到具体保存语句" if artifact else "按步骤中的图表文件名定位",
                lineage_ids=lineage_ids,
                code_lines=code_lines,
            )
        figure_payload = {
            "id": figure_id,
            "type": "image",
            "title": figure_path.stem.replace("_", " "),
            "name": figure_path.name,
            "path": figure_path.as_posix(),
            "datasetId": dataset_id if dataset else "",
            "sourceId": source_id,
            "lineageNodeIds": list(lineage_ids),
            "matchConfidence": confidence,
        }
        figures.append(figure_payload)
        source_map["figures"][figure_id] = {
            "datasetId": dataset_id if dataset else "",
            "sourceIds": [source_id] if source_id else [],
            "stepIndex": trace.step_index if trace else None,
            "codeLineStart": code_lines[0] if code_lines else None,
            "codeLineEnd": code_lines[1] if code_lines else None,
            "lineageNodeIds": list(lineage_ids),
            "confidence": confidence,
        }

    claims: list[dict[str, Any]] = []
    traces_by_step = {trace.step_index: trace for trace in step_traces}
    for claim in extract_report_claims(report_markdown):
        claim_id = _stable_id("claim", claim.text[:48], claim.claim_index)
        matches = match_claim_to_steps(claim, semantics)
        source_ids: list[str] = []
        dataset_id = ""
        locator_confidence: float | str = "unmatched"
        match_details: list[dict[str, Any]] = []
        if matches:
            step_index, locator_confidence, reason = matches[0]
            step = semantics_by_step.get(step_index)
            trace = traces_by_step.get(step_index)
            fields = fields_for_claim(claim, step) if step else ()
            dataset_id = f"dataset_{claim_id}"
            if trace and step:
                focus_code, code_lines = _claim_code(unwrap_python_code(trace.tool_input or ""), fields, claim)
                source_id = f"source_{step_index}_{claim_id}"
                lineage_ids = _lineage_ids_for_step(lineage, step_index)
                source_entries[source_id] = _source_entry(
                    source_id=source_id,
                    trace=trace,
                    code=focus_code,
                    summary=f"复核结论：{claim.text[:60]}",
                    confidence=locator_confidence,
                    reason=reason,
                    lineage_ids=lineage_ids,
                    code_lines=code_lines,
                )
                source_ids.append(source_id)
                row_selector = "清洗后数据的全部行"
                if any("分类" in field or "category" in field.lower() for field in fields):
                    grouping = next((field for field in fields if "分类" in field or "category" in field.lower()), "分类字段")
                    row_selector = f"清洗后数据的全部行，按「{grouping}」分组或比较"
                dataset, dataset_warnings = _dataset_snapshot(
                    dataset_id=dataset_id,
                    label=f"结论 {claim.claim_index} 使用的数据",
                    run_context=run_context,
                    fields=fields,
                    semantics=step,
                    row_selector=row_selector,
                    filter_conditions=(),
                    step_index=step_index,
                    code_lines=code_lines,
                    confidence=locator_confidence,
                )
                warnings.extend(dataset_warnings)
                if dataset:
                    dataset_entries[dataset_id] = dataset
                else:
                    dataset_id = ""
            match_details = [
                {"stepIndex": item[0], "confidence": item[1], "reason": item[2]}
                for item in matches
            ]
        claim_payload = {
            "id": claim_id,
            "text": claim.text,
            "section": claim.section,
            "sourceIds": source_ids,
            "datasetId": dataset_id,
            "numericTokens": list(claim.numeric_tokens),
            "matchConfidence": locator_confidence,
        }
        claims.append(claim_payload)
        source_map["claims"][claim_id] = {
            "sourceIds": source_ids,
            "datasetId": dataset_id,
            "matches": match_details,
            "confidence": locator_confidence,
        }

    generated_at = datetime.now().isoformat(timespec="seconds")
    unmatched_figure_count = sum(1 for item in figures if item["matchConfidence"] == "unmatched")
    unmatched_claim_count = sum(1 for item in claims if item["matchConfidence"] == "unmatched")
    manifest = {
        "version": 2,
        "generatorVersion": GENERATOR_VERSION,
        "surface": "interactive_report",
        "runId": run_context.run_id,
        "generatedAt": generated_at,
        "figures": figures,
        "claims": claims,
        "sources": list(source_entries.values()),
        "summary": {
            "figureCount": len(figures),
            "claimCount": len(claims),
            "datasetCount": len(dataset_entries),
            "sourceCount": len(source_entries),
            "unmatchedFigureCount": unmatched_figure_count,
            "unmatchedClaimCount": unmatched_claim_count,
        },
    }
    snapshot = {"version": 2, "runId": run_context.run_id, "generatedAt": generated_at, "datasets": dataset_entries}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    source_map_path.write_text(json.dumps(source_map, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return InteractiveReportArtifact(
        manifest_path=manifest_path,
        snapshot_path=snapshot_path,
        source_map_path=source_map_path,
        status="generated",
        figure_count=len(figures),
        claim_count=len(claims),
        dataset_count=len(dataset_entries),
        source_count=len(source_entries),
        unmatched_figure_count=unmatched_figure_count,
        unmatched_claim_count=unmatched_claim_count,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _trace_records(payload: dict[str, Any]) -> tuple[AgentStepTrace, ...]:
    allowed = set(AgentStepTrace.__dataclass_fields__)
    records: list[AgentStepTrace] = []
    for raw in payload.get("step_traces", []):
        if not isinstance(raw, dict):
            continue
        values = {key: value for key, value in raw.items() if key in allowed}
        values.setdefault("step_index", len(records) + 1)
        values.setdefault("raw_response", "")
        values.setdefault("action", "")
        records.append(AgentStepTrace(**values))
    return tuple(records)


def ensure_interactive_report_for_run(run_dir: Path) -> InteractiveReportArtifact | None:
    """Backfill precise interactive evidence for a historical run when missing."""
    run_dir = run_dir.resolve()
    logs_dir = run_dir / "logs"
    manifest_path = logs_dir / MANIFEST_FILENAME
    snapshot_path = logs_dir / SNAPSHOT_FILENAME
    source_map_path = logs_dir / SOURCE_MAP_FILENAME
    if manifest_path.exists() and snapshot_path.exists() and source_map_path.exists():
        manifest = _load_json(manifest_path)
        if int(manifest.get("generatorVersion", 0)) >= GENERATOR_VERSION:
            summary = manifest.get("summary", {}) if isinstance(manifest.get("summary"), dict) else {}
            return InteractiveReportArtifact(
                manifest_path, snapshot_path, source_map_path, "existing",
                int(summary.get("figureCount", 0)), int(summary.get("claimCount", 0)),
                int(summary.get("datasetCount", 0)), int(summary.get("sourceCount", 0)),
                int(summary.get("unmatchedFigureCount", 0)),
                int(summary.get("unmatchedClaimCount", 0)),
            )
    report_path = run_dir / "final_report.md"
    trace_path = logs_dir / "agent_trace.json"
    cleaned_path = run_dir / "data" / "cleaned_data.csv"
    if not report_path.exists() or not trace_path.exists() or not cleaned_path.exists():
        return None
    trace_payload = _load_json(trace_path)
    metadata = trace_payload.get("run_metadata", {}) if isinstance(trace_payload.get("run_metadata"), dict) else {}
    source_path = Path(str(metadata.get("data_path", "")))
    if not source_path.is_absolute():
        source_path = (Path.cwd() / source_path).resolve()
    telemetry_payload = trace_payload.get("telemetry", {}) if isinstance(trace_payload.get("telemetry"), dict) else {}
    telemetry = ReportTelemetry(
        figures_generated=tuple(str(item) for item in telemetry_payload.get("figures_generated", []) or []),
        cleaned_data_path=str(cleaned_path),
        valid=True,
    )
    context = RunContext(
        run_id=run_dir.name,
        session_id=str(metadata.get("session_id", run_dir.name)),
        source_path=source_path,
        output_root=run_dir.parent,
        run_dir=run_dir,
        data_dir=run_dir / "data",
        figures_dir=run_dir / "figures",
        logs_dir=logs_dir,
        cleaned_data_path=cleaned_path,
        report_path=report_path,
        trace_path=trace_path,
        quality_mode=str(metadata.get("quality_mode", "standard")),
        latency_mode=str(metadata.get("latency_mode", "auto")),
        vision_review_mode=str(metadata.get("vision_review_mode", "auto")),
        document_ingestion_mode=str(metadata.get("document_ingestion_mode", "tabular_only")),
    )
    return build_interactive_report_artifacts(
        run_context=context,
        report_markdown=report_path.read_text(encoding="utf-8"),
        telemetry=telemetry,
        step_traces=_trace_records(trace_payload),
    )
