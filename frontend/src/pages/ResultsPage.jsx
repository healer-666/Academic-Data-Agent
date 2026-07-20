import { useEffect, useMemo, useRef } from "react";
import { Activity, Clock3, Download, ExternalLink, Globe2, Search, ShieldCheck, WifiOff } from "lucide-react";
import { toAbsoluteFileUrl } from "../api";
import InteractiveReportView from "../components/InteractiveReportView";
import MarkdownView from "../components/MarkdownView";
import { StatCard } from "../components/WorkspacePrimitives";
import { compactStatus, formatBytes, formatDuration } from "../utils/formatters";

const SEARCH_STATUS_LABELS = {
  used: "已使用联网资料",
  attempted: "已尝试搜索",
  unavailable: "搜索不可用",
  not_used: "本次无需搜索",
};

function SearchStatusPanel({ result }) {
  const sources = result.searchSources || [];
  const unavailable = result.searchStatus === "unavailable";
  const Icon = unavailable ? WifiOff : Globe2;
  return (
    <section className={`panel search-status-panel search-${result.searchStatus || "not_used"}`}>
      <header>
        <span className="search-status-icon"><Icon size={19} /></span>
        <div>
          <small>联网搜索</small>
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
  const logEndRef = useRef(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [logs]);

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
    <section className="view-stack">
      <div className="stat-grid">
        {stats.map(([label, value, Icon]) => (
          <StatCard key={label} label={label} value={value} icon={Icon} />
        ))}
      </div>

      <div className="results-layout">
        <div className="panel">
          <div className="section-header compact">
            <span className="kicker">Progress</span>
            <h2>运行日志</h2>
          </div>
          <div className="log-box">
            {logs.length ? logs.map((line, index) => <p key={`${index}-${line}`}>{line}</p>) : <p>等待任务开始。</p>}
            <span ref={logEndRef} />
          </div>
        </div>

        <div className="panel">
          <div className="section-header compact">
            <span className="kicker">Overview</span>
            <h2>{result ? result.runId : "暂无结果"}</h2>
          </div>
          {result ? (
            <div className="overview-list">
              <span>输出深度：{compactStatus(result.qualityMode)}</span>
              <span>RAG：{compactStatus(result.ragStatus)}，命中 {result.ragMatchCount || 0}</span>
              <span>历史经验写回：{compactStatus(result.memoryWritebackStatus)}</span>
              <span>联网搜索：{SEARCH_STATUS_LABELS[result.searchStatus] || compactStatus(result.searchStatus)}</span>
              <span>工作流：{result.workflowComplete ? "已完成" : "有提醒"}</span>
            </div>
          ) : (
            <p className="muted">分析完成后会在这里展示关键质量状态。</p>
          )}
        </div>
      </div>

      {result && <SearchStatusPanel result={result} />}

      {result && (
        <InteractiveReportView
          runId={result.runId}
          outputDir={outputDir}
          reportMarkdown={result.reportMarkdown}
          figures={result.figures || []}
          available={result.interactiveReportAvailable}
        />
      )}


      {result && (
        <div className="panel diagnostics-panel">
          <div className="section-header compact">
            <span className="kicker">Audit</span>
            <h2>可信度检查与执行轨迹</h2>
          </div>
          <div className="diagnostic-grid">
            <article>
              <strong>文本审阅</strong>
              <p>{result.review?.critique || "暂无审阅摘要。"}</p>
            </article>
            <article>
              <strong>图表检查</strong>
              <p>{result.review?.visionSummary || "暂无图表检查摘要。"}</p>
            </article>
            <article>
              <strong>阶段审计</strong>
              <p>
                {result.executionAudit?.passed ? "已通过" : compactStatus(result.executionAudit?.status)}
                {result.executionAudit?.findings?.length ? `：${result.executionAudit.findings.join("；")}` : ""}
              </p>
            </article>
          </div>
          <div className="trace-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>步骤</th>
                  <th>工具</th>
                  <th>状态</th>
                  <th>决策</th>
                  <th>摘要</th>
                </tr>
              </thead>
              <tbody>
                {(result.trace || []).map((item) => (
                  <tr key={`${item.stepIndex}-${item.toolName}`}>
                    <td>{item.stepIndex}</td>
                    <td>{item.toolName}</td>
                    <td>{item.toolStatus}</td>
                    <td>{item.decision}</td>
                    <td>{item.summary}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {result?.downloads?.length > 0 && (
        <div className="panel">
          <div className="section-header compact">
            <span className="kicker">Files</span>
            <h2>运行工件</h2>
          </div>
          <div className="download-list">
            {result.downloads.map((file) => (
              <a
                className={`download-item ${file.url ? "" : "disabled"}`}
                href={toAbsoluteFileUrl(file.url)}
                key={`${file.path}-${file.name}`}
                target="_blank"
                rel="noreferrer"
              >
                <Download size={16} />
                <span>{file.name}</span>
                <em>{formatBytes(file.size)}</em>
              </a>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

export default ResultsView;
