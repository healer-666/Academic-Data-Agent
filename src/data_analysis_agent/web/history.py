"""History scanning helpers for the React/FastAPI workspace."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class RunHistoryEntry:
    run_dir: Path
    timestamp: str
    quality_mode: str
    latency_mode: str
    input_kind: str
    document_ingestion_status: str
    document_ingestion_summary: str
    candidate_table_count: int
    selected_table_id: str
    selected_table_shape: tuple[int, int] | None
    pdf_multi_table_mode: bool
    review_status: str
    vision_review_status: str
    vision_review_summary: str
    workflow_complete: bool
    stage_contract_status: str
    stage_contract_findings: tuple[str, ...]
    stage_contract_passed: bool
    domain: str
    report_path: Path | None
    trace_path: Path | None
    cleaned_data_path: Path | None
    document_ingestion_log_path: Path | None
    figure_paths: tuple[Path, ...]
    trace_payload: dict[str, object]


def _resolve_outputs_root(outputs_root: str | Path = "outputs") -> Path:
    root = Path(outputs_root)
    return root if root.is_absolute() else (PROJECT_ROOT / root)


def _resolve_candidate_path(path_value: str | Path | None, *, base_dir: Path) -> Path | None:
    if not path_value:
        return None
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    direct = (PROJECT_ROOT / candidate).resolve()
    if direct.exists():
        return direct
    nested = (base_dir / candidate).resolve()
    if nested.exists():
        return nested
    return direct


def _read_trace_payload(trace_path: Path | None) -> dict[str, object]:
    if trace_path is None or not trace_path.exists():
        return {}
    try:
        payload = json.loads(trace_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _infer_timestamp_from_name(run_dir: Path) -> str:
    name = run_dir.name
    if not name.startswith("run_"):
        return name
    parts = name.split("_", 2)
    if len(parts) < 3:
        return name
    date_part, time_part = parts[1], parts[2]
    if len(date_part) == 8 and len(time_part) == 6:
        return (
            f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]} "
            f"{time_part[0:2]}:{time_part[2:4]}:{time_part[4:6]}"
        )
    return name


def _is_viewable_figure(path: Path) -> bool:
    """Reject mislabeled or truncated image artifacts before they reach the browser."""

    try:
        size = path.stat().st_size
        suffix = path.suffix.lower()
        if suffix == ".svg":
            if size < 11:
                return False
            with path.open("rb") as handle:
                prefix = handle.read(2048).lstrip(b"\xef\xbb\xbf\x00\t\r\n ").lower()
            return b"<svg" in prefix

        with path.open("rb") as handle:
            prefix = handle.read(32)
        if suffix == ".png":
            return (
                size >= 33
                and prefix.startswith(b"\x89PNG\r\n\x1a\n")
                and prefix[12:16] == b"IHDR"
                and int.from_bytes(prefix[16:20], "big") > 0
                and int.from_bytes(prefix[20:24], "big") > 0
            )
        if suffix in {".jpg", ".jpeg"}:
            if size < 4 or not prefix.startswith(b"\xff\xd8\xff"):
                return False
            with path.open("rb") as handle:
                handle.seek(-2, 2)
                return handle.read(2) == b"\xff\xd9"
        if suffix == ".webp":
            return size >= 20 and prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP"
    except (OSError, ValueError):
        return False
    return False


def _collect_figure_paths(run_dir: Path, trace_payload: dict[str, object]) -> tuple[Path, ...]:
    telemetry = trace_payload.get("telemetry", {})
    if isinstance(telemetry, dict):
        figure_values = telemetry.get("figures_generated", [])
        if isinstance(figure_values, list) and figure_values:
            resolved = [
                _resolve_candidate_path(item, base_dir=run_dir)
                for item in figure_values
                if str(item).strip()
            ]
            return tuple(
                path
                for path in resolved
                if path is not None and path.is_file() and _is_viewable_figure(path)
            )

    figure_dir = run_dir / "figures"
    if not figure_dir.exists():
        return ()

    image_paths = sorted(
        path
        for path in figure_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg", ".webp"}
        and _is_viewable_figure(path)
    )
    return tuple(image_paths)


def _latest_visual_summary(trace_payload: dict[str, object]) -> tuple[str, str]:
    history = trace_payload.get("vision_review_history", [])
    if isinstance(history, list) and history:
        latest = history[-1]
        if isinstance(latest, dict):
            return (
                str(latest.get("status", "skipped")).strip() or "skipped",
                str(latest.get("summary", "")).strip() or "暂无图表视觉检查摘要。",
            )
    return "skipped", "暂无图表视觉检查摘要。"


def _selected_table_shape(document_ingestion: dict[str, object]) -> tuple[int, int] | None:
    selected_shape_value = document_ingestion.get("selected_table_shape")
    if isinstance(selected_shape_value, list) and len(selected_shape_value) == 2:
        try:
            return int(selected_shape_value[0]), int(selected_shape_value[1])
        except (TypeError, ValueError):
            return None
    return None


def _build_history_entry(run_dir: Path) -> RunHistoryEntry:
    trace_path = run_dir / "logs" / "agent_trace.json"
    trace_payload = _read_trace_payload(trace_path if trace_path.exists() else None)
    run_metadata = trace_payload.get("run_metadata", {})
    telemetry = trace_payload.get("telemetry", {})
    artifact_validation = trace_payload.get("artifact_validation", {})
    document_ingestion = trace_payload.get("document_ingestion", {})

    if not isinstance(run_metadata, dict):
        run_metadata = {}
    if not isinstance(telemetry, dict):
        telemetry = {}
    if not isinstance(artifact_validation, dict):
        artifact_validation = {}
    if not isinstance(document_ingestion, dict):
        document_ingestion = {}

    report_path = run_dir / "final_report.md"
    cleaned_data_path = run_dir / "data" / "cleaned_data.csv"
    ingestion_log_path = run_dir / "logs" / "document_ingestion.json"
    vision_status, vision_summary = _latest_visual_summary(trace_payload)
    findings_value = artifact_validation.get("stage_contract_findings", [])
    findings = (
        tuple(str(item).strip() for item in findings_value if str(item).strip())
        if isinstance(findings_value, list)
        else ()
    )

    return RunHistoryEntry(
        run_dir=run_dir.resolve(),
        timestamp=str(run_metadata.get("timestamp", "")).strip() or _infer_timestamp_from_name(run_dir),
        quality_mode=str(run_metadata.get("quality_mode", "unknown")).strip() or "unknown",
        latency_mode=str(run_metadata.get("latency_mode", "auto")).strip() or "auto",
        input_kind=str(run_metadata.get("input_kind", document_ingestion.get("input_kind", "tabular"))).strip()
        or "tabular",
        document_ingestion_status=str(document_ingestion.get("status", "not_needed")).strip() or "not_needed",
        document_ingestion_summary=str(document_ingestion.get("summary", "")).strip(),
        candidate_table_count=int(document_ingestion.get("candidate_table_count", 0) or 0),
        selected_table_id=str(document_ingestion.get("selected_table_id", "")).strip(),
        selected_table_shape=_selected_table_shape(document_ingestion),
        pdf_multi_table_mode=bool(document_ingestion.get("pdf_multi_table_mode", False)),
        review_status=str(trace_payload.get("review_status", "unknown")).strip() or "unknown",
        vision_review_status=vision_status,
        vision_review_summary=vision_summary,
        workflow_complete=bool(artifact_validation.get("workflow_complete", False)),
        stage_contract_status=str(artifact_validation.get("stage_contract_status", "not_checked")).strip()
        or "not_checked",
        stage_contract_findings=findings,
        stage_contract_passed=bool(artifact_validation.get("stage_contract_passed", False)),
        domain=str(telemetry.get("domain", "unknown")).strip() or "unknown",
        report_path=report_path.resolve() if report_path.exists() else None,
        trace_path=trace_path.resolve() if trace_path.exists() else None,
        cleaned_data_path=cleaned_data_path.resolve() if cleaned_data_path.exists() else None,
        document_ingestion_log_path=ingestion_log_path.resolve() if ingestion_log_path.exists() else None,
        figure_paths=_collect_figure_paths(run_dir, trace_payload),
        trace_payload=trace_payload,
    )


def scan_run_history(outputs_root: str | Path = "outputs", *, limit: int | None = None) -> list[RunHistoryEntry]:
    root = _resolve_outputs_root(outputs_root)
    if not root.exists():
        return []

    candidates = sorted(
        (candidate for candidate in root.iterdir() if candidate.is_dir() and candidate.name.startswith("run_")),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    entries = [_build_history_entry(candidate) for candidate in candidates]
    entries = [entry for entry in entries if entry.report_path or entry.trace_path or entry.cleaned_data_path]
    entries = sorted(entries, key=lambda item: (item.timestamp, item.run_dir.name), reverse=True)
    return entries[: max(0, int(limit))] if limit is not None else entries


def find_run_history(run_id: str, outputs_root: str | Path = "outputs") -> RunHistoryEntry | None:
    root = _resolve_outputs_root(outputs_root).resolve()
    normalized_run_id = Path(str(run_id)).name
    candidate = (root / normalized_run_id).resolve()
    if (
        normalized_run_id != str(run_id)
        or candidate.parent != root
        or not candidate.is_dir()
        or not candidate.name.startswith("run_")
    ):
        return None
    entry = _build_history_entry(candidate)
    if not (entry.report_path or entry.trace_path or entry.cleaned_data_path):
        return None
    return entry
