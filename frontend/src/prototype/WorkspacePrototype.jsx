import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BookOpenCheck,
  Box,
  Check,
  ChevronRight,
  CircleDot,
  Clock3,
  Code2,
  Database,
  Download,
  FileArchive,
  FileChartColumn,
  FileSpreadsheet,
  FlaskConical,
  FolderInput,
  GitBranch,
  Info,
  LayoutDashboard,
  ListChecks,
  Menu,
  Network,
  NotebookPen,
  PackageCheck,
  Pause,
  Play,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  TableProperties,
  Upload,
  X,
} from "lucide-react";

const VARIANTS = [
  { id: "A", name: "研究流水线" },
  { id: "B", name: "证据台账" },
];

const STAGES = [
  { id: "intake", label: "资料", short: "01", icon: FolderInput },
  { id: "plan", label: "方案", short: "02", icon: ListChecks },
  { id: "run", label: "运行", short: "03", icon: Play },
  { id: "results", label: "结果", short: "04", icon: BarChart3 },
];

const SCENARIOS = {
  general: {
    label: "通用数据分析",
    project: "城市门诊服务质量分析",
    brief: "比较三个院区的候诊时间、满意度与复诊率，识别可解释的服务差异。",
    files: [
      ["clinic_visits.csv", "18.4 MB", "42,810 行"],
      ["survey_scores.xlsx", "2.1 MB", "3 张表"],
    ],
    questions: ["各院区候诊时间是否显著不同？", "满意度变化由哪些因素驱动？", "结论对异常值处理是否稳健？"],
    methods: ["缺失值与异常值审计", "Kruskal-Wallis + 事后检验", "稳健回归与敏感性分析"],
    artifact: "可复现分析报告",
  },
  modeling: {
    label: "数学建模项目",
    project: "2026 校园共享单车调度题",
    brief: "基于多站点借还记录与天气数据，设计高峰期车辆调度方案并验证稳定性。",
    files: [
      ["赛题说明.pdf", "1.8 MB", "12 页"],
      ["station_flows.xlsx", "26.3 MB", "6 张表"],
      ["weather.csv", "640 KB", "8,760 行"],
    ],
    questions: ["站点需求如何分群与预测？", "调度目标和约束如何形式化？", "方案对需求波动是否稳健？"],
    methods: ["表关系识别与质量审计", "时序聚类 + 需求预测", "约束优化 + 敏感性分析"],
    artifact: "竞赛分析材料包",
  },
};

const RUN_STEPS = [
  ["资料解析与字段对齐", "done", "00:18"],
  ["质量审计与描述统计", "done", "00:42"],
  ["模型拟合与诊断", "active", "01:36"],
  ["敏感性分析", "queued", "预计 00:55"],
  ["报告与血缘打包", "queued", "预计 00:24"],
];

function usePrototypeState() {
  const [scenario, setScenario] = useState("general");
  const [stage, setStage] = useState("intake");
  const [extraFile, setExtraFile] = useState(false);
  const [planConfirmed, setPlanConfirmed] = useState(false);
  const [runState, setRunState] = useState("ready");
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const data = SCENARIOS[scenario];
  const files = extraFile ? [...data.files, ["补充约束说明.md", "6 KB", "已识别"]] : data.files;

  const changeScenario = (next) => {
    setScenario(next);
    setStage("intake");
    setExtraFile(false);
    setPlanConfirmed(false);
    setRunState("ready");
    setInspectorOpen(false);
  };

  const advance = () => {
    const index = STAGES.findIndex((item) => item.id === stage);
    if (index < STAGES.length - 1) setStage(STAGES[index + 1].id);
  };

  const toggleRun = () => {
    if (runState === "ready") {
      setRunState("running");
      setStage("run");
    } else if (runState === "running") {
      setRunState("complete");
      setStage("results");
    } else {
      setRunState("ready");
      setStage("plan");
    }
  };

  return {
    scenario,
    stage,
    data,
    files,
    extraFile,
    planConfirmed,
    runState,
    inspectorOpen,
    mobileMenuOpen,
    setStage,
    setExtraFile,
    setPlanConfirmed,
    setInspectorOpen,
    setMobileMenuOpen,
    changeScenario,
    advance,
    toggleRun,
  };
}

