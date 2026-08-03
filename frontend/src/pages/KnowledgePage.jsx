import { Database, FileText } from "lucide-react";
import { compactStatus, formatBytes } from "../utils/formatters";

function KnowledgeView({ knowledgeBase }) {
  const files = knowledgeBase?.recentFiles || [];
  return (
    <section className="knowledge-page">
      <header className="page-heading">
        <div><h1>本地知识库</h1><p>通用分析可引用的本地资料。</p></div>
        <div className="knowledge-summary">
          <span><strong>{knowledgeBase?.indexedFileCount ?? 0}</strong> 个文件</span>
          <span><strong>{knowledgeBase?.chunkCount ?? 0}</strong> 个切片</span>
          <span><Database size={15} />{compactStatus(knowledgeBase?.vectorStatus)}</span>
        </div>
      </header>

      {files.length ? (
        <div className="file-table knowledge-table" role="table" aria-label="知识库文件">
          <div className="file-table-head" role="row"><span>名称</span><span>类型</span><span>更新时间</span><span>大小</span></div>
          {files.map((file) => (
            <div className="file-table-row" role="row" key={file.path}>
              <strong><FileText size={16} />{file.name}</strong>
              <span>{file.name?.split(".").pop()?.toUpperCase() || "文件"}</span>
              <span>{file.modifiedAt || "—"}</span>
              <span>{formatBytes(file.size)}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="knowledge-empty"><FileText size={22} /><h2>还没有本地资料</h2><p>在新建分析时添加参考资料，索引后的文件会显示在这里。</p></div>
      )}
    </section>
  );
}

export default KnowledgeView;
