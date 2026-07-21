"""Browse approved competition cases and build auditable modeling plans.

The module keeps library resolution, public-card validation, deterministic case
matching, modeling-skill selection, and plan composition behind one interface.
Web callers never read bundled JSON files directly.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..modeling_skills import ModelingSkillCatalog, ModelingSkillError, ModelingTaskProfile
from .library import ExperienceLibraryManager, ExperienceLibraryResolution


GENERIC_MATCH_TERMS = frozenset(
    {
        "分析",
        "数据",
        "模型",
        "预测",
        "分类",
        "验证",
        "敏感性分析",
        "交叉验证",
        "全国大学生数学建模竞赛",
        "cumcm",
    }
)
MATCH_THRESHOLD = 0.28


class CompetitionExperienceError(ValueError):
    """Raised when a requested public case or plan operation is invalid."""


class CompetitionExperienceLibrary:
    """Resolve, browse, match, and plan with the active competition library."""

    def __init__(self, manager: ExperienceLibraryManager | None = None) -> None:
        self.manager = manager or ExperienceLibraryManager()

    def browse(self) -> dict[str, Any]:
        """Return a safe library snapshot and approved case summaries."""

        state = self._load_state()
        return {
            "status": state["resolution"].status,
            "usable": state["resolution"].usable,
            "version": state["resolution"].version,
            "contentStatus": state["resolution"].content_status,
            "warnings": state["warnings"],
            "cases": [_case_summary(card, state["keywords"].get(_case_id(card), ())) for card in state["cards"]],
        }

    def get(self, case_id: str) -> dict[str, Any]:
        """Return one approved public case without private or raw-source fields."""

        normalized_id = str(case_id or "").strip()
        state = self._load_state()
        for card in state["cards"]:
            if _case_id(card) == normalized_id:
                return {
                    "library": {
                        "status": state["resolution"].status,
                        "version": state["resolution"].version,
                        "contentStatus": state["resolution"].content_status,
                    },
                    **_case_detail(card, state["keywords"].get(normalized_id, ())),
                }
        raise CompetitionExperienceError(f"Approved competition case not found: {normalized_id}")

    def build_plan(self, context: Mapping[str, Any], *, case_limit: int = 3) -> dict[str, Any]:
        """Match cases and skills, then compose a reviewable pre-execution plan."""

        if str(context.get("packageStatus", "") or "") != "confirmed":
            raise CompetitionExperienceError("Modeling package must be confirmed before generating a plan.")
        state = self._load_state()
        matches = _match_cases(
            cards=state["cards"],
            keyword_chunks=state["keywordChunks"],
            context=context,
            limit=max(0, int(case_limit)),
        )
        selected_skills, skill_warnings = _select_skills(state["resolution"], context)
        warnings = [*state["warnings"], *_string_list(context.get("problemWarnings", [])), *skill_warnings]
        if not matches and state["cards"]:
            warnings.append("未找到达到相关性门槛的历史案例；方案仅使用通用建模 skills，不强行套用案例。")
        return _compose_plan(
            context=context,
            matches=matches,
            selected_skills=selected_skills,
            cards=state["cards"],
            resolution=state["resolution"],
            warnings=warnings,
        )

    def _load_state(self) -> dict[str, Any]:
        resolution = self.manager.resolve()
        warnings = list(resolution.warnings)
        if not resolution.usable:
            return {
                "resolution": resolution,
                "cards": [],
                "keywordChunks": [],
                "keywords": {},
                "warnings": warnings,
            }

        cards: list[Mapping[str, Any]] = []
        for path in resolution.case_card_paths:
            try:
                card = _read_approved_card(path)
            except CompetitionExperienceError as exc:
                warnings.append(str(exc))
                continue
            cards.append(card)
        cards.sort(
            key=lambda item: (
                -int(item["case"].get("year", 0) or 0),
                str(item["case"].get("problem_number", "") or ""),
                _case_id(item),
            )
        )

        chunks = _read_keyword_chunks(resolution.keyword_index_path, warnings)
        keywords: dict[str, list[str]] = defaultdict(list)
        for chunk in chunks:
            case_id = str(chunk.get("case_id", "") or "")
            for keyword in chunk.get("keywords", []):
                text = str(keyword or "").strip()
                if text and text not in keywords[case_id]:
                    keywords[case_id].append(text)
        return {
            "resolution": resolution,
            "cards": cards,
            "keywordChunks": chunks,
            "keywords": {key: tuple(value) for key, value in keywords.items()},
            "warnings": warnings,
        }


def _read_approved_card(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompetitionExperienceError(f"Competition case is unreadable: {path.name}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise CompetitionExperienceError(f"Competition case must be an object: {path.name}")
    case = payload.get("case")
    extraction = payload.get("extraction")
    review = payload.get("review")
    if not isinstance(case, Mapping) or not _case_id(payload):
        raise CompetitionExperienceError(f"Competition case is missing case metadata: {path.name}")
    if not isinstance(extraction, Mapping):
        raise CompetitionExperienceError(f"Competition case is missing extraction: {path.name}")
    if not isinstance(review, Mapping) or review.get("status") != "approved":
        raise CompetitionExperienceError(f"Competition case is not approved and was skipped: {path.name}")
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    if (
        "_private_provenance" in payload
        or "raw_excerpt" in serialized
        or re.search(r"(?<![a-z])[a-z]:[/\\]", serialized)
    ):
        raise CompetitionExperienceError(f"Competition case contains a private field or local path: {path.name}")
    return payload


def _read_keyword_chunks(path: Path | None, warnings: list[str]) -> list[Mapping[str, Any]]:
    if path is None:
        warnings.append("竞赛经验库没有关键词索引；案例浏览可用，但自动匹配已降级。")
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"竞赛案例关键词索引不可用：{exc}")
        return []
    chunks = payload.get("chunks", []) if isinstance(payload, Mapping) else []
    if not isinstance(chunks, list):
        warnings.append("竞赛案例关键词索引格式无效。")
        return []
    return [chunk for chunk in chunks if isinstance(chunk, Mapping)]


def _case_summary(card: Mapping[str, Any], keywords: Sequence[str]) -> dict[str, Any]:
    case = card["case"]
    extraction = card["extraction"]
    return {
        "id": _case_id(card),
        "competition": str(case.get("competition", "") or ""),
        "year": int(case.get("year", 0) or 0),
        "problemNumber": str(case.get("problem_number", "") or ""),
        "title": str(case.get("title", "") or ""),
        "locale": str(case.get("locale", "") or ""),
        "problemSummary": str(extraction.get("problem_summary", "") or ""),
        "methods": [str(item.get("name", "") or "") for item in extraction.get("models", []) if isinstance(item, Mapping)],
        "findingCount": len(extraction.get("key_findings", [])),
        "limitationCount": len(extraction.get("limitations", [])),
        "sourceCount": len(card.get("sources", [])),
        "keywords": list(keywords[:12]),
        "reviewStatus": "approved",
        "publishedAt": str(card.get("published_at", "") or ""),
    }


def _case_detail(card: Mapping[str, Any], keywords: Sequence[str]) -> dict[str, Any]:
    extraction = card["extraction"]
    return {
        "case": _case_summary(card, keywords),
        "dataOperations": _safe_named_items(extraction.get("data_operations", [])),
        "models": _safe_models(extraction.get("models", [])),
        "validationMethods": _safe_named_items(extraction.get("validation_methods", [])),
        "charts": _safe_named_items(extraction.get("charts", [])),
        "keyFindings": [
            {
                "statement": str(item.get("statement", "") or ""),
                "evidenceSourceIds": _string_list(item.get("evidence_source_ids", [])),
            }
            for item in extraction.get("key_findings", [])
            if isinstance(item, Mapping)
        ],
        "limitations": _string_list(extraction.get("limitations", [])),
        "sources": [
            {
                "id": str(item.get("id", "") or ""),
                "role": str(item.get("role", "") or ""),
                "title": str(item.get("title", "") or ""),
                "uri": str(item.get("uri", "") or ""),
                "license": str(item.get("license", "") or ""),
                "distribution": str(item.get("distribution", "") or ""),
            }
            for item in card.get("sources", [])
            if isinstance(item, Mapping)
        ],
        "review": {
            "status": "approved",
            "reviewedAt": str(card.get("review", {}).get("reviewed_at", "") or ""),
            "notes": str(card.get("review", {}).get("notes", "") or ""),
        },
    }


def _safe_named_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        {
            "name": str(item.get("name", "") or ""),
            "purpose": str(item.get("purpose", "") or ""),
            "evidenceSourceIds": _string_list(item.get("evidence_source_ids", [])),
        }
        for item in value
        if isinstance(item, Mapping)
    ]


def _safe_models(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        {
            "name": str(item.get("name", "") or ""),
            "purpose": str(item.get("purpose", "") or ""),
            "assumptions": _string_list(item.get("assumptions", [])),
            "evidenceSourceIds": _string_list(item.get("evidence_source_ids", [])),
        }
        for item in value
        if isinstance(item, Mapping)
    ]


def _match_cases(
    *,
    cards: Sequence[Mapping[str, Any]],
    keyword_chunks: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    context_text = _context_text(context)
    normalized_context = _normalize_search_text(context_text)
    chunks_by_case: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for chunk in keyword_chunks:
        chunks_by_case[str(chunk.get("case_id", "") or "")].append(chunk)

    scored: list[tuple[float, Mapping[str, Any], list[str]]] = []
    for card in cards:
        case_id = _case_id(card)
        keywords = _unique_strings(
            keyword
            for chunk in chunks_by_case.get(case_id, [])
            for keyword in chunk.get("keywords", [])
        )
        matched = [keyword for keyword in keywords if _term_matches(keyword, normalized_context)]
        distinctive = [term for term in matched if term.strip().lower() not in GENERIC_MATCH_TERMS]
        title = str(card.get("case", {}).get("title", "") or "")
        title_match = bool(title and _normalize_search_text(title) in normalized_context)
        if not distinctive and not title_match:
            continue
        score = min(1.0, sum(_term_weight(term) for term in distinctive) + (0.45 if title_match else 0.0))
        if score < MATCH_THRESHOLD:
            continue
        scored.append((round(score, 3), card, distinctive))
    scored.sort(key=lambda item: (-item[0], _case_id(item[1])))

    matches: list[dict[str, Any]] = []
    columns = _context_columns(context)
    for score, card, terms in scored[:limit]:
        summary = _case_summary(card, terms)
        similarities = [f"当前任务与历史案例共同涉及：{term}" for term in terms[:5]]
        differences = ["历史案例的数值阈值和结论不能作为当前任务结果，必须重新估计和验证。"]
        historical_components = {"sio2", "pbo", "bao", "k2o", "化学成分"}
        if not any(any(token in column.lower() for token in historical_components) for column in columns):
            differences.append("当前字段没有显示出历史案例相同的古代玻璃化学成分口径。")
        differences.append(
            f"当前资料包含 {len(context.get('tables', []))} 张表，需按当前表粒度和关系重新设计数据处理。"
        )
        matches.append(
            {
                "caseId": summary["id"],
                "title": summary["title"],
                "year": summary["year"],
                "problemNumber": summary["problemNumber"],
                "score": score,
                "relevance": "high" if score >= 0.6 else "medium",
                "matchedTerms": terms[:8],
                "similarities": similarities,
                "differences": differences,
                "applicability": "仅复用方法设计、验证要求和风险提示；不复用历史数值结果。",
                "sources": _case_detail(card, terms)["sources"],
            }
        )
    return matches


def _select_skills(
    resolution: ExperienceLibraryResolution,
    context: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    if not resolution.usable or resolution.skill_catalog_path is None:
        return [], ["建模 skills 目录不可用；方案保留通用数据检查，但无法自动选择 skills。"]
    columns = _context_columns(context)
    tables = [table for table in context.get("tables", []) if isinstance(table, Mapping)]
    row_count = sum(int(table.get("rowCount", 0) or 0) for table in tables)
    column_count = sum(int(table.get("columnCount", 0) or 0) for table in tables)
    try:
        catalog = ModelingSkillCatalog.load(resolution.skill_catalog_path)
        profile = ModelingTaskProfile.from_task(
            task_type="mathematical_modeling",
            query=str(context.get("query", "") or ""),
            columns=columns,
            shape=(row_count, column_count),
        )
        selections = catalog.select(profile, limit=6)
    except ModelingSkillError as exc:
        return [], [f"建模 skills 选择已降级：{exc}"]
    return [
        {
            "id": item.skill_id,
            "name": item.name,
            "category": item.category,
            "score": item.score,
            "reasons": list(item.reasons),
            "description": str(item.skill.get("description", "") or ""),
            "validationRequirements": [
                {
                    "name": str(requirement.get("name", "") or ""),
                    "description": str(requirement.get("description", "") or ""),
                }
                for requirement in item.skill.get("validation_requirements", [])
                if isinstance(requirement, Mapping)
            ],
        }
        for item in selections
    ], []


def _compose_plan(
    *,
    context: Mapping[str, Any],
    matches: Sequence[Mapping[str, Any]],
    selected_skills: Sequence[Mapping[str, Any]],
    cards: Sequence[Mapping[str, Any]],
    resolution: ExperienceLibraryResolution,
    warnings: Sequence[str],
) -> dict[str, Any]:
    tables = [table for table in context.get("tables", []) if isinstance(table, Mapping)]
    relationships = [item for item in context.get("relationships", []) if isinstance(item, Mapping)]
    quality_warnings = sum(len(table.get("quality", {}).get("warnings", [])) for table in tables)
    data_operations: list[dict[str, Any]] = [
        {
            "name": "表粒度、主键与质量审计",
            "purpose": f"核对 {len(tables)} 张表的粒度、字段类型、缺失、重复和异常；当前识别到 {quality_warnings} 条质量提醒。",
            "origin": "current_task",
            "caseIds": [],
        },
        {
            "name": "表间关系确认与行数核算",
            "purpose": f"逐项验证 {len(relationships)} 条候选关系，并报告每次连接前后的行数、未匹配率和重复放大。",
            "origin": "current_task",
            "caseIds": [],
        },
        {
            "name": "建模数据准备",
            "purpose": "依据变量角色处理缺失、编码、尺度和潜在泄漏；所有转换只在训练折内拟合。",
            "origin": "selected_skills",
            "caseIds": [],
        },
    ]

    cards_by_id = {_case_id(card): card for card in cards}
    historical_models: list[dict[str, Any]] = []
    historical_validations: list[dict[str, Any]] = []
    for match in matches:
        case_id = str(match.get("caseId", "") or "")
        card = cards_by_id.get(case_id)
        if card is None:
            continue
        extraction = card["extraction"]
        for item in extraction.get("models", []):
            if isinstance(item, Mapping) and len(historical_models) < 4:
                historical_models.append(
                    {
                        "name": str(item.get("name", "") or ""),
                        "purpose": str(item.get("purpose", "") or ""),
                        "origin": "historical_reference",
                        "caseIds": [case_id],
                        "referenceOnly": True,
                    }
                )
        for item in extraction.get("validation_methods", []):
            if isinstance(item, Mapping) and len(historical_validations) < 4:
                historical_validations.append(
                    {
                        "name": str(item.get("name", "") or ""),
                        "purpose": str(item.get("purpose", "") or ""),
                        "origin": "historical_reference",
                        "caseIds": [case_id],
                    }
                )

    models = [
        {
            "name": "可解释基线模型",
            "purpose": "先建立与目标一致、可解释且可复现的基线，再比较更复杂候选模型。",
            "origin": "selected_skills",
            "caseIds": [],
            "referenceOnly": False,
        },
        *historical_models,
    ]
    validations: list[dict[str, Any]] = [
        {
            "name": "结构保持的交叉验证",
            "purpose": "按实体、时间或组别切分，防止同源记录跨训练集和验证集。",
            "origin": "selected_skills",
            "caseIds": [],
        },
        {
            "name": "假设与敏感性检查",
            "purpose": "改变关键预处理、参数和阈值，报告结论是否稳定以及失效边界。",
            "origin": "selected_skills",
            "caseIds": [],
        },
        *historical_validations,
    ]
    generated_at = _utc_now()
    return {
        "schemaVersion": 1,
        "status": "needs_confirmation",
        "generatedAt": generated_at,
        "summary": "先完成数据结构与质量审计，再比较可解释基线和有依据的候选模型，并用结构保持验证、敏感性分析和来源审计约束结论。",
        "dataOperations": data_operations,
        "models": models,
        "validationMethods": validations,
        "caseMatches": list(matches),
        "selectedSkills": list(selected_skills),
        "externalSources": [],
        "externalSourceNote": "当前阶段未使用联网来源；如后续补充资料，必须记录标题、链接、用途和与当前任务的差异。",
        "warnings": _unique_strings(warnings),
        "userAdjustments": "",
        "audit": {
            "generatedAt": generated_at,
            "libraryStatus": resolution.status,
            "libraryVersion": resolution.version,
            "contentStatus": resolution.content_status,
            "consideredCaseIds": [_case_id(card) for card in cards],
            "selectedCaseIds": [str(item.get("caseId", "") or "") for item in matches],
            "selectedSkillIds": [str(item.get("id", "") or "") for item in selected_skills],
            "lowRelevancePolicy": "低于 0.28 的案例不进入方案；无匹配时只使用通用 skills。",
            "query": str(context.get("query", "") or "").strip(),
        },
    }


def _context_text(context: Mapping[str, Any]) -> str:
    parts = [str(context.get("query", "") or ""), str(context.get("problemText", "") or "")]
    for table in context.get("tables", []):
        if not isinstance(table, Mapping):
            continue
        parts.extend((str(table.get("name", "") or ""), str(table.get("sourceFileName", "") or "")))
        for field in table.get("fields", []):
            if isinstance(field, Mapping):
                parts.append(str(field.get("name", "") or ""))
    return " ".join(parts)


def _context_columns(context: Mapping[str, Any]) -> list[str]:
    return _unique_strings(
        str(field.get("name", "") or "")
        for table in context.get("tables", [])
        if isinstance(table, Mapping)
        for field in table.get("fields", [])
        if isinstance(field, Mapping)
    )


def _term_matches(term: str, normalized_context: str) -> bool:
    normalized = _normalize_search_text(term)
    return bool(normalized and normalized in normalized_context)


def _term_weight(term: str) -> float:
    normalized = str(term or "").strip().lower()
    if re.search(r"[\u4e00-\u9fff]", normalized):
        return 0.24 if len(normalized) >= 4 else 0.16
    return 0.18 if len(normalized) >= 4 else 0.12


def _normalize_search_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def _case_id(card: Mapping[str, Any]) -> str:
    case = card.get("case", {})
    return str(case.get("id", "") or "").strip() if isinstance(case, Mapping) else ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _unique_strings(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["CompetitionExperienceError", "CompetitionExperienceLibrary"]
