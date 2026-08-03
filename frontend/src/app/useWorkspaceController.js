import { useCallback, useEffect, useRef, useState } from "react";
import {
  askHistoryQuestion,
  createModelingPackage,
  fetchExperienceCase,
  fetchExperienceCases,
  fetchHistoryRun,
  fetchWorkspace,
  generateModelingPlan,
  startAnalysis,
  updateModelingPackage,
  updateModelingPlan,
} from "../api";
import { DEFAULT_FORM } from "./defaults";

export function useWorkspaceController() {
  const [activeView, setActiveView] = useState("analysis");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem("academic-agent-sidebar") === "collapsed";
    } catch {
      return false;
    }
  });
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [workspace, setWorkspace] = useState(null);
  const [workspaceError, setWorkspaceError] = useState("");
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [dataFile, setDataFile] = useState(null);
  const [knowledgeFiles, setKnowledgeFiles] = useState([]);
  const [problemFile, setProblemFile] = useState(null);
  const [modelingDataFiles, setModelingDataFiles] = useState([]);
  const [modelingAttachments, setModelingAttachments] = useState([]);
  const [modelingPackage, setModelingPackage] = useState(null);
  const [modelingBusy, setModelingBusy] = useState(false);
  const [modelingError, setModelingError] = useState("");
  const [caseLibrary, setCaseLibrary] = useState(null);
  const [caseLibraryDetail, setCaseLibraryDetail] = useState(null);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [caseLibraryLoading, setCaseLibraryLoading] = useState(false);
  const [caseLibraryError, setCaseLibraryError] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState({ state: "idle", message: "等待任务开始" });
  const [logs, setLogs] = useState([]);
  const [result, setResult] = useState(null);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [historyDetail, setHistoryDetail] = useState(null);
  const [historyLoadingRunId, setHistoryLoadingRunId] = useState("");
  const [qaQuestion, setQaQuestion] = useState("");
  const [qaMode, setQaMode] = useState("single");
  const [qaSelected, setQaSelected] = useState([]);
  const [qaResult, setQaResult] = useState(null);
  const [qaLoading, setQaLoading] = useState(false);
  const workspaceRequestRef = useRef(0);
  const historyRequestRef = useRef(0);
  const caseRequestRef = useRef(0);

  useEffect(() => {
    try {
      window.localStorage.setItem("academic-agent-sidebar", sidebarCollapsed ? "collapsed" : "expanded");
    } catch {
      // The workspace remains usable when storage is blocked.
    }
  }, [sidebarCollapsed]);

  const refreshWorkspace = useCallback(
    async (outputDir = form.outputDir) => {
      const requestId = ++workspaceRequestRef.current;
      setWorkspaceLoading(true);
      try {
        const payload = await fetchWorkspace(outputDir || "outputs");
        if (requestId !== workspaceRequestRef.current) return null;
        setWorkspace(payload);
        setWorkspaceError("");
        setSelectedRunId((current) =>
          payload.historyRuns?.some((run) => run.runId === current) ? current : payload.selectedRunId || "",
        );
        setQaSelected((current) =>
          current.length || !payload.historyQaRuns?.length ? current : [payload.historyQaRuns[0].runId],
        );
        return payload;
      } catch (error) {
        if (requestId !== workspaceRequestRef.current) return null;
        setWorkspaceError(error instanceof Error ? error.message : "工作台加载失败。");
        return null;
      } finally {
        if (requestId === workspaceRequestRef.current) setWorkspaceLoading(false);
      }
    },
    [form.outputDir],
  );

  const loadHistoryDetail = useCallback(
    async (runId) => {
      if (!runId) return;
      const requestId = ++historyRequestRef.current;
      setHistoryLoadingRunId(runId);
      setHistoryDetail(null);
      try {
        const payload = await fetchHistoryRun(runId, form.outputDir || "outputs");
        if (requestId !== historyRequestRef.current) return;
        setHistoryDetail(payload);
      } catch (error) {
        if (requestId !== historyRequestRef.current) return;
        setHistoryDetail({
          runId,
          reportMarkdown: `## 历史记录加载失败\n\n${error instanceof Error ? error.message : "未知错误"}`,
        });
      } finally {
        if (requestId === historyRequestRef.current) setHistoryLoadingRunId("");
      }
    },
    [form.outputDir],
  );

  useEffect(() => {
    refreshWorkspace();
  }, [refreshWorkspace]);

  useEffect(() => {
    if (
      ["history", "lineage"].includes(activeView)
      && selectedRunId
      && historyDetail?.runId !== selectedRunId
      && historyLoadingRunId !== selectedRunId
    ) {
      loadHistoryDetail(selectedRunId);
    }
  }, [activeView, historyDetail, historyLoadingRunId, loadHistoryDetail, selectedRunId]);

  const selectExperienceCase = useCallback(async (caseId) => {
    if (!caseId) return;
    const requestId = ++caseRequestRef.current;
    setSelectedCaseId(caseId);
    setCaseLibraryDetail(null);
    setCaseLibraryLoading(true);
    try {
      const payload = await fetchExperienceCase(caseId);
      if (requestId !== caseRequestRef.current) return;
      setCaseLibraryDetail(payload);
      setCaseLibraryError("");
    } catch (error) {
      if (requestId !== caseRequestRef.current) return;
      setCaseLibraryError(error instanceof Error ? error.message : "案例详情加载失败");
    } finally {
      if (requestId === caseRequestRef.current) setCaseLibraryLoading(false);
    }
  }, []);

  const refreshCaseLibrary = useCallback(async () => {
    const requestId = ++caseRequestRef.current;
    setCaseLibraryLoading(true);
    try {
      const payload = await fetchExperienceCases();
      if (requestId !== caseRequestRef.current) return;
      setCaseLibrary(payload);
      setCaseLibraryError("");
      const nextId = payload.cases?.some((item) => item.id === selectedCaseId)
        ? selectedCaseId
        : payload.cases?.[0]?.id || "";
      setSelectedCaseId(nextId);
      if (nextId) {
        const detail = await fetchExperienceCase(nextId);
        if (requestId !== caseRequestRef.current) return;
        setCaseLibraryDetail(detail);
      } else {
        setCaseLibraryDetail(null);
      }
    } catch (error) {
      if (requestId !== caseRequestRef.current) return;
      setCaseLibraryError(error instanceof Error ? error.message : "竞赛案例库加载失败");
    } finally {
      if (requestId === caseRequestRef.current) setCaseLibraryLoading(false);
    }
  }, [selectedCaseId]);

  useEffect(() => {
    if (form.scenario === "modeling" && activeView === "knowledge" && !caseLibrary && !caseLibraryLoading) {
      refreshCaseLibrary();
    }
  }, [activeView, caseLibrary, caseLibraryLoading, form.scenario, refreshCaseLibrary]);

  const submitAnalysis = async (event) => {
    event.preventDefault();
    if (!dataFile || isRunning) return;

    const formData = new FormData();
    formData.append("data_file", dataFile);
    formData.append("scenario", form.scenario);
    formData.append("query", form.query);
    formData.append("output_dir", form.outputDir || "outputs");
    formData.append("agent_name", form.agentName);
    formData.append("env_file", form.envFile);
    formData.append("session_label", form.sessionLabel);
    formData.append("memory_scope_label", form.memoryScopeLabel);
    knowledgeFiles.forEach((file) => formData.append("knowledge_uploads", file));

    setIsRunning(true);
    setActiveView("results");
    setLogs([]);
    setResult(null);
    setStatus({ state: "starting", message: "正在启动分析任务" });

    try {
      await startAnalysis(formData, ({ event: eventName, data }) => {
        if (eventName === "status") {
          setStatus({ state: data.state || "running", message: data.message || "任务运行中" });
          setLogs(data.logs || []);
        } else if (eventName === "log") {
          setStatus({ state: "running", message: data.message || "任务运行中" });
          setLogs(data.logs || []);
        } else if (eventName === "result") {
          setStatus({ state: "success", message: data.message || "分析完成" });
          setLogs(data.logs || []);
          setResult(data.result);
          if (data.workspace) {
            setWorkspace(data.workspace);
            if (data.workspace.selectedRunId) {
              setSelectedRunId(data.workspace.selectedRunId);
            }
          }
        } else if (eventName === "error") {
          setStatus({ state: "error", message: data.message || "分析失败" });
          setLogs(data.logs || []);
        }
      });
      await refreshWorkspace(form.outputDir || "outputs");
    } catch (error) {
      setStatus({ state: "error", message: error instanceof Error ? error.message : "分析失败" });
    } finally {
      setIsRunning(false);
    }
  };

  const inspectModelingPackage = async () => {
    if (!problemFile || !modelingDataFiles.length || modelingBusy) return;
    const formData = new FormData();
    formData.append("problem_file", problemFile);
    modelingDataFiles.forEach((file) => formData.append("data_files", file));
    modelingAttachments.forEach((file) => formData.append("attachments", file));
    setModelingBusy(true);
    setModelingError("");
    setModelingPackage(null);
    try {
      const payload = await createModelingPackage(formData);
      setModelingPackage(payload);
    } catch (error) {
      setModelingError(error instanceof Error ? error.message : "赛题资料识别失败");
    } finally {
      setModelingBusy(false);
    }
  };

  const saveModelingReview = async (corrections) => {
    if (!modelingPackage?.packageId || modelingBusy) return;
    setModelingBusy(true);
    setModelingError("");
    try {
      const payload = await updateModelingPackage(modelingPackage.packageId, corrections);
      setModelingPackage(payload);
      if (payload.status === "confirmed") {
        const planned = await generateModelingPlan(payload.packageId, form.query);
        setModelingPackage(planned);
      }
    } catch (error) {
      setModelingError(error instanceof Error ? error.message : "资料包修正保存失败");
    } finally {
      setModelingBusy(false);
    }
  };

  const saveModelingPlanReview = async (corrections) => {
    if (!modelingPackage?.packageId || modelingBusy) return;
    setModelingBusy(true);
    setModelingError("");
    try {
      const payload = await updateModelingPlan(modelingPackage.packageId, corrections);
      setModelingPackage(payload);
    } catch (error) {
      setModelingError(error instanceof Error ? error.message : "分析方案保存失败");
    } finally {
      setModelingBusy(false);
    }
  };

  const resetModelingPackage = () => {
    setModelingPackage(null);
    setModelingError("");
  };

  const handleAskQuestion = async () => {
    if (!qaQuestion.trim()) return;
    setQaLoading(true);
    setQaResult(null);
    try {
      const payload = await askHistoryQuestion({
        question: qaQuestion,
        selectedRunIds: qaSelected,
        mode: qaMode,
        outputDir: form.outputDir || "outputs",
        envFile: form.envFile,
      });
      setQaResult(payload);
    } catch (error) {
      setQaResult({
        answerMarkdown: `## 历史追问失败\n\n${error instanceof Error ? error.message : "未知错误"}`,
        sources: [],
        warnings: [],
      });
    } finally {
      setQaLoading(false);
    }
  };

  return {
    navigation: { activeView, setActiveView, sidebarCollapsed, setSidebarCollapsed, mobileSidebarOpen, setMobileSidebarOpen },
    workspace: { data: workspace, error: workspaceError, loading: workspaceLoading, refresh: refreshWorkspace },
    analysis: {
      form, setForm, dataFile, setDataFile, knowledgeFiles, setKnowledgeFiles,
      problemFile, setProblemFile, modelingDataFiles, setModelingDataFiles,
      modelingAttachments, setModelingAttachments, modelingPackage,
      modelingBusy, modelingError, inspectModelingPackage, saveModelingReview, saveModelingPlanReview, resetModelingPackage,
      isRunning, status, logs, result, submit: submitAnalysis,
    },
    history: {
      selectedRunId, setSelectedRunId, detail: historyDetail, loadingRunId: historyLoadingRunId,
      qaQuestion, setQaQuestion, qaMode, setQaMode, qaSelected, setQaSelected,
      qaResult, qaLoading, ask: handleAskQuestion,
    },
    caseLibrary: {
      data: caseLibrary,
      detail: caseLibraryDetail,
      selectedCaseId,
      loading: caseLibraryLoading,
      error: caseLibraryError,
      select: selectExperienceCase,
      refresh: refreshCaseLibrary,
    },
  };
}
