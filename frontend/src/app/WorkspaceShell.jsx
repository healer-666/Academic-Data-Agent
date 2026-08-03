import { useEffect, useRef } from "react";
import { Files, Menu, PanelLeftClose, PanelLeftOpen, RefreshCw, X } from "lucide-react";
import { getNavigationItems } from "./navigation";
import AnalysisView from "../pages/AnalysisPage";
import CaseLibraryView from "../pages/CaseLibraryPage";
import HistoryView from "../pages/HistoryPage";
import KnowledgeView from "../pages/KnowledgePage";
import LineageView from "../pages/LineagePage";
import ResultsView from "../pages/ResultsPage";
import ModelSettingsView from "../pages/ModelSettingsPage";
import { ViewLoading } from "../components/WorkspacePrimitives";

export default function WorkspaceShell({ controller }) {
  const viewStageRef = useRef(null);
  const { navigation, workspace: workspaceState, analysis, history, caseLibrary } = controller;
  const { activeView, setActiveView, sidebarCollapsed, setSidebarCollapsed, mobileSidebarOpen, setMobileSidebarOpen } = navigation;
  const { data: workspace, error: workspaceError, loading: workspaceLoading, refresh: refreshWorkspace } = workspaceState;
  const {
    form, setForm, dataFile, setDataFile, knowledgeFiles, setKnowledgeFiles,
    problemFile, setProblemFile, modelingDataFiles, setModelingDataFiles,
    modelingAttachments, setModelingAttachments, modelingPackage,
    modelingBusy, modelingError, inspectModelingPackage, saveModelingReview, saveModelingPlanReview, resetModelingPackage,
    isRunning, status, logs, result, submit: submitAnalysis,
  } = analysis;
  const {
    selectedRunId, setSelectedRunId, detail: historyDetail, loadingRunId: historyLoadingRunId,
    qaQuestion, setQaQuestion, qaMode, setQaMode, qaSelected, setQaSelected,
    qaResult, qaLoading, ask: handleAskQuestion,
  } = history;
  const {
    data: caseLibraryData, detail: caseLibraryDetail, selectedCaseId,
    loading: caseLibraryLoading, error: caseLibraryError,
    select: selectCase, refresh: refreshCaseLibrary,
  } = caseLibrary;

  const navigationItems = getNavigationItems(form.scenario);
  const activeItem = navigationItems.find((item) => item.id === activeView) || navigationItems[0];
  const showingCaseLibrary = activeView === "knowledge" && form.scenario === "modeling";
  const refreshBusy = showingCaseLibrary ? caseLibraryLoading : workspaceLoading;
  const handleRefresh = showingCaseLibrary ? refreshCaseLibrary : refreshWorkspace;
  const resultFiles = result?.downloads?.length || 0;

  useEffect(() => {
    viewStageRef.current?.scrollTo({ top: 0, behavior: "auto" });
  }, [activeView]);

  useEffect(() => {
    if (!mobileSidebarOpen) return undefined;
    const handleKeyDown = (event) => {
      if (event.key === "Escape") setMobileSidebarOpen(false);
    };
    document.body.classList.add("sidebar-drawer-open");
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.classList.remove("sidebar-drawer-open");
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [mobileSidebarOpen, setMobileSidebarOpen]);

  const openView = (viewId) => {
    setActiveView(viewId);
    setMobileSidebarOpen(false);
  };

  const renderNavigationItem = (item) => {
    const Icon = item.icon;
    return (
      <button
        type="button"
        key={item.id}
        className={activeView === item.id ? "nav-item active" : "nav-item"}
        aria-current={activeView === item.id ? "page" : undefined}
        title={sidebarCollapsed ? item.label : undefined}
        onClick={() => openView(item.id)}
      >
        <span><Icon size={18} /></span>
        <strong>{item.label}</strong>
      </button>
    );
  };

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-is-collapsed" : ""}`}>
      <aside className={`sidebar ${mobileSidebarOpen ? "sidebar-open" : ""}`} aria-label="应用导航">
        <div className="sidebar-top">
          <button className="brand" type="button" onClick={() => openView("analysis")} title="Academic Agent">
            <span className="brand-mark" aria-hidden="true">A</span>
            <strong>Academic Agent</strong>
          </button>
          {!sidebarCollapsed && (
            <button className="icon-button desktop-only" type="button" onClick={() => setSidebarCollapsed(true)} aria-label="收起侧边栏" title="收起侧边栏">
              <PanelLeftClose size={18} />
            </button>
          )}
          <button className="icon-button mobile-only" type="button" aria-label="关闭导航" onClick={() => setMobileSidebarOpen(false)}>
            <X size={19} />
          </button>
        </div>

        <nav className="nav-list" aria-label="主导航">
          {navigationItems.slice(0, 4).map(renderNavigationItem)}
          <span className="nav-section-label">资源</span>
          {navigationItems.slice(4, 5).map(renderNavigationItem)}
        </nav>

        <div className="sidebar-footer">
          {status.state !== "idle" && (
            <div className="sidebar-status" title={status.message}>
              <span className={`status-dot ${status.state}`} aria-hidden="true" />
              <span>{status.message}</span>
            </div>
          )}
          {navigationItems.slice(5).map(renderNavigationItem)}
        </div>
      </aside>

      {mobileSidebarOpen && <button className="backdrop" type="button" aria-label="关闭导航" onClick={() => setMobileSidebarOpen(false)} />}

      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-leading">
            <button className="icon-button mobile-only" type="button" aria-label="打开导航" onClick={() => setMobileSidebarOpen(true)}>
              <Menu size={20} />
            </button>
            {sidebarCollapsed && (
              <button className="icon-button desktop-only" type="button" aria-label="展开侧边栏" title="展开侧边栏" onClick={() => setSidebarCollapsed(false)}>
                <PanelLeftOpen size={19} />
              </button>
            )}
            <strong>{activeItem.label}</strong>
          </div>
          <div className="topbar-actions">
            {status.state !== "idle" && status.state !== "success" && (
              <span className={`topbar-status ${status.state}`}><span />{status.message}</span>
            )}
            {resultFiles > 0 && (
              <button className="topbar-text-action" type="button" onClick={() => openView("results")}>
                <Files size={16} />文件 <span>{resultFiles}</span>
              </button>
            )}
            {activeView !== "settings" && (
              <button className="icon-button" type="button" onClick={() => handleRefresh()} disabled={refreshBusy} aria-label="刷新" title="刷新">
                <RefreshCw className={refreshBusy ? "spin" : ""} size={17} />
              </button>
            )}
          </div>
        </header>

        {workspaceError && <div className="error-banner" role="alert">{workspaceError}</div>}

        <div className="view-stage" key={activeView} ref={viewStageRef}>
          {activeView === "analysis" && (
            <AnalysisView
              form={form}
              setForm={setForm}
              dataFile={dataFile}
              setDataFile={setDataFile}
              knowledgeFiles={knowledgeFiles}
              setKnowledgeFiles={setKnowledgeFiles}
              problemFile={problemFile}
              setProblemFile={setProblemFile}
              modelingDataFiles={modelingDataFiles}
              setModelingDataFiles={setModelingDataFiles}
              modelingAttachments={modelingAttachments}
              setModelingAttachments={setModelingAttachments}
              modelingPackage={modelingPackage}
              modelingBusy={modelingBusy}
              modelingError={modelingError}
              onInspectModeling={inspectModelingPackage}
              onSaveModelingReview={saveModelingReview}
              onResetModeling={resetModelingPackage}
              onSaveModelingPlan={saveModelingPlanReview}
              isRunning={isRunning}
              onSubmit={submitAnalysis}
            />
          )}
          {activeView === "results" && <ResultsView status={status} logs={logs} result={result} outputDir={form.outputDir || "outputs"} />}
          {activeView === "lineage" && (
            <LineageView
              workspace={workspace}
              selectedRunId={selectedRunId}
              setSelectedRunId={setSelectedRunId}
              historyDetail={historyDetail}
              result={result}
              historyLoading={Boolean(selectedRunId) && historyLoadingRunId === selectedRunId}
            />
          )}
          {activeView === "history" && (
            <HistoryView
              workspace={workspace}
              selectedRunId={selectedRunId}
              setSelectedRunId={setSelectedRunId}
              historyDetail={historyDetail}
              outputDir={form.outputDir || "outputs"}
              qaQuestion={qaQuestion}
              setQaQuestion={setQaQuestion}
              qaMode={qaMode}
              setQaMode={setQaMode}
              qaSelected={qaSelected}
              setQaSelected={setQaSelected}
              qaResult={qaResult}
              qaLoading={qaLoading}
              historyLoading={Boolean(selectedRunId) && historyLoadingRunId === selectedRunId}
              onAskQuestion={handleAskQuestion}
            />
          )}
          {activeView === "knowledge" && (
            form.scenario === "modeling" ? (
              <CaseLibraryView
                library={caseLibraryData}
                detail={caseLibraryDetail}
                selectedCaseId={selectedCaseId}
                loading={caseLibraryLoading}
                error={caseLibraryError}
                onSelect={selectCase}
                onRetry={refreshCaseLibrary}
              />
            ) : workspaceLoading && !workspace ? (
              <ViewLoading message="正在加载知识库" />
            ) : <KnowledgeView knowledgeBase={workspace?.knowledgeBase} />
          )}
          {activeView === "settings" && <ModelSettingsView />}
        </div>
      </main>
    </div>
  );
}
