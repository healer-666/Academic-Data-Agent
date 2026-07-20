import { BookOpen, Database, Loader2, Play, Settings2, ShieldCheck } from "lucide-react";
import { FileInput } from "../components/WorkspacePrimitives";

function AnalysisView({
  form,
  setForm,
  dataFile,
  setDataFile,
  knowledgeFiles,
  setKnowledgeFiles,
  isRunning,
  onSubmit,
}) {
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  return (
    <section className="chat-page analysis-grid">
      <div className="chat-body">
        <div className="chat-welcome">
          <span className="kicker">New Analysis</span>
          <h1>今天要分析什么数据？</h1>
          <p>上传 CSV/Excel，输入任务要求，系统会生成可审计报告、图表、日志和可下载工件。</p>
        </div>

        <div className="guide-list nextchat-guide">
          <article>
            <Database size={18} />
            <div>
              <strong>数据主线</strong>
              <p>围绕结构化表格完成清洗、统计、建模解释和结论输出。</p>
            </div>
          </article>
          <article>
            <BookOpen size={18} />
            <div>
              <strong>参考资料</strong>
              <p>可上传文档沉淀到本地知识库，后续任务可继续检索使用。</p>
            </div>
          </article>
          <article>
            <ShieldCheck size={18} />
            <div>
              <strong>审计轨迹</strong>
              <p>保留日志、过程、图表检查与下载入口，便于复查。</p>
            </div>
          </article>
        </div>
      </div>

      <form className="analysis-form chat-input-panel" onSubmit={onSubmit}>
        <div className="chat-input-panel-inner">
          <label className="field field-wide">
            <span>分析问题</span>
            <textarea
              rows={6}
              value={form.query}
              onChange={(event) => update("query", event.target.value)}
              placeholder="例如：哪些变量最重要？是否存在显著差异？需要哪些图表支撑结论？"
            />
          </label>
        </div>

        <div className="chat-input-actions">
          <FileInput
            label="数据"
            description="CSV / XLS / XLSX"
            accept=".csv,.xls,.xlsx"
            files={dataFile ? [dataFile] : []}
            onChange={(files) => setDataFile(files[0] || null)}
            onClear={() => setDataFile(null)}
          />
          <FileInput
            label="资料"
            description="TXT / MD / PDF"
            accept=".txt,.md,.pdf"
            multiple
            files={knowledgeFiles}
            onChange={setKnowledgeFiles}
            onClear={() => setKnowledgeFiles([])}
          />

          <details className="advanced-settings">
            <summary>
              <Settings2 size={16} />
              <span>高级设置</span>
            </summary>
            <div className="form-grid">
              <label className="field">
                <span>输出深度</span>
                <select value={form.qualityMode} onChange={(event) => update("qualityMode", event.target.value)}>
                  <option value="draft">快速草稿</option>
                  <option value="standard">标准分析</option>
                  <option value="publication">深入分析</option>
                </select>
              </label>
              <label className="field">
                <span>速度偏好</span>
                <select value={form.latencyMode} onChange={(event) => update("latencyMode", event.target.value)}>
                  <option value="auto">自动平衡</option>
                  <option value="quality">质量优先</option>
                  <option value="fast">速度优先</option>
                </select>
              </label>
              <label className="field">
                <span>图表检查</span>
                <select
                  value={form.visionReviewMode}
                  onChange={(event) => update("visionReviewMode", event.target.value)}
                >
                  <option value="off">关闭</option>
                  <option value="auto">自动</option>
                  <option value="on">始终检查</option>
                </select>
              </label>
              <label className="field">
                <span>最大步骤</span>
                <input
                  type="number"
                  min="2"
                  max="12"
                  value={form.maxSteps}
                  onChange={(event) => update("maxSteps", event.target.value)}
                />
              </label>
              <label className="field">
                <span>最大返修</span>
                <input
                  type="number"
                  min="0"
                  max="4"
                  value={form.maxReviews}
                  onChange={(event) => update("maxReviews", event.target.value)}
                />
              </label>
              <label className="field">
                <span>结果目录</span>
                <input value={form.outputDir} onChange={(event) => update("outputDir", event.target.value)} />
              </label>
              <label className="field">
                <span>分析角色</span>
                <input value={form.agentName} onChange={(event) => update("agentName", event.target.value)} />
              </label>
              <label className="field">
                <span>任务标签</span>
                <input value={form.sessionLabel} onChange={(event) => update("sessionLabel", event.target.value)} />
              </label>
              <label className="toggle-chip">
                <input
                  type="checkbox"
                  checked={form.useRag}
                  onChange={(event) => update("useRag", event.target.checked)}
                />
                使用参考资料
              </label>
              <label className="toggle-chip">
                <input
                  type="checkbox"
                  checked={form.useMemory}
                  onChange={(event) => update("useMemory", event.target.checked)}
                />
                参考历史经验
              </label>
            </div>
          </details>

          <button className="primary-button chat-input-send" type="submit" disabled={isRunning || !dataFile}>
            {isRunning ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
            <span>{isRunning ? "分析中" : "开始"}</span>
          </button>
        </div>
      </form>
    </section>
  );
}

export default AnalysisView;
