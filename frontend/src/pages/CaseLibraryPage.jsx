import {
  AlertTriangle,
  BookOpenCheck,
  CheckCircle2,
  ExternalLink,
  FileSearch,
  FlaskConical,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { StatCard, ViewLoading } from "../components/WorkspacePrimitives";

function MethodList({ title, items, icon: Icon = FlaskConical }) {
  if (!items?.length) return null;
  return (
    <section className="case-detail-section">
      <header><Icon size={17} /><h3>{title}</h3></header>
      <div className="case-method-list">
        {items.map((item, index) => (
          <article key={`${item.name}-${index}`}>
            <strong>{item.name}</strong>
            <p>{item.purpose}</p>
            {item.assumptions?.length > 0 && (
              <details><summary>查看假设</summary><ul>{item.assumptions.map((value) => <li key={value}>{value}</li>)}</ul></details>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

function CaseDetail({ detail }) {
  if (!detail) {
    return <div className="case-detail-empty"><FileSearch size={28} /><strong>选择一张案例卡查看详情</strong></div>;
  }
  const item = detail.case;
  return (
    <article className="case-detail-panel">
      <header className="case-detail-hero">
        <div>
          <span className="kicker">{item.competition}</span>
          <h2>{item.year} 年 {item.problemNumber} 题 · {item.title}</h2>
          <p>{item.problemSummary}</p>
        </div>
        <span className="approved-badge"><CheckCircle2 size={15} />已审核</span>
      </header>

      <div className="case-keywords">
        {item.keywords?.map((keyword) => <span key={keyword}>{keyword}</span>)}
      </div>

      <MethodList title="数据操作" items={detail.dataOperations} icon={FileSearch} />
      <MethodList title="模型与方法" items={detail.models} />
      <MethodList title="验证方法" items={detail.validationMethods} icon={ShieldCheck} />

      <section className="case-detail-section">
        <header><CheckCircle2 size={17} /><h3>关键结论</h3></header>
        <ol className="case-finding-list">
          {detail.keyFindings?.map((finding, index) => <li key={`${index}-${finding.statement}`}>{finding.statement}</li>)}
        </ol>
      </section>

      <section className="case-detail-section limitations">
        <header><AlertTriangle size={17} /><h3>局限与复用边界</h3></header>
        <ul>{detail.limitations?.map((value) => <li key={value}>{value}</li>)}</ul>
      </section>

      <section className="case-detail-section">
        <header><BookOpenCheck size={17} /><h3>来源</h3></header>
        <div className="case-source-list">
          {detail.sources?.map((source) => (
            <a href={source.uri} target="_blank" rel="noreferrer" key={source.id}>
              <span><strong>{source.title}</strong><small>{source.role} · {source.distribution}</small></span>
              <ExternalLink size={15} />
            </a>
          ))}
        </div>
      </section>
    </article>
  );
}

export default function CaseLibraryView({ library, detail, selectedCaseId, loading, error, onSelect, onRetry }) {
  if (loading && !library) return <ViewLoading message="正在加载竞赛案例库" />;
  const cases = library?.cases || [];
  return (
    <section className="view-stack case-library-page">
      <div className="stat-grid">
        <StatCard label="内置版本" value={library?.version || "不可用"} icon={BookOpenCheck} />
        <StatCard label="已审核案例" value={cases.length} icon={CheckCircle2} />
        <StatCard label="经验库状态" value={library?.usable ? "可用" : "已降级"} icon={ShieldCheck} />
      </div>

      {(error || !library?.usable) && (
        <div className="case-library-warning">
          <AlertTriangle size={18} />
          <div><strong>竞赛案例库暂不可用</strong><p>{error || library?.warnings?.[0] || "系统将继续使用通用分析能力。"}</p></div>
          <button className="secondary-button" type="button" onClick={onRetry}><RefreshCw size={15} />重试</button>
        </div>
      )}

      <div className="case-library-layout">
        <aside className="case-card-list panel">
          <div className="section-header compact"><span className="kicker">Curated cases</span><h2>竞赛案例</h2></div>
          {cases.length ? cases.map((item) => (
            <button
              type="button"
              className={selectedCaseId === item.id ? "case-card-button active" : "case-card-button"}
              key={item.id}
              onClick={() => onSelect(item.id)}
            >
              <span>{item.year} · {item.problemNumber} 题</span>
              <strong>{item.title}</strong>
              <small>{item.methods?.slice(0, 3).join(" · ")}</small>
              <em><CheckCircle2 size={13} />approved</em>
            </button>
          )) : <p className="muted">当前没有可展示的已审核案例。</p>}
        </aside>

        <div className="panel case-detail-container">
          {loading && selectedCaseId && !detail ? <ViewLoading message="正在加载案例详情" /> : <CaseDetail detail={detail} />}
        </div>
      </div>
    </section>
  );
}
