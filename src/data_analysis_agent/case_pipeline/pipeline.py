"""Offline production workflow for reviewable competition case cards.

The module deliberately keeps raw historical materials on the maintainer side.
Only ``publish`` creates a distributable artifact, and that artifact contains
structured extraction fields plus source citations rather than source content.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml


SCHEMA_VERSION = "1.0"
REQUIRED_SOURCE_ROLES = frozenset({"problem_statement", "dataset", "paper"})
ALLOWED_DISTRIBUTION_POLICIES = frozenset({"metadata_only", "redistributable"})
EXTRACTION_LIST_FIELDS = (
    "data_operations",
    "models",
    "validation_methods",
    "charts",
    "key_findings",
)
MAX_SOURCE_CHARS = 60_000
MAX_TOTAL_SOURCE_CHARS = 180_000


class CasePipelineError(ValueError):
    """Raised when a case cannot safely move to the next pipeline state."""


@dataclass(frozen=True)
class CasePipelineResult:
    """Observable result returned by every state-changing pipeline action."""

    status: str
    case_id: str
    revision: int
    artifact_path: Path


class JsonFileCaseExtractor:
    """Adapter that loads a prepared extraction response from a JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()

    def __call__(self, _prompt: str) -> Mapping[str, Any]:
        return _read_json(self.path)


class ConfiguredCaseExtractor:
    """Adapter that uses the project's configured text model for extraction."""

    def __init__(self, env_file: str | Path | None = None) -> None:
        self.env_file = env_file

    def __call__(self, prompt: str) -> Mapping[str, Any]:
        from data_analysis_agent.config import load_runtime_config
        from data_analysis_agent.llm import build_llm

        llm = build_llm(load_runtime_config(self.env_file))
        response = llm.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "You extract auditable mathematical-modeling case cards. "
                        "Return one JSON object only. Never invent evidence or source identifiers."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        return _parse_json_response(response)


