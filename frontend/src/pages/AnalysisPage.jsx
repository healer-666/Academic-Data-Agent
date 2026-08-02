import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  BookOpenCheck,
  Check,
  CheckCircle2,
  Database,
  FileSpreadsheet,
  FileText,
  FlaskConical,
  Info,
  Link2,
  Loader2,
  PackageCheck,
  Plus,
  RotateCcw,
  Save,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Trash2,
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

const RELATION_STATUSES = [
  { value: "inferred", label: "系统推断" },
  { value: "confirmed", label: "已确认" },
  { value: "uncertain", label: "不确定" },
  { value: "rejected", label: "已排除" },
];

const RELATION_KINDS = [
  { value: "one_to_one", label: "一对一" },
  { value: "one_to_many", label: "一对多" },
  { value: "many_to_one", label: "多对一" },
  { value: "many_to_many", label: "多对多" },
  { value: "unknown", label: "待确认" },
];

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

function SummaryMetric({ label, value, warning = false }) {
  return (
    <div className={`package-metric ${warning ? "warning" : ""}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function TableReviewCard({ table, label, primary, onLabelChange, onPrimaryChange }) {
  const warnings = table.quality?.warnings || [];
  return (
    <article className={`package-table-card ${primary ? "primary" : ""}`}>
      <header>
        <span className="package-table-icon"><FileSpreadsheet size={18} /></span>
        <div>
          <strong>{label || table.name}</strong>
          <small>{table.sourceFileName}{table.sheetName ? ` · ${table.sheetName}` : ""}</small>
        </div>
        <label className="primary-table-choice">
          <input type="radio" name="primary-table" checked={primary} onChange={onPrimaryChange} />
          主表
        </label>
      </header>
      <div className="package-table-stats">
        <span>{table.rowCount} 行</span>
        <span>{table.columnCount} 列</span>
        <span>{Math.round((table.quality?.missingRate || 0) * 100)}% 缺失</span>
        <span>{table.quality?.duplicateRows || 0} 行重复</span>
      </div>
      <label className="compact-field">
        <span>显示名称</span>
        <input value={label || ""} placeholder={table.name} onChange={(event) => onLabelChange(event.target.value)} />
      </label>
      {warnings.length > 0 && (
        <ul className="package-warning-list">
          {warnings.map((warning) => <li key={warning}><AlertTriangle size={13} />{warning}</li>)}
        </ul>
      )}
      <details className="field-overview">
        <summary>查看 {table.fields.length} 个字段</summary>
        <div className="field-overview-table" role="table" aria-label={`${table.name} 字段概览`}>
          {table.fields.map((field) => (
            <div className="field-overview-row" role="row" key={field.name}>
              <strong role="cell">{field.name}</strong>
              <span role="cell">{field.type}</span>
              <span role="cell">唯一值 {field.uniqueCount}</span>
              <span role="cell">缺失 {field.missingCount}</span>
              <small role="cell">{field.sampleValues?.join("、") || "无样例"}</small>
            </div>
          ))}
        </div>
      </details>
    </article>
  );
}

function RelationshipEditor({ relation, tables, tableName, onChange, onRemove }) {
  const leftTable = tables.find((table) => table.id === relation.leftTableId) || tables[0];
  const rightTable = tables.find((table) => table.id === relation.rightTableId) || tables[1] || tables[0];
  const changeTable = (side, tableId) => {
    const table = tables.find((item) => item.id === tableId);
    onChange({
      ...relation,
      [`${side}TableId`]: tableId,
      [`${side}Column`]: table?.fields?.[0]?.name || "",
      source: "user",
      reason: "人工修正",
    });
  };
  return (
    <article className={`relationship-card status-${relation.status}`}>
      <header>
        <span><Link2 size={16} /></span>
        <strong>{tableName(leftTable?.id)} ↔ {tableName(rightTable?.id)}</strong>
        {relation.confidence != null && <small>置信度 {Math.round(Number(relation.confidence) * 100)}%</small>}
        <button className="icon-button subtle" type="button" onClick={onRemove} title="删除关系">
          <Trash2 size={14} />
        </button>
      </header>
      <div className="relationship-grid">
        <label>
          <span>左表</span>
          <select value={relation.leftTableId} onChange={(event) => changeTable("left", event.target.value)}>
            {tables.map((table) => <option value={table.id} key={table.id}>{tableName(table.id)}</option>)}
          </select>
        </label>
        <label>
          <span>左字段</span>
          <select value={relation.leftColumn} onChange={(event) => onChange({ ...relation, leftColumn: event.target.value, source: "user" })}>
            {(leftTable?.fields || []).map((field) => <option value={field.name} key={field.name}>{field.name}</option>)}
          </select>
        </label>
        <label>
          <span>右表</span>
          <select value={relation.rightTableId} onChange={(event) => changeTable("right", event.target.value)}>
            {tables.map((table) => <option value={table.id} key={table.id}>{tableName(table.id)}</option>)}
          </select>
        </label>
        <label>
          <span>右字段</span>
          <select value={relation.rightColumn} onChange={(event) => onChange({ ...relation, rightColumn: event.target.value, source: "user" })}>
            {(rightTable?.fields || []).map((field) => <option value={field.name} key={field.name}>{field.name}</option>)}
          </select>
        </label>
        <label>
          <span>关系类型</span>
          <select value={relation.kind || "unknown"} onChange={(event) => onChange({ ...relation, kind: event.target.value, source: "user" })}>
            {RELATION_KINDS.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label>
          <span>审核状态</span>
          <select value={relation.status} onChange={(event) => onChange({ ...relation, status: event.target.value, source: "user" })}>
            {RELATION_STATUSES.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
          </select>
        </label>
      </div>
      <p>{relation.reason}</p>
    </article>
  );
}

function ModelingPackageReview({ packageData, busy, onSave, onReset }) {
  const [primaryTableId, setPrimaryTableId] = useState(packageData.primaryTableId);
  const [tableLabels, setTableLabels] = useState(packageData.review?.tableLabels || {});
  const [relationships, setRelationships] = useState(packageData.relationships || []);
  const [relationshipNotes, setRelationshipNotes] = useState(packageData.review?.relationshipNotes || "");

  useEffect(() => {
    setPrimaryTableId(packageData.primaryTableId);
    setTableLabels(packageData.review?.tableLabels || {});
    setRelationships(packageData.relationships || []);
    setRelationshipNotes(packageData.review?.relationshipNotes || "");
  }, [packageData]);

  const tables = packageData.tables || [];
  const tableName = (tableId) => {
    const table = tables.find((item) => item.id === tableId);
    return tableLabels[tableId] || table?.name || tableId;
  };
  const addRelationship = () => {
    if (tables.length < 2) return;
    const left = tables[0];
    const right = tables[1];
    setRelationships((current) => [
      ...current,
      {
        id: `manual-${Date.now()}`,
        leftTableId: left.id,
        leftColumn: left.fields?.[0]?.name || "",
        rightTableId: right.id,
        rightColumn: right.fields?.[0]?.name || "",
        kind: "unknown",
        confidence: null,
        overlapRate: null,
        status: "uncertain",
        source: "user",
        reason: "人工新增，等待确认",
      },
    ]);
  };
  const submitReview = () => onSave({
    primaryTableId,
    tableLabels,
    relationships,
    relationshipNotes,
    confirmed: true,
  });

  return (
    <section className="modeling-package-review" aria-label="赛题资料包审核">
      <header className="package-review-header">
        <div>
          <span className="kicker">Modeling package review</span>
          <h2>检查系统识别的赛题资料</h2>
          <p>确认主表、字段质量和表间关系。这里保存的修正会作为后续分析方案的正式输入。</p>
        </div>
        <span className={`package-status ${packageData.status}`}>
          {packageData.status === "confirmed" ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          {packageData.status === "confirmed" ? "已确认" : "待审核"}
        </span>
      </header>

      <div className="package-summary-grid">
        <SummaryMetric label="数据表" value={packageData.summary.tableCount} />
        <SummaryMetric label="字段" value={packageData.summary.fieldCount} />
        <SummaryMetric label="数据行" value={packageData.summary.rowCount} />
        <SummaryMetric label="质量提醒" value={packageData.summary.qualityWarningCount} warning={packageData.summary.qualityWarningCount > 0} />
        <SummaryMetric label="候选关系" value={relationships.length} />
      </div>

      <div className="package-source-line">
        <FileText size={16} />
        <span>赛题说明：<strong>{packageData.problem.name}</strong></span>
        <span>附件：<strong>{packageData.attachments.length}</strong></span>
      </div>

      <div className="package-section-heading">
        <div><FileSpreadsheet size={17} /><strong>数据表与字段质量</strong></div>
        <small>请选择后续规划时优先关注的主表</small>
      </div>
      <div className="package-table-grid">
        {tables.map((table) => (
          <TableReviewCard
            key={table.id}
            table={table}
            label={tableLabels[table.id]}
            primary={primaryTableId === table.id}
            onPrimaryChange={() => setPrimaryTableId(table.id)}
            onLabelChange={(value) => setTableLabels((current) => ({ ...current, [table.id]: value }))}
          />
        ))}
      </div>

      <div className="package-section-heading relationship-heading">
        <div><Link2 size={17} /><strong>表间关系</strong></div>
        <button className="secondary-button" type="button" onClick={addRelationship} disabled={tables.length < 2}>
          <Plus size={15} />添加关系
        </button>
      </div>
      {relationships.length ? (
        <div className="relationship-list">
          {relationships.map((relation, index) => (
            <RelationshipEditor
              key={`${relation.id}-${index}`}
              relation={relation}
              tables={tables}
              tableName={tableName}
              onChange={(next) => setRelationships((current) => current.map((item, itemIndex) => itemIndex === index ? next : item))}
              onRemove={() => setRelationships((current) => current.filter((_, itemIndex) => itemIndex !== index))}
            />
          ))}
        </div>
      ) : (
        <div className="empty-relationships"><Info size={16} />没有推断出可靠关系；如表之间实际有关联，请人工添加。</div>
      )}

      <label className="field package-notes">
        <span>关系与字段修正说明</span>
        <textarea rows={3} value={relationshipNotes} onChange={(event) => setRelationshipNotes(event.target.value)} placeholder="记录字段含义、关系依据或仍需确认的问题" />
      </label>

      <footer className="package-review-actions">
        <button className="secondary-button" type="button" onClick={onReset} disabled={busy}>
          <RotateCcw size={15} />重新上传
        </button>
        <button className="primary-button" type="button" onClick={submitReview} disabled={busy}>
          {busy ? <Loader2 className="spin" size={17} /> : <Save size={17} />}
          {busy ? "保存中" : "确认并保存资料包"}
        </button>
      </footer>
      {packageData.status === "confirmed" && (
        <div className="package-next-step">
          <CheckCircle2 size={18} />
          <div><strong>资料包已经确认</strong><span>系统已基于当前目标、表结构、历史案例和建模 skills 生成下方方案。</span></div>
        </div>
      )}
    </section>
  );
}

function PlanItemGroup({ title, items }) {
  if (!items?.length) return null;
  return (
    <section className="plan-review-section">
      <h3>{title}</h3>
      <div className="plan-item-grid">
        {items.map((item, index) => (
          <article key={`${item.name}-${index}`}>
            <header><strong>{item.name}</strong>{item.referenceOnly && <span>历史参考</span>}</header>
            <p>{item.purpose}</p>
            {item.caseIds?.length > 0 && <small>来源案例：{item.caseIds.join("、")}</small>}
          </article>
        ))}
      </div>
    </section>
  );
}

function ModelingPlanReview({ plan, busy, onSave }) {
  const [adjustments, setAdjustments] = useState(plan.userAdjustments || "");
  useEffect(() => setAdjustments(plan.userAdjustments || ""), [plan]);
  const confirmed = plan.status === "confirmed";
  return (
    <section className="modeling-plan-review" aria-label="案例启发的分析方案">
      <header className="plan-review-header">
        <div>
          <span className="kicker">Case-informed plan</span>
          <h2>检查案例启发的分析方案</h2>
          <p>{plan.summary}</p>
        </div>
        <span className={`package-status ${confirmed ? "confirmed" : "needs_review"}`}>
          {confirmed ? <CheckCircle2 size={16} /> : <Info size={16} />}
          {confirmed ? "方案已确认" : "等待确认"}
        </span>
      </header>

      <div className="plan-audit-strip">
        <span><BookOpenCheck size={15} />经验库 {plan.audit?.libraryVersion || "不可用"}</span>
        <span>候选案例 {plan.audit?.consideredCaseIds?.length || 0}</span>
        <span>采用案例 {plan.caseMatches?.length || 0}</span>
        <span>建模 skills {plan.selectedSkills?.length || 0}</span>
      </div>

      {plan.caseMatches?.length ? (
        <section className="plan-review-section">
          <h3>匹配的历史案例</h3>
          <div className="matched-case-list">
            {plan.caseMatches.map((match) => (
              <article key={match.caseId}>
                <header><strong>{match.year} 年 {match.problemNumber} 题 · {match.title}</strong><span>{Math.round(match.score * 100)}% 相关</span></header>
                <div className="match-columns">
                  <div><small>相似点</small><ul>{match.similarities.map((value) => <li key={value}>{value}</li>)}</ul></div>
                  <div><small>差异与边界</small><ul>{match.differences.map((value) => <li key={value}>{value}</li>)}</ul></div>
                </div>
                <p className="match-applicability">{match.applicability}</p>
                <div className="match-source-links">
                  {match.sources.map((source) => <a href={source.uri} target="_blank" rel="noreferrer" key={source.id}>{source.title}</a>)}
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : (
        <div className="plan-no-match"><Info size={16} /><span>没有达到相关性门槛的历史案例；系统没有强行套用案例，仅保留通用建模 skills。</span></div>
      )}

      <PlanItemGroup title="准备处理的数据与操作" items={plan.dataOperations} />
      <PlanItemGroup title="候选模型" items={plan.models} />
      <PlanItemGroup title="验证与敏感性分析" items={plan.validationMethods} />

      <section className="plan-review-section">
        <h3>选用的建模 skills</h3>
        <div className="selected-skill-list">
          {plan.selectedSkills?.map((skill) => (
            <article key={skill.id}><strong>{skill.name}</strong><span>{skill.category}</span><p>{skill.description}</p><small>{skill.reasons.join("；")}</small></article>
          ))}
        </div>
      </section>

      {plan.warnings?.length > 0 && <div className="plan-warning-list">{plan.warnings.map((value) => <p key={value}><AlertTriangle size={14} />{value}</p>)}</div>}
      <div className="plan-external-note"><Info size={15} />{plan.externalSourceNote}</div>

      <label className="field package-notes">
        <span>调整意见</span>
        <textarea rows={4} value={adjustments} onChange={(event) => setAdjustments(event.target.value)} placeholder="例如：增加一个简单基线；按文物编号分组验证；不要采用历史阈值。" disabled={confirmed} />
      </label>
      <footer className="package-review-actions">
        {!confirmed && (
          <button className="secondary-button" type="button" onClick={() => onSave({ userAdjustments: adjustments, confirmed: false })} disabled={busy}>
            <Save size={16} />保存调整
          </button>
        )}
        <button className="primary-button" type="button" onClick={() => onSave({ userAdjustments: adjustments, confirmed: true })} disabled={busy || confirmed}>
          {busy ? <Loader2 className="spin" size={17} /> : <CheckCircle2 size={17} />}
          {confirmed ? "方案已确认" : "确认分析方案"}
        </button>
      </footer>
      {confirmed && <div className="package-next-step"><CheckCircle2 size={18} /><div><strong>方案已进入审计记录</strong><span>后续分析执行会严格使用已确认方案；执行工作区由 Issue #16 接续。</span></div></div>}
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
  problemFile,
  setProblemFile,
  modelingDataFiles,
  setModelingDataFiles,
  modelingAttachments,
  setModelingAttachments,
  modelingPackage,
  modelingBusy,
  modelingError,
  onInspectModeling,
  onSaveModelingReview,
  onSaveModelingPlan,
  onResetModeling,
  isRunning,
  onSubmit,
}) {
  const scenario = getAnalysisScenario(form.scenario);
  const modeling = scenario.id === "modeling";
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const selectScenario = (scenarioId) => setForm((current) => selectAnalysisScenario(current, scenarioId));
  const modelingReady = Boolean(problemFile && modelingDataFiles.length);
  const packageInputKey = useMemo(
    () => [problemFile, ...modelingDataFiles, ...modelingAttachments].filter(Boolean).map((file) => `${file.name}:${file.size}:${file.lastModified}`).join("|"),
    [problemFile, modelingDataFiles, modelingAttachments],
  );

  useEffect(() => {
    if (modelingPackage) onResetModeling();
    // Reset only when the selected local files change, not when a server response arrives.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [packageInputKey]);

  const handleSubmit = (event) => {
    if (!modeling) {
      onSubmit(event);
      return;
    }
    event.preventDefault();
    onInspectModeling();
  };

  return (
    <section className="chat-page analysis-grid analysis-task-creation">
      <div className="task-creation-grid">
        <div className="task-primary-column">
          <div className="chat-body">
            <div className="chat-welcome task-welcome">
              <span className="kicker">New research task</span>
              <h1>从一个清楚的问题开始</h1>
              <p>选择工作方式，说明你想解决的问题并添加资料。系统会先检查输入，再安排分析与验证。</p>
            </div>
            <ScenarioSelector selectedId={scenario.id} onSelect={selectScenario} />
            <StrategySummary scenario={scenario} />
          </div>

          <form className="analysis-form chat-input-panel task-input-panel" onSubmit={handleSubmit}>
            <div className="task-context-row">
              <span className={`task-context-badge ${scenario.id}`}>
                {modeling ? <FlaskConical size={15} /> : <BarChart3 size={15} />}
                {scenario.label}
              </span>
              <span>{scenario.inputHint}</span>
            </div>
            <div className="chat-input-panel-inner">
              <label className="field field-wide task-query-field">
                <span>{modeling ? "赛题目标与补充要求" : "分析问题"}</span>
                <textarea rows={5} value={form.query} onChange={(event) => update("query", event.target.value)} placeholder={scenario.queryPlaceholder} />
              </label>
            </div>
            {scenario.boundary && <div className="scenario-boundary"><Info size={15} /><span>{scenario.boundary}</span></div>}

            <div className="chat-input-actions task-input-actions">
              {modeling ? (
                <>
                  <FileInput
                    label="赛题说明"
                    description="一份 TXT / MD / 可提取文本的 PDF"
                    accept=".txt,.md,.pdf"
                    files={problemFile ? [problemFile] : []}
                    onChange={(files) => setProblemFile(files[0] || null)}
                    onClear={() => setProblemFile(null)}
                  />
                  <FileInput
                    label="赛题数据"
                    description="可一次选择多份 CSV / XLS / XLSX"
                    accept=".csv,.xls,.xlsx"
                    multiple
                    files={modelingDataFiles}
                    onChange={setModelingDataFiles}
                    onClear={() => setModelingDataFiles([])}
                  />
                  <FileInput
                    label="必要附件"
                    description="可选：说明、图片、补充表格等"
                    accept=".txt,.md,.pdf,.doc,.docx,.png,.jpg,.jpeg,.csv,.xls,.xlsx"
                    multiple
                    files={modelingAttachments}
                    onChange={setModelingAttachments}
                    onClear={() => setModelingAttachments([])}
                  />
                </>
              ) : (
                <>
                  <FileInput label="主要数据" description="CSV / XLS / XLSX" accept=".csv,.xls,.xlsx" files={dataFile ? [dataFile] : []} onChange={(files) => setDataFile(files[0] || null)} onClear={() => setDataFile(null)} />
                  <FileInput label="参考资料" description="TXT / MD / PDF" accept=".txt,.md,.pdf" multiple files={knowledgeFiles} onChange={setKnowledgeFiles} onClear={() => setKnowledgeFiles([])} />
                </>
              )}

              {modelingError && <div className="modeling-package-error"><AlertTriangle size={16} />{modelingError}</div>}
              <div className="task-trust-note"><ShieldCheck size={15} /><span>{modeling ? "文件会先形成可审核资料包，不会在你确认关系前开始分析" : "运行参数由场景自动配置，过程与结果均保留审计记录"}</span></div>
              <button className="primary-button chat-input-send" type="submit" disabled={modeling ? (modelingBusy || !modelingReady) : (isRunning || !dataFile)}>
                {(modelingBusy || isRunning) ? <Loader2 className="spin" size={18} /> : (modeling ? <ScanSearch size={18} /> : <FileText size={18} />)}
                <span>{modeling ? (modelingBusy ? "正在识别资料" : "识别并检查资料包") : (isRunning ? "任务运行中" : `开始${scenario.shortLabel}`)}</span>
              </button>
            </div>
          </form>
        </div>
        <aside className="task-guidance-panel" aria-label="任务流程说明">
          <span className="kicker">How it works</span>
          <h2>{modeling ? "先理解资料，再开始建模" : "一次可追溯的分析流程"}</h2>
          <ol className="task-workflow">
            <li className="active"><span>1</span><div><strong>描述问题</strong><p>说明目标、限制和你关心的判断。</p></div></li>
            <li className={modelingPackage ? "active" : ""}><span>2</span><div><strong>{modeling ? "审核资料" : "检查数据"}</strong><p>{modeling ? "确认表结构、字段质量与表间关系。" : "识别字段、质量风险和分析边界。"}</p></div></li>
            <li className={modelingPackage?.analysisPlan ? "active" : ""}><span>3</span><div><strong>{modeling ? "确认方案" : "执行与验证"}</strong><p>{modeling ? "查看案例依据、候选模型与验证方法。" : "运行分析并留下可复现记录。"}</p></div></li>
            <li><span>4</span><div><strong>阅读交付</strong><p>在结果中心查看报告、可信度和文件。</p></div></li>
          </ol>
          <div className="task-guidance-note"><ShieldCheck size={17} /><span>原始资料留在本地工作区；关键操作会进入审计记录。</span></div>
        </aside>
      </div>

      {modeling && modelingPackage && (
        <ModelingPackageReview packageData={modelingPackage} busy={modelingBusy} onSave={onSaveModelingReview} onReset={onResetModeling} />
      )}
      {modeling && modelingPackage?.analysisPlan && (
        <ModelingPlanReview plan={modelingPackage.analysisPlan} busy={modelingBusy} onSave={onSaveModelingPlan} />
      )}
    </section>
  );
}

export default AnalysisView;
