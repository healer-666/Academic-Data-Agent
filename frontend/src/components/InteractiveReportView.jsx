import { useEffect, useMemo, useState } from "react";
import { Activity, CheckCircle2, ChevronRight, Download, GitBranch, Loader2, Maximize2, MoreHorizontal, TableProperties, X } from "lucide-react";
import { fetchHistoryDataPreview, fetchInteractiveReport, toAbsoluteFileUrl } from "../api";
import { buildTraceSources, figureFileKey, matchMarkdownClaim, resolveEvidenceSources, sourcesForFigure } from "../utils/reportEvidence";
import MarkdownView from "./MarkdownView";

const STATUS_LABELS = {
  success: "已完成",
  completed: "已完成",
  passed: "已通过",
  generated: "已生成",
  recorded: "已记录",
  missing: "文件未定位",
  failed: "失败",
};

function statusLabel(value) {
  return STATUS_LABELS[String(value || "recorded").toLowerCase()] || "已记录";
}

function nodeTypeLabel(type) {
  if (["raw_data", "source_field"].includes(type)) return "原始数据";
  if (["cleaned_data", "derived_field"].includes(type)) return "分析数据";
  if (type === "python_step") return "分析步骤";
  if (["execution_evidence", "figure"].includes(type)) return "结果证据";
  if (["report_claim", "final_report"].includes(type)) return "报告结论";
  return "分析记录";
}

function readableNodeText(node) {
  if (!node) return "";
  if (node.type === "python_step") {
    const text = String(node.summary || "").toLowerCase();
    if (text.includes("raw") || text.includes("load")) return "读取、检查并准备原始数据";
    if (text.includes("statistical") || text.includes("hypothesis") || text.includes("test")) return "执行统计分析并计算关键指标";
    if (text.includes("figure") || text.includes("plot")) return "生成并核对报告图表";
    return `完成第 ${node.step_index || "—"} 个数据分析步骤`;
  }
  return node.text || node.field_name || node.label || "已保存对应分析记录";
}

