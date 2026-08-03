import { useEffect, useMemo, useState } from "react";
import { Braces, Download, FileText, GitBranch, Link2, TableProperties } from "lucide-react";
import { toAbsoluteFileUrl } from "../api";
import { ViewLoading } from "../components/WorkspacePrimitives";

const LINEAGE_COLUMNS = [
  { type: "field", label: "字段", description: "分析实际读取或生成的数据列", icon: TableProperties },
  { type: "python_step", label: "Python 步骤", description: "真实执行的数据处理与统计代码", icon: Braces },
  { type: "execution_evidence", label: "执行证据", description: "代码运行后返回的数值与结果", icon: Link2 },
  { type: "report_claim", label: "报告结论", description: "最终报告中的关键判断", icon: FileText },
];

function lineageColumnType(nodeType) {
  return ["source_field", "derived_field"].includes(nodeType) ? "field" : nodeType;
}

function buildLineageChains(lineage) {
  const nodes = new Map((lineage?.nodes || []).map((node) => [node.id, node]));
  const edges = lineage?.edges || [];
  return edges
    .filter((edge) => String(edge.label || "").startsWith("supports:"))
    .map((supportEdge) => {
      const stepEdge = edges.find(
        (edge) => edge.target === supportEdge.source && edge.label === "produces_evidence",
      );
      const fieldEdges = stepEdge
        ? edges.filter((edge) => edge.target === stepEdge.source && edge.label === "used_by")
        : [];
      return {
        id: `${supportEdge.source}-${supportEdge.target}`,
        fields: fieldEdges.map((edge) => nodes.get(edge.source)).filter(Boolean),
        step: stepEdge ? nodes.get(stepEdge.source) : null,
        evidence: nodes.get(supportEdge.source),
        claim: nodes.get(supportEdge.target),
      };
    });
}

function LineageNodeCard({ node, selected, connected, onSelect }) {
  const text = node.text || node.summary || node.field_name || node.label;
  return (
    <button
      type="button"
      className={`lineage-node ${selected ? "selected" : ""} ${connected ? "connected" : ""} ${node.status || ""}`}
      onClick={() => onSelect(node.id)}
    >
      <span className="lineage-node-label">{node.label}</span>
      <span className="lineage-node-text">{text}</span>
      <em>{node.status || "recorded"}</em>
    </button>
  );
}

