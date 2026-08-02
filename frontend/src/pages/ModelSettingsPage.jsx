import { useEffect, useState } from "react";
import { CheckCircle2, KeyRound, Loader2, PlugZap, RotateCcw, Save, ShieldCheck } from "lucide-react";
import {
  clearModelSettings,
  fetchModelSettings,
  saveModelSettings,
  testModelConnection,
} from "../api";

const EMPTY_FORM = {
  modelId: "",
  baseUrl: "",
  apiKey: "",
  timeout: 120,
};

function statusLabel(status) {
  if (status?.source === "web") return "本次服务会话配置";
  if (status?.source === "environment") return "环境文件配置";
  return "尚未配置";
}

export default function ModelSettingsView() {
  const [form, setForm] = useState(EMPTY_FORM);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState("");
  const [message, setMessage] = useState(null);

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  useEffect(() => {
    let active = true;
    fetchModelSettings()
      .then((payload) => {
        if (!active) return;
        setStatus(payload);
        setForm((current) => ({
          ...current,
          modelId: current.modelId || payload.modelId || "",
          baseUrl: current.baseUrl || payload.baseUrl || "",
        }));
      })
      .catch((error) => active && setMessage({ type: "error", text: error.message }))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  const payloadFromForm = () => ({
    modelId: form.modelId.trim(),
    baseUrl: form.baseUrl.trim(),
    apiKey: form.apiKey,
    timeout: Number(form.timeout) || 120,
  });

  const handleSave = async (event) => {
    event.preventDefault();
    setAction("save");
    setMessage(null);
    try {
      const payload = await saveModelSettings(payloadFromForm());
      setStatus(payload);
      setForm((current) => ({ ...current, apiKey: "" }));
      setMessage({ type: "success", text: "已保存到当前服务会话；密钥不会写入项目文件。" });
    } catch (error) {
      setMessage({ type: "error", text: error.message });
    } finally {
      setAction("");
    }
  };

  const handleTest = async () => {
    setAction("test");
    setMessage(null);
    try {
      const useSavedSettings = !form.apiKey && status?.source === "web";
      const payload = await testModelConnection(useSavedSettings ? null : payloadFromForm());
      setMessage({ type: "success", text: payload.message });
      if (useSavedSettings) {
        setStatus(await fetchModelSettings());
      }
    } catch (error) {
      setMessage({ type: "error", text: error.message });
      if (!form.apiKey && status?.source === "web") {
        fetchModelSettings().then(setStatus).catch(() => {});
      }
    } finally {
      setAction("");
    }
  };

  const handleClear = async () => {
    setAction("clear");
    setMessage(null);
    try {
      const payload = await clearModelSettings();
      setStatus(payload);
      setForm({
        ...EMPTY_FORM,
        modelId: payload.modelId || "",
        baseUrl: payload.baseUrl || "",
      });
      setMessage({ type: "success", text: "已清除网页会话配置，后续分析将继续使用环境文件。" });
    } catch (error) {
      setMessage({ type: "error", text: error.message });
    } finally {
      setAction("");
    }
  };

  return (
    <section className="view-stack model-settings-page">
      <div className="settings-intro">
        <span className="kicker">Model Connection</span>
        <h1>连接你的模型服务</h1>
        <p>在网页中设置兼容的模型接口。配置仅保存在当前后端进程内存中，服务重启后会自动清除。</p>
      </div>

      <div className={`model-status-card ${status?.configured ? "configured" : ""}`}>
        <span className="model-status-icon">
          {status?.configured ? <CheckCircle2 size={22} /> : <ShieldCheck size={22} />}
        </span>
        <div>
          <small>当前来源</small>
          <strong>{loading ? "正在检查…" : statusLabel(status)}</strong>
          <p>{status?.message || "正在读取安全配置状态。"}</p>
        </div>
        {status?.connectionStatus === "connected" && <span className="status-pill success">连接正常</span>}
        {status?.connectionStatus === "failed" && <span className="status-pill error">连接失败</span>}
      </div>

      <form className="panel model-settings-form" onSubmit={handleSave}>
        <header className="section-header">
          <h2>模型 API</h2>
          <p>支持 OpenAI 兼容接口及项目已有的 Anthropic Messages 兼容地址。</p>
        </header>

        <div className="settings-fields">
          <label className="field">
            <span>模型名称</span>
            <input
              value={form.modelId}
              onChange={(event) => update("modelId", event.target.value)}
              placeholder="例如 gpt-4.1-mini"
              autoComplete="off"
            />
          </label>
          <label className="field">
            <span>请求超时（秒）</span>
            <input
              type="number"
              min="10"
              max="600"
              value={form.timeout}
              onChange={(event) => update("timeout", event.target.value)}
              inputMode="numeric"
            />
          </label>
          <label className="field field-wide">
            <span>Base URL</span>
            <input
              type="url"
              value={form.baseUrl}
              onChange={(event) => update("baseUrl", event.target.value)}
              placeholder="https://api.example.com/v1"
              autoComplete="url"
            />
          </label>
          <label className="field field-wide">
            <span>API Key</span>
            <div className="secret-field">
              <KeyRound size={17} />
              <input
                type="password"
                value={form.apiKey}
                onChange={(event) => update("apiKey", event.target.value)}
                placeholder={status?.source === "web" ? "已安全保存；留空可测试现有连接" : "输入 API Key"}
                autoComplete="new-password"
              />
            </div>
          </label>
        </div>

        {message && (
          <div className={`settings-message ${message.type}`} role="status">
            {message.type === "success" ? <CheckCircle2 size={17} /> : <ShieldCheck size={17} />}
            <span>{message.text}</span>
          </div>
        )}

        <div className="settings-actions">
          <button className="primary-button" type="submit" disabled={Boolean(action)}>
            {action === "save" ? <Loader2 className="spin" size={17} /> : <Save size={17} />}
            保存到本次会话
          </button>
          <button className="secondary-button" type="button" onClick={handleTest} disabled={Boolean(action)}>
            {action === "test" ? <Loader2 className="spin" size={17} /> : <PlugZap size={17} />}
            测试连接
          </button>
          {status?.source === "web" && (
            <button className="text-button" type="button" onClick={handleClear} disabled={Boolean(action)}>
              {action === "clear" ? <Loader2 className="spin" size={16} /> : <RotateCcw size={16} />}
              恢复环境文件配置
            </button>
          )}
        </div>
      </form>

      <aside className="settings-security-note">
        <ShieldCheck size={18} />
        <div>
          <strong>密钥保护</strong>
          <p>API Key 不会出现在状态接口、分析日志、报告、下载文件或版本控制中。连接测试也不会启动分析任务。</p>
        </div>
      </aside>
    </section>
  );
}
