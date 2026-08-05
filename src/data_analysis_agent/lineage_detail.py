"""Static extraction helpers for result-level, reviewable provenance."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .runtime_models import AgentStepTrace


_EXPLICIT_EVIDENCE_PATTERN = re.compile(
    r"\[(?:Evidence|证据)\s*:\s*(?:Python\s*)?step[_\s-]*(\d+)\]",
    re.IGNORECASE,
)
_HIDDEN_EVIDENCE_PATTERN = re.compile(
    r"<!--\s*result-evidence\s*:\s*(?:Python\s*)?step[_\s-]*(\d+)\s*-->",
    re.IGNORECASE,
)
_NUMBER_PATTERN = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?%?")
_STAT_KEYWORDS = (
    "p-value", "p value", "confidence interval", "effect size", "anova",
    "t-test", "mann-whitney", "kruskal", "pearson", "spearman",
    "correlation", "regression", "accuracy", "auc", "mean", "median",
    "significant", "均值", "中位数", "平均", "显著", "相关", "回归",
    "置信区间", "效应量", "分布", "占比", "频数", "长度",
)
_CLAIM_SECTION_HINTS = (
    "result", "finding", "conclusion", "interpretation", "discussion",
    "结果", "结论", "解释", "讨论", "统计", "检验",
)
_COLUMN_CALLS = {
    "groupby", "pivot", "pivot_table", "sort_values", "drop", "dropna",
    "fillna", "set_index", "value_counts", "corr", "corrwith", "plot",
    "scatter", "barplot", "boxplot", "lineplot", "histplot", "regplot",
}
_COLUMN_KEYWORDS = {"x", "y", "hue", "columns", "values", "index", "subset", "by", "on"}
_FIGURE_WRITERS = {"save_figure", "savefig"}


@dataclass(frozen=True)
class DerivedField:
    name: str
    source_fields: tuple[str, ...]
    operation: str
    expression: str


@dataclass(frozen=True)
class ArtifactSemantics:
    artifact_name: str
    code_line_start: int
    code_line_end: int
    focused_code: str
    fields: tuple[str, ...]
    row_selector: str
    filter_conditions: tuple[str, ...]


@dataclass(frozen=True)
class StepSemantics:
    step_index: int
    tool_status: str
    read_fields: tuple[str, ...]
    written_fields: tuple[str, ...]
    derived_fields: tuple[DerivedField, ...]
    artifact_names: tuple[str, ...]
    artifacts: tuple[ArtifactSemantics, ...]
    evidence_text: str
    numeric_tokens: tuple[str, ...]
    keyword_tokens: tuple[str, ...]


@dataclass(frozen=True)
class ReportClaim:
    claim_index: int
    text: str
    section: str
    explicit_step_indices: tuple[int, ...]
    numeric_tokens: tuple[str, ...]
    keyword_tokens: tuple[str, ...]


def unwrap_python_code(tool_input: str) -> str:
    text = str(tool_input or "").strip()
    if not text.startswith("{"):
        return text
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    if not isinstance(payload, dict):
        return text
    return str(payload.get("code", payload.get("input", text)) or "")


def _string_values(node: ast.AST | None) -> tuple[str, ...]:
    if node is None:
        return ()
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (node.value,)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return tuple(value for item in node.elts for value in _string_values(item))
    return ()


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _root_name(node: ast.AST | None) -> str:
    current = node
    while isinstance(current, (ast.Attribute, ast.Subscript, ast.Call)):
        if isinstance(current, ast.Attribute):
            current = current.value
        elif isinstance(current, ast.Subscript):
            current = current.value
        else:
            current = current.func
    return current.id if isinstance(current, ast.Name) else ""


def _dataframe_names(tree: ast.AST) -> set[str]:
    names = {"df", "data", "dataset", "cleaned_df", "clean_df", "df_clean", "df_raw"}
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            call_name = _call_name(node.value)
            looks_like_frame = call_name in {
                "read_csv", "read_excel", "read_parquet", "read_json", "DataFrame",
            } or _root_name(node.value) in names
            if looks_like_frame:
                for target in targets:
                    if target not in names:
                        names.add(target)
                        changed = True
    return names


class _FieldVisitor(ast.NodeVisitor):
    def __init__(self, dataframe_names: set[str]) -> None:
        self.read_fields: list[str] = []
        self.written_fields: list[str] = []
        self.dataframe_names = dataframe_names

    @staticmethod
    def _append_unique(target: list[str], values: Iterable[str]) -> None:
        for value in values:
            normalized = str(value).strip()
            if normalized and normalized not in target:
                target.append(normalized)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        fields = _string_values(node.slice) if _root_name(node.value) in self.dataframe_names else ()
        self._append_unique(self.written_fields if isinstance(node.ctx, ast.Store) else self.read_fields, fields)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        receiver_is_dataframe = _root_name(node.func) in self.dataframe_names
        data_is_dataframe = any(
            keyword.arg == "data" and _root_name(keyword.value) in self.dataframe_names
            for keyword in node.keywords
        )
        if _call_name(node) in _COLUMN_CALLS and (receiver_is_dataframe or data_is_dataframe):
            for argument in node.args:
                self._append_unique(self.read_fields, _string_values(argument))
            for keyword in node.keywords:
                if keyword.arg in _COLUMN_KEYWORDS:
                    self._append_unique(self.read_fields, _string_values(keyword.value))
        self.generic_visit(node)


def extract_python_fields(code: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        tree = ast.parse(unwrap_python_code(code))
    except (SyntaxError, ValueError):
        return (), ()
    visitor = _FieldVisitor(_dataframe_names(tree))
    visitor.visit(tree)
    written = tuple(visitor.written_fields)
    return tuple(field for field in visitor.read_fields if field not in written), written


def _derived_fields(tree: ast.AST, dataframe_names: set[str]) -> tuple[DerivedField, ...]:
    results: list[DerivedField] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        for target in targets:
            if not isinstance(target, ast.Subscript) or _root_name(target.value) not in dataframe_names:
                continue
            names = _string_values(target.slice)
            if not names:
                continue
            visitor = _FieldVisitor(dataframe_names)
            visitor.visit(value)
            expression = ast.unparse(value) if hasattr(ast, "unparse") else ""
            operation = "expression"
            if ".str.len(" in expression or expression.endswith(".str.len()"):
                operation = "string_length"
            results.append(DerivedField(names[0], tuple(visitor.read_fields), operation, expression))
    return tuple(results)


def extract_artifact_names(text: str, *, extensions: Iterable[str]) -> tuple[str, ...]:
    extension_pattern = "|".join(re.escape(item.lstrip(".")) for item in sorted(set(extensions)))
    pattern = re.compile(rf"(?<![\w.-])([\w./\\:()-]+\.(?:{extension_pattern}))", re.IGNORECASE)
    names: list[str] = []
    for match in pattern.finditer(str(text or "")):
        value = match.group(1).strip("`'\"),.;")
        if value not in names:
            names.append(value)
    return tuple(names)


def _assigned_names(node: ast.AST) -> tuple[str, ...]:
    names: list[str] = []
    for item in ast.walk(node):
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store) and item.id not in names:
            names.append(item.id)
    return tuple(names)


def _loaded_names(node: ast.AST) -> tuple[str, ...]:
    names: list[str] = []
    for item in ast.walk(node):
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load) and item.id not in names:
            names.append(item.id)
    return tuple(names)


def _dependency_nodes(tree: ast.Module, target: ast.AST) -> tuple[ast.AST, ...]:
    assignments: dict[str, list[ast.AST]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.For, ast.comprehension)):
            continue
        for name in _assigned_names(node):
            assignments.setdefault(name, []).append(node)
    selected: dict[int, ast.AST] = {id(target): target}
    pending = list(_loaded_names(target))
    while pending:
        name = pending.pop()
        target_line = getattr(target, "lineno", 0)
        candidates = [node for node in assignments.get(name, []) if getattr(node, "lineno", 0) <= target_line]
        dependency = max(candidates, key=lambda node: getattr(node, "lineno", 0), default=None)
        if dependency is None or id(dependency) in selected:
            continue
        selected[id(dependency)] = dependency
        pending.extend(_loaded_names(dependency))
    return tuple(selected.values())


def _figure_artifacts(code: str, tree: ast.Module, dataframe_names: set[str]) -> tuple[ArtifactSemantics, ...]:
    lines = code.splitlines()
    results: list[ArtifactSemantics] = []
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _call_name(node) in _FIGURE_WRITERS
    ]
    calls.sort(key=lambda node: getattr(node, "lineno", 0))
    previous_line = 1
    for call in calls:
        names = _string_values(call.args[0]) if call.args else ()
        if not names and call.args:
            names = tuple(
                str(node.value) for node in ast.walk(call.args[0])
                if isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and Path(str(node.value)).suffix.lower() in {".png", ".jpg", ".jpeg"}
            )
        if not names:
            continue
        artifact_name = Path(names[0]).name
        anchor_lines = [
            getattr(node, "lineno", 0)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and _call_name(node) in {"subplots", "figure"}
            and previous_line <= getattr(node, "lineno", 0) <= getattr(call, "lineno", 0)
        ]
        block_start = max(anchor_lines, default=previous_line)
        block_end = int(getattr(call, "end_lineno", getattr(call, "lineno", block_start)))
        dependencies: list[ast.AST] = []
        for node in ast.walk(tree):
            node_line = getattr(node, "lineno", 0)
            if (
                isinstance(node, ast.Call)
                and block_start <= node_line <= block_end
                and _call_name(node) not in _FIGURE_WRITERS
            ):
                dependencies.extend(_dependency_nodes(tree, node))
        dependencies.extend(_dependency_nodes(tree, call))
        unique_dependencies = {id(node): node for node in dependencies}
        visitor = _FieldVisitor(dataframe_names)
        conditions: list[str] = []
        for node in unique_dependencies.values():
            visitor.visit(node)
            for candidate in ast.walk(node):
                if isinstance(candidate, (ast.Compare, ast.BoolOp)):
                    rendered = ast.unparse(candidate) if hasattr(ast, "unparse") else ""
                    if rendered and rendered not in conditions:
                        conditions.append(rendered)
        upstream_segments: list[tuple[int, str]] = []
        for node in unique_dependencies.values():
            line_number = getattr(node, "lineno", 0)
            end_number = getattr(node, "end_lineno", line_number)
            if line_number >= block_start or not isinstance(node, (ast.Assign, ast.AnnAssign)) or end_number - line_number > 12:
                continue
            segment = ast.get_source_segment(code, node)
            if segment and all(existing[1] != segment for existing in upstream_segments):
                upstream_segments.append((line_number, segment))
        upstream_segments.sort(key=lambda item: item[0])
        focused_parts = [f"# 上游数据准备（原代码第 {line} 行）\n{segment}" for line, segment in upstream_segments]
        focused_parts.append(f"# 当前图表生成（原代码第 {block_start}–{block_end} 行）\n" + "\n".join(lines[block_start - 1:block_end]))
        focused_code = "\n\n".join(focused_parts).strip()
        fields = tuple(dict.fromkeys((*visitor.read_fields, *visitor.written_fields)))
        group_fields = [field for field in fields if "分类" in field or "group" in field.lower() or "category" in field.lower()]
        if conditions:
            row_selector = "满足筛选条件的数据行"
        elif group_fields:
            row_selector = f"清洗后数据的全部行，按「{group_fields[0]}」分组或汇总"
        else:
            row_selector = "清洗后数据的全部行"
        results.append(ArtifactSemantics(
            artifact_name=artifact_name,
            code_line_start=block_start,
            code_line_end=block_end,
            focused_code=focused_code,
            fields=fields,
            row_selector=row_selector,
            filter_conditions=tuple(conditions[:8]),
        ))
        previous_line = block_end + 1
    return tuple(results)


def _tokens(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    normalized = str(text or "").lower()
    return (
        tuple(dict.fromkeys(_NUMBER_PATTERN.findall(normalized))),
        tuple(keyword for keyword in _STAT_KEYWORDS if keyword in normalized),
    )


def extract_step_semantics(
    traces: Iterable[AgentStepTrace],
    *,
    artifact_extensions: Iterable[str],
) -> tuple[StepSemantics, ...]:
    results: list[StepSemantics] = []
    for trace in traces:
        if trace.tool_name != "PythonInterpreterTool":
            continue
        code = unwrap_python_code(trace.tool_input or "")
        try:
            tree = ast.parse(code)
            dataframe_names = _dataframe_names(tree)
            derived = _derived_fields(tree, dataframe_names)
            artifacts = _figure_artifacts(code, tree, dataframe_names)
        except (SyntaxError, ValueError):
            derived, artifacts = (), ()
        read_fields, written_fields = extract_python_fields(code)
        evidence_text = str(trace.observation or trace.observation_preview or trace.summary or "").strip()
        numeric_tokens, keyword_tokens = _tokens(evidence_text)
        results.append(StepSemantics(
            step_index=trace.step_index,
            tool_status=str(trace.tool_status or "unknown"),
            read_fields=read_fields,
            written_fields=written_fields,
            derived_fields=derived,
            artifact_names=extract_artifact_names(
                "\n".join((code, evidence_text)), extensions=artifact_extensions,
            ),
            artifacts=artifacts,
            evidence_text=evidence_text,
            numeric_tokens=numeric_tokens,
            keyword_tokens=keyword_tokens,
        ))
    return tuple(results)


def extract_report_claims(report_markdown: str) -> tuple[ReportClaim, ...]:
    claims: list[ReportClaim] = []
    current_section = ""
    in_code_block = False
    for raw_line in str(report_markdown or "").splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or not line or line.startswith("![") or line.count("|") >= 2:
            continue
        heading = re.match(r"^#+\s+(.+)$", line)
        if heading:
            current_section = heading.group(1).strip()
            continue
        section_is_relevant = any(hint in current_section.lower() for hint in _CLAIM_SECTION_HINTS)
        prepared = re.sub(
            r"([.!?;。！？；])\s*(\[(?:Evidence|证据)\s*:[^\]]+\])",
            r" \2\1",
            line.lstrip("-*0123456789.、 "),
            flags=re.IGNORECASE,
        )
        prepared = re.sub(
            r"([.!?;。！？；])\s*(<!--\s*result-evidence\s*:[^>]+-->)",
            r" \2\1",
            prepared,
            flags=re.IGNORECASE,
        )
        for sentence in re.split(r"(?<!<!)(?<=[!?;。！？；])\s*|(?<!\d)\.(?:\s+|$)", prepared):
            text = sentence.strip()
            numbers, keywords = _tokens(text)
            explicit = tuple(
                dict.fromkeys(
                    int(item)
                    for item in (
                        *_EXPLICIT_EVIDENCE_PATTERN.findall(text),
                        *_HIDDEN_EVIDENCE_PATTERN.findall(text),
                    )
                )
            )
            if len(text) < 12 or not (explicit or (section_is_relevant and (numbers or keywords))):
                continue
            claims.append(ReportClaim(
                claim_index=len(claims) + 1,
                text=text,
                section=current_section or "Document",
                explicit_step_indices=explicit,
                numeric_tokens=numbers,
                keyword_tokens=keywords,
            ))
    return tuple(claims)


def match_claim_to_steps(
    claim: ReportClaim,
    semantics: Iterable[StepSemantics],
) -> tuple[tuple[int, float, str], ...]:
    candidates: list[tuple[int, float, str]] = []
    claim_lower = claim.text.lower()
    explicit = set(claim.explicit_step_indices)
    for step in semantics:
        if step.tool_status.lower() in {"error", "failed"} or not step.evidence_text:
            continue
        if step.step_index in explicit:
            candidates.append((step.step_index, 1.0, "explicit_reference"))
            continue
        numeric_overlap = set(claim.numeric_tokens) & set(step.numeric_tokens)
        keyword_overlap = set(claim.keyword_tokens) & set(step.keyword_tokens)
        field_overlap = {
            field for field in (*step.read_fields, *step.written_fields)
            if field.lower() in claim_lower
        }
        score = len(numeric_overlap) * 3 + len(field_overlap) * 2 + len(keyword_overlap)
        if score < 3:
            continue
        confidence = min(0.95, 0.45 + score * 0.08)
        reasons = []
        if numeric_overlap:
            reasons.append("numeric_overlap")
        if field_overlap:
            reasons.append("field_overlap")
        if keyword_overlap:
            reasons.append("statistical_keyword_overlap")
        candidates.append((step.step_index, round(confidence, 2), "+".join(reasons)))
    candidates.sort(key=lambda item: (-item[1], -item[0]))
    return tuple(candidates[:2])


def fields_for_claim(claim: ReportClaim, step: StepSemantics) -> tuple[str, ...]:
    text = f"{claim.section} {claim.text}".lower()
    fields: list[str] = []
    all_fields = (*step.read_fields, *step.written_fields)
    for field in all_fields:
        normalized = field.lower().replace("_", " ")
        if field.lower() in text or normalized in text:
            fields.append(field)
    if any(token in text for token in ("分类", "类别", "分布", "category", "group", "distribution")):
        fields.extend(field for field in all_fields if any(token in field.lower() for token in ("分类", "类别", "category", "group")))
    if any(token in text for token in ("名称长度", "字符", "name length", "length")):
        fields.extend(field for field in all_fields if any(token in field.lower() for token in ("名称", "name", "length")))
    for derived in step.derived_fields:
        derived_words = derived.name.lower().replace("_", " ").split()
        if derived.name in fields or any(word in text for word in derived_words if len(word) > 3):
            fields.append(derived.name)
            fields.extend(derived.source_fields)
    return tuple(dict.fromkeys(field for field in fields if field))
