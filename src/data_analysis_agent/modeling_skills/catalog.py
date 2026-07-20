"""Reusable mathematical-modeling skills derived from reviewed case cards.

The public interface is deliberately small: build a catalog from approved case
cards, load a catalog, and select the methods that fit one modeling task.  All
schema checks and prompt rendering stay behind that interface.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


SCHEMA_VERSION = "1.0"
DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[3] / "data" / "modeling_skills" / "catalog.json"
SKILL_CATEGORIES = (
    "data_diagnostics",
    "feature_engineering",
    "modeling",
    "validation",
    "sensitivity_analysis",
    "result_organization",
)


class ModelingSkillError(ValueError):
    """Raised when cases or skills do not satisfy the runtime contract."""


@dataclass(frozen=True)
class ModelingTaskProfile:
    """Task features used by the deterministic runtime selector."""

    task_type: str
    query: str
    columns: tuple[str, ...]
    row_count: int
    column_count: int
    characteristics: frozenset[str]

    @classmethod
    def from_task(
        cls,
        *,
        task_type: str,
        query: str,
        columns: Iterable[str],
        shape: Sequence[int],
        characteristics: Iterable[str] = (),
    ) -> "ModelingTaskProfile":
        normalized_columns = tuple(str(item).strip() for item in columns if str(item).strip())
        rows = int(shape[0]) if len(shape) > 0 else 0
        cols = int(shape[1]) if len(shape) > 1 else len(normalized_columns)
        inferred = _infer_characteristics(query=query, columns=normalized_columns, row_count=rows)
        inferred.update(_slug(item) for item in characteristics if str(item).strip())
        return cls(
            task_type=_slug(task_type),
            query=str(query or "").strip(),
            columns=normalized_columns,
            row_count=rows,
            column_count=cols,
            characteristics=frozenset(inferred),
        )


@dataclass(frozen=True)
class ModelingSkillSelection:
    """One selected skill with an observable score and selection reasons."""

    skill_id: str
    name: str
    category: str
    score: int
    reasons: tuple[str, ...]
    skill: Mapping[str, Any]


class ModelingSkillCatalog:
    """Load, validate, select, and render reusable modeling methods."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._payload = _normalize_catalog(payload)
        self.skills = tuple(self._payload["skills"])

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CATALOG_PATH) -> "ModelingSkillCatalog":
        catalog_path = Path(path).resolve()
        try:
            payload = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelingSkillError(f"Unable to load modeling skill catalog: {catalog_path}: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise ModelingSkillError("Modeling skill catalog must be a JSON object.")
        return cls(payload)

    @property
    def payload(self) -> Mapping[str, Any]:
        return self._payload

    def select(
        self,
        profile: ModelingTaskProfile,
        *,
        limit: int = 6,
    ) -> tuple[ModelingSkillSelection, ...]:
        """Return applicable skills ordered by category coverage, then fit."""

        if profile.task_type != "mathematical_modeling" or limit <= 0:
            return ()

        candidates: list[ModelingSkillSelection] = []
        for skill in self.skills:
            selection = _score_skill(skill, profile)
            if selection is not None:
                candidates.append(selection)
        candidates.sort(key=lambda item: (-item.score, SKILL_CATEGORIES.index(item.category), item.skill_id))

        selected: list[ModelingSkillSelection] = []
        seen_categories: set[str] = set()
        for candidate in candidates:
            if candidate.category not in seen_categories:
                selected.append(candidate)
                seen_categories.add(candidate.category)
            if len(selected) >= limit:
                return tuple(selected)
        for candidate in candidates:
            if candidate not in selected:
                selected.append(candidate)
            if len(selected) >= limit:
                break
        return tuple(selected)

    def render_for_prompt(self, selections: Iterable[ModelingSkillSelection]) -> str:
        selected = tuple(selections)
        if not selected:
            return ""
        blocks = [
            "<Modeling_Skills_Context>",
            "These are reusable methods derived from multiple reviewed historical cases. "
            "Use them as method constraints and checklists, never as evidence or results for the current task.",
        ]
        for item in selected:
            skill = item.skill
            blocks.extend(
                [
                    f"\n## {item.name} [{item.category}]",
                    f"When to use: {skill['description']}",
                    "Inputs: " + _render_named_items(skill["inputs"]),
                    "Procedure: " + " ".join(
                        f"{step['order']}. {step['action']}" for step in skill["procedure"]
                    ),
                    "Outputs: " + _render_named_items(skill["outputs"]),
                    "Validation requirements: " + _render_named_items(skill["validation_requirements"]),
                    "Selection reasons: " + "; ".join(item.reasons),
                ]
            )
        blocks.append("</Modeling_Skills_Context>")
        return "\n".join(blocks)


class ModelingSkillBuilder:
    """Build a validated catalog from multiple approved, published case cards."""

    def build(
        self,
        case_paths: Iterable[str | Path],
        extractor: Callable[[str], Mapping[str, Any]],
        output_path: str | Path,
    ) -> Path:
        cases = [_load_case_card(Path(path).resolve()) for path in case_paths]
        case_ids = [case["case"]["id"] for case in cases]
        if len(set(case_ids)) < 2:
            raise ModelingSkillError("At least two distinct approved case cards are required.")

        prompt = _build_synthesis_prompt(cases)
        extracted = extractor(prompt)
        if not isinstance(extracted, Mapping):
            raise ModelingSkillError("Skill extractor output must be a JSON object.")
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": _utc_now(),
            "source_case_ids": sorted(set(case_ids)),
            "skills": extracted.get("skills"),
        }
        normalized = _normalize_catalog(payload, allowed_case_ids=set(case_ids), require_category_coverage=True)
        destination = Path(output_path).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return destination


