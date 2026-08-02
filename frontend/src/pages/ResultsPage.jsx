import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, Clock3, Download, ExternalLink, Globe2, Search, ShieldCheck, WifiOff } from "lucide-react";
import { toAbsoluteFileUrl } from "../api";
import InteractiveReportView from "../components/InteractiveReportView";
import { EmptyState, StatCard } from "../components/WorkspacePrimitives";
import { compactStatus, formatBytes, formatDuration } from "../utils/formatters";

const SEARCH_STATUS_LABELS = {
  used: "已使用联网资料",
  attempted: "已尝试搜索",
  unavailable: "搜索不可用",
  not_used: "本次无需搜索",
};

const RESULT_TABS = [
  { id: "report", label: "分析报告" },
  { id: "activity", label: "执行日志" },
  { id: "audit", label: "可信度检查" },
  { id: "files", label: "生成文件" },
];

function SearchStatusPanel({ result }) {
  const sources = result.searchSources || [];
  const unavailable = result.searchStatus === "unavailable";
  const Icon = unavailable ? WifiOff : Globe2;
  return (
    <section className={`panel search-status-panel search-${result.searchStatus || "not_used"}`}>
      <header>
        <span className="search-status-icon"><Icon size={19} /></span>
        <div>
          <small>外部资料</small>
          <strong>{SEARCH_STATUS_LABELS[result.searchStatus] || compactStatus(result.searchStatus)}</strong>
          <p>{result.searchNotes || "系统会根据任务内容自动判断是否需要外部资料。"}</p>
        </div>
      </header>
      {sources.length > 0 && (
        <div className="search-source-list">
          {sources.map((source) => (
            <a href={source.url} target="_blank" rel="noreferrer" key={source.url}>
              <span>
                <strong>{source.title || source.url}</strong>
                {source.snippet && <small>{source.snippet}</small>}
              </span>
              <ExternalLink size={15} />
            </a>
          ))}
        </div>
      )}
    </section>
  );
}

function ResultsView({ status, logs, result, outputDir }) {
  const [activeTab, setActiveTab] = useState("report");
  const logEndRef = useRef(null);

  useEffect(() => {
    if (activeTab === "activity") logEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [activeTab, logs]);

  const stats = useMemo(
    () => [
      ["运行状态", status.message || "等待任务开始", Activity],
      ["领域识别", result?.detectedDomain || "暂无", Search],
      ["审阅状态", result?.reviewStatus || "暂无", ShieldCheck],
      ["联网搜索", result ? (SEARCH_STATUS_LABELS[result.searchStatus] || "已评估") : "暂无", Globe2],
      ["总耗时", result ? formatDuration(result.totalDurationMs) : "暂无", Clock3],
    ],
    [result, status],
  );

  return (
    <section className="view-stack results-page">
      <div className="stat-grid results-stat-grid">
        {stats.map(([label, value, Icon]) => <StatCard key={label} label={label} value={value} icon={Icon} />)}
      </div>

      <nav className="result-tabs" aria-label="结果内容">
        {RESULT_TABS.map((tab) => (
          <button
            type="button"
            className={activeTab === tab.id ? "active" : ""}
            aria-current={activeTab === tab.id ? "page" : undefined}
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
            {tab.id === "files" && result?.downloads?.length > 0 && <span>{result.downloads.length}</span>}
          </button>
        ))}
      </nav>

      {activeTab === "report" && (
        <div className="result-tab-panel report-tab-panel">
          {result ? (
            <>
              <SearchStatusPanel result={result} />
              <InteractiveReportView
                runId={result.runId}
                outputDir={outputDir}
                reportMarkdown={result.reportMarkdown}
                figures={result.figures || []}
                available={result.interactiveReportAvailable}
              />
            </>
          ) : (
            <EmptyState title="报告尚未生成" description="创建并完成一次分析任务后，正式报告会出现在这里。" icon={Activity} />
          )}
        </div>
      )}

      {activeTab === "activity" && (
        <div className="result-tab-panel results-layout">
          <section className="panel">
            <div className="section-header compact"><span className="kicker">Progress</span><h2>运行日志</h2></div>
            <div className="log-box">
              {logs.length ? logs.map((line, index) => <p key={`${index}-${line}`}>{line}</p>) : <p>等待任务开始。</p>}
              <span ref={logEndRef} />
            </div>
          </section>
          <section className="panel run-overview-panel">
            <div className="section-header compact"><span className="kicker">Overview</span><h2>{result ? result.runId : "运行概览"}</h2></div>
            {result ? (
              <div className="overview-list">
                <span><small>输出深度</small>{compactStatus(result.qualityMode)}</span>
                <span><small>知识检索</small>{compactStatus(result.ragStatus)} · 命中 {result.ragMatchCount || 0}</span>
                <span><small>经验写回</small>{compactStatus(result.memoryWritebackStatus)}</span>
                <span><small>联网搜索</small>{SEARCH_STATUS_LABELS[result.searchStatus] || compactStatus(result.searchStatus)}</span>
                <span><small>工作流</small>{result.workflowComplete ? "已完成" : "有提醒"}</span>
              </div>
            ) : <p className="muted">分析完成后会在这里展示关键运行状态。</p>}
          </section>
        </div>
      )}

      {activeTab === "audit" && (
        <div className="result-tab-panel">
          {result ? (
            <section className="panel diagnostics-panel">
              <div className="section-header compact"><span className="kicker">Audit</span><h2>可信度检查与执行轨迹</h2></div>
              <div className="diagnostic-grid">
                <article><strong>文本审阅</strong><p>{result.review?.critique || "暂无审阅摘要。"}</p></article>
                <article><strong>图表检查</strong><p>{result.review?.visionSummary || "暂无图表检查摘要。"}</p></article>
                <article>
                  <strong>阶段审计</strong>
                  <p>{result.executionAudit?.passed ? "已通过" : compactStatus(result.executionAudit?.status)}{result.executionAudit?.findings?.length ? `：${result.executionAudit.findings.join("；")}` : ""}</p>
                </article>
              </div>
              <div className="trace-table-wrap">
                <table>
                  <thead><tr><th>步骤</th><th>工具</th><th>状态</th><th>决策</th><th>摘要</th></tr></thead>
                  <tbody>
                    {(result.trace || []).map((item) => (
                      <tr key={`${item.stepIndex}-${item.toolName}`}><td>{item.stepIndex}</td><td>{item.toolName}</td><td>{item.toolStatus}</td><td>{item.decision}</td><td>{item.summary}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : <EmptyState title="暂无可信度记录" description="分析完成后会展示审阅、验证和执行轨迹。" icon={ShieldCheck} />}
        </div>
      )}

      {activeTab === "files" && (
        <div className="result-tab-panel">
          {result?.downloads?.length > 0 ? (
            <section className="panel">
              <div className="section-header compact"><span className="kicker">Deliverables</span><h2>生成文件</h2></div>
              <div className="download-list">
                {result.downloads.map((file) => (
                  <a className={`download-item ${file.url ? "" : "disabled"}`} href={toAbsoluteFileUrl(file.url)} key={`${file.path}-${file.name}`} target="_blank" rel="noreferrer">
                    <span className="download-icon"><Download size={17} /></span>
                    <span><strong>{file.name}</strong><small>分析产物</small></span>
                    <em>{formatBytes(file.size)}</em>
                  </a>
                ))}
              </div>
            </section>
          ) : <EmptyState title="暂无生成文件" description="分析产物会按类型整理在这里，并提供清晰的下载入口。" icon={Download} />}
        </div>
      )}
    </section>
  );
}

export default ResultsView;