class CasePipeline:
    """Deep module for generating, reviewing, and publishing case cards.

    ``workspace`` is maintainer-owned. Raw source files remain at their original
    paths and are never copied into the workspace or published artifacts.
    """

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).resolve()

    def generate(
        self,
        manifest_path: str | Path,
        extractor: Callable[[str], Mapping[str, Any]],
    ) -> CasePipelineResult:
        manifest_file = Path(manifest_path).resolve()
        manifest = _load_manifest(manifest_file)
        case = _normalize_case(manifest.get("case"))
        sources, private_sources, source_sections = _prepare_sources(
            manifest.get("sources"),
            manifest_dir=manifest_file.parent,
        )
        prompt = _build_extraction_prompt(case, sources, source_sections)
        extraction = _normalize_extraction(extractor(prompt), source_ids={item["id"] for item in sources})

        revision = self._next_revision(case["id"])
        previous_revision = revision - 1 if revision > 1 else None
        payload = {
            "schema_version": SCHEMA_VERSION,
            "case": case,
            "revision": revision,
            "previous_revision": previous_revision,
            "status": "draft",
            "generated_at": _utc_now(),
            "input_fingerprint": _fingerprint_inputs(case, sources),
            "sources": sources,
            "extraction": extraction,
            "review": {"status": "pending"},
            "_private_provenance": {
                "manifest_path": manifest_file.as_posix(),
                "local_sources": private_sources,
            },
        }
        artifact_path = self.workspace / "drafts" / case["id"] / f"revision-{revision:03d}.json"
        _write_json(artifact_path, payload)
        return CasePipelineResult("draft", case["id"], revision, artifact_path)

    def review(
        self,
        draft_path: str | Path,
        *,
        decision: str,
        reviewer: str,
        notes: str = "",
        corrections: Mapping[str, Any] | None = None,
    ) -> CasePipelineResult:
        normalized_decision = str(decision or "").strip().lower()
        if normalized_decision not in {"approved", "rejected"}:
            raise CasePipelineError("Review decision must be 'approved' or 'rejected'.")
        normalized_reviewer = str(reviewer or "").strip()
        if not normalized_reviewer:
            raise CasePipelineError("A reviewer name is required.")

        draft = _read_json(Path(draft_path).resolve())
        if draft.get("status") != "draft":
            raise CasePipelineError("Only draft artifacts can be reviewed.")
        case_id = str(draft.get("case", {}).get("id", "") or "").strip()
        revision = int(draft.get("revision", 0) or 0)
        if not case_id or revision < 1:
            raise CasePipelineError("Draft artifact is missing its case id or revision.")

        reviewed = copy.deepcopy(draft)
        correction_payload = dict(corrections or {})
        if "extraction" in correction_payload:
            correction_payload = correction_payload["extraction"]
        if correction_payload:
            reviewed["extraction"] = _deep_merge(reviewed.get("extraction", {}), correction_payload)
        source_ids = {str(item.get("id", "")) for item in reviewed.get("sources", []) if isinstance(item, dict)}
        reviewed["extraction"] = _normalize_extraction(reviewed.get("extraction"), source_ids=source_ids)
        reviewed["status"] = normalized_decision
        reviewed["review"] = {
            "status": normalized_decision,
            "reviewer": normalized_reviewer,
            "reviewed_at": _utc_now(),
            "notes": str(notes or "").strip(),
            "corrections_applied": bool(correction_payload),
        }

        review_number = self._next_review_number(case_id, revision)
        artifact_path = (
            self.workspace
            / "reviews"
            / case_id
            / f"revision-{revision:03d}-review-{review_number:03d}.json"
        )
        _write_json(artifact_path, reviewed)
        return CasePipelineResult(normalized_decision, case_id, revision, artifact_path)

    def publish(self, reviewed_path: str | Path, output_dir: str | Path) -> CasePipelineResult:
        reviewed = _read_json(Path(reviewed_path).resolve())
        if reviewed.get("status") != "approved" or reviewed.get("review", {}).get("status") != "approved":
            raise CasePipelineError("Only an approved review artifact can be published.")

        case_id = str(reviewed.get("case", {}).get("id", "") or "").strip()
        revision = int(reviewed.get("revision", 0) or 0)
        if not case_id or revision < 1:
            raise CasePipelineError("Reviewed artifact is missing its case id or revision.")
        source_ids = {str(item.get("id", "")) for item in reviewed.get("sources", []) if isinstance(item, dict)}
        normalized_extraction = _normalize_extraction(reviewed.get("extraction"), source_ids=source_ids)

        public_payload = {
            "schema_version": SCHEMA_VERSION,
            "library_version": f"{case_id}-r{revision:03d}",
            "published_at": _utc_now(),
            "case": copy.deepcopy(reviewed["case"]),
            "sources": [_public_source(item) for item in reviewed["sources"]],
            "extraction": normalized_extraction,
            "review": copy.deepcopy(reviewed["review"]),
        }
        artifact_path = Path(output_dir).resolve() / f"{case_id}.json"
        _write_json(artifact_path, public_payload)
        return CasePipelineResult("published", case_id, revision, artifact_path)

    def _next_revision(self, case_id: str) -> int:
        case_dir = self.workspace / "drafts" / case_id
        revisions = [_number_from_name(path.name, r"revision-(\d+)\.json") for path in case_dir.glob("revision-*.json")]
        return max((number for number in revisions if number is not None), default=0) + 1

    def _next_review_number(self, case_id: str, revision: int) -> int:
        case_dir = self.workspace / "reviews" / case_id
        pattern = rf"revision-{revision:03d}-review-(\d+)\.json"
        reviews = [_number_from_name(path.name, pattern) for path in case_dir.glob(f"revision-{revision:03d}-review-*.json")]
        return max((number for number in reviews if number is not None), default=0) + 1


