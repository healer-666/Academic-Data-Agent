import { useEffect, useRef } from "react";
import { AlertTriangle, ArrowRight, CheckCircle2, CircleDashed, Files, Menu, PanelLeftClose, PanelLeftOpen, RefreshCw, X } from "lucide-react";
import { getNavigationItems } from "./navigation";
import AnalysisView from "../pages/AnalysisPage";
import HistoryView from "../pages/HistoryPage";
import ResultsView from "../pages/ResultsPage";
import ModelSettingsView from "../pages/ModelSettingsPage";
import ResourceLibraryView from "../pages/ResourceLibraryPage";

export default function WorkspaceShell({ controller }) {
  const viewStageRef = useRef(null);
  const { navigation, workspace: workspaceState, modelSettings, analysis, history, caseLibrary } = controller;
  const {
    activeView, setActiveView, workspaceMode, startNewAnalysis, openHistoryRun, openCurrentResult,
    sidebarCollapsed, setSidebarCollapsed, mobileSidebarOpen, setMobileSidebarOpen,
  } = navigation;
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
  const historyRuns = workspace?.historyRuns || [];
  const topbarTitle = activeView === "analysis"
    ? workspaceMode === "history" ? (historyDetail?.runId || selectedRunId || "历史分析") : workspaceMode === "current" ? "分析结果" : "新建分析"
    : activeItem.label;
  const showingLibrary = activeView === "knowledge";
  const refreshBusy = showingLibrary ? caseLibraryLoading || workspaceLoading : workspaceLoading;
  const handleRefresh = showingLibrary ? () => Promise.all([refreshWorkspace(), refreshCaseLibrary()]) : refreshWorkspace;
  const resultFiles = result?.downloads?.length || 0;
  const modelConfigured = Boolean(modelSettings.data?.configured);
  const modelStatus = (() => {
    if (modelSettings.loading && !modelSettings.data) return { tone: "checking", label: "检查模型配置", icon: CircleDashed };
    if (modelSettings.error) return { tone: "error", label: "模型状态未知", icon: AlertTriangle };
    if (!modelConfigured) return { tone: "warning", label: "模型未配置", icon: AlertTriangle };
    if (modelSettings.data?.connectionStatus === "failed") return { tone: "error", label: "模型连接失败", icon: AlertTriangle };
    if (modelSettings.data?.connectionStatus === "connected") return { tone: "success", label: "模型已连接", icon: CheckCircle2 };
    return { tone: "ready", label: "模型已配置", icon: CheckCircle2 };
  })();
  const ModelStatusIcon = modelStatus.icon;

  useEffect(() => {
    viewStageRef.current?.scrollTo({ top: 0, behavior: "auto" });
  }, [activeView, workspaceMode, selectedRunId]);

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

  const openNewAnalysis = () => {
    startNewAnalysis();
    setMobileSidebarOpen(false);
  };

  const selectHistoryRun = (runId) => {
    openHistoryRun(runId);
    setMobileSidebarOpen(false);
  };

  const renderNavigationItem = (item) => {
    const Icon = item.icon;
    return (
      <button
        type="button"
        key={item.id}
        className={activeView === item.id && (item.id !== "analysis" || workspaceMode === "new") ? "nav-item active" : "nav-item"}
        aria-current={activeView === item.id && (item.id !== "analysis" || workspaceMode === "new") ? "page" : undefined}
        title={sidebarCollapsed ? item.label : undefined}
        onClick={() => item.id === "analysis" ? openNewAnalysis() : openView(item.id)}
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
          <button className="brand" type="button" onClick={openNewAnalysis} title="Academic Agent">
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
          {navigationItems.slice(0, 1).map(renderNavigationItem)}
          <span className="nav-section-label">资源</span>
          {navigationItems.slice(1, 2).map(renderNavigationItem)}
        </nav>

        <section className="sidebar-history" aria-label="最近任务">
            <header><span>最近任务</span><small>{historyRuns.length}</small></header>
            <div>
              {historyRuns.length ? historyRuns.slice(0, 18).map((run) => {
                const title = run.sessionLabel || run.query || (run.domain && run.domain !== "unknown" ? run.domain : run.runId);
                const meta = run.timestamp && run.timestamp !== run.runId ? run.timestamp : run.runId;
                return (
                  <button type="button" className={workspaceMode === "history" && run.runId === selectedRunId ? "active" : ""} key={run.runId} onClick={() => selectHistoryRun(run.runId)} title={run.runId}>
                    <strong>{title}</strong><small>{meta}</small>
                  </button>
                );
              }) : <p>完成分析后，任务会出现在这里。</p>}
            </div>
        </section>

        <div className="sidebar-footer">
          {status.state !== "idle" && (
            <div className="sidebar-status" title={status.message}>
              <span className={`status-dot ${status.state}`} aria-hidden="true" />
              <span>{status.message}</span>
            </div>
          )}
          {navigationItems.slice(2).map(renderNavigationItem)}
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
            <strong>{topbarTitle}</strong>
          </div>
          <div className="topbar-actions">
            <button
              className={`model-config-indicator ${modelStatus.tone}`}
              type="button"
              onClick={() => openView("settings")}
              title={`${modelStatus.label}，点击前往模型设置`}
            >
              <ModelStatusIcon className={modelStatus.tone === "checking" ? "spin" : ""} size={15} />
              <span>{modelStatus.label}</span>
            </button>
            {status.state !== "idle" && status.state !== "success" && (
              <span className={`topbar-status ${status.state}`}><span />{status.message}</span>
            )}
            {resultFiles > 0 && (
              <button className="topbar-text-action" type="button" onClick={openCurrentResult}>
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

        {activeView === "analysis" && workspaceMode === "new" && !modelSettings.loading && !modelConfigured && (
          <button className="model-setup-notice" type="button" onClick={() => openView("settings")}>
            <AlertTriangle size={18} />
            <span><strong>分析前请先配置模型 API</strong><small>设置模型名称、Base URL 和 API Key，并测试连接。</small></span>
            <em>前往设置<ArrowRight size={15} /></em>
          </button>
        )}

        <div className="view-stage" key={`${activeView}-${workspaceMode}-${workspaceMode === "history" ? selectedRunId : ""}`} ref={viewStageRef}>
          {activeView === "analysis" && workspaceMode === "new" && (
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
          {activeView === "analysis" && workspaceMode === "current" && (
            <ResultsView
              status={status}
              logs={logs}
              result={result || historyDetail}
              outputDir={form.outputDir || "outputs"}
            />
          )}
          {activeView === "analysis" && workspaceMode === "history" && (
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
              showHistoryList={false}
            />
          )}
          {activeView === "knowledge" && (
            <ResourceLibraryView
              scenario={form.scenario}
              knowledgeBase={workspace?.knowledgeBase}
              caseLibrary={caseLibraryData}
              caseDetail={caseLibraryDetail}
              selectedCaseId={selectedCaseId}
              caseLoading={caseLibraryLoading}
              caseError={caseLibraryError}
              onSelectCase={selectCase}
              onRetryCases={refreshCaseLibrary}
            />
          )}
          {activeView === "settings" && (
            <ModelSettingsView
              status={modelSettings.data}
              loading={modelSettings.loading}
              loadError={modelSettings.error}
              onRefresh={modelSettings.refresh}
              onStatusChange={modelSettings.update}
            />
          )}
        </div>
      </main>
    </div>
  );
}