function ScenarioControl({ scenario, onChange, compact = false }) {
  return (
    <div className={`proto-segmented ${compact ? "compact" : ""}`} aria-label="项目类型">
      {Object.entries(SCENARIOS).map(([id, item]) => (
        <button
          key={id}
          type="button"
          className={scenario === id ? "active" : ""}
          aria-pressed={scenario === id}
          onClick={() => onChange(id)}
        >
          {id === "general" ? <Database size={15} /> : <FlaskConical size={15} />}
          <span>{item.label}</span>
        </button>
      ))}
    </div>
  );
}

function PrototypeSwitcher({ current, onChange }) {
  useEffect(() => {
    const handleKeydown = (event) => {
      const target = event.target;
      if (target instanceof HTMLElement && (target.matches("input, textarea, [contenteditable='true']") || target.closest("[contenteditable='true']"))) {
        return;
      }
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const currentIndex = VARIANTS.findIndex((item) => item.id === current);
      const offset = event.key === "ArrowRight" ? 1 : -1;
      const next = VARIANTS[(currentIndex + offset + VARIANTS.length) % VARIANTS.length];
      onChange(next.id);
    };
    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [current, onChange]);

  if (!import.meta.env.DEV) return null;
  const index = VARIANTS.findIndex((item) => item.id === current);
  const previous = VARIANTS[(index - 1 + VARIANTS.length) % VARIANTS.length];
  const next = VARIANTS[(index + 1) % VARIANTS.length];

  return (
    <div className="prototype-switcher" aria-label="原型方案切换器">
      <button type="button" title={`切换到方案 ${previous.id}`} onClick={() => onChange(previous.id)}>
        <ArrowLeft size={16} />
      </button>
      <div>
        <span>PROTOTYPE</span>
        <strong>{current} · {VARIANTS[index].name}</strong>
      </div>
      <button type="button" title={`切换到方案 ${next.id}`} onClick={() => onChange(next.id)}>
        <ArrowRight size={16} />
      </button>
    </div>
  );
}

function StateSummary({ state }) {
  return (
    <div className="proto-state-summary" aria-label="当前原型状态">
      <span><CircleDot size={12} /> {state.data.label}</span>
      <span>{STAGES.find((item) => item.id === state.stage)?.label}</span>
      <span>{state.files.length} 份资料</span>
      <span>{state.planConfirmed ? "方案已确认" : "方案待确认"}</span>
      <span>运行：{state.runState === "ready" ? "待启动" : state.runState === "running" ? "执行中" : "已完成"}</span>
    </div>
  );
}

function FileRows({ state, dense = false }) {
  return (
    <div className={`proto-file-list ${dense ? "dense" : ""}`}>
      {state.files.map(([name, size, meta], index) => (
        <div className="proto-file-row" key={name}>
          <span className="proto-file-icon">{name.endsWith(".pdf") ? <FileChartColumn size={17} /> : <FileSpreadsheet size={17} />}</span>
          <span><strong>{name}</strong><small>{size} · {meta}</small></span>
          <span className="proto-file-status"><Check size={13} /> 已解析</span>
          {index === 0 && <button type="button" className="proto-icon-button" title="移除文件"><X size={15} /></button>}
        </div>
      ))}
    </div>
  );
}

function EvidenceInspector({ state, inline = false }) {
  const content = (
    <>
      <header>
        <div><span className="proto-eyebrow">EVIDENCE INSPECTOR</span><h2>结论证据</h2></div>
        {!inline && <button type="button" className="proto-icon-button" title="关闭检查器" onClick={() => state.setInspectorOpen(false)}><X size={17} /></button>}
      </header>
      <div className="proto-inspector-tabs">
        <button type="button" className="active">数据</button><button type="button">代码</button><button type="button">血缘</button>
      </div>
      <div className="proto-inspector-body">
        <div className="proto-evidence-status"><ShieldCheck size={18} /><span><strong>证据完整</strong><small>3 个来源 · 2 个处理步骤</small></span></div>
        <dl>
          <div><dt>结论</dt><dd>{state.scenario === "general" ? "院区 B 的中位候诊时间显著较低" : "分区滚动调度可降低高峰缺车率"}</dd></div>
          <div><dt>来源字段</dt><dd><code>site_id</code> <code>wait_minutes</code> <code>time_slot</code></dd></div>
          <div><dt>计算步骤</dt><dd>清洗 v3 → 稳健检验 → 敏感性复核</dd></div>
        </dl>
        <pre><code>{state.scenario === "general" ? "kruskal(wait_minutes ~ site_id)\np_adj = 0.008\neffect_size = 0.31" : "service_rate = 0.924\nshortage_rate = 0.061\nrobustness = 0.88"}</code></pre>
      </div>
    </>
  );

  if (inline) return <aside className="proto-inline-inspector">{content}</aside>;
  return state.inspectorOpen ? <div className="proto-inspector-backdrop" onClick={() => state.setInspectorOpen(false)}><aside className="proto-inspector" onClick={(event) => event.stopPropagation()}>{content}</aside></div> : null;
}

function PipelineIntake({ state }) {
  return (
    <section className="pipeline-work-panel">
      <header className="pipeline-section-header">
        <div><span className="proto-eyebrow">STEP 01 · INTAKE</span><h1>组织项目资料</h1><p>{state.data.brief}</p></div>
        <button type="button" className="proto-secondary-button"><SlidersHorizontal size={16} /> 解析设置</button>
      </header>
      <div className="pipeline-upload-zone">
        <Upload size={22} />
        <div><strong>拖放赛题或数据文件</strong><span>CSV、XLSX、PDF，可一次上传多份资料</span></div>
        <button type="button" className="proto-primary-button" onClick={() => state.setExtraFile(true)}><FolderInput size={16} /> {state.extraFile ? "资料已加入" : "加入示例资料"}</button>
      </div>
      <div className="pipeline-subheading"><div><h2>已识别资料</h2><span>{state.files.length} 份</span></div><button type="button" className="proto-icon-button" title="搜索资料"><Search size={16} /></button></div>
      <FileRows state={state} />
      <footer className="pipeline-footer"><span><Info size={14} /> 文件只用于当前项目，原型不上传数据。</span><button type="button" className="proto-primary-button" onClick={state.advance}>生成分析方案 <ChevronRight size={16} /></button></footer>
    </section>
  );
}

function PipelinePlan({ state }) {
  return (
    <section className="pipeline-work-panel">
      <header className="pipeline-section-header"><div><span className="proto-eyebrow">STEP 02 · PLAN</span><h1>审查分析方案</h1><p>所有数值结果都将在当前资料上重新计算，确认后才开始运行。</p></div><span className="proto-version">方案 v2</span></header>
      <div className="pipeline-plan-grid">
        <div className="pipeline-question-list"><h2>研究问题</h2>{state.data.questions.map((question, index) => <article key={question}><span>Q{index + 1}</span><p>{question}</p><button type="button" className="proto-icon-button" title="编辑问题"><NotebookPen size={15} /></button></article>)}</div>
        <div className="pipeline-method-list"><h2>方法与验证</h2>{state.data.methods.map((method, index) => <article key={method}><span>{index + 1}</span><div><strong>{method}</strong><small>{index === 2 ? "包含假设检查与稳健性复核" : "输出可追溯中间结果"}</small></div></article>)}</div>
      </div>
      {state.scenario === "modeling" && <div className="pipeline-case-note"><BookOpenCheck size={18} /><div><strong>案例启发已匹配</strong><p>相似点、差异和适用理由将在运行前展示；历史结果不会作为当前结论。</p></div><button type="button">查看 3 张案例卡片</button></div>}
      <footer className="pipeline-footer"><button type="button" className="proto-secondary-button" onClick={() => state.setStage("intake")}><ArrowLeft size={16} /> 返回资料</button><button type="button" className="proto-primary-button" onClick={() => { state.setPlanConfirmed(true); state.toggleRun(); }}><Check size={16} /> 确认并运行</button></footer>
    </section>
  );
}

function PipelineRun({ state }) {
  return (
    <section className="pipeline-work-panel">
      <header className="pipeline-section-header"><div><span className="proto-eyebrow">STEP 03 · RUN</span><h1>分析正在执行</h1><p>运行 03 · 已用时 02:36 · 预计剩余 01:19</p></div><button type="button" className="proto-secondary-button"><Pause size={15} /> 暂停</button></header>
      <div className="pipeline-progress"><span style={{ width: "62%" }} /></div>
      <div className="pipeline-run-layout">
        <div className="pipeline-timeline">{RUN_STEPS.map(([label, status, time], index) => <article className={status} key={label}><span>{status === "done" ? <Check size={14} /> : index + 1}</span><div><strong>{label}</strong><small>{time}</small></div>{status === "active" && <em>执行中</em>}</article>)}</div>
        <div className="pipeline-run-log"><div><span>LIVE LOG</span><button type="button" className="proto-icon-button" title="展开日志"><Box size={15} /></button></div><pre><code>12:43:08  loaded 42,810 observations{`\n`}12:43:21  quality checks passed: 18/20{`\n`}12:44:02  fitting robust candidate models{`\n`}12:44:31  validating fold 4/5 ...</code></pre></div>
      </div>
      <footer className="pipeline-footer"><span><ShieldCheck size={14} /> 每个步骤都记录输入、代码与输出。</span><button type="button" className="proto-primary-button" onClick={state.toggleRun}>模拟完成 <ChevronRight size={16} /></button></footer>
    </section>
  );
}

function PipelineResults({ state }) {
  return (
    <section className="pipeline-work-panel">
      <header className="pipeline-section-header"><div><span className="proto-eyebrow">STEP 04 · RESULTS</span><h1>{state.data.artifact}</h1><p>运行成功 · 3 项主要结论 · 1 项限制需要关注</p></div><button type="button" className="proto-primary-button"><Download size={16} /> 下载材料包</button></header>
      <div className="pipeline-result-summary"><article><span>主要指标</span><strong>{state.scenario === "general" ? "-18.6%" : "92.4%"}</strong><small>{state.scenario === "general" ? "院区 B 候诊时间差异" : "仿真服务率"}</small></article><article><span>验证状态</span><strong>通过</strong><small>5 折验证 + 3 组敏感性</small></article><article><span>可追溯性</span><strong>96%</strong><small>24 / 25 结论已绑定来源</small></article></div>
      <div className="pipeline-result-body"><div className="pipeline-chart"><div className="pipeline-chart-head"><div><h2>{state.scenario === "general" ? "院区候诊时间分布" : "各时段服务率对比"}</h2><span>点击结论可检查证据</span></div><BarChart3 size={18} /></div><div className="pipeline-bars"><span style={{ height: "68%" }} /><span style={{ height: "43%" }} /><span style={{ height: "79%" }} /><span style={{ height: "58%" }} /><span style={{ height: "86%" }} /></div><div className="pipeline-chart-labels"><span>基线</span><span>方案 A</span><span>方案 B</span><span>压力 1</span><span>压力 2</span></div></div><div className="pipeline-findings"><h2>关键结论</h2>{["主效应在稳健检验后仍成立", "结果对异常值阈值不敏感", "一项外推限制需要在报告中保留"].map((item, index) => <button type="button" key={item} onClick={() => state.setInspectorOpen(true)}><span>{index + 1}</span><p>{item}</p><ChevronRight size={15} /></button>)}</div></div>
    </section>
  );
}

function PipelineWorkspace({ state }) {
  if (state.stage === "intake") return <PipelineIntake state={state} />;
  if (state.stage === "plan") return <PipelinePlan state={state} />;
  if (state.stage === "run") return <PipelineRun state={state} />;
  return <PipelineResults state={state} />;
}

function VariantA({ state }) {
  return (
    <div className="prototype-root proto-a">
      <header className="pipeline-topbar">
        <div className="pipeline-brand"><span>AD</span><div><strong>Academic Data Agent</strong><small>研究工作台 · 方案 A</small></div></div>
        <ScenarioControl scenario={state.scenario} onChange={state.changeScenario} />
        <div className="pipeline-top-actions"><button type="button" className="proto-icon-button" title="项目设置"><SlidersHorizontal size={17} /></button><span className="proto-avatar">研</span></div>
      </header>
      <div className="pipeline-shell">
        <aside className={`pipeline-sidebar ${state.mobileMenuOpen ? "open" : ""}`}>
          <header><button type="button" className="proto-icon-button pipeline-mobile-close" title="关闭导航" onClick={() => state.setMobileMenuOpen(false)}><X size={17} /></button><span className="proto-eyebrow">CURRENT PROJECT</span><h2>{state.data.project}</h2><p>{state.data.brief}</p></header>
          <nav>{STAGES.map((item, index) => { const Icon = item.icon; const activeIndex = STAGES.findIndex((stage) => stage.id === state.stage); return <button type="button" key={item.id} className={`${state.stage === item.id ? "active" : ""} ${index < activeIndex ? "complete" : ""}`} onClick={() => { state.setStage(item.id); state.setMobileMenuOpen(false); }}><span>{index < activeIndex ? <Check size={14} /> : item.short}</span><Icon size={16} /><strong>{item.label}</strong></button>; })}</nav>
          <div className="pipeline-sidebar-output"><PackageCheck size={17} /><div><strong>目标产物</strong><span>{state.data.artifact}</span></div></div>
        </aside>
        {state.mobileMenuOpen && <button type="button" className="proto-mobile-backdrop" aria-label="关闭导航" onClick={() => state.setMobileMenuOpen(false)} />}
        <main className="pipeline-main"><div className="pipeline-mobile-bar"><button type="button" className="proto-icon-button" title="打开流程导航" onClick={() => state.setMobileMenuOpen(true)}><Menu size={18} /></button><strong>{state.data.project}</strong></div><StateSummary state={state} /><PipelineWorkspace state={state} /></main>
        <aside className="pipeline-context">
          <div><span className="proto-eyebrow">PROJECT HEALTH</span><h2>项目状态</h2></div>
          <dl><div><dt>资料完整度</dt><dd>92%</dd></div><div><dt>方案风险</dt><dd className="warning">2 项待看</dd></div><div><dt>证据覆盖</dt><dd>96%</dd></div></dl>
          <div className="pipeline-context-block"><h3>当前检查</h3><p>{state.stage === "intake" ? "确认表之间的主键关系与时间粒度。" : state.stage === "plan" ? "检查方法假设和验证是否覆盖研究问题。" : state.stage === "run" ? "监控模型诊断与异常步骤。" : "逐条核对结论的数据、代码和血缘。"}</p></div>
          <button type="button" className="proto-secondary-button" onClick={() => state.setInspectorOpen(true)}><GitBranch size={15} /> 打开证据检查器</button>
        </aside>
      </div>
      <EvidenceInspector state={state} />
    </div>
  );
}

function LedgerIntake({ state }) {
  return (
    <div className="ledger-stage-grid">
      <section className="ledger-sheet"><header><div><span className="proto-eyebrow">INPUT LEDGER</span><h1>资料登记册</h1></div><button type="button" className="proto-primary-button" onClick={() => state.setExtraFile(true)}><Upload size={15} /> 登记资料</button></header><div className="ledger-table-head"><span>资料</span><span>结构</span><span>状态</span><span>动作</span></div><FileRows state={state} dense /></section>
      <aside className="ledger-brief"><span className="proto-eyebrow">RESEARCH BRIEF</span><h2>{state.data.project}</h2><p>{state.data.brief}</p><h3>边界</h3><ul><li>仅基于当前数据生成数值结果</li><li>{state.scenario === "modeling" ? "首版聚焦数据密集型赛题" : "通用流程不依赖竞赛经验库"}</li><li>所有限制进入最终报告</li></ul><button type="button" className="proto-primary-button" onClick={state.advance}>建立研究台账 <ArrowRight size={15} /></button></aside>
    </div>
  );
}

function LedgerPlan({ state }) {
  return (
    <section className="ledger-plan"><header><div><span className="proto-eyebrow">METHOD REGISTER</span><h1>研究问题与方法台账</h1></div><div className="ledger-plan-actions"><button type="button" className="proto-secondary-button"><Sparkles size={15} /> 重新生成</button><button type="button" className="proto-primary-button" onClick={() => { state.setPlanConfirmed(true); state.toggleRun(); }}><Check size={15} /> 批准运行</button></div></header><div className="ledger-register"><div className="ledger-register-head"><span>ID</span><span>研究问题</span><span>方法</span><span>验证</span><span>状态</span></div>{state.data.questions.map((question, index) => <div className="ledger-register-row" key={question}><span>Q-{String(index + 1).padStart(2, "0")}</span><strong>{question}</strong><span>{state.data.methods[index]}</span><span>{index === 0 ? "假设检查" : index === 1 ? "5 折验证" : "压力测试"}</span><em>待批准</em></div>)}</div>{state.scenario === "modeling" && <div className="ledger-case-strip"><BookOpenCheck size={17} /><strong>3 张案例卡片提供方法启发</strong><span>已记录相似点、差异、适用理由与来源</span><button type="button">展开</button></div>}</section>
  );
}

function LedgerRun({ state }) {
  return (
    <div className="ledger-run-grid"><section className="ledger-run-board"><header><div><span className="proto-eyebrow">RUN BOARD · 03</span><h1>执行台账</h1></div><button type="button" className="proto-secondary-button"><Pause size={15} /> 暂停</button></header>{RUN_STEPS.map(([label, status, time], index) => <div className={`ledger-run-row ${status}`} key={label}><span>{String(index + 1).padStart(2, "0")}</span><strong>{label}</strong><div className="ledger-run-meter"><i style={{ width: status === "done" ? "100%" : status === "active" ? "64%" : "0%" }} /></div><span>{time}</span><em>{status === "done" ? "完成" : status === "active" ? "运行中" : "排队"}</em></div>)}<footer><span>运行状态每 5 秒更新</span><button type="button" className="proto-primary-button" onClick={state.toggleRun}>模拟完成 <ArrowRight size={15} /></button></footer></section><aside className="ledger-console"><header><Code2 size={16} /><strong>执行日志</strong><span>LIVE</span></header><pre><code>$ load project_manifest.json{`\n`}✓ 3 sources validated{`\n`}✓ schema links resolved{`\n`}$ fit candidate_models{`\n`}→ fold 4/5 running{`\n`}→ audit trail synced</code></pre><div><span>CPU 48%</span><span>内存 1.2 GB</span></div></aside></div>
  );
}

function LedgerResults({ state }) {
  return (
    <div className="ledger-results-grid"><section className="ledger-findings"><header><div><span className="proto-eyebrow">FINDINGS REGISTER</span><h1>结论台账</h1></div><button type="button" className="proto-primary-button"><FileArchive size={15} /> 导出材料包</button></header><div className="ledger-kpis"><div><span>主要结果</span><strong>{state.scenario === "general" ? "-18.6%" : "92.4%"}</strong></div><div><span>证据覆盖</span><strong>96%</strong></div><div><span>限制</span><strong>1</strong></div></div><div className="ledger-findings-table"><div className="ledger-findings-head"><span>结论</span><span>证据</span><span>验证</span><span>状态</span></div>{["主效应在稳健检验后仍成立", "方案在中等需求波动下保持稳定", "外推范围受样本时间窗口限制"].map((item, index) => <button type="button" key={item} onClick={() => state.setInspectorOpen(true)}><strong>F-{index + 1} · {item}</strong><span>{index + 2} 个来源</span><span>{index === 2 ? "边界检查" : "通过"}</span><em className={index === 2 ? "warning" : ""}>{index === 2 ? "需说明" : "可信"}</em></button>)}</div></section><EvidenceInspector state={state} inline /></div>
  );
}

function LedgerWorkspace({ state }) {
  if (state.stage === "intake") return <LedgerIntake state={state} />;
  if (state.stage === "plan") return <LedgerPlan state={state} />;
  if (state.stage === "run") return <LedgerRun state={state} />;
  return <LedgerResults state={state} />;
}

function VariantB({ state }) {
  return (
    <div className="prototype-root proto-b">
      <header className="ledger-topbar"><div className="ledger-brand"><LayoutDashboard size={19} /><strong>ADA / RESEARCH LEDGER</strong><span>方案 B</span></div><ScenarioControl scenario={state.scenario} onChange={state.changeScenario} compact /><div className="ledger-actions"><button type="button" className="proto-icon-button" title="搜索"><Search size={16} /></button><button type="button" className="proto-icon-button" title="项目设置"><SlidersHorizontal size={16} /></button><span>LOCAL</span></div></header>
      <div className="ledger-project-bar"><div><span>PROJECT /</span><strong>{state.data.project}</strong></div><div><Clock3 size={14} /> 今天 12:44</div></div>
      <nav className="ledger-stage-nav">{STAGES.map((item, index) => { const Icon = item.icon; return <button type="button" key={item.id} className={state.stage === item.id ? "active" : ""} onClick={() => state.setStage(item.id)}><span>{item.short}</span><Icon size={15} /><strong>{item.label}</strong>{index < STAGES.length - 1 && <ChevronRight size={13} />}</button>; })}</nav>
      <StateSummary state={state} />
      <main className="ledger-main"><LedgerWorkspace state={state} /></main>
      <div className="ledger-command-dock"><span><Network size={15} /> {state.stage === "results" ? "证据网络已同步" : "所有更改仅保存在当前原型"}</span><div><button type="button" className="proto-icon-button" title="查看数据表"><TableProperties size={16} /></button><button type="button" className="proto-icon-button" title="查看血缘"><GitBranch size={16} /></button></div></div>
      <EvidenceInspector state={state} />
    </div>
  );
}

export default function WorkspacePrototype() {
  const initialVariant = new URLSearchParams(window.location.search).get("variant")?.toUpperCase();
  const [variant, setVariant] = useState(VARIANTS.some((item) => item.id === initialVariant) ? initialVariant : "A");
  const state = usePrototypeState();

  const changeVariant = (next) => {
    const params = new URLSearchParams(window.location.search);
    params.set("variant", next);
    window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}${window.location.hash}`);
    setVariant(next);
  };

  const Variant = useMemo(() => variant === "B" ? VariantB : VariantA, [variant]);

  return (
    <>
      <Variant state={state} />
      <PrototypeSwitcher current={variant} onChange={changeVariant} />
    </>
  );
}
