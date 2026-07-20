import { Menu, PanelLeftClose, PanelLeftOpen, RefreshCw, X } from "lucide-react";
import { NAV_ITEMS } from "./navigation";
import AnalysisView from "../pages/AnalysisPage";
import HistoryView from "../pages/HistoryPage";
import KnowledgeView from "../pages/KnowledgePage";
import LineageView from "../pages/LineagePage";
import ResultsView from "../pages/ResultsPage";
import ModelSettingsView from "../pages/ModelSettingsPage";
import { ViewLoading } from "../components/WorkspacePrimitives";

export default function WorkspaceShell({ controller }) {
  const { navigation, workspace: workspaceState, analysis, history } = controller;
  const { activeView, setActiveView, sidebarCollapsed, setSidebarCollapsed, mobileSidebarOpen, setMobileSidebarOpen } = navigation;
  const { data: workspace, error: workspaceError, loading: workspaceLoading, refresh: refreshWorkspace } = workspaceState;
  const {
    form, setForm, dataFile, setDataFile, knowledgeFiles, setKnowledgeFiles,
    problemFile, setProblemFile, modelingDataFiles, setModelingDataFiles,
    modelingAttachments, setModelingAttachments, modelingPackage,
    modelingBusy, modelingError, inspectModelingPackage, saveModelingReview, resetModelingPackage,
    isRunning, status, logs, result, submit: submitAnalysis,
  } = analysis;
  const {
    selectedRunId, setSelectedRunId, detail: historyDetail, loadingRunId: historyLoadingRunId,
    qaQuestion, setQaQuestion, qaMode, setQaMode, qaSelected, setQaSelected,
    qaResult, qaLoading, ask: handleAskQuestion,
  } = history;

  const activeItem = NAV_ITEMS.find((item) => item.id === activeView) || NAV_ITEMS[0];
  const ActiveIcon = activeItem.icon;

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-is-collapsed" : ""}`}>
      <aside className={`sidebar ${mobileSidebarOpen ? "sidebar-open" : ""}`}>
        <div className="sidebar-top">
          <div className="brand">
            <span className="brand-mark">A</span>
            <div>
              <strong>Academic Data Agent</strong>
              <span>科研数据分析工作台</span>
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
          <button className="icon-button mobile-only" type="button" onClick={() => setMobileSidebarOpen(false)}>
            <X size={18} />
          </button>
        </div>

        <nav className="nav-list">
          {NAV_ITEMS.map((item) => {
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
                <span>
                  <Icon size={18} />
                </span>
                <strong>{item.label}</strong>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <span className={`status-dot ${status.state}`} />
          <p>{status.message}</p>
        </div>
      </aside>

      {mobileSidebarOpen && <button className="backdrop" type="button" onClick={() => setMobileSidebarOpen(false)} />}

      <main className="main-panel">
        <header className="topbar">
          <button className="icon-button mobile-only" type="button" onClick={() => setMobileSidebarOpen(true)}>
            <Menu size={20} />
          </button>
          <div className="topbar-title">
            <span className="topbar-icon">
              <ActiveIcon size={18} />
            </span>
            <div>
              <strong>{activeItem.label}</strong>
              <span>{activeView === "settings" ? "当前服务会话" : (form.outputDir || "outputs")}</span>
            </div>
          </div>
          {activeView !== "settings" && (
            <button
              className="secondary-button"
              type="button"
              onClick={() => refreshWorkspace()}
              disabled={workspaceLoading}
            >
              <RefreshCw className={workspaceLoading ? "spin" : ""} size={16} />
              {workspaceLoading ? "刷新中" : "刷新"}
            </button>
          )}
        </header>

        {workspaceError && <div className="error-banner">{workspaceError}</div>}

        <div className="view-stage" key={activeView}>
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
            workspaceLoading && !workspace ? (
              <ViewLoading message="正在加载知识库" />
            ) : (
              <KnowledgeView knowledgeBase={workspace?.knowledgeBase} />
            )
          )}
          {activeView === "settings" && <ModelSettingsView />}
        </div>
      </main>
    </div>
  );
}