class JsonFileSkillExtractor:
    """Local adapter for deterministic builds and maintainer review."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()

    def __call__(self, _prompt: str) -> Mapping[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelingSkillError(f"Unable to read prepared skill JSON: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise ModelingSkillError("Prepared skill JSON must be an object.")
        return payload


class ConfiguredSkillExtractor:
    """Adapter using the project's configured language model."""

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
                        "You synthesize reusable mathematical-modeling methods from reviewed case cards. "
                        "Return one JSON object only and preserve cross-case evidence."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        return _parse_json_response(response)


def load_runtime_modeling_skills(
    *,
    task_type: str,
    query: str,
    columns: Iterable[str],
    shape: Sequence[int],
    catalog_path: str | Path | None = None,
    characteristics: Iterable[str] = (),
    limit: int = 6,
) -> tuple[ModelingSkillCatalog | None, tuple[ModelingSkillSelection, ...]]:
    """Load and select skills only for mathematical-modeling runs."""

    if _slug(task_type) != "mathematical_modeling":
        return None, ()
    path = Path(catalog_path).resolve() if catalog_path is not None else DEFAULT_CATALOG_PATH
    catalog = ModelingSkillCatalog.load(path)
    profile = ModelingTaskProfile.from_task(
        task_type=task_type,
        query=query,
        columns=columns,
        shape=shape,
        characteristics=characteristics,
    )
    return catalog, catalog.select(profile, limit=limit)


def _normalize_catalog(
    value: Mapping[str, Any],
    *,
    allowed_case_ids: set[str] | None = None,
    require_category_coverage: bool = False,
) -> dict[str, Any]:
    if str(value.get("schema_version", "") or "") != SCHEMA_VERSION:
        raise ModelingSkillError(f"Unsupported modeling skill schema version: {value.get('schema_version')}")
    raw_skills = value.get("skills")
    if not isinstance(raw_skills, list) or not raw_skills:
        raise ModelingSkillError("Modeling skill catalog requires a non-empty skills list.")

    normalized_skills = [_normalize_skill(item, allowed_case_ids=allowed_case_ids) for item in raw_skills]
    skill_ids = [item["id"] for item in normalized_skills]
    if len(skill_ids) != len(set(skill_ids)):
        raise ModelingSkillError("Modeling skill ids must be unique.")
    covered = {item["category"] for item in normalized_skills}
    if require_category_coverage:
        missing = sorted(set(SKILL_CATEGORIES) - covered)
        if missing:
            raise ModelingSkillError("Catalog is missing required categories: " + ", ".join(missing))

    source_case_ids = _string_list(value.get("source_case_ids", []), "source_case_ids")
    if allowed_case_ids is not None:
        source_case_ids = sorted(allowed_case_ids)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": str(value.get("generated_at", "") or "").strip(),
        "source_case_ids": source_case_ids,
        "skills": normalized_skills,
    }


