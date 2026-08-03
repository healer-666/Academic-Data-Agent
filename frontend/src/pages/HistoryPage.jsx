import { ArrowUp, History, Loader2, SlidersHorizontal } from "lucide-react";
import InteractiveReportView from "../components/InteractiveReportView";
import MarkdownView from "../components/MarkdownView";
import { EmptyState, ViewLoading } from "../components/WorkspacePrimitives";
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
  const handleKeyDown = (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && qaQuestion.trim() && !qaLoading) {
      event.preventDefault();
      onAskQuestion();
    }
  };

  return (
    <section className="history-layout">
      <aside className="history-list" aria-label="历史任务">
        <h2>历史任务</h2>
        <div className="run-list">
          {runs.length ? runs.map((run) => {
            const domain = run.domain && run.domain !== "unknown" ? run.domain : "领域待识别";
            const timestamp = run.timestamp && run.timestamp !== run.runId ? run.timestamp : "";
            return (
              <button type="button" className={run.runId === selectedRunId ? "active" : ""} key={run.runId} onClick={() => setSelectedRunId(run.runId)}>
                <strong>{run.runId}</strong>
                <span>{domain}</span>
                <small>{[timestamp, compactStatus(run.reviewStatus)].filter(Boolean).join(" · ")}</small>
              </button>
            );
          }) : <p>还没有历史任务。</p>}
        </div>
      </aside>

      <div className="conversation-workspace">
        <div className="conversation-thread">
          {historyLoading ? (
            <ViewLoading message="正在加载历史报告" />
          ) : historyDetail ? (
            <section className="assistant-message">
              <span className="assistant-mark" aria-hidden="true">A</span>
              <div>
                <div className="message-meta">{historyDetail.runId}</div>
                <InteractiveReportView
                  runId={historyDetail.runId}
                  outputDir={outputDir}
                  reportMarkdown={historyDetail.reportMarkdown}
                  figures={historyDetail.figures || []}
                  available={historyDetail.interactiveReportAvailable}
                />
              </div>
            </section>
          ) : (
            <EmptyState title="选择一个历史任务" description="打开报告后，可以围绕已有结果继续追问。" icon={History} />
          )}

          {qaResult && (
            <>
              <div className="user-message"><p>{qaQuestion}</p></div>
              <section className="assistant-message follow-up-answer">
                <span className="assistant-mark" aria-hidden="true">A</span>
                <div>
                  <MarkdownView content={qaResult.answerMarkdown} />
                  {(qaResult.sources?.length > 0 || qaResult.warnings?.length > 0) && (
                    <details className="answer-sources">
                      <summary>来源与提示</summary>
                      {qaResult.sources?.map((source) => <p key={source}>{source}</p>)}
                      {qaResult.warnings?.map((warning) => <p className="warning" key={warning}>{warning}</p>)}
                    </details>
                  )}
                </div>
              </section>
            </>
          )}
        </div>

        <div className="history-composer-wrap">
          <div className="history-composer">
            <textarea rows={2} value={qaQuestion} onChange={(event) => setQaQuestion(event.target.value)} onKeyDown={handleKeyDown} placeholder="继续追问这份分析…" />
            <div className="history-composer-footer">
              <details className="history-options">
                <summary title="追问范围"><SlidersHorizontal size={17} />追问范围</summary>
                <div>
                  <label>方式<select value={qaMode} onChange={(event) => setQaMode(event.target.value)}><option value="single">单次追问</option><option value="compare">跨运行对比</option></select></label>
                  <fieldset>
                    <legend>参考任务</legend>
                    {(workspace?.historyQaRuns || []).slice(0, 8).map((run) => (
                      <label key={run.runId}><input type="checkbox" checked={qaSelected.includes(run.runId)} onChange={(event) => setQaSelected((current) => event.target.checked ? [...new Set([...current, run.runId])] : current.filter((item) => item !== run.runId))} />{run.runId}</label>
                    ))}
                  </fieldset>
                </div>
              </details>
              <button type="button" className="composer-submit" onClick={onAskQuestion} disabled={qaLoading || !qaQuestion.trim()} aria-label="发送追问">
                {qaLoading ? <Loader2 className="spin" size={18} /> : <ArrowUp size={18} />}
              </button>
            </div>
          </div>
          <small>Ctrl + Enter 发送</small>
        </div>
      </div>
    </section>
  );
}

export default HistoryView;
