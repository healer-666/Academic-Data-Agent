import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Braces, CheckCircle2, Database, Download, FileText, GitBranch, Image, Link2 } from "lucide-react";
import { toAbsoluteFileUrl } from "../api";
import { ViewLoading } from "../components/WorkspacePrimitives";

const STAGES = [
  { id: "data", label: "数据依据", description: "分析实际使用的数据", icon: Database, types: ["raw_data", "cleaned_data", "source_field", "derived_field"] },
  { id: "analysis", label: "分析计算", description: "产生结果的处理与统计步骤", icon: Braces, types: ["python_step"] },
  { id: "evidence", label: "结果证据", description: "计算结果和生成图表", icon: Link2, types: ["execution_evidence", "figure"] },
  { id: "report", label: "报告表达", description: "报告中的结论与最终产物", icon: FileText, types: ["report_claim", "final_report"] },
];

const STATUS_LABELS = { success: "已完成", completed: "已完成", passed: "已通过", generated: "已生成", recorded: "已记录", missing: "原文件位置已变化", failed: "失败" };

function statusLabel(value) {
  return STATUS_LABELS[String(value || "recorded").toLowerCase()] || "已记录";
}

function nodeLabel(node) {
  if (!node) return "未知记录";
  if (node.type === "python_step") return `分析步骤 ${node.step_index || "—"}`;
  if (node.type === "raw_data") return "原始上传数据";
  if (node.type === "cleaned_data") return "清洗后的分析数据";
  if (node.type === "final_report") return "最终分析报告";
  return node.text || node.label || node.field_name || "分析记录";
}

function nodeDescription(node) {
  if (!node) return "";
  if (node.type === "python_step") {
    const text = String(node.summary || "").toLowerCase();
    if (text.includes("raw") || text.includes("load")) return "读取并检查数据，确认字段、缺失值和数据规模。";
    if (text.includes("clean")) return "清洗数据并生成可用于后续分析的数据集。";
    if (text.includes("statistical") || text.includes("test") || text.includes("chi-square") || text.includes("kruskal")) return "执行统计检验并计算报告中使用的关键指标。";
    if (text.includes("figure") || text.includes("plot")) return "生成报告图表并核对关键数值。";
    return "完成数据处理与结果计算。";
  }
  if (node.type === "figure") return "由分析步骤生成，并在报告中用于支持对应判断。";
  if (node.type === "report_claim") return node.text || "报告中的关键判断。";
  if (node.type === "final_report") return "汇总数据、分析步骤、结论和图表的最终交付物。";
  return node.summary || node.field_name || "分析过程保存的可追溯记录。";
}

function collectTraceNodes(lineage, seedIds) {
  const nodeMap = new Map((lineage?.nodes || []).map((node) => [node.id, node]));
  const selected = new Set(seedIds.filter((id) => nodeMap.has(id)));
  const edges = lineage?.edges || [];
  let changed = true;
  while (changed) {
    changed = false;
    edges.forEach((edge) => {
      if (selected.has(edge.target) && !selected.has(edge.source)) { selected.add(edge.source); changed = true; }
    });
  }
  if (!selected.size) (lineage?.nodes || []).forEach((node) => selected.add(node.id));
  return [...selected].map((id) => nodeMap.get(id)).filter(Boolean);
}

function EvidenceNode({ node, selected, onSelect }) {
  return (
    <button type="button" className={`evidence-node ${selected ? "selected" : ""}`} onClick={() => onSelect(node.id)}>
      <CheckCircle2 size={16} />
      <span><strong>{nodeLabel(node)}</strong><small>{nodeDescription(node)}</small></span>
      <em>{statusLabel(node.status)}</em>
    </button>
  );
}