function LineageView({
  workspace,
  selectedRunId,
  setSelectedRunId,
  historyDetail,
  result,
  historyLoading,
}) {
  const runs = workspace?.historyRuns || [];
  const activePayload = result?.runId === selectedRunId ? result : historyDetail;
  const lineage = activePayload?.lineage;
  const [selectedNodeId, setSelectedNodeId] = useState("");

  useEffect(() => {
    const claim = lineage?.nodes?.find((node) => node.type === "report_claim");
    const first = claim || lineage?.nodes?.[0];
    setSelectedNodeId(first?.id || "");
  }, [lineage, selectedRunId]);

  const nodeMap = useMemo(
    () => new Map((lineage?.nodes || []).map((node) => [node.id, node])),
    [lineage],
  );
  const selectedNode = nodeMap.get(selectedNodeId);
  const connectedIds = useMemo(() => {
    const ids = new Set();
    (lineage?.edges || []).forEach((edge) => {
      if (edge.source === selectedNodeId) ids.add(edge.target);
      if (edge.target === selectedNodeId) ids.add(edge.source);
    });
    return ids;
  }, [lineage, selectedNodeId]);
  const chains = useMemo(() => buildLineageChains(lineage), [lineage]);
  const summary = lineage?.summary || {};

  return (
    <section className="lineage-layout">
      <div className="lineage-main">
        <div className="lineage-heading">
          <div>
            <h1>{activePayload?.runId || "尚未选择运行记录"}</h1>
          </div>
          <div className="lineage-actions">
            <label className="lineage-run-select">
              <span>运行记录</span>
              <select value={selectedRunId} onChange={(event) => setSelectedRunId(event.target.value)}>
                {runs.slice(0, 12).map((run) => (
                  <option value={run.runId} key={run.runId}>
                    {run.runId}
                  </option>
                ))}
              </select>
            </label>
            {lineage?.downloads?.length > 0 && (
              <div className="lineage-downloads">
              {lineage.downloads.map((file) => (
                <a href={toAbsoluteFileUrl(file.url)} key={file.path} target="_blank" rel="noreferrer">
                  <Download size={15} />
                  {file.name}
                </a>
              ))}
              </div>
            )}
          </div>
        </div>

        {historyLoading && !activePayload ? (
          <ViewLoading message="正在加载血缘记录" />
        ) : lineage?.available ? (
          <>
            <div className="lineage-summary">
              <span>字段 <strong>{summary.field_count ?? 0}</strong></span>
              <span>报告结论 <strong>{summary.claim_count ?? 0}</strong></span>
              <span>有证据结论 <strong>{summary.supported_claim_count ?? 0}</strong></span>
              <span>证据支持率 <strong>{Math.round(Number(summary.claim_support_rate ?? 0) * 100)}%</strong></span>
            </div>

            <div className="lineage-flow" aria-label="字段到报告结论的血缘链">
              {LINEAGE_COLUMNS.map(({ type, label, description, icon: Icon }, columnIndex) => {
                const nodes = (lineage.nodes || []).filter((node) => lineageColumnType(node.type) === type);
                return (
                  <section className="lineage-column" key={type}>
                    <header>
                      <span><Icon size={17} /></span>
                      <div>
                        <strong>{columnIndex + 1}. {label}</strong>
                        <p>{description}</p>
                      </div>
                      {columnIndex < LINEAGE_COLUMNS.length - 1 && <b aria-hidden="true">→</b>}
                    </header>
                    <div className="lineage-node-list">
                      {nodes.length ? nodes.map((node) => (
                        <LineageNodeCard
                          key={node.id}
                          node={node}
                          selected={node.id === selectedNodeId}
                          connected={connectedIds.has(node.id)}
                          onSelect={setSelectedNodeId}
                        />
                      )) : <p className="lineage-empty">本次运行没有记录该类节点。</p>}
                    </div>
                  </section>
                );
              })}
            </div>

            <div className="lineage-detail-grid">
              <section className="lineage-detail">
                <div className="section-header compact">
                  <span className="kicker">Selected Node</span>
                  <h2>节点详情</h2>
                </div>
                {selectedNode ? (
                  <>
                    <strong>{selectedNode.label}</strong>
                    <p>{selectedNode.text || selectedNode.summary || selectedNode.field_name || "暂无详细内容。"}</p>
                    <div className="lineage-detail-meta">
                      <span>类型：{lineageColumnType(selectedNode.type)}</span>
                      <span>状态：{selectedNode.status || "recorded"}</span>
                      {selectedNode.step_index != null && <span>步骤：{selectedNode.step_index}</span>}
                      {selectedNode.section && <span>报告章节：{selectedNode.section}</span>}
                    </div>
                  </>
                ) : <p className="muted">点击上方节点查看详情。</p>}
              </section>

              <section className="lineage-chain-list">
                <div className="section-header compact">
                  <span className="kicker">Supported Claims</span>
                  <h2>已建立的结论证据链</h2>
                </div>
                {chains.length ? chains.map((chain) => (
                  <article key={chain.id}>
                    <span>{chain.fields.map((field) => field.label).join("、") || "未识别字段"}</span>
                    <b>→</b>
                    <span>{chain.step?.label || "未识别步骤"}</span>
                    <b>→</b>
                    <span>{chain.evidence?.label || "未识别证据"}</span>
                    <b>→</b>
                    <span>{chain.claim?.text || chain.claim?.label || "未识别结论"}</span>
                  </article>
                )) : <p className="muted">本次运行尚未建立完整的结论证据链。</p>}
              </section>
            </div>
          </>
        ) : (
          <div className="lineage-unavailable">
            <GitBranch size={28} />
            <strong>当前运行没有可展示的字段级与结论级血缘</strong>
            <p>请选择升级后生成的运行记录，或重新执行一次分析任务。</p>
          </div>
        )}
      </div>
    </section>
  );
}

export default LineageView;
