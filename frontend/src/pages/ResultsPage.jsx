import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, Download, ExternalLink, FileText, Globe2, Loader2, ShieldAlert } from "lucide-react";
import { toAbsoluteFileUrl } from "../api";
import InteractiveReportView from "../components/InteractiveReportView";
import { EmptyState } from "../components/WorkspacePrimitives";
import { compactStatus, formatBytes, formatDuration } from "../utils/formatters";

const RESULT_TABS = [
  { id: "report", label: "报告" },
  { id: "activity", label: "运行过程" },
  { id: "audit", label: "可信度检查" },
  { id: "files", label: "文件" },
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

function ResultsView({ status, logs, result, outputDir }) {
  const [activeTab, setActiveTab] = useState("report");
  const logEndRef = useRef(null);

  useEffect(() => {
    if (activeTab === "activity") logEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [activeTab, logs]);

  const auditItems = useMemo(() => result ? [
    { label: "文本审阅", detail: result.review?.critique || "没有返回审阅摘要", passed: Boolean(result.review?.critique) },
    { label: "图表检查", detail: result.review?.visionSummary || "没有返回图表检查摘要", passed: Boolean(result.review?.visionSummary) },
    {
      label: "阶段审计",
      detail: result.executionAudit?.findings?.join("；") || compactStatus(result.executionAudit?.status),
      passed: Boolean(result.executionAudit?.passed),
    },
  ] : [], [result]);
  const passedAuditCount = auditItems.filter((item) => item.passed).length;

  return (
    <section className="results-page">
      {result && (
        <div className="run-summary-line">
          <span className="run-success"><CheckCircle2 size={16} />分析完成</span>
          <span>{result.detectedDomain || "未识别领域"}</span>
          <span>{formatDuration(result.totalDurationMs)}</span>
          <span>{result.runId}</span>
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
                available={result.interactiveReportAvailable}
              />
            </>
          ) : (
            <EmptyState title={status.state === "starting" || status.state === "running" ? status.message : "报告尚未生成"} description="开始分析后，报告会在这里逐步生成。" icon={FileText} />
          )}
        </main>
      )}

      {activeTab === "activity" && (
        <div className="activity-document">
          <header>
            <h2>{status.message || "等待任务开始"}</h2>
            {status.state === "starting" || status.state === "running" ? <Loader2 className="spin" size={18} /> : null}
          </header>
          <ol className="activity-timeline">
            {logs.length ? logs.map((line, index) => (
              <li key={`${index}-${line}`}><span>{index + 1}</span><p>{line}</p></li>
            )) : <li className="empty"><span>·</span><p>运行步骤会依次显示在这里。</p></li>}
            <span ref={logEndRef} />
          </ol>
          {result && (
            <details className="run-details">
              <summary>查看运行详情</summary>
              <dl>
                <div><dt>输出深度</dt><dd>{compactStatus(result.qualityMode)}</dd></div>
                <div><dt>知识检索</dt><dd>{compactStatus(result.ragStatus)} · 命中 {result.ragMatchCount || 0}</dd></div>
                <div><dt>经验写回</dt><dd>{compactStatus(result.memoryWritebackStatus)}</dd></div>
                <div><dt>工作流</dt><dd>{result.workflowComplete ? "已完成" : "有提醒"}</dd></div>
              </dl>
            </details>
          )}
        </div>
      )}

      {activeTab === "audit" && (
        <div className="audit-document">
          {result ? (
            <>
              <header className={passedAuditCount === auditItems.length ? "passed" : "warning"}>
                {passedAuditCount === auditItems.length ? <CheckCircle2 size={22} /> : <ShieldAlert size={22} />}
                <div><h2>已通过 {passedAuditCount} 项检查</h2><p>{auditItems.length - passedAuditCount > 0 ? `另有 ${auditItems.length - passedAuditCount} 项需要留意。` : "没有发现需要处理的问题。"}</p></div>
              </header>
              <div className="audit-list">
                {auditItems.map((item) => (
                  <details key={item.label}>
                    <summary><span className={item.passed ? "passed" : "warning"} />{item.label}<em>{item.passed ? "通过" : "提示"}</em></summary>
                    <p>{item.detail}</p>
                  </details>
                ))}
              </div>
              {result.trace?.length > 0 && (
                <details className="trace-details">
                  <summary>查看详细执行轨迹</summary>
                  <div className="trace-table-wrap"><table><thead><tr><th>步骤</th><th>工具</th><th>状态</th><th>决策</th><th>摘要</th></tr></thead><tbody>
                    {result.trace.map((item) => <tr key={`${item.stepIndex}-${item.toolName}`}><td>{item.stepIndex}</td><td>{item.toolName}</td><td>{item.toolStatus}</td><td>{item.decision}</td><td>{item.summary}</td></tr>)}
                  </tbody></table></div>
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
