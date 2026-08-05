import { useMemo, useState } from "react";
import {
  CheckCircle2,
  ChevronDown,
  Database,
  Download,
  ExternalLink,
  FileCheck2,
  FileText,
  Globe2,
  Loader2,
  SearchCheck,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { historyReportPdfUrl, toAbsoluteFileUrl } from "../api";
import InteractiveReportView from "../components/InteractiveReportView";
import { EmptyState } from "../components/WorkspacePrimitives";
import { compactStatus, formatBytes, formatDuration } from "../utils/formatters";

const RESULT_TABS = [
  { id: "report", label: "报告" },
  { id: "activity", label: "运行过程" },
  { id: "audit", label: "可信度检查" },
  { id: "files", label: "文件" },
];

const PHASE_DEFINITIONS = [
  { id: "prepare", label: "读取资料", description: "识别文件与数据结构", icon: Database },
  { id: "understand", label: "理解数据", description: "检查字段、质量与分析目标", icon: SearchCheck },
  { id: "analyze", label: "执行分析", description: "运行数据处理、统计与建模", icon: Sparkles },
  { id: "verify", label: "验证结果", description: "复核结论、图表与分析过程", icon: ShieldCheck },
  { id: "deliver", label: "生成报告", description: "整理结论、图表与交付文件", icon: FileCheck2 },
];

function ReportContext({ result }) {
  const sources = result.searchSources || [];
  if (!result.searchNotes && !sources.length) return null;
  return (
    <details className="report-context">
      <summary><Globe2 size={15} />外部资料与检索说明</summary>
      {result.searchNotes && <p>{result.searchNotes}</p>}
      {sources.map((source) => (
        <a href={source.url} target="_blank" rel="noreferrer" key={source.url}>
          <span>{source.title || source.url}</span><ExternalLink size={14} />
        </a>
      ))}
    </details>
  );
}

function includesAny(text, terms) {
  return terms.some((term) => text.includes(term));
}

function buildActivityPhases(status, logs, result) {
  const logText = logs.join(" ").toLowerCase();
  const isFinished = Boolean(result) || status.state === "completed";
  const markers = [
    true,
    includesAny(logText, ["context", "数据上下文", "输入数据", "data_context"]),
    includesAny(logText, ["analy", "python", "执行分析", "统计", "tool_"]),
    includesAny(logText, ["valid", "review", "audit", "审阅", "检查"]),
    includesAny(logText, ["report", "final", "报告", "分析完成"]),
  ];
  let activeIndex = Math.max(0, markers.lastIndexOf(true));
  if (isFinished) activeIndex = PHASE_DEFINITIONS.length - 1;

  const traceCount = Array.isArray(result?.trace) ? result.trace.length : 0;
  const figureCount = result?.figures?.length || 0;
  const downloadCount = result?.downloads?.length || 0;
  const completedDescriptions = [
    "输入资料已保存并完成格式识别",
    result?.dataContextSummary || "数据结构与分析目标已确认",
    traceCount ? `已完成 ${traceCount} 个分析步骤` : "数据处理与统计分析已完成",
    "已完成报告、图表与执行过程检查",
    `报告已生成${figureCount ? `，包含 ${figureCount} 张图表` : ""}${downloadCount ? `、${downloadCount} 个文件` : ""}`,
  ];

  return PHASE_DEFINITIONS.map((phase, index) => ({
    ...phase,
    state: isFinished || index < activeIndex ? "done" : index === activeIndex ? "active" : "waiting",
    description: isFinished || index < activeIndex ? completedDescriptions[index] : phase.description,
  }));
}

function buildAuditItems(result) {
  if (!result) return [];
  const reviewStatus = String(result.reviewStatus || "").toLowerCase();
  const hasTextReview = Boolean(result.review?.critique) || includesAny(reviewStatus, ["approved", "passed", "complete"]);
  const reviewAtLimit = reviewStatus === "max_reviews_reached";
  const hasVisionReview = Boolean(result.review?.visionSummary);
  const workflowPassed = Boolean(result.executionAudit?.passed || result.workflowComplete);

  return [
    {
      label: "报告内容审阅",
      description: hasTextReview
        ? "已检查报告结构、统计表述和结论一致性。"
        : reviewAtLimit
          ? "已完成预设轮次的报告修订，建议重点查看最终结论和局限性。"
          : "本次结果没有保存独立的文字审阅记录，建议人工复核关键结论。",
      state: hasTextReview ? "passed" : "notice",
    },
    {
      label: "图表可读性",
      description: hasVisionReview
        ? "已检查图表清晰度以及图文对应关系。"
        : "本次未启用独立的图表视觉复核；图表来自已完成的分析步骤。",
      state: hasVisionReview ? "passed" : "notice",
    },
    {
      label: "分析流程完整性",
      description: workflowPassed
        ? "数据处理、分析执行和报告生成流程均已正常结束。"
        : "未发现明确的流程失败，但当前记录缺少完整的阶段审计摘要。",
      state: workflowPassed ? "passed" : "notice",
    },
  ];
}

function localizeTraceStep(item, index) {
  const raw = `${item?.decision || ""} ${item?.summary || ""}`.toLowerCase();
  let action = "完成数据处理与结果计算";
  if (includesAny(raw, ["load the raw", "raw data", "读取原始"])) action = "读取并检查原始数据";
  else if (includesAny(raw, ["clean", "清洗"])) action = "清洗数据并准备分析数据集";
  else if (includesAny(raw, ["hypothesis", "statistical", "chi-square", "kruskal", "检验"])) action = "完成统计检验并整理关键数值";
  else if (includesAny(raw, ["figure", "plot", "图表"])) action = "生成并检查分析图表";
  else if (includesAny(raw, ["revision", "review", "修订"])) action = "根据审阅意见补充分析";
  const status = String(item?.toolStatus || item?.status || "success").toLowerCase();
  return {
    id: `${item?.stepIndex ?? index}-${item?.toolName || "step"}`,
    index: item?.stepIndex ?? index + 1,
    action,
    status: includesAny(status, ["success", "passed", "complete"]) ? "已完成" : status === "failed" ? "失败" : "已记录",
  };
}

function ResultsView({ status, logs, result, outputDir, onTraceEvidence }) {
  const [activeTab, setActiveTab] = useState("report");
  const phases = useMemo(() => buildActivityPhases(status, logs, result), [status, logs, result]);
  const auditItems = useMemo(() => buildAuditItems(result), [result]);
  const passedAuditCount = auditItems.filter((item) => item.state === "passed").length;
  const traceSteps = Array.isArray(result?.trace) ? result.trace.map(localizeTraceStep) : [];

  return (
    <section className="results-page">
      {result && (
        <div className="run-summary-line">
          <span className="run-success"><CheckCircle2 size={16} />分析完成</span>
          <span>{result.detectedDomain || "未识别领域"}</span>
          <span>{formatDuration(result.totalDurationMs)}</span>
          <span>{result.runId}</span>
          <span className="run-summary-actions">
            {result.report?.url && <a href={toAbsoluteFileUrl(result.report.url)} target="_blank" rel="noreferrer"><FileText size={14} />导出 Markdown</a>}
            <a href={historyReportPdfUrl(result.runId, outputDir)} target="_blank" rel="noreferrer"><Download size={14} />导出 PDF</a>
          </span>
        </div>
      )}

      <nav className="result-tabs" aria-label="结果内容">
        {RESULT_TABS.map((tab) => (
          <button type="button" className={activeTab === tab.id ? "active" : ""} key={tab.id} onClick={() => setActiveTab(tab.id)}>
            {tab.label}
            {tab.id === "files" && result?.downloads?.length > 0 && <span>{result.downloads.length}</span>}
          </button>
        ))}
      </nav>

      {activeTab === "report" && (
        <main className="result-document">
          {result ? (
            <>
              <ReportContext result={result} />
              <InteractiveReportView
                runId={result.runId}
                outputDir={outputDir}
                reportMarkdown={result.reportMarkdown}
                figures={result.figures || []}
                lineage={result.lineage}
                tracePayload={result.tracePayload}
                artifacts={{
                  sourceData: result.sourceData,
                  cleanedData: result.cleanedData,
                  report: result.report,
                  figures: result.figures || [],
                }}
                available={result.interactiveReportAvailable}
                onTraceEvidence={onTraceEvidence}
              />
            </>
          ) : (
            <EmptyState title={status.state === "starting" || status.state === "running" ? status.message : "报告尚未生成"} description="开始分析后，报告会在这里逐步生成。" icon={FileText} />
          )}
        </main>
      )}

      {activeTab === "activity" && (
        <div className="activity-document activity-overview">
          <header className="activity-overview-header">
            <div>
              <span className="kicker">分析进度</span>
              <h2>{result ? "分析已完成" : status.message || "等待任务开始"}</h2>
              <p>这里只展示关键阶段；技术事件和调试信息已收起。</p>
            </div>
            {status.state === "starting" || status.state === "running" ? <Loader2 className="spin" size={20} /> : <CheckCircle2 size={22} />}
          </header>

          <div className="activity-phase-grid">
            {phases.map((phase, index) => {
              const Icon = phase.icon;
              return (
                <article className={`activity-phase ${phase.state}`} key={phase.id}>
                  <div className="activity-phase-icon">{phase.state === "done" ? <CheckCircle2 size={18} /> : <Icon size={18} />}</div>
                  <span>{index + 1}</span>
                  <div><strong>{phase.label}</strong><p>{phase.description}</p></div>
                </article>
              );
            })}
          </div>

          {result && (
            <div className="run-facts">
              <div><span>分析模式</span><strong>{compactStatus(result.qualityMode) || "标准"}</strong></div>
              <div><span>历史经验</span><strong>{result.ragMatchCount ? `匹配 ${result.ragMatchCount} 条` : "本次未使用"}</strong></div>
              <div><span>工作流</span><strong>{result.workflowComplete ? "完整结束" : "已生成结果"}</strong></div>
            </div>
          )}

          <details className="technical-log-details">
            <summary><span>技术日志</span><em>{logs.length} 条，仅供排查问题</em><ChevronDown size={16} /></summary>
            <div className="technical-log-body">
              {logs.length ? logs.map((line, index) => <p key={`${index}-${line}`}><span>{index + 1}</span>{line}</p>) : <p>尚无技术日志。</p>}
            </div>
          </details>
        </div>
      )}

      {activeTab === "audit" && (
        <div className="audit-document audit-overview">
          {result ? (
            <>
              <header className={passedAuditCount === auditItems.length ? "passed" : "warning"}>
                {passedAuditCount === auditItems.length ? <CheckCircle2 size={22} /> : <ShieldAlert size={22} />}
                <div>
                  <span className="kicker">可信度检查</span>
                  <h2>{passedAuditCount === auditItems.length ? "检查全部通过" : "结果可用，但有事项需要留意"}</h2>
                  <p>{passedAuditCount} 项通过，{auditItems.length - passedAuditCount} 项为使用提醒，不代表分析失败。</p>
                </div>
              </header>
              <div className="audit-card-grid">
                {auditItems.map((item) => (
                  <article className={item.state} key={item.label}>
                    <span>{item.state === "passed" ? <CheckCircle2 size={18} /> : <ShieldAlert size={18} />}</span>
                    <div><strong>{item.label}</strong><p>{item.description}</p></div>
                    <em>{item.state === "passed" ? "通过" : "提醒"}</em>
                  </article>
                ))}
              </div>
              {traceSteps.length > 0 && (
                <details className="trace-details localized-trace-details">
                  <summary>查看分析步骤摘要</summary>
                  <div className="localized-trace-list">
                    {traceSteps.map((item) => (
                      <div key={item.id}><span>{item.index}</span><strong>{item.action}</strong><em>{item.status}</em></div>
                    ))}
                  </div>
                </details>
              )}
            </>
          ) : <EmptyState title="暂无可信度记录" description="分析完成后会显示检查结论。" />}
        </div>
      )}

      {activeTab === "files" && (
        <div className="files-document">
          {result?.downloads?.length > 0 ? (
            <div className="file-table" role="table" aria-label="生成文件">
              <div className="file-table-head" role="row"><span>名称</span><span>类型</span><span>大小</span><span /></div>
              {result.downloads.map((file) => (
                <div className="file-table-row" role="row" key={`${file.path}-${file.name}`}>
                  <strong><FileText size={16} />{file.name}</strong>
                  <span>分析产物</span><span>{formatBytes(file.size)}</span>
                  <a className={file.url ? "" : "disabled"} href={toAbsoluteFileUrl(file.url)} target="_blank" rel="noreferrer"><Download size={16} />下载</a>
                </div>
              ))}
            </div>
          ) : <EmptyState title="暂无生成文件" description="分析完成后可在这里下载产物。" icon={Download} />}
        </div>
      )}
    </section>
  );
}

export default ResultsView;