def _load_manifest(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise CasePipelineError(f"Manifest does not exist: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise CasePipelineError(f"Failed to read manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise CasePipelineError("Manifest must contain a YAML object.")
    if str(payload.get("schema_version", SCHEMA_VERSION)) != SCHEMA_VERSION:
        raise CasePipelineError(f"Unsupported manifest schema version: {payload.get('schema_version')}")
    return payload


def _normalize_case(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CasePipelineError("Manifest 'case' must be an object.")
    required = ("id", "competition", "year", "problem_number", "title")
    normalized = {key: value.get(key) for key in required}
    missing = [key for key, item in normalized.items() if str(item or "").strip() == ""]
    if missing:
        raise CasePipelineError("Case metadata is missing: " + ", ".join(missing))
    normalized["id"] = _safe_case_id(str(normalized["id"]))
    try:
        normalized["year"] = int(normalized["year"])
    except (TypeError, ValueError) as exc:
        raise CasePipelineError("Case year must be an integer.") from exc
    if normalized["year"] < 1900 or normalized["year"] > 2200:
        raise CasePipelineError("Case year is outside the supported range.")
    for key in ("competition", "problem_number", "title"):
        normalized[key] = str(normalized[key]).strip()
    normalized["locale"] = str(value.get("locale", "zh-CN") or "zh-CN").strip()
    return normalized


def _prepare_sources(
    value: Any,
    *,
    manifest_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[tuple[str, str]]]:
    if not isinstance(value, list) or not value:
        raise CasePipelineError("Manifest 'sources' must be a non-empty list.")
    public_sources: list[dict[str, Any]] = []
    private_sources: list[dict[str, str]] = []
    source_sections: list[tuple[str, str]] = []
    seen_ids: set[str] = set()
    seen_roles: set[str] = set()
    total_chars = 0

    for index, source in enumerate(value, start=1):
        if not isinstance(source, dict):
            raise CasePipelineError(f"Source #{index} must be an object.")
        source_id = str(source.get("id", "") or "").strip()
        role = str(source.get("role", "") or "").strip()
        title = str(source.get("title", "") or "").strip()
        raw_path = str(source.get("path", "") or "").strip()
        source_url = str(source.get("url", "") or "").strip()
        source_license = str(source.get("license", "") or "").strip()
        distribution = str(source.get("distribution", "metadata_only") or "metadata_only").strip()
        if not source_id or not role or not title or not raw_path or not source_url or not source_license:
            raise CasePipelineError(f"Source #{index} requires id, role, title, path, url, and license.")
        if distribution not in ALLOWED_DISTRIBUTION_POLICIES:
            raise CasePipelineError(
                f"Source #{index} distribution must be one of: {', '.join(sorted(ALLOWED_DISTRIBUTION_POLICIES))}."
            )
        if source_id in seen_ids:
            raise CasePipelineError(f"Duplicate source id: {source_id}")
        seen_ids.add(source_id)
        seen_roles.add(role)

        local_path = Path(raw_path)
        if not local_path.is_absolute():
            local_path = (manifest_dir / local_path).resolve()
        if not local_path.is_file():
            raise CasePipelineError(f"Source file does not exist: {local_path}")
        source_text = _extract_source_text(local_path)
        remaining = max(0, MAX_TOTAL_SOURCE_CHARS - total_chars)
        excerpt = source_text[: min(MAX_SOURCE_CHARS, remaining)]
        total_chars += len(excerpt)

        public_sources.append(
            {
                "id": source_id,
                "role": role,
                "title": title,
                "uri": source_url,
                "license": source_license,
                "distribution": distribution,
                "sha256": _sha256_file(local_path),
            }
        )
        private_sources.append({"id": source_id, "path": local_path.as_posix()})
        source_sections.append((source_id, excerpt))

    missing_roles = sorted(REQUIRED_SOURCE_ROLES - seen_roles)
    if missing_roles:
        raise CasePipelineError("Sources are missing required roles: " + ", ".join(missing_roles))
    return public_sources, private_sources, source_sections


def _extract_source_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    if suffix == ".csv":
        return _summarize_table(path)
    if suffix in {".xls", ".xlsx"}:
        return _summarize_workbook(path)
    if suffix == ".pdf":
        from data_analysis_agent.rag.document_reader import load_knowledge_documents

        documents, warnings = load_knowledge_documents(path)
        text = "\n\n".join(document.text for document in documents if document.text.strip())
        if not text:
            detail = "; ".join(warnings) or "no readable text"
            raise CasePipelineError(f"PDF source could not be extracted ({path.name}): {detail}")
        return text
    raise CasePipelineError(f"Unsupported case source format: {path.suffix or '<none>'}")


def _summarize_table(path: Path) -> str:
    import pandas as pd

    frame = pd.read_csv(path)
    return _dataframe_summary(path.name, frame)


def _summarize_workbook(path: Path) -> str:
    import pandas as pd

    workbook = pd.ExcelFile(path)
    sections: list[str] = []
    for sheet_name in workbook.sheet_names:
        frame = workbook.parse(sheet_name)
        sections.append(f"Sheet: {sheet_name}\n{_dataframe_summary(path.name, frame)}")
    return "\n\n".join(sections)


def _dataframe_summary(name: str, frame: Any) -> str:
    dtypes = ", ".join(f"{column}: {dtype}" for column, dtype in frame.dtypes.items())
    return (
        f"Dataset: {name}\n"
        f"Shape: {frame.shape[0]} rows x {frame.shape[1]} columns\n"
        f"Columns and types: {dtypes}\n"
        f"Sample rows:\n{frame.head(8).to_csv(index=False)}"
    )


def _build_extraction_prompt(
    case: Mapping[str, Any],
    sources: list[dict[str, Any]],
    source_sections: list[tuple[str, str]],
) -> str:
    source_catalog = json.dumps(sources, ensure_ascii=False, indent=2)
    contents = "\n\n".join(f"<source id=\"{source_id}\">\n{text}\n</source>" for source_id, text in source_sections)
    return f"""Extract a reusable, auditable case card for this competition problem.

Case metadata:
{json.dumps(case, ensure_ascii=False, indent=2)}

Source catalog (cite only ids from this catalog):
{source_catalog}

Return this exact JSON shape:
{{
  "problem_summary": "concise paraphrase, never a copy of the full problem",
  "data_operations": [{{"name": "...", "purpose": "...", "evidence_source_ids": ["..."]}}],
  "models": [{{"name": "...", "purpose": "...", "assumptions": ["..."], "evidence_source_ids": ["..."]}}],
  "validation_methods": [{{"name": "...", "purpose": "...", "evidence_source_ids": ["..."]}}],
  "charts": [{{"name": "...", "purpose": "...", "evidence_source_ids": ["..."]}}],
  "key_findings": [{{"statement": "...", "evidence_source_ids": ["..."]}}],
  "limitations": ["..."]
}}

Rules:
- Extract only claims supported by the provided sources.
- Do not copy raw tables, long passages, or full paper/problem text.
- Describe historical methods as inspiration, never as results for a new problem.
- Keep source identifiers on every extracted operation, method, chart, and finding.
- Include at least one item in every required list.

Source content:
{contents}
"""


def _normalize_extraction(value: Any, *, source_ids: set[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CasePipelineError("Extractor output must be a JSON object.")
    problem_summary = str(value.get("problem_summary", "") or "").strip()
    if not problem_summary:
        raise CasePipelineError("Extraction is missing problem_summary.")
    normalized: dict[str, Any] = {"problem_summary": problem_summary}
    for field in EXTRACTION_LIST_FIELDS:
        items = value.get(field)
        if not isinstance(items, list) or not items:
            raise CasePipelineError(f"Extraction field '{field}' must be a non-empty list.")
        normalized_items: list[dict[str, Any]] = []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, Mapping):
                raise CasePipelineError(f"{field}[{index}] must be an object.")
            required_text_key = "statement" if field == "key_findings" else "name"
            if not str(item.get(required_text_key, "") or "").strip():
                raise CasePipelineError(f"{field}[{index}] is missing '{required_text_key}'.")
            if field != "key_findings" and not str(item.get("purpose", "") or "").strip():
                raise CasePipelineError(f"{field}[{index}] is missing 'purpose'.")
            if field == "models" and not isinstance(item.get("assumptions"), list):
                raise CasePipelineError(f"{field}[{index}] requires an assumptions list.")
            evidence_ids = item.get("evidence_source_ids")
            if not isinstance(evidence_ids, list) or not evidence_ids:
                raise CasePipelineError(f"{field}[{index}] requires evidence_source_ids.")
            unknown_ids = sorted({str(source_id) for source_id in evidence_ids} - source_ids)
            if unknown_ids:
                raise CasePipelineError(f"{field}[{index}] cites unknown sources: {', '.join(unknown_ids)}")
            normalized_item = {
                required_text_key: str(item[required_text_key]).strip(),
                "evidence_source_ids": [str(source_id) for source_id in evidence_ids],
            }
            if field != "key_findings":
                normalized_item["purpose"] = str(item["purpose"]).strip()
            if field == "models":
                normalized_item["assumptions"] = [
                    str(assumption).strip()
                    for assumption in item["assumptions"]
                    if str(assumption or "").strip()
                ]
            normalized_items.append(normalized_item)
        normalized[field] = normalized_items
    limitations = value.get("limitations", [])
    if not isinstance(limitations, list):
        raise CasePipelineError("Extraction field 'limitations' must be a list.")
    normalized["limitations"] = [str(item).strip() for item in limitations if str(item or "").strip()]
    return normalized


def _parse_json_response(response: Any) -> Mapping[str, Any]:
    if isinstance(response, Mapping):
        return response
    text = str(response or "").strip()
    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    candidate = fenced_match.group(1) if fenced_match else text
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise CasePipelineError(f"Extractor did not return valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise CasePipelineError("Extractor response must be a JSON object.")
    return payload


def _public_source(source: Any) -> dict[str, Any]:
    if not isinstance(source, Mapping):
        raise CasePipelineError("Reviewed artifact contains an invalid source.")
    allowed = ("id", "role", "title", "uri", "license", "distribution", "sha256")
    return {key: copy.deepcopy(source.get(key)) for key in allowed}


def _deep_merge(original: Any, corrections: Any) -> Any:
    if isinstance(original, Mapping) and isinstance(corrections, Mapping):
        merged = copy.deepcopy(dict(original))
        for key, value in corrections.items():
            merged[key] = _deep_merge(merged.get(key), value)
        return merged
    return copy.deepcopy(corrections)


def _fingerprint_inputs(case: Mapping[str, Any], sources: list[dict[str, Any]]) -> str:
    material = json.dumps({"case": case, "sources": sources}, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CasePipelineError(f"JSON artifact does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise CasePipelineError(f"Failed to read JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CasePipelineError(f"JSON artifact must contain an object: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _safe_case_id(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-.").lower()
    if not normalized:
        raise CasePipelineError("Case id must contain letters or numbers.")
    return normalized


def _number_from_name(name: str, pattern: str) -> int | None:
    match = re.fullmatch(pattern, name)
    return int(match.group(1)) if match else None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
