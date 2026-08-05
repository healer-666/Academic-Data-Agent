import { useEffect, useState } from "react";
import { BookOpenCheck, Database } from "lucide-react";
import CaseLibraryView from "./CaseLibraryPage";
import KnowledgeView from "./KnowledgePage";

export default function ResourceLibraryView({
  scenario,
  knowledgeBase,
  caseLibrary,
  caseDetail,
  selectedCaseId,
  caseLoading,
  caseError,
  onSelectCase,
  onRetryCases,
}) {
  const [activeTab, setActiveTab] = useState(scenario === "modeling" ? "cases" : "files");

  useEffect(() => {
    setActiveTab(scenario === "modeling" ? "cases" : "files");
  }, [scenario]);

  return (
    <section className="unified-library-page">
      <header className="unified-library-header">
        <div><h1>资料库</h1><p>在同一个地方查看通用参考资料与经过审核的竞赛案例。</p></div>
        <nav className="library-tabs" aria-label="资料库分类">
          <button type="button" className={activeTab === "files" ? "active" : ""} onClick={() => setActiveTab("files")}><Database size={16} />通用资料</button>
          <button type="button" className={activeTab === "cases" ? "active" : ""} onClick={() => setActiveTab("cases")}><BookOpenCheck size={16} />竞赛案例</button>
        </nav>
      </header>

      <div className="unified-library-content">
        {activeTab === "files" ? (
          <KnowledgeView knowledgeBase={knowledgeBase} embedded />
        ) : (
          <CaseLibraryView
            library={caseLibrary}
            detail={caseDetail}
            selectedCaseId={selectedCaseId}
            loading={caseLoading}
            error={caseError}
            onSelect={onSelectCase}
            onRetry={onRetryCases}
          />
        )}
      </div>
    </section>
  );
}
