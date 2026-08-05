import { useEffect, useState } from "react";
import {
  AlertTriangle,
  BookOpenCheck,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  ExternalLink,
  FileSearch,
  FlaskConical,
  Lightbulb,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { ViewLoading } from "../components/WorkspacePrimitives";

function MethodItems({ items }) {
  if (!items?.length) return null;
  return (
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
  );
}

function DetailDisclosure({ title, count, icon: Icon, children }) {
  return (
    <details className="case-detail-disclosure">
      <summary>
        <span><Icon size={16} />{title}</span>
        <small>{count} 项</small>
        <ChevronRight className="case-disclosure-chevron" size={16} />
      </summary>
      <div className="case-disclosure-content">{children}</div>
    </details>
  );
}

function CaseDetail({ detail }) {
  const [summaryExpanded, setSummaryExpanded] = useState(false);
  const caseId = detail?.case?.id || "";

  useEffect(() => setSummaryExpanded(false), [caseId]);

  if (!detail) {
    return <div className="case-detail-empty"><FileSearch size={28} /><strong>选择一张案例卡查看详情</strong></div>;
  }
  const item = detail.case;
  return (
    <article className="case-detail-panel">
      <header className="case-detail-hero">
        <div>
          <span className="case-eyebrow">{item.competition} · {item.year} 年 · {item.problemNumber} 题</span>
          <h2>{item.year} 年 {item.problemNumber} 题 · {item.title}</h2>
          <p className={summaryExpanded ? "case-summary-text expanded" : "case-summary-text"}>{item.problemSummary}</p>
          <button
            type="button"
            className="case-summary-toggle"
            aria-expanded={summaryExpanded}
            onClick={() => setSummaryExpanded((current) => !current)}
          >
            {summaryExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {summaryExpanded ? "收起题目简介" : "展开题目简介"}
          </button>
        </div>
        <span className="approved-badge"><CheckCircle2 size={15} />已审核</span>
      </header>

      <div className="case-keywords">
        {item.keywords?.map((keyword) => <span key={keyword}>{keyword}</span>)}
      </div>

      <section className="case-focus-section">
        <header>
          <span className="case-focus-kicker">案例速览</span>
          <h3>先抓住最值得借鉴的部分</h3>
        </header>
        <div className="case-focus-grid">
          <div className="case-focus-card methods">
            <div className="case-focus-title"><FlaskConical size={17} /><strong>核心方法</strong></div>
            <ol>
              {detail.models?.slice(0, 3).map((model) => (
                <li key={model.name}><strong>{model.name}</strong><p>{model.purpose}</p></li>
              ))}
            </ol>
          </div>
          <div className="case-focus-card findings">
            <div className="case-focus-title"><Lightbulb size={17} /><strong>主要结论</strong></div>
            <ol>
              {detail.keyFindings?.slice(0, 3).map((finding, index) => (
                <li key={`${index}-${finding.statement}`}>{finding.statement}</li>
              ))}
            </ol>
          </div>
        </div>
        {detail.limitations?.[0] && (
          <div className="case-reuse-alert">
            <AlertTriangle size={17} />
            <div><strong>复用提醒</strong><p>{detail.limitations[0]}</p></div>
          </div>
        )}
      </section>

      <section className="case-full-detail">
        <header><span>完整案例资料</span><p>需要深入研究时再展开，默认不打断快速阅读。</p></header>
        <DetailDisclosure title="数据处理" count={detail.dataOperations?.length || 0} icon={FileSearch}>
          <MethodItems items={detail.dataOperations} />
        </DetailDisclosure>
        <DetailDisclosure title="模型与方法" count={detail.models?.length || 0} icon={FlaskConical}>
          <MethodItems items={detail.models} />
        </DetailDisclosure>
        <DetailDisclosure title="验证方法" count={detail.validationMethods?.length || 0} icon={ShieldCheck}>
          <MethodItems items={detail.validationMethods} />
        </DetailDisclosure>
        <DetailDisclosure title="全部结论" count={detail.keyFindings?.length || 0} icon={CheckCircle2}>
          <ol className="case-finding-list">
            {detail.keyFindings?.map((finding, index) => <li key={`${index}-${finding.statement}`}>{finding.statement}</li>)}
          </ol>
        </DetailDisclosure>
        <DetailDisclosure title="局限与复用边界" count={detail.limitations?.length || 0} icon={AlertTriangle}>
          <ul className="case-limitation-list">{detail.limitations?.map((value) => <li key={value}>{value}</li>)}</ul>
        </DetailDisclosure>
        <DetailDisclosure title="来源" count={detail.sources?.length || 0} icon={BookOpenCheck}>
          <div className="case-source-list">
            {detail.sources?.map((source) => (
              <a href={source.uri} target="_blank" rel="noreferrer" key={source.id}>
                <span><strong>{source.title}</strong><small>{source.role} · {source.distribution}</small></span>
                <ExternalLink size={15} />
              </a>
            ))}
          </div>
        </DetailDisclosure>
      </section>
    </article>
  );
}

export default function CaseLibraryView({ library, detail, selectedCaseId, loading, error, onSelect, onRetry }) {
  if (loading && !library) return <ViewLoading message="正在加载竞赛案例库" />;
  const cases = library?.cases || [];
  return (
    <section className="case-library-page">
      <div className="case-library-meta">
        <span><BookOpenCheck size={16} />版本 {library?.version || "不可用"}</span>
        <span>{cases.length} 个已审核案例</span>
        <span>{library?.usable ? "经验库可用" : "经验库已降级"}</span>
      </div>

      {(error || !library?.usable) && (
        <div className="case-library-warning">
          <AlertTriangle size={18} />
          <div><strong>竞赛案例库暂不可用</strong><p>{error || library?.warnings?.[0] || "系统将继续使用通用分析能力。"}</p></div>
          <button className="secondary-button" type="button" onClick={onRetry}><RefreshCw size={15} />重试</button>
        </div>
      )}

      <div className="case-library-layout">
        <aside className="case-card-list">
          <h2>竞赛案例</h2>
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
              <em><CheckCircle2 size={13} />已审核</em>
            </button>
          )) : <p className="muted">当前没有可展示的已审核案例。</p>}
        </aside>

        <div className="case-detail-container">
          {loading && selectedCaseId && !detail ? <ViewLoading message="正在加载案例详情" /> : <CaseDetail detail={detail} />}
        </div>
      </div>
    </section>
  );
}
