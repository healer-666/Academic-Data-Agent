"""Inspectable multi-file workspace for data-intensive modeling problems."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd


PACKAGE_SCHEMA_VERSION = 1
MAX_RELATIONSHIPS = 20
MAX_RELATION_VALUES = 5000


class ModelingWorkspaceError(ValueError):
    """Raised when a modeling package is invalid or cannot be updated safely."""


class ModelingWorkspace:
    """Create, inspect, and correct persisted modeling-problem packages."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def create(
        self,
        package_id: str,
        *,
        problem_path: str | Path,
        data_paths: Sequence[str | Path],
        attachment_paths: Sequence[str | Path] = (),
    ) -> dict[str, Any]:
        safe_id = _safe_package_id(package_id)
        problem = Path(problem_path).resolve()
        data_files = tuple(Path(path).resolve() for path in data_paths)
        attachments = tuple(Path(path).resolve() for path in attachment_paths)
        if not problem.is_file():
            raise ModelingWorkspaceError("Problem statement file does not exist.")
        if not data_files:
            raise ModelingWorkspaceError("At least one CSV or Excel data file is required.")
        if any(not path.is_file() for path in (*data_files, *attachments)):
            raise ModelingWorkspaceError("One or more package files do not exist.")

        tables, relation_frames = _inspect_data_files(data_files)
        relationships = _infer_relationships(tables, relation_frames)
        primary_table_id = _select_primary_table(tables)
        now = _utc_now()
        package = {
            "schemaVersion": PACKAGE_SCHEMA_VERSION,
            "packageId": safe_id,
            "status": "needs_review",
            "createdAt": now,
            "updatedAt": now,
            "problem": _file_summary(problem, "problem_statement"),
            "attachments": [_file_summary(path, "attachment") for path in attachments],
            "tables": tables,
            "relationships": relationships,
            "primaryTableId": primary_table_id,
            "review": {
                "confirmed": False,
                "tableLabels": {},
                "relationshipNotes": "",
            },
            "summary": _package_summary(tables, relationships),
            "_private": {
                "problemPath": problem.as_posix(),
                "dataPaths": [path.as_posix() for path in data_files],
                "attachmentPaths": [path.as_posix() for path in attachments],
            },
        }
        self._write(package)
        return _public_package(package)

    def update(self, package_id: str, corrections: Mapping[str, Any]) -> dict[str, Any]:
        package = self._read(package_id)
        table_ids = {str(table["id"]) for table in package["tables"]}
        primary_table_id = str(corrections.get("primaryTableId", package.get("primaryTableId", "")) or "")
        if primary_table_id not in table_ids:
            raise ModelingWorkspaceError("Primary table must reference a table in this package.")

        raw_labels = corrections.get("tableLabels", package.get("review", {}).get("tableLabels", {}))
        if not isinstance(raw_labels, Mapping):
            raise ModelingWorkspaceError("tableLabels must be an object keyed by table id.")
        unknown_labels = set(str(key) for key in raw_labels) - table_ids
        if unknown_labels:
            raise ModelingWorkspaceError("Unknown table label ids: " + ", ".join(sorted(unknown_labels)))
        table_labels = {
            str(key): str(value or "").strip()[:120]
            for key, value in raw_labels.items()
            if str(value or "").strip()
        }

        relationships = package["relationships"]
        if "relationships" in corrections:
            relationships = _normalize_relationships(corrections["relationships"], package["tables"])
        confirmed = bool(corrections.get("confirmed", package.get("review", {}).get("confirmed", False)))
        package["primaryTableId"] = primary_table_id
        package["relationships"] = relationships
        package["status"] = "confirmed" if confirmed else "needs_review"
        package["updatedAt"] = _utc_now()
        package["review"] = {
            "confirmed": confirmed,
            "tableLabels": table_labels,
            "relationshipNotes": str(
                corrections.get("relationshipNotes", package.get("review", {}).get("relationshipNotes", "")) or ""
            ).strip()[:2000],
        }
        package["summary"] = _package_summary(package["tables"], relationships)
        self._write(package)
        return _public_package(package)

    def load(self, package_id: str) -> dict[str, Any]:
        return _public_package(self._read(package_id))

    def _package_path(self, package_id: str) -> Path:
        return self.root / _safe_package_id(package_id) / "package.json"

    def _read(self, package_id: str) -> dict[str, Any]:
        path = self._package_path(package_id)
        if not path.is_file():
            raise ModelingWorkspaceError("Modeling package was not found.")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ModelingWorkspaceError(f"Modeling package is damaged: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("schemaVersion") != PACKAGE_SCHEMA_VERSION:
            raise ModelingWorkspaceError("Modeling package has an unsupported schema.")
        return payload

    def _write(self, payload: Mapping[str, Any]) -> None:
        path = self._package_path(str(payload["packageId"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _inspect_data_files(paths: Sequence[Path]) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame]]:
    tables: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    for file_index, path in enumerate(paths, start=1):
        suffix = path.suffix.lower()
        if suffix == ".csv":
            frame = _read_csv(path)
            table_id = _table_id(file_index, path.stem, "")
            tables.append(_inspect_frame(table_id, path.name, "", frame))
            frames[table_id] = frame
            continue
        if suffix not in {".xls", ".xlsx"}:
            raise ModelingWorkspaceError(f"Unsupported data file: {path.name}")
        try:
            with pd.ExcelFile(path) as workbook:
                for sheet_index, sheet_name in enumerate(workbook.sheet_names, start=1):
                    frame = workbook.parse(sheet_name)
                    table_id = _table_id(file_index, path.stem, f"{sheet_index}-{sheet_name}")
                    tables.append(_inspect_frame(table_id, path.name, str(sheet_name), frame))
                    frames[table_id] = frame
        except ModelingWorkspaceError:
            raise
        except Exception as exc:
            raise ModelingWorkspaceError(f"Failed to read workbook {path.name}: {exc}") from exc
    if not tables:
        raise ModelingWorkspaceError("No readable data tables were found.")
    return tables, frames


def _read_csv(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
        except Exception as exc:
            raise ModelingWorkspaceError(f"Failed to read CSV {path.name}: {exc}") from exc
    raise ModelingWorkspaceError(f"Failed to decode CSV {path.name}: {last_error}")


def _inspect_frame(table_id: str, file_name: str, sheet_name: str, frame: pd.DataFrame) -> dict[str, Any]:
    row_count, column_count = int(frame.shape[0]), int(frame.shape[1])
    missing_cells = int(frame.isna().sum().sum()) if column_count else 0
    total_cells = row_count * column_count
    duplicate_rows = int(frame.duplicated().sum()) if column_count else 0
    fields: list[dict[str, Any]] = []
    constant_columns: list[str] = []
    empty_columns: list[str] = []
    for raw_name in frame.columns:
        name = str(raw_name)
        series = frame[raw_name]
        missing_count = int(series.isna().sum())
        unique_count = int(series.nunique(dropna=True))
        if unique_count <= 1 and missing_count < row_count:
            constant_columns.append(name)
        if missing_count == row_count:
            empty_columns.append(name)
        samples = [_json_scalar(value) for value in series.dropna().head(3).tolist()]
        fields.append(
            {
                "name": name,
                "type": str(series.dtype),
                "nonNullCount": row_count - missing_count,
                "missingCount": missing_count,
                "missingRate": _ratio(missing_count, row_count),
                "uniqueCount": unique_count,
                "sampleValues": samples,
                "identifierCandidate": bool(row_count and unique_count == row_count - missing_count),
            }
        )
    warnings: list[str] = []
    if row_count == 0:
        warnings.append("表格没有数据行")
    if missing_cells:
        warnings.append(f"存在 {missing_cells} 个缺失单元格")
    if duplicate_rows:
        warnings.append(f"存在 {duplicate_rows} 行重复记录")
    if empty_columns:
        warnings.append("存在全空字段：" + "、".join(empty_columns[:5]))
    if constant_columns:
        warnings.append("存在常量字段：" + "、".join(constant_columns[:5]))
    return {
        "id": table_id,
        "name": sheet_name or Path(file_name).stem,
        "sourceFileName": file_name,
        "sheetName": sheet_name,
        "rowCount": row_count,
        "columnCount": column_count,
        "fields": fields,
        "quality": {
            "missingCells": missing_cells,
            "missingRate": _ratio(missing_cells, total_cells),
            "duplicateRows": duplicate_rows,
            "constantColumns": constant_columns,
            "emptyColumns": empty_columns,
            "warnings": warnings,
        },
    }


def _infer_relationships(
    tables: Sequence[Mapping[str, Any]],
    frames: Mapping[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for left_index, left in enumerate(tables):
        for right in tables[left_index + 1 :]:
            left_frame = frames[str(left["id"])]
            right_frame = frames[str(right["id"])]
            for left_column in left_frame.columns:
                for right_column in right_frame.columns:
                    name_score = _column_name_score(str(left_column), str(right_column))
                    if name_score == 0:
                        continue
                    metrics = _relationship_metrics(left_frame[left_column], right_frame[right_column])
                    if metrics is None or metrics["overlap"] < 0.35:
                        continue
                    confidence = round(min(0.99, 0.45 * name_score + 0.55 * metrics["overlap"]), 3)
                    status = "inferred" if confidence >= 0.82 else "uncertain"
                    candidates.append(
                        {
                            "id": f"rel-{len(candidates) + 1:03d}",
                            "leftTableId": left["id"],
                            "leftColumn": str(left_column),
                            "rightTableId": right["id"],
                            "rightColumn": str(right_column),
                            "kind": metrics["kind"],
                            "confidence": confidence,
                            "overlapRate": metrics["overlap"],
                            "status": status,
                            "source": "inferred",
                            "reason": _relationship_reason(name_score, metrics["overlap"], metrics["kind"]),
                        }
                    )
    candidates.sort(key=lambda item: (-float(item["confidence"]), str(item["id"])))
    for index, candidate in enumerate(candidates[:MAX_RELATIONSHIPS], start=1):
        candidate["id"] = f"rel-{index:03d}"
    return candidates[:MAX_RELATIONSHIPS]


def _relationship_metrics(left: pd.Series, right: pd.Series) -> dict[str, Any] | None:
    left_values = {_relation_value(value) for value in left.dropna().head(MAX_RELATION_VALUES).tolist()}
    right_values = {_relation_value(value) for value in right.dropna().head(MAX_RELATION_VALUES).tolist()}
    left_values.discard("")
    right_values.discard("")
    if not left_values or not right_values:
        return None
    intersection = left_values & right_values
    overlap = _ratio(len(intersection), min(len(left_values), len(right_values)))
    left_unique = len(left_values) == int(left.dropna().head(MAX_RELATION_VALUES).shape[0])
    right_unique = len(right_values) == int(right.dropna().head(MAX_RELATION_VALUES).shape[0])
    if left_unique and right_unique:
        kind = "one_to_one"
    elif left_unique:
        kind = "one_to_many"
    elif right_unique:
        kind = "many_to_one"
    else:
        kind = "many_to_many"
    return {"overlap": overlap, "kind": kind}


def _normalize_relationships(value: Any, tables: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ModelingWorkspaceError("relationships must be a list.")
    columns = {
        str(table["id"]): {str(field["name"]) for field in table.get("fields", [])}
        for table in tables
    }
    normalized: list[dict[str, Any]] = []
    for index, relation in enumerate(value, start=1):
        if not isinstance(relation, Mapping):
            raise ModelingWorkspaceError(f"Relationship #{index} must be an object.")
        left_table = str(relation.get("leftTableId", ""))
        right_table = str(relation.get("rightTableId", ""))
        left_column = str(relation.get("leftColumn", ""))
        right_column = str(relation.get("rightColumn", ""))
        if left_table == right_table or left_column not in columns.get(left_table, set()) or right_column not in columns.get(right_table, set()):
            raise ModelingWorkspaceError(f"Relationship #{index} references an unknown table or field.")
        status = str(relation.get("status", "uncertain") or "uncertain")
        if status not in {"confirmed", "rejected", "uncertain", "inferred"}:
            raise ModelingWorkspaceError(f"Relationship #{index} has an invalid status.")
        normalized.append(
            {
                "id": str(relation.get("id", "") or f"rel-{index:03d}"),
                "leftTableId": left_table,
                "leftColumn": left_column,
                "rightTableId": right_table,
                "rightColumn": right_column,
                "kind": str(relation.get("kind", "unknown") or "unknown"),
                "confidence": relation.get("confidence"),
                "overlapRate": relation.get("overlapRate"),
                "status": status,
                "source": str(relation.get("source", "user") or "user"),
                "reason": str(relation.get("reason", "人工修正") or "人工修正")[:500],
            }
        )
    return normalized


def _package_summary(tables: Sequence[Mapping[str, Any]], relationships: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    warnings = sum(len(table.get("quality", {}).get("warnings", [])) for table in tables)
    return {
        "tableCount": len(tables),
        "fieldCount": sum(int(table.get("columnCount", 0)) for table in tables),
        "rowCount": sum(int(table.get("rowCount", 0)) for table in tables),
        "qualityWarningCount": warnings,
        "relationshipCount": len(relationships),
        "uncertainRelationshipCount": sum(1 for item in relationships if item.get("status") == "uncertain"),
    }


def _select_primary_table(tables: Sequence[Mapping[str, Any]]) -> str:
    selected = max(tables, key=lambda table: (int(table.get("rowCount", 0)), int(table.get("columnCount", 0))))
    return str(selected["id"])


def _public_package(package: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in package.items() if not str(key).startswith("_")}


def _file_summary(path: Path, role: str) -> dict[str, Any]:
    return {"name": path.name, "role": role, "suffix": path.suffix.lower(), "size": path.stat().st_size}


def _safe_package_id(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "").strip()).strip("-")
    if not normalized:
        raise ModelingWorkspaceError("Package id is required.")
    return normalized[:80]


def _table_id(file_index: int, stem: str, sheet: str) -> str:
    label = f"{stem}-{sheet}" if sheet else stem
    safe = re.sub(r"[^a-zA-Z0-9]+", "-", label).strip("-").lower() or "table"
    return f"table-{file_index:02d}-{safe[:48]}"


def _column_name_score(left: str, right: str) -> float:
    left_name = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", left.lower())
    right_name = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", right.lower())
    if not left_name or not right_name:
        return 0.0
    if left_name == right_name:
        return 1.0
    id_tokens = {"id", "编号", "代码", "code", "key"}
    if any(token in left_name and token in right_name for token in id_tokens):
        return 0.65
    return 0.0


def _relationship_reason(name_score: float, overlap: float, kind: str) -> str:
    name_text = "字段名一致" if name_score >= 1 else "字段名具有标识符特征"
    return f"{name_text}，取值重合率 {overlap:.0%}，推断为 {kind}；请在分析前确认。"


def _relation_value(value: Any) -> str:
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip().lower()


def _json_scalar(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _ratio(numerator: int, denominator: int) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["ModelingWorkspace", "ModelingWorkspaceError"]
