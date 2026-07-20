import {
  ArrowRight,
  BarChart3,
  Check,
  Database,
  FileText,
  FlaskConical,
  Info,
  Loader2,
  PackageCheck,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { FileInput } from "../components/WorkspacePrimitives";
import {
  ANALYSIS_SCENARIOS,
  getAnalysisScenario,
  selectAnalysisScenario,
} from "../app/defaults";

const SCENARIO_ICONS = {
  general: Database,
  modeling: FlaskConical,
};

function ScenarioSelector({ selectedId, onSelect }) {
  return (
    <div className="scenario-selector" aria-label="选择任务场景">
      {Object.values(ANALYSIS_SCENARIOS).map((item) => {
        const Icon = SCENARIO_ICONS[item.id];
        const selected = selectedId === item.id;
        return (
          <button
            className={`scenario-card ${selected ? "selected" : ""}`}
            type="button"
            key={item.id}
            aria-pressed={selected}
            onClick={() => onSelect(item.id)}
          >
            <span className="scenario-card-icon"><Icon size={22} /></span>
            <span className="scenario-card-copy">
              <strong>{item.label}</strong>
              <small>{item.description}</small>
            </span>
            <span className="scenario-card-state" aria-hidden="true">
              {selected ? <Check size={16} /> : <ArrowRight size={16} />}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function StrategySummary({ scenario }) {
  return (
    <section className={`strategy-summary strategy-${scenario.id}`} aria-label="系统采用的分析策略">
      <header>
        <span><Sparkles size={16} /></span>
        <div>
          <small>系统将自动采用</small>
          <strong>{scenario.strategyTitle}</strong>
        </div>
      </header>
      <ul>
        {scenario.strategySummary.map((item) => (
          <li key={item}><Check size={14} /> {item}</li>
        ))}
      </ul>
      <footer>
        <PackageCheck size={15} />
        <span>目标产物：{scenario.deliverable}</span>
      </footer>
    </section>
  );
}

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
  const scenario = getAnalysisScenario(form.scenario);
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const selectScenario = (scenarioId) => {
    setForm((current) => selectAnalysisScenario(current, scenarioId));
  };

  return (
    <section className="chat-page analysis-grid analysis-task-creation">
      <div className="chat-body">
        <div className="chat-welcome task-welcome">
          <span className="kicker">New Research Task</span>
          <h1>选择你要完成的任务</h1>
          <p>只需选择场景、说明问题并上传资料。系统会自动安排合适的分析深度、验证和结果检查。</p>
        </div>

        <ScenarioSelector selectedId={scenario.id} onSelect={selectScenario} />
        <StrategySummary scenario={scenario} />
      </div>

      <form className="analysis-form chat-input-panel task-input-panel" onSubmit={onSubmit}>
        <div className="task-context-row">
          <span className={`task-context-badge ${scenario.id}`}>
            {scenario.id === "general" ? <BarChart3 size={15} /> : <FlaskConical size={15} />}
            {scenario.label}
          </span>
          <span>{scenario.inputHint}</span>
        </div>

        <div className="chat-input-panel-inner">
          <label className="field field-wide task-query-field">
            <span>{scenario.id === "general" ? "分析问题" : "赛题目标与补充要求"}</span>
            <textarea
              rows={5}
              value={form.query}
              onChange={(event) => update("query", event.target.value)}
              placeholder={scenario.queryPlaceholder}
            />
          </label>
        </div>

        {scenario.boundary && (
          <div className="scenario-boundary"><Info size={15} /><span>{scenario.boundary}</span></div>
        )}

        <div className="chat-input-actions task-input-actions">
          <FileInput
            label={scenario.id === "general" ? "主要数据" : "赛题数据"}
            description="CSV / XLS / XLSX"
            accept=".csv,.xls,.xlsx"
            files={dataFile ? [dataFile] : []}
            onChange={(files) => setDataFile(files[0] || null)}
            onClear={() => setDataFile(null)}
          />
          <FileInput
            label={scenario.id === "general" ? "参考资料" : "赛题说明与附件"}
            description="TXT / MD / PDF"
            accept=".txt,.md,.pdf"
            multiple
            files={knowledgeFiles}
            onChange={setKnowledgeFiles}
            onClear={() => setKnowledgeFiles([])}
          />

          <div className="task-trust-note">
            <ShieldCheck size={15} />
            <span>运行参数由场景自动配置，过程与结果均保留审计记录</span>
          </div>

          <button className="primary-button chat-input-send" type="submit" disabled={isRunning || !dataFile}>
            {isRunning ? <Loader2 className="spin" size={18} /> : <FileText size={18} />}
            <span>{isRunning ? "任务运行中" : `开始${scenario.shortLabel}`}</span>
          </button>
        </div>
      </form>
    </section>
  );
}

export default AnalysisView;
