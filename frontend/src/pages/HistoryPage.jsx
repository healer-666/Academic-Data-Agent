import { History, Loader2, MessageSquareText } from "lucide-react";
import InteractiveReportView from "../components/InteractiveReportView";
import MarkdownView from "../components/MarkdownView";
import { ViewLoading } from "../components/WorkspacePrimitives";
import { compactStatus } from "../utils/formatters";

function HistoryView({
  workspace,
  selectedRunId,
  setSelectedRunId,
  historyDetail,
  outputDir,
  qaQuestion,
  setQaQuestion,
  qaMode,
  setQaMode,
  qaSelected,
  setQaSelected,
  qaResult,
  qaLoading,
  historyLoading,
  onAskQuestion,
}) {
  const runs = workspace?.historyRuns || [];
  return (
    <section className="history-layout">
      <aside className="panel history-list-panel">
        <div className="section-header compact">
          <span className="kicker">History</span>
          <h2>历史运行</h2>
        </div>
        <div className="run-list">
          {runs.length ? (
            runs.map((run) => (
              <button
                type="button"
                className={run.runId === selectedRunId ? "run-card active" : "run-card"}
                key={run.runId}
                onClick={() => {
                  setSelectedRunId(run.runId);
                }}
              >
                <strong>{run.runId}</strong>
                <span>{run.domain} · {compactStatus(run.reviewStatus)}</span>
                <em>{run.timestamp}</em>
              </button>
            ))
          ) : (
            <p className="muted">还没有可浏览的历史记录。</p>
          )}
        </div>
      </aside>

      <div className="view-stack history-content-stack">
        <div className="panel follow-up-panel">
          <div className="section-header compact">
            <span className="kicker">Follow-up</span>
            <h2>历史追问</h2>
          </div>
          <div className="qa-grid">
            <label className="field select-field">
              <span>追问方式</span>
              <select value={qaMode} onChange={(event) => setQaMode(event.target.value)}>
                <option value="single">单次追问</option>
                <option value="compare">跨运行对比</option>
              </select>
            </label>
            <div className="qa-run-picker">
              {(workspace?.historyQaRuns || []).slice(0, 8).map((run) => (
                <label className={qaSelected.includes(run.runId) ? "qa-chip selected" : "qa-chip"} key={run.runId}>
                  <input
                    type="checkbox"
                    checked={qaSelected.includes(run.runId)}
                    onChange={(event) => {
                      setQaSelected((current) =>
                        event.target.checked
                          ? [...new Set([...current, run.runId])]
                          : current.filter((item) => item !== run.runId),
                      );
                    }}
                  />
                  {run.runId}
                </label>
              ))}
            </div>
            <label className="field field-wide">
              <span>问题</span>
              <textarea
                rows={3}
                value={qaQuestion}
                onChange={(event) => setQaQuestion(event.target.value)}
                placeholder="例如：哪次报告没有通过审阅？上次用了什么统计方法？"
              />
            </label>
            <button className="primary-button" type="button" onClick={onAskQuestion} disabled={qaLoading || !qaQuestion.trim()}>
              {qaLoading ? <Loader2 className="spin" size={18} /> : <MessageSquareText size={18} />}
              开始追问
            </button>
          </div>
          {qaResult && (
            <div className="qa-result">
              <MarkdownView content={qaResult.answerMarkdown} />
              <div className="source-list">
                <strong>来源</strong>
                {(qaResult.sources || []).map((source) => <span key={source}>{source}</span>)}
                {(qaResult.warnings || []).map((warning) => <em key={warning}>{warning}</em>)}
              </div>
            </div>
          )}
        </div>

        {historyLoading ? (
          <div className="panel report-panel">
            <ViewLoading message="正在加载历史报告" />
          </div>
        ) : historyDetail ? (
          <InteractiveReportView
            runId={historyDetail.runId}
            outputDir={outputDir}
            reportMarkdown={historyDetail.reportMarkdown}
            figures={historyDetail.figures || []}
            available={historyDetail.interactiveReportAvailable}
          />
        ) : (
          <div className="panel report-panel">
            <p className="muted">请选择左侧记录。</p>
          </div>
        )}


      </div>
    </section>
  );
}

export default HistoryView;
