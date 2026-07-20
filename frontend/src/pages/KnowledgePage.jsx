import { BookOpen, Database, FileText, ShieldCheck } from "lucide-react";
import { StatCard } from "../components/WorkspacePrimitives";
import { compactStatus, formatBytes } from "../utils/formatters";

function KnowledgeView({ knowledgeBase }) {
  return (
    <section className="view-stack">
      <div className="stat-grid">
        <StatCard label="已收录文件" value={knowledgeBase?.indexedFileCount ?? 0} icon={BookOpen} />
        <StatCard label="知识切片" value={knowledgeBase?.chunkCount ?? 0} icon={Database} />
        <StatCard label="向量索引" value={compactStatus(knowledgeBase?.vectorStatus)} icon={ShieldCheck} />
      </div>
      <div className="panel">
        <div className="section-header compact">
          <span className="kicker">Knowledge</span>
          <h2>本地知识库</h2>
        </div>
        <div className="knowledge-list">
          {knowledgeBase?.recentFiles?.length ? (
            knowledgeBase.recentFiles.map((file) => (
              <article key={file.path}>
                <FileText size={18} />
                <div>
                  <strong>{file.name}</strong>
                  <span>{file.modifiedAt} · {formatBytes(file.size)}</span>
                </div>
              </article>
            ))
          ) : (
            <p className="muted">还没有长期收录的参考资料。</p>
          )}
        </div>
      </div>
    </section>
  );
}

export default KnowledgeView;