function LineageView({ workspace, selectedRunId, setSelectedRunId, historyDetail, result, historyLoading, focus, onBackToReport }) {
  const runs = workspace?.historyRuns || [];
  const activePayload = result?.runId === selectedRunId ? result : historyDetail;
  const storedLineage = activePayload?.lineage;
  const [localFocus, setLocalFocus] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState("");

  const lineage = useMemo(() => {
    if (!storedLineage?.available) return storedLineage;
    const nodes = [...(storedLineage.nodes || [])];
    const edges = [...(storedLineage.edges || [])];
    const firstStep = nodes.filter((node) => node.type === "python_step").sort((a, b) => Number(a.step_index || 0) - Number(b.step_index || 0))[0];
    const figureNodes = nodes.filter((node) => node.type === "figure");

    if (!nodes.some((node) => STAGES[0].types.includes(node.type)) && activePayload?.cleanedData) {
      const recoveredData = { id: "recovered_cleaned_data", type: "cleaned_data", label: activePayload.cleanedData.name || "清洗后的分析数据", status: "recorded", summary: "从本次运行保存的清洗数据文件恢复。" };
      nodes.unshift(recoveredData);
      if (firstStep) edges.push({ source: recoveredData.id, target: firstStep.id, label: "used_by" });
    }

    if (!nodes.some((node) => STAGES[3].types.includes(node.type)) && (activePayload?.report || activePayload?.reportMarkdown)) {
      const recoveredReport = { id: "recovered_final_report", type: "final_report", label: activePayload?.report?.name || "最终分析报告", status: "generated", summary: "从本次运行保存的最终报告恢复。" };
      nodes.push(recoveredReport);
      figureNodes.forEach((node) => edges.push({ source: node.id, target: recoveredReport.id, label: "reported_in" }));
    }
    return { ...storedLineage, nodes, edges };
  }, [storedLineage, activePayload?.cleanedData, activePayload?.report, activePayload?.reportMarkdown]);

  useEffect(() => {
    if (focus?.runId === selectedRunId) setLocalFocus(focus);
    else setLocalFocus(null);
  }, [focus, selectedRunId]);

  const traceNodes = useMemo(() => {
    const seedIds = [...(localFocus?.lineageNodeIds || [])];
    const traced = collectTraceNodes(lineage, seedIds);
    if (localFocus?.type === "claim") {
      const finalReport = (lineage?.nodes || []).find((node) => node.type === "final_report");
      if (finalReport && !traced.some((node) => node.id === finalReport.id)) traced.push(finalReport);
    }
    return traced;
  }, [lineage, localFocus]);
  const nodeMap = useMemo(() => new Map((lineage?.nodes || []).map((node) => [node.id, node])), [lineage]);
  const selectedNode = nodeMap.get(selectedNodeId);
  const traceableTargets = useMemo(() => (lineage?.nodes || []).filter((node) => ["report_claim", "figure"].includes(node.type)), [lineage]);

  useEffect(() => {
    const seed = localFocus?.lineageNodeIds?.find((id) => nodeMap.has(id));
    setSelectedNodeId(seed || traceNodes.at(-1)?.id || "");
  }, [localFocus, traceNodes, nodeMap]);

  const counts = useMemo(() => ({
    data: (lineage?.nodes || []).filter((node) => STAGES[0].types.includes(node.type)).length,
    steps: (lineage?.nodes || []).filter((node) => node.type === "python_step").length,
    evidence: (lineage?.nodes || []).filter((node) => STAGES[2].types.includes(node.type)).length,
  }), [lineage]);

  return (
    <section className="lineage-layout lineage-redesign">
      <div className="lineage-main">
        <div className="lineage-heading">
          <div><span className="kicker">结果追溯</span><h1>证据链追溯</h1><p>从报告结论或图表出发，查看它使用了哪些数据、经过哪些分析步骤。</p></div>
          <div className="lineage-actions">
            <label className="lineage-run-select"><span>运行记录</span><select value={selectedRunId} onChange={(event) => setSelectedRunId(event.target.value)}>{runs.slice(0, 12).map((run) => <option value={run.runId} key={run.runId}>{run.runId}</option>)}</select></label>
            {lineage?.downloads?.length > 0 && <details className="lineage-export"><summary>导出记录</summary><div>{lineage.downloads.map((file) => <a href={toAbsoluteFileUrl(file.url)} key={file.path} target="_blank" rel="noreferrer"><Download size={15} />{file.name}</a>)}</div></details>}
          </div>
        </div>

        {historyLoading && !activePayload ? <ViewLoading message="正在加载证据链" /> : lineage?.available ? (
          <>
            <div className="lineage-summary compact-summary"><span>数据节点 <strong>{counts.data}</strong></span><span>分析步骤 <strong>{counts.steps}</strong></span><span>结果证据 <strong>{counts.evidence}</strong></span><span>当前运行 <strong>{activePayload?.runId || selectedRunId}</strong></span></div>

            {localFocus ? (
              <div className="trace-focus-banner"><button type="button" onClick={onBackToReport}><ArrowLeft size={16} />返回报告</button><div><span>正在追溯</span><strong>{localFocus.label || "当前报告结果"}</strong></div><em><GitBranch size={16} />已定位证据链</em></div>
            ) : (
              <div className="trace-start-card"><GitBranch size={24} /><div><strong>建议从报告直接进入</strong><p>在报告的关键结论或图表旁点击“查看证据链”，这里会自动定位到对应记录。</p></div>{onBackToReport && <button type="button" onClick={onBackToReport}>返回分析报告</button>}</div>
            )}

            {!localFocus && traceableTargets.length > 0 && <section className="trace-targets"><div className="section-header compact"><span className="kicker">可追溯结果</span><h2>也可以从这里选择</h2></div><div>{traceableTargets.map((node) => <button type="button" key={node.id} onClick={() => setLocalFocus({ runId: selectedRunId, label: nodeLabel(node), lineageNodeIds: [node.id] })}>{node.type === "figure" ? <Image size={16} /> : <FileText size={16} />}<span><strong>{nodeLabel(node)}</strong><small>{node.type === "figure" ? "分析图表" : "报告结论"}</small></span><GitBranch size={15} /></button>)}</div></section>}

            <div className="evidence-flow" aria-label="从数据到报告的证据链">
              {STAGES.map(({ id, label, description, icon: Icon, types }, index) => {
                const nodes = traceNodes.filter((node) => types.includes(node.type));
                return <section className={`evidence-stage ${nodes.length ? "has-content" : "empty"}`} key={id}><header><span>{index + 1}</span><Icon size={18} /><div><strong>{label}</strong><p>{description}</p></div></header><div>{nodes.length ? nodes.slice(-5).map((node) => <EvidenceNode key={node.id} node={node} selected={node.id === selectedNodeId} onSelect={setSelectedNodeId} />) : <p>当前运行未保存更细的{label}记录。</p>}</div></section>;
              })}
            </div>

            <section className="evidence-detail-panel"><div><span className="kicker">记录说明</span><h2>{selectedNode ? nodeLabel(selectedNode) : "选择一条记录"}</h2></div>{selectedNode ? <><p>{nodeDescription(selectedNode)}</p><dl><div><dt>记录类型</dt><dd>{STAGES.find((stage) => stage.types.includes(selectedNode.type))?.label || "分析记录"}</dd></div><div><dt>状态</dt><dd>{statusLabel(selectedNode.status)}</dd></div>{selectedNode.step_index != null && <div><dt>分析步骤</dt><dd>第 {selectedNode.step_index} 步</dd></div>}</dl></> : <p className="muted">点击证据链中的节点查看说明。</p>}</section>
          </>
        ) : <div className="lineage-unavailable"><GitBranch size={28} /><strong>当前运行没有可展示的证据链</strong><p>请选择新的运行记录，或重新执行一次分析任务。</p></div>}
      </div>
    </section>
  );
}

export default LineageView;
