import { useEffect, useRef } from "react";
import { FolderOutput, Menu, PanelLeftClose, PanelLeftOpen, RefreshCw, X } from "lucide-react";
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
  const ActiveIcon = activeItem.icon;
  const showingCaseLibrary = activeView === "knowledge" && form.scenario === "modeling";
  const refreshBusy = showingCaseLibrary ? caseLibraryLoading : workspaceLoading;
  const handleRefresh = showingCaseLibrary ? refreshCaseLibrary : refreshWorkspace;

  useEffect(() => {
    viewStageRef.current?.scrollTo({ top: 0, behavior: "auto" });
  }, [activeView]);
  const renderNavigationItem = (item) => {
    const Icon = item.icon;
    return (
      <button
        type="button"
        key={item.id}
        className={activeView === item.id ? "nav-item active" : "nav-item"}
        aria-current={activeView === item.id ? "page" : undefined}
        title={sidebarCollapsed ? item.label : undefined}
        onClick={() => {
          setActiveView(item.id);
          setMobileSidebarOpen(false);
        }}
      >
        <span><Icon size={18} /></span>
        <strong>{item.label}</strong>
      </button>
    );
  };

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-is-collapsed" : ""}`}>
      <aside className={`sidebar ${mobileSidebarOpen ? "sidebar-open" : ""}`}>
        <div className="sidebar-top">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">✦</span>
            <div>
              <strong>Academic Agent</strong>
              <span>研究与建模工作台</span>
            </div>
          </div>
          <button
            className="icon-button desktop-only"
            type="button"
            onClick={() => setSidebarCollapsed((value) => !value)}
            title={sidebarCollapsed ? "展开侧栏" : "收起侧栏"}
          >
            {sidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
          <button className="icon-button mobile-only" type="button" aria-label="关闭导航" onClick={() => setMobileSidebarOpen(false)}>
            <X size={18} />
          </button>
        </div>

        <nav className="nav-list" aria-label="主导航">
          <span className="nav-section-label">工作台</span>
          {navigationItems.slice(0, 4).map(renderNavigationItem)}
          <span className="nav-section-label">资源与设置</span>
          {navigationItems.slice(4).map(renderNavigationItem)}
        </nav>

        <div className="sidebar-footer">
          <span className={`status-dot ${status.state}`} aria-hidden="true" />
          <div><small>当前状态</small><p>{status.message}</p></div>
        </div>
      </aside>

      {mobileSidebarOpen && <button className="backdrop" type="button" onClick={() => setMobileSidebarOpen(false)} />}

      <main className="main-panel">
        <header className="topbar">
          <button className="icon-button mobile-only" type="button" aria-label="打开导航" onClick={() => setMobileSidebarOpen(true)}>
            <Menu size={20} />
          </button>
          <div className="topbar-title">
            <span className="topbar-icon">
              <ActiveIcon size={18} />
            </span>
            <div>
              <strong>{activeItem.label}</strong>
              <span>{activeItem.description}</span>
            </div>
          </div>
          <div className="topbar-actions">
            {activeView !== "settings" && (
              <span className="topbar-context"><FolderOutput size={15} />{form.outputDir || "outputs"}</span>
            )}
            {activeView !== "settings" && (
              <button
                className="secondary-button compact-button"
                type="button"
                onClick={() => handleRefresh()}
                disabled={refreshBusy}
              >
                <RefreshCw className={refreshBusy ? "spin" : ""} size={16} />
                {refreshBusy ? "刷新中" : "刷新"}
              </button>
            )}
          </div>
        </header>

        {workspaceError && <div className="error-banner">{workspaceError}</div>}

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
          {activeView === "results" && (
            <ResultsView status={status} logs={logs} result={result} outputDir={form.outputDir || "outputs"} />
          )}
          {activeView === "lineage" && (
            <LineageView
              workspace={workspace}
              selectedRunId={selectedRunId}
              setSelectedRunId={setSelectedRunId}
              historyDetail={historyDetail}
              result={result}
              historyLoading={historyLoadingRunId === selectedRunId}
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
              historyLoading={historyLoadingRunId === selectedRunId}
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
