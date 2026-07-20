import { useEffect, useState } from "react";
import { Activity, Braces, Download, GitBranch, MoreHorizontal, TableProperties, X } from "lucide-react";
import { fetchInteractiveReport, toAbsoluteFileUrl } from "../api";
import MarkdownView from "./MarkdownView";

function SnapshotTable({ dataset }) {
  const columns = dataset?.columns || [];
  const rows = dataset?.rows || [];
  if (!dataset || !columns.length) {
    return <p className="muted">当前产物没有可展示的数据快照。</p>;
  }
  return (
    <div className="snapshot-table-wrap">
      <div className="snapshot-meta">
        <strong>{dataset.label || dataset.id}</strong>
        <span>
          {rows.length} / {dataset.rowCount ?? rows.length} 行
          {dataset.truncated ? "，已截断" : ""}
        </span>
      </div>
      <table>
        <thead>
          <tr>{columns.map((column) => <th key={column.key}>{column.label || column.key}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={`row-${rowIndex}`}>
              {columns.map((column) => (
                <td key={column.key}>{row[column.key] == null ? "" : String(row[column.key])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SourceDrawer({ report, selection, initialTab = "data", onClose }) {
  const [activeTab, setActiveTab] = useState("data");

  useEffect(() => {
    if (selection) {
      setActiveTab(initialTab || "data");
    }
  }, [selection?.type, selection?.id, initialTab]);

  if (!selection) return null;

  const { manifest = {}, snapshot = {}, sourceMap = {}, lineage = {} } = report || {};
  const figure = selection.type === "figure"
    ? (manifest.figures || []).find((item) => item.id === selection.id)
    : null;
  const claim = selection.type === "claim"
    ? (manifest.claims || []).find((item) => item.id === selection.id)
    : null;
  const mapping = selection.type === "figure"
    ? sourceMap?.figures?.[selection.id]
    : sourceMap?.claims?.[selection.id];
  const datasetId = mapping?.datasetId || figure?.datasetId || "";
  const dataset = datasetId ? snapshot?.datasets?.[datasetId] : null;
  const sourceIds = mapping?.sourceIds || (mapping?.sourceId ? [mapping.sourceId] : claim?.sourceIds || []);
  const source = (manifest.sources || []).find((item) => sourceIds.includes(item.id));
  const lineageIds = new Set([...(mapping?.lineageNodeIds || []), ...(figure?.lineageNodeIds || []), ...(claim?.lineageNodeIds || [])]);
  const lineageNodes = (lineage.nodes || []).filter((node) => lineageIds.has(node.id));
  const lineageEdges = (lineage.edges || []).filter((edge) => lineageIds.has(edge.source) || lineageIds.has(edge.target));
  const tabs = [
    ["data", "数据"],
    ["code", "代码"],
    ["step", "执行步骤"],
    ["lineage", "血缘"],
  ];

  return (
    <div className="source-drawer-backdrop" role="presentation" onClick={onClose}>
      <aside className="source-drawer" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <header>
          <div>
            <span className="kicker">Source</span>
            <h2>{figure?.title || claim?.section || "来源详情"}</h2>
            <p>{figure?.name || claim?.text || "查看该产物背后的数据、代码和血缘。"}</p>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </header>

        <div className="source-tabs">
          {tabs.map(([id, label]) => (
            <button
              type="button"
              key={id}
              className={activeTab === id ? "active" : ""}
              onClick={() => setActiveTab(id)}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="source-drawer-body">
          {activeTab === "data" && <SnapshotTable dataset={dataset} />}
          {activeTab === "code" && (
            source?.code ? (
              <pre className="source-code"><code>{source.code}</code></pre>
            ) : (
              <p className="muted">当前产物没有匹配到可展示的 Python 代码。</p>
            )
          )}
          {activeTab === "step" && (
            source ? (
              <div className="source-step">
                <div><strong>步骤</strong><span>Python step {source.stepIndex}</span></div>
                <div><strong>状态</strong><span>{source.status || "unknown"} · {source.confidence || "matched"}</span></div>
                <div><strong>摘要</strong><p>{source.summary || "暂无摘要。"}</p></div>
                <div><strong>输出</strong><pre>{source.stdout || "暂无 stdout。"}</pre></div>
              </div>
            ) : (
              <p className="muted">当前产物没有匹配到执行步骤。</p>
            )
          )}
          {activeTab === "lineage" && (
            <div className="source-lineage">
              {lineageNodes.length ? lineageNodes.map((node) => (
                <article key={node.id}>
                  <strong>{node.label || node.id}</strong>
                  <span>{node.type} · {node.status || "recorded"}</span>
                  <p>{node.text || node.summary || node.field_name || ""}</p>
                </article>
              )) : <p className="muted">当前产物没有匹配到血缘节点。</p>}
              {lineageEdges.length > 0 && (
                <div className="source-lineage-edges">
                  {lineageEdges.slice(0, 12).map((edge) => (
                    <span key={`${edge.source}-${edge.target}-${edge.label}`}>
                      {edge.source} → {edge.target} · {edge.label}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {figure?.file?.url && (
          <footer>
            <a href={toAbsoluteFileUrl(figure.file.url)} target="_blank" rel="noreferrer">
              <Download size={15} />
              下载图表
            </a>
          </footer>
        )}
      </aside>
    </div>
  );
}

function ImagePreviewModal({ figure, onClose }) {
  useEffect(() => {
    if (!figure) return undefined;
    const handleKeydown = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeydown);
    return () => document.removeEventListener("keydown", handleKeydown);
  }, [figure, onClose]);

  if (!figure) return null;
  const imageUrl = toAbsoluteFileUrl(figure.url || figure.file?.url);
  return (
    <div className="image-preview-backdrop" role="presentation" onClick={onClose}>
      <div className="image-preview-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <header>
          <div>
            <span className="kicker">Figure preview</span>
            <h2>{figure.title || figure.name}</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭预览">
            <X size={18} />
          </button>
        </header>
        <img src={imageUrl} alt={figure.name || figure.title || "figure preview"} />
      </div>
    </div>
  );
}

function InteractiveReportView({ runId, outputDir, reportMarkdown, figures = [], available }) {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selection, setSelection] = useState(null);
  const [sourceInitialTab, setSourceInitialTab] = useState("data");
  const [openMenuFigureId, setOpenMenuFigureId] = useState("");
  const [previewFigure, setPreviewFigure] = useState(null);

  useEffect(() => {
    let cancelled = false;
    if (!runId || !available) {
      setPayload(null);
      setError("");
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    setError("");
    fetchInteractiveReport(runId, outputDir || "outputs")
      .then((report) => {
        if (!cancelled) setPayload(report);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "交互报告加载失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [runId, outputDir, available]);

  useEffect(() => {
    if (!openMenuFigureId) return undefined;

    const closeMenu = () => setOpenMenuFigureId("");
    const handleKeydown = (event) => {
      if (event.key === "Escape") closeMenu();
    };

    document.addEventListener("click", closeMenu);
    document.addEventListener("keydown", handleKeydown);
    return () => {
      document.removeEventListener("click", closeMenu);
      document.removeEventListener("keydown", handleKeydown);
    };
  }, [openMenuFigureId]);

  const interactive = payload?.available ? payload : null;
  const manifest = interactive?.manifest || {};
  const artifactFigures = interactive ? (manifest.figures || []) : [];
  const claims = interactive ? (manifest.claims || []) : [];

  const openSourceDrawer = (figureId, tab = "data") => {
    setOpenMenuFigureId("");
    setSourceInitialTab(tab);
    setSelection({ type: "figure", id: figureId });
  };

  return (
    <div className="interactive-report-shell">
      <div className="panel report-panel interactive-report-panel">
        <div className="section-header compact">
          <span className="kicker">Report</span>
          <h2>最终分析报告</h2>
          {loading && <p className="muted">正在加载交互来源...</p>}
          {error && <p className="muted">{error}</p>}
        </div>
        <MarkdownView content={reportMarkdown} />
      </div>

      {artifactFigures.length > 0 ? (
        <div className="panel artifact-panel">
          <div className="section-header compact">
            <span className="kicker">Figures</span>
            <h2>可追溯图表</h2>
          </div>
          <div className="artifact-figure-grid">
            {artifactFigures.map((figure) => {
              const imageUrl = toAbsoluteFileUrl(figure.url || figure.file?.url);
              const downloadUrl = figure.file?.url ? toAbsoluteFileUrl(figure.file.url) : "";
              const menuOpen = openMenuFigureId === figure.id;
              return (
                <article className="artifact-figure-card" key={figure.id}>
                  <button
                    type="button"
                    className="artifact-figure-preview"
                    onClick={() => setPreviewFigure(figure)}
                  >
                    <img src={imageUrl} alt={figure.name} />
                  </button>
                  <button
                    type="button"
                    className="artifact-menu-button"
                    aria-label="打开图表菜单"
                    aria-expanded={menuOpen}
                    onClick={(event) => {
                      event.stopPropagation();
                      setOpenMenuFigureId((current) => (current === figure.id ? "" : figure.id));
                    }}
                  >
                    <MoreHorizontal size={18} />
                  </button>
                  {menuOpen && (
                    <div className="artifact-menu" role="menu" onClick={(event) => event.stopPropagation()}>
                      <button type="button" role="menuitem" onClick={() => openSourceDrawer(figure.id, "data")}>
                        <TableProperties size={15} />
                        查看数据源
                      </button>
                      <button type="button" role="menuitem" onClick={() => openSourceDrawer(figure.id, "code")}>
                        <Braces size={15} />
                        查看生成代码
                      </button>
                      <button type="button" role="menuitem" onClick={() => openSourceDrawer(figure.id, "step")}>
                        <Activity size={15} />
                        查看执行步骤
                      </button>
                      <button type="button" role="menuitem" onClick={() => openSourceDrawer(figure.id, "lineage")}>
                        <GitBranch size={15} />
                        查看数据血缘
                      </button>
                      {downloadUrl && (
                        <a href={downloadUrl} target="_blank" rel="noreferrer" role="menuitem">
                          <Download size={15} />
                          下载图表
                        </a>
                      )}
                    </div>
                  )}
                  <div className="artifact-figure-meta">
                    <span>{figure.title || figure.name}</span>
                    <em>{figure.matchConfidence || "matched"}</em>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      ) : figures.length > 0 && (
        <div className="panel">
          <div className="section-header compact">
            <span className="kicker">Figures</span>
            <h2>生成的图表</h2>
          </div>
          <div className="figure-grid">
            {figures.map((figure) => (
              <figure key={figure.path}>
                <img src={toAbsoluteFileUrl(figure.url)} alt={figure.name} />
                <figcaption>{figure.name}</figcaption>
              </figure>
            ))}
          </div>
        </div>
      )}

      {claims.length > 0 && (
        <div className="panel claim-panel">
          <div className="section-header compact">
            <span className="kicker">Claims</span>
            <h2>可追溯结论</h2>
          </div>
          <div className="claim-list">
            {claims.slice(0, 10).map((claim) => (
              <button
                type="button"
                key={claim.id}
                onClick={() => {
                  setSourceInitialTab("data");
                  setSelection({ type: "claim", id: claim.id });
                }}
              >
                <strong>{claim.section}</strong>
                <span>{claim.text}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <SourceDrawer
        report={interactive}
        selection={selection}
        initialTab={sourceInitialTab}
        onClose={() => setSelection(null)}
      />
      <ImagePreviewModal figure={previewFigure} onClose={() => setPreviewFigure(null)} />
    </div>
  );
}

export default InteractiveReportView;