function SnapshotTable({ dataset }) {
  const columns = dataset?.columns || [];
  const rows = dataset?.rows || [];
  if (!dataset || !columns.length) return <p className="muted">当前结果没有可展示的数据快照。</p>;
  return (
    <div className="snapshot-table-wrap">
      <div className="snapshot-meta"><strong>{dataset.label || dataset.id}</strong><span>{rows.length} / {dataset.rowCount ?? rows.length} 行{dataset.truncated ? "，已截取" : ""}</span></div>
      <table>
        <thead><tr>{columns.map((column) => <th key={column.key}>{column.label || column.key}</th>)}</tr></thead>
        <tbody>{rows.map((row, rowIndex) => (
          <tr key={`row-${rowIndex}`}>{columns.map((column) => <td key={column.key}>{row[column.key] == null ? "" : String(row[column.key])}</td>)}</tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function confidenceLabel(value) {
  if (value === "exact_artifact" || Number(value) >= 0.85) return "精确定位";
  if (value === "step_artifact" || Number(value) >= 0.6) return "高相关定位";
  return "定位信息有限";
}

function EvidenceLocator({ dataset }) {
  const locator = dataset?.locator;
  if (!locator) return <div className="evidence-locator warning"><strong>未保存结果级数据定位</strong><p>这项结果只能查看文件级记录，尚不足以逐行复核。</p></div>;
  const coverage = Number(locator.sourceRowMappingCoverage ?? 0);
  return (
    <section className="evidence-locator">
      <div className="evidence-locator-heading">
        <div><span className="kicker">本结果实际使用的数据</span><strong>{locator.rowSelector || "已定位的数据范围"}</strong></div>
        <em className={coverage >= 0.95 ? "precise" : "limited"}>{confidenceLabel(locator.confidence)}</em>
      </div>
      <dl>
        <div><dt>原始文件</dt><dd><code>{locator.sourcePath || "未记录"}</code>{locator.sourceFile?.url && <a href={toAbsoluteFileUrl(locator.sourceFile.url)} target="_blank" rel="noreferrer"><Download size={13} />下载</a>}</dd></div>
        {locator.sourceSheet && <div><dt>工作表</dt><dd>{locator.sourceSheet}</dd></div>}
        <div><dt>原始行</dt><dd>第 {locator.sourceRows || "未定位"} 行{coverage < 1 && <small>（行号映射覆盖率 {(coverage * 100).toFixed(1)}%）</small>}</dd></div>
        <div><dt>清洗后行</dt><dd>第 {locator.cleanedRows || "未定位"} 行</dd></div>
        <div><dt>使用列</dt><dd className="locator-chips">{(locator.columns || []).length ? locator.columns.map((column) => <span key={column}>{column}</span>) : <small>没有可靠解析出具体列</small>}</dd></div>
        <div><dt>计算位置</dt><dd>{locator.stepIndex ? `分析步骤 ${locator.stepIndex}` : "未定位到具体步骤"}{locator.codeLineStart && ` · 代码第 ${locator.codeLineStart}–${locator.codeLineEnd} 行`}</dd></div>
      </dl>
      {(locator.filterConditions || []).length > 0 && <div className="locator-detail"><strong>筛选条件</strong>{locator.filterConditions.map((condition) => <code key={condition}>{condition}</code>)}</div>}
      {(locator.derivedFields || []).length > 0 && <div className="locator-detail"><strong>派生字段</strong>{locator.derivedFields.map((field) => <p key={field.name}><b>{field.name}</b> ← {field.sourceFields?.join("、") || "未知来源列"}<code>{field.expression}</code></p>)}</div>}
      <p className="evidence-locator-note">下表只展示本结果涉及的列，并同时给出清洗后行号和原始文件行号；下载完整文件不是复核的前提。</p>
    </section>
  );
}

function DataPreviewPanel({ runId, outputDir, dataset, artifacts = {} }) {
  const [kind, setKind] = useState("cleaned");
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    if (dataset || !runId) return () => { cancelled = true; };
    setPreview(null);
    setLoading(true);
    setError("");
    fetchHistoryDataPreview(runId, kind, outputDir || "outputs")
      .then((payload) => { if (!cancelled) setPreview(payload); })
      .catch((err) => { if (!cancelled) { setPreview(null); setError(err instanceof Error ? err.message : "数据预览加载失败"); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [runId, outputDir, kind, dataset]);

  if (dataset) return <div className="result-data-evidence"><EvidenceLocator dataset={dataset} /><SnapshotTable dataset={dataset} /></div>;
  const activeFile = kind === "source" ? artifacts.sourceData : artifacts.cleanedData;
  const tableDataset = preview ? {
    id: kind,
    label: preview.name,
    columns: (preview.columns || []).map((column) => ({ key: column, label: column })),
    rows: preview.rows || [],
    rowCount: preview.rowCount,
    truncated: preview.truncated,
  } : null;
  return (
    <div className="data-preview-panel">
      <div className="data-preview-switcher">
        <button type="button" className={kind === "source" ? "active" : ""} onClick={() => setKind("source")}>原始数据</button>
        <button type="button" className={kind === "cleaned" ? "active" : ""} onClick={() => setKind("cleaned")}>清洗后数据</button>
      </div>
      <div className="data-preview-location">
        <span>实际读取位置</span>
        <code>{preview?.path || activeFile?.path || "当前运行未记录文件位置"}</code>
        {(preview?.download?.url || activeFile?.url) && <a href={toAbsoluteFileUrl(preview?.download?.url || activeFile.url)} target="_blank" rel="noreferrer"><Download size={14} />下载完整文件</a>}
      </div>
      {loading && <div className="data-preview-loading"><Loader2 className="spin" size={18} />正在读取数据预览...</div>}
      {!loading && error && <div className="data-preview-error"><p>{error}</p>{activeFile?.path && <code>{activeFile.path}</code>}</div>}
      {!loading && tableDataset && <><p className="data-preview-note">显示前 {preview.displayedRowCount} 行{preview.rowCount != null ? `，共 ${preview.rowCount} 行` : ""}{preview.sheetName ? ` · 工作表：${preview.sheetName}` : ""}</p><SnapshotTable dataset={tableDataset} /></>}
    </div>
  );
}

function collectEvidenceNodes(lineage, seedIds) {
  const nodes = lineage?.nodes || [];
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  const selected = new Set(seedIds.filter(Boolean));
  const edges = lineage?.edges || [];
  let changed = true;
  while (changed) {
    changed = false;
    edges.forEach((edge) => {
      if (selected.has(edge.target) && !selected.has(edge.source)) {
        selected.add(edge.source);
        changed = true;
      }
    });
  }
  if (!selected.size) nodes.filter((node) => node.type === "python_step").slice(-2).forEach((node) => selected.add(node.id));
  return [...selected].map((id) => nodeMap.get(id)).filter(Boolean);
}

function ArtifactRecord({ label, description, file }) {
  const content = <><CheckCircle2 size={15} /><div><b>{label}</b><p>{description || file?.name || "已保存"}</p></div><em>{file?.url ? "可下载" : "已记录"}</em></>;
  return file?.url ? <a className="evidence-artifact-record" href={toAbsoluteFileUrl(file.url)} target="_blank" rel="noreferrer">{content}</a> : <article>{content}</article>;
}

function EvidenceChain({ lineage, lineageIds, selectionLabel, artifacts = {}, sources = [], figure }) {
  const nodes = collectEvidenceNodes(lineage, lineageIds);
  const dataNodes = nodes.filter((node) => ["raw_data", "source_field"].includes(node.type));
  const intermediateNodes = nodes.filter((node) => ["cleaned_data", "derived_field", "execution_evidence", "figure"].includes(node.type));
  const stepNodes = nodes.filter((node) => node.type === "python_step");
  return (
    <div className="evidence-chain">
      <div className="evidence-chain-intro"><GitBranch size={18} /><div><strong>这项结果是怎么得出的？</strong><p>{selectionLabel}</p></div></div>
      <section className="evidence-chain-stage"><span>1</span><div><strong>原始数据</strong>
        {artifacts.sourceData ? <ArtifactRecord label="原始上传文件" description={artifacts.sourceData.name} file={artifacts.sourceData} /> : dataNodes.length ? dataNodes.map((node) => <article key={node.id}><CheckCircle2 size={15} /><div><b>{nodeTypeLabel(node.type)}</b><p>{readableNodeText(node)}</p></div><em>{statusLabel(node.status)}</em></article>) : <p className="muted">当前运行没有保留可下载的原始文件。</p>}
      </div></section>
      <section className="evidence-chain-stage"><span>2</span><div><strong>中间产物</strong>
        {artifacts.cleanedData && <ArtifactRecord label="清洗后的分析数据" description={artifacts.cleanedData.name} file={artifacts.cleanedData} />}
        {figure && <ArtifactRecord label="当前分析图表" description={figure.title || figure.name} file={figure.file || figure} />}
        {!artifacts.cleanedData && !figure && intermediateNodes.length ? intermediateNodes.slice(-3).map((node) => <article key={node.id}><CheckCircle2 size={15} /><div><b>{nodeTypeLabel(node.type)}</b><p>{readableNodeText(node)}</p></div><em>{statusLabel(node.status)}</em></article>) : null}
      </div></section>
      <section className="evidence-chain-stage"><span>3</span><div><strong>执行代码与步骤</strong>
        {sources.length ? sources.slice(0, 6).map((source) => <details className="evidence-code-step" key={source.id}><summary><CheckCircle2 size={15} /><span><b>分析步骤 {source.stepIndex || "—"}</b><small>{source.summary || "执行数据分析代码"}</small></span><em>{statusLabel(source.status)}</em></summary>{source.code && <pre><code>{source.code}</code></pre>}</details>) : stepNodes.length ? stepNodes.slice(-4).map((node) => <article key={node.id}><CheckCircle2 size={15} /><div><b>{nodeTypeLabel(node.type)}</b><p>{readableNodeText(node)}</p></div><em>{statusLabel(node.status)}</em></article>) : <p className="muted">当前运行没有保存可展示的执行代码。</p>}
      </div></section>
      <section className="evidence-chain-stage result"><span>4</span><div><strong>报告结论</strong><article><CheckCircle2 size={15} /><div><b>当前结论或图表</b><p>{selectionLabel}</p></div><em>已写入报告</em></article></div></section>
    </div>
  );
}

function SourceDrawer({ report, selection, initialTab = "lineage", onClose }) {
  const [activeTab, setActiveTab] = useState(initialTab);
  useEffect(() => { if (selection) setActiveTab(initialTab || "lineage"); }, [selection?.type, selection?.id, initialTab]);
  if (!selection) return null;

  const { manifest = {}, snapshot = {}, sourceMap = {}, lineage = {}, artifacts = {} } = report || {};
  const figure = selection.type === "figure" ? (manifest.figures || []).find((item) => item.id === selection.id) : null;
  const claim = selection.type === "claim" ? (manifest.claims || []).find((item) => item.id === selection.id) : null;
  const mapping = selection.type === "figure" ? sourceMap?.figures?.[selection.id] : sourceMap?.claims?.[selection.id];
  const datasetId = mapping?.datasetId || figure?.datasetId || claim?.datasetId || "";
  const dataset = datasetId ? snapshot?.datasets?.[datasetId] : null;
  const sourceIds = mapping?.sourceIds || (mapping?.sourceId ? [mapping.sourceId] : claim?.sourceIds || []);
  const matchedSources = resolveEvidenceSources(manifest.sources || [], sourceIds, figure);
  const lineageIds = [...(mapping?.lineageNodeIds || []), ...(figure?.lineageNodeIds || []), ...(claim?.lineageNodeIds || [])];
  const selectionLabel = figure?.title || claim?.text || selection.label || "当前报告结果";
  const tabs = [["lineage", "证据链"], ["data", "数据定位"], ["process", "复核过程"]];

  return (
    <div className="source-drawer-backdrop" role="presentation" onClick={onClose}>
      <aside className="source-drawer" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <header><div><span className="kicker">结果追溯</span><h2>{figure?.title || claim?.section || "证据链详情"}</h2><p>{selectionLabel}</p></div><button type="button" className="icon-button" onClick={onClose} aria-label="关闭"><X size={18} /></button></header>
        <div className="source-tabs">{tabs.map(([id, label]) => <button type="button" key={id} className={activeTab === id ? "active" : ""} onClick={() => setActiveTab(id)}>{label}</button>)}</div>
        <div className="source-drawer-body">
          {activeTab === "lineage" && <EvidenceChain lineage={lineage} lineageIds={lineageIds} selectionLabel={selectionLabel} artifacts={artifacts} sources={matchedSources} figure={figure} />}
          {activeTab === "data" && <DataPreviewPanel runId={report?.runId} outputDir={report?.outputDir} dataset={dataset} artifacts={artifacts} />}
          {activeTab === "process" && (matchedSources.length ? <div className="source-step-list">{matchedSources.map((item) => <article key={item.id}><span>{item.stepIndex || "—"}</span><div><strong>{item.summary || item.toolName || "分析计算"}</strong><p>{item.matchReason || "依据运行记录定位到这项结果的计算过程"}</p>{item.codeLineStart && <small>原步骤代码第 {item.codeLineStart}–{item.codeLineEnd} 行</small>}</div><em>{statusLabel(item.status)}</em>{(item.code || item.stdout) && <details className="source-step-inspection" open><summary>检查代码与运行输出</summary>{item.code && <section><b>与当前结果有关的代码</b><pre><code>{item.code}</code></pre></section>}{item.stdout && <section><b>该步骤的运行输出</b><pre>{item.stdout}</pre></section>}</details>}</article>)}</div> : <div className="evidence-locator warning"><strong>没有足够的结果级执行记录</strong><p>系统没有找到能可靠支持当前结果的代码和运行输出，因此没有用其他步骤代替。</p></div>)}
        </div>
        {figure?.file?.url && <footer><a href={toAbsoluteFileUrl(figure.file.url)} target="_blank" rel="noreferrer"><Download size={15} />下载图表</a></footer>}
      </aside>
    </div>
  );
}

function ImagePreviewModal({ figure, onClose }) {
  useEffect(() => {
    if (!figure) return undefined;
    const handleKeydown = (event) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", handleKeydown);
    return () => document.removeEventListener("keydown", handleKeydown);
  }, [figure, onClose]);
  if (!figure) return null;
  return <div className="image-preview-backdrop" role="presentation" onClick={onClose}><div className="image-preview-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}><header><div><span className="kicker">图表预览</span><h2>{figure.title || figure.name}</h2></div><button type="button" className="icon-button" onClick={onClose} aria-label="关闭预览"><X size={18} /></button></header><img src={toAbsoluteFileUrl(figure.url || figure.file?.url)} alt={figure.name || figure.title || "图表预览"} /></div></div>;
}

function extractMarkdownFigures(markdown) {
  const figures = [];
  const expression = /!\[([^\]]*)\]\(([^)]+)\)/g;
  for (const match of String(markdown || "").matchAll(expression)) {
    const url = match[2];
    const fileName = decodeURIComponent(url.split("%2F").pop()?.split("/").pop() || match[1] || `图表 ${figures.length + 1}`);
    figures.push({ id: `report-figure-${figures.length + 1}`, title: match[1] || `图表 ${figures.length + 1}`, name: fileName, url });
  }
  return figures;
}

function extractConclusionClaims(markdown) {
  const text = String(markdown || "");
  const match = text.match(/(?:^|\n)##\s+[^\n]*(?:Conclusion|结论)[^\n]*\n([\s\S]*?)(?=\n##\s|$)/i);
  if (!match) return [];
  return match[1].split("\n").map((line) => line.match(/^\s*\d+[.)、]\s*\*\*(.+?)\*\*[:：]?\s*(.+)$/)).filter(Boolean).slice(0, 5).map((item, index) => ({ id: `report-claim-${index + 1}`, section: item[1].replace(/[：:]$/, ""), text: item[2] }));
}

function InteractiveFigureCard({ figure, menuOpen, onToggleMenu, onPreview, onOpenEvidence }) {
  const imageUrl = toAbsoluteFileUrl(figure.url || figure.file?.url);
  const downloadUrl = figure.file?.url || figure.url;
  return (
    <article className={`artifact-figure-card ${menuOpen ? "menu-open" : ""}`}>
      <header className="artifact-figure-header">
        <strong>{figure.title || figure.name}</strong>
        <button
          type="button"
          className="artifact-menu-button"
          aria-label={`打开${figure.title || figure.name || "图表"}菜单`}
          aria-expanded={menuOpen}
          onClick={(event) => { event.stopPropagation(); onToggleMenu(); }}
        >
          <MoreHorizontal size={18} />
        </button>
      </header>
      {menuOpen && (
        <div className="artifact-menu" role="menu" onClick={(event) => event.stopPropagation()}>
          <button type="button" role="menuitem" onClick={onPreview}><Maximize2 size={16} /><span>放大查看图表</span></button>
          <button type="button" role="menuitem" onClick={() => onOpenEvidence("data")}><TableProperties size={16} /><span>查看数据来源</span></button>
          <button type="button" role="menuitem" onClick={() => onOpenEvidence("lineage")}><GitBranch size={16} /><span>查看证据链</span><ChevronRight className="menu-chevron" size={15} /></button>
          <button type="button" role="menuitem" onClick={() => onOpenEvidence("process")}><Activity size={16} /><span>查看复核过程</span></button>
          {downloadUrl && <a href={toAbsoluteFileUrl(downloadUrl)} target="_blank" rel="noreferrer" role="menuitem"><Download size={16} /><span>下载图表</span></a>}
        </div>
      )}
      <button type="button" className="artifact-figure-preview" onClick={onPreview}>
        <img src={imageUrl} alt={figure.name || figure.title} />
      </button>
    </article>
  );
}

function InteractiveReportView({ runId, outputDir, reportMarkdown, figures = [], lineage, tracePayload, artifacts = {}, available, onTraceEvidence }) {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selection, setSelection] = useState(null);
  const [sourceInitialTab, setSourceInitialTab] = useState("lineage");
  const [openMenuFigureId, setOpenMenuFigureId] = useState("");
  const [previewFigure, setPreviewFigure] = useState(null);

  useEffect(() => {
    let cancelled = false;
    if (!runId) { setPayload(null); return () => { cancelled = true; }; }
    setLoading(true);
    fetchInteractiveReport(runId, outputDir || "outputs").then((report) => { if (!cancelled) setPayload(report); }).catch(() => { if (!cancelled) setPayload(null); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [runId, outputDir]);

  useEffect(() => {
    if (!openMenuFigureId) return undefined;
    const closeMenu = () => setOpenMenuFigureId("");
    document.addEventListener("click", closeMenu);
    return () => document.removeEventListener("click", closeMenu);
  }, [openMenuFigureId]);

  const interactive = payload?.available ? payload : null;
  const markdownFigures = useMemo(() => extractMarkdownFigures(reportMarkdown), [reportMarkdown]);
  const markdownClaims = useMemo(() => extractConclusionClaims(reportMarkdown), [reportMarkdown]);
  const artifactFigures = interactive?.manifest?.figures?.length ? interactive.manifest.figures : figures.length ? figures.map((item, index) => ({ ...item, id: item.id || `result-figure-${index + 1}`, title: item.title || item.name })) : markdownFigures;
  const claims = interactive?.manifest?.claims?.length ? interactive.manifest.claims : markdownClaims;
  const lineageNodes = lineage?.nodes || interactive?.lineage?.nodes || [];
  const legacySources = useMemo(() => buildTraceSources(tracePayload), [tracePayload]);
  const fallbackSourceMap = useMemo(() => {
    const pythonIds = lineageNodes.filter((node) => node.type === "python_step").map((node) => node.id);
    const figureMap = {};
    artifactFigures.forEach((figure) => {
      const name = String(figure.name || figure.title || "").toLowerCase();
      const matched = lineageNodes.find((node) => node.type === "figure" && (name.includes(String(node.label || "").toLowerCase().replace(/\.png$/, "")) || String(node.label || "").toLowerCase().includes(name.replace(/\.png$/, ""))));
      const relatedSources = sourcesForFigure(figure, legacySources);
      figureMap[figure.id] = { lineageNodeIds: matched ? [matched.id] : pythonIds.slice(-1), sourceIds: relatedSources.map((source) => source.id) };
    });
    const claimMap = Object.fromEntries(claims.map((claim, index) => {
      return [claim.id, { lineageNodeIds: [], sourceIds: [] }];
    }));
    return { figures: figureMap, claims: claimMap };
  }, [artifactFigures, claims, lineageNodes, legacySources]);
  const mergedSources = interactive
    ? [...(interactive.manifest?.sources || []), ...legacySources.filter((legacy) => !(interactive.manifest?.sources || []).some((source) => source.id === legacy.id))]
    : legacySources;
  const report = interactive
    ? { ...interactive, manifest: { ...interactive.manifest, sources: mergedSources }, artifacts, runId, outputDir }
    : { available: true, manifest: { figures: artifactFigures, claims, sources: legacySources }, snapshot: {}, sourceMap: fallbackSourceMap, lineage: lineage || {}, artifacts, runId, outputDir };

  const openEvidence = (type, item, tab = "lineage") => {
    setOpenMenuFigureId("");
    setSourceInitialTab(tab);
    setSelection({ type, id: item.id, label: item.title || item.text });
  };

  const renderInteractiveImage = ({ alt, url, index }) => {
    const fileKey = figureFileKey(url);
    const matched = artifactFigures.find((figure) => {
      const candidates = [figure.url, figure.file?.url, figure.name, figure.file?.name];
      return candidates.some((candidate) => figureFileKey(candidate) === fileKey);
    }) || artifactFigures[index];
    const figure = matched
      ? { ...matched, url: matched.url || matched.file?.url || url, title: matched.title || alt }
      : { id: `report-figure-${index + 1}`, title: alt, name: fileKey || alt, url };
    const figureId = figure.id || `report-figure-${index + 1}`;
    return (
      <InteractiveFigureCard
        key={`inline-${figureId}-${index}`}
        figure={{ ...figure, id: figureId }}
        menuOpen={openMenuFigureId === figureId}
        onToggleMenu={() => setOpenMenuFigureId((current) => current === figureId ? "" : figureId)}
        onPreview={() => { setOpenMenuFigureId(""); setPreviewFigure(figure); }}
        onOpenEvidence={(tab) => openEvidence("figure", { ...figure, id: figureId }, tab)}
      />
    );
  };

  const renderInteractiveClaim = ({ text, defaultContent }) => {
    const claim = matchMarkdownClaim(text, claims);
    if (!claim) return null;
    return (
      <button type="button" className="inline-claim-button" onClick={() => openEvidence("claim", claim)}>
        <span>{defaultContent}</span><em><GitBranch size={14} />查看证据</em>
      </button>
    );
  };

  return (
    <div className="interactive-report-shell">
      <div className="panel report-panel interactive-report-panel"><div className="section-header compact"><span className="kicker">分析报告</span><h2>最终分析报告</h2>{loading && <p className="muted">正在整理结果来源...</p>}</div><MarkdownView content={reportMarkdown} renderImage={renderInteractiveImage} renderListItem={renderInteractiveClaim} /></div>

      {markdownFigures.length === 0 && artifactFigures.length > 0 && (
        <div className="panel artifact-panel">
          <div className="section-header compact">
            <span className="kicker">分析图表</span>
            <h2>图表与证据</h2>
            <p>点击图表右上角菜单，可以查看数据和证据来源。</p>
          </div>
          <div className="artifact-figure-grid">
            {artifactFigures.map((figure) => <InteractiveFigureCard key={figure.id} figure={figure} menuOpen={openMenuFigureId === figure.id} onToggleMenu={() => setOpenMenuFigureId((current) => current === figure.id ? "" : figure.id)} onPreview={() => { setOpenMenuFigureId(""); setPreviewFigure(figure); }} onOpenEvidence={(tab) => openEvidence("figure", figure, tab)} />)}
          </div>
        </div>
      )}

      <SourceDrawer report={report} selection={selection} initialTab={sourceInitialTab} onClose={() => setSelection(null)} />
      <ImagePreviewModal figure={previewFigure} onClose={() => setPreviewFigure(null)} />
    </div>
  );
}

export default InteractiveReportView;
