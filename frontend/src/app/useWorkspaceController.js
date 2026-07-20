import { useCallback, useEffect, useRef, useState } from "react";
import { askHistoryQuestion, fetchHistoryRun, fetchWorkspace, startAnalysis } from "../api";
import { DEFAULT_FORM } from "./defaults";

export function useWorkspaceController() {
  const [activeView, setActiveView] = useState("analysis");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [workspace, setWorkspace] = useState(null);
  const [workspaceError, setWorkspaceError] = useState("");
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [dataFile, setDataFile] = useState(null);
  const [knowledgeFiles, setKnowledgeFiles] = useState([]);
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

  const submitAnalysis = async (event) => {
    event.preventDefault();
    if (!dataFile || isRunning) return;

    const formData = new FormData();
    formData.append("data_file", dataFile);
    formData.append("query", form.query);
    formData.append("quality_mode", form.qualityMode);
    formData.append("latency_mode", form.latencyMode);
    formData.append("vision_review_mode", form.visionReviewMode);
    formData.append("max_steps", form.maxSteps);
    formData.append("max_reviews", form.maxReviews);
    formData.append("vision_max_images", form.visionMaxImages);
    formData.append("vision_max_image_side", form.visionMaxImageSide);
    formData.append("output_dir", form.outputDir || "outputs");
    formData.append("agent_name", form.agentName);
    formData.append("env_file", form.envFile);
    formData.append("session_label", form.sessionLabel);
    formData.append("use_rag", String(form.useRag));
    formData.append("use_memory", String(form.useMemory));
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
      isRunning, status, logs, result, submit: submitAnalysis,
    },
    history: {
      selectedRunId, setSelectedRunId, detail: historyDetail, loadingRunId: historyLoadingRunId,
      qaQuestion, setQaQuestion, qaMode, setQaMode, qaSelected, setQaSelected,
      qaResult, qaLoading, ask: handleAskQuestion,
    },
  };
}