def _normalize_skill(value: Any, *, allowed_case_ids: set[str] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ModelingSkillError("Every modeling skill must be an object.")
    skill_id = _normalize_skill_id(value.get("id", ""))
    if not skill_id:
        raise ModelingSkillError("Every modeling skill requires an id.")
    category = _slug(value.get("category", ""))
    if category not in SKILL_CATEGORIES:
        raise ModelingSkillError(f"Skill '{skill_id}' has unsupported category '{category}'.")
    name = _required_text(value, "name", skill_id)
    description = _required_text(value, "description", skill_id)

    applicability = value.get("applicability")
    if not isinstance(applicability, Mapping):
        raise ModelingSkillError(f"Skill '{skill_id}' requires applicability.")
    normalized_applicability = {
        "task_types": [_slug(item) for item in _string_list(applicability.get("task_types", []), "task_types")],
        "characteristics_any": [
            _slug(item) for item in _string_list(applicability.get("characteristics_any", []), "characteristics_any")
        ],
        "characteristics_all": [
            _slug(item) for item in _string_list(applicability.get("characteristics_all", []), "characteristics_all")
        ],
        "query_terms_any": [
            str(item).strip().lower() for item in _string_list(applicability.get("query_terms_any", []), "query_terms_any")
        ],
        "exclusions": _string_list(applicability.get("exclusions", []), "exclusions"),
    }
    if not normalized_applicability["task_types"]:
        raise ModelingSkillError(f"Skill '{skill_id}' applicability requires task_types.")

    source_case_ids = sorted(set(_string_list(value.get("source_case_ids", []), "source_case_ids")))
    if len(source_case_ids) < 2:
        raise ModelingSkillError(f"Skill '{skill_id}' must cite at least two distinct source cases.")
    if allowed_case_ids is not None:
        unknown = sorted(set(source_case_ids) - allowed_case_ids)
        if unknown:
            raise ModelingSkillError(f"Skill '{skill_id}' cites unknown source cases: {', '.join(unknown)}")

    return {
        "id": skill_id,
        "name": name,
        "category": category,
        "description": description,
        "applicability": normalized_applicability,
        "inputs": _normalize_named_items(value.get("inputs"), skill_id, "inputs", allow_required=True),
        "procedure": _normalize_procedure(value.get("procedure"), skill_id),
        "outputs": _normalize_named_items(value.get("outputs"), skill_id, "outputs", allow_required=False),
        "validation_requirements": _normalize_named_items(
            value.get("validation_requirements"), skill_id, "validation_requirements", allow_required=True
        ),
        "source_case_ids": source_case_ids,
    }


def _normalize_named_items(value: Any, skill_id: str, field: str, *, allow_required: bool) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ModelingSkillError(f"Skill '{skill_id}' requires non-empty {field}.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, Mapping):
            raise ModelingSkillError(f"Skill '{skill_id}' {field}[{index}] must be an object.")
        result: dict[str, Any] = {
            "name": _required_text(item, "name", f"{skill_id}.{field}[{index}]"),
            "description": _required_text(item, "description", f"{skill_id}.{field}[{index}]"),
        }
        if allow_required:
            result["required"] = bool(item.get("required", True))
        normalized.append(result)
    return normalized


def _normalize_procedure(value: Any, skill_id: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ModelingSkillError(f"Skill '{skill_id}' requires a non-empty procedure.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, Mapping):
            raise ModelingSkillError(f"Skill '{skill_id}' procedure[{index}] must be an object.")
        normalized.append(
            {
                "order": index,
                "action": _required_text(item, "action", f"{skill_id}.procedure[{index}]"),
                "purpose": _required_text(item, "purpose", f"{skill_id}.procedure[{index}]"),
            }
        )
    return normalized


def _score_skill(skill: Mapping[str, Any], profile: ModelingTaskProfile) -> ModelingSkillSelection | None:
    applicability = skill["applicability"]
    if profile.task_type not in applicability["task_types"]:
        return None
    text = " ".join((profile.query, *profile.columns)).lower()
    all_characteristics = set(applicability["characteristics_all"])
    if not all_characteristics.issubset(profile.characteristics):
        return None

    score = 10
    reasons = [f"task_type={profile.task_type}"]
    any_characteristics = set(applicability["characteristics_any"])
    matched_characteristics = sorted(any_characteristics & profile.characteristics)
    matched_terms = sorted(term for term in applicability["query_terms_any"] if term in text)
    if any_characteristics or applicability["query_terms_any"]:
        if not matched_characteristics and not matched_terms:
            return None
    if matched_characteristics:
        score += 4 * len(matched_characteristics)
        reasons.append("characteristics=" + ",".join(matched_characteristics))
    if matched_terms:
        score += 2 * len(matched_terms)
        reasons.append("query_terms=" + ",".join(matched_terms))
    if all_characteristics:
        score += 5 * len(all_characteristics)
        reasons.append("required_characteristics=" + ",".join(sorted(all_characteristics)))
    if not any_characteristics and not applicability["query_terms_any"]:
        reasons.append("core modeling method")
    return ModelingSkillSelection(
        skill_id=skill["id"],
        name=skill["name"],
        category=skill["category"],
        score=score,
        reasons=tuple(reasons),
        skill=skill,
    )


def _infer_characteristics(*, query: str, columns: Iterable[str], row_count: int) -> set[str]:
    text = " ".join((str(query or ""), *(str(item) for item in columns))).lower()
    rules = {
        "time_series": ("date", "time", "year", "month", "day", "日期", "时间", "年度", "月份", "forecast", "预测"),
        "optimization": ("optimiz", "allocate", "schedule", "capacity", "最优", "优化", "分配", "调度"),
        "classification": ("class", "label", "category", "分类", "类别"),
        "spatial": ("latitude", "longitude", "location", "distance", "经度", "纬度", "空间", "距离"),
        "panel_data": ("entity", "region", "company", "province", "城市", "地区", "企业", "面板"),
        "uncertainty": ("uncertain", "risk", "scenario", "robust", "敏感", "风险", "情景", "不确定"),
    }
    inferred = {name for name, terms in rules.items() if any(term in text for term in terms)}
    if row_count and row_count < 30:
        inferred.add("small_sample")
    return inferred


def _build_synthesis_prompt(cases: list[Mapping[str, Any]]) -> str:
    compact_cases = [
        {
            "case": case["case"],
            "extraction": case["extraction"],
            "review": case["review"],
        }
        for case in cases
    ]
    return f"""Synthesize reusable mathematical-modeling skills from these approved case cards.

Case cards:
{json.dumps(compact_cases, ensure_ascii=False, indent=2)}

Return {{"skills": [...]}}. Every skill must contain:
- id, name, category, description
- applicability: task_types, characteristics_any, characteristics_all, query_terms_any, exclusions
- inputs: name, description, required
- procedure: action, purpose
- outputs: name, description
- validation_requirements: name, description, required
- source_case_ids

Rules:
- Organize by reusable method, never by paper or competition.
- Use only these categories: {', '.join(SKILL_CATEGORIES)}.
- Cover all six categories in the catalog.
- Every skill must be supported by at least two distinct case ids.
- Historical case findings are design evidence, not results for a new task.
- State observable validation requirements; do not use vague checks such as "ensure quality".
"""


def _load_case_card(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelingSkillError(f"Unable to read case card {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ModelingSkillError(f"Case card must be an object: {path}")
    case = payload.get("case")
    review = payload.get("review")
    if not isinstance(case, Mapping) or not str(case.get("id", "") or "").strip():
        raise ModelingSkillError(f"Case card is missing case.id: {path}")
    if not isinstance(review, Mapping) or review.get("status") != "approved" or "published_at" not in payload:
        raise ModelingSkillError(f"Case card must be approved and published: {path}")
    if not isinstance(payload.get("extraction"), Mapping):
        raise ModelingSkillError(f"Case card is missing extraction: {path}")
    return payload


def _parse_json_response(response: Any) -> Mapping[str, Any]:
    if isinstance(response, Mapping):
        return response
    text = str(response or "").strip()
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    candidate = match.group(1) if match else text
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ModelingSkillError(f"Skill extractor did not return valid JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ModelingSkillError("Skill extractor response must be an object.")
    return payload


def _render_named_items(items: Iterable[Mapping[str, Any]]) -> str:
    return "; ".join(f"{item['name']} — {item['description']}" for item in items)


def _required_text(value: Mapping[str, Any], key: str, owner: str) -> str:
    text = str(value.get(key, "") or "").strip()
    if not text:
        raise ModelingSkillError(f"'{owner}' requires {key}.")
    return text


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ModelingSkillError(f"{field} must be a list.")
    return [str(item).strip() for item in value if str(item or "").strip()]


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")


def _normalize_skill_id(value: Any) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", str(value or "").strip().lower()).strip("-_")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
