import { useEffect, useState } from "react";
import { CheckCircle2, KeyRound, Loader2, PlugZap, RotateCcw, Save, ShieldCheck } from "lucide-react";
import {
  clearModelSettings,
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

export default function ModelSettingsView({ status, loading, loadError, onRefresh, onStatusChange }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [action, setAction] = useState("");
  const [message, setMessage] = useState(null);

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  useEffect(() => {
    if (!status) return;
    setForm((current) => ({
      ...current,
      modelId: current.modelId || status.modelId || "",
      baseUrl: current.baseUrl || status.baseUrl || "",
    }));
  }, [status]);

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
      onStatusChange(payload);
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
        await onRefresh();
      }
    } catch (error) {
      setMessage({ type: "error", text: error.message });
      if (!form.apiKey && status?.source === "web") {
        onRefresh();
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
      onStatusChange(payload);
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
    <section className="model-settings-page">
      <aside className="settings-navigation">
        <h1>设置</h1>
        <button className="active" type="button">模型服务</button>
      </aside>

      <main className="settings-content">
        <header className="settings-intro">
          <h2>模型服务</h2>
          <p>配置当前会话使用的兼容模型接口。</p>
        </header>

        <section className="settings-status-section">
          <div>
            {status?.configured ? <CheckCircle2 size={19} /> : <ShieldCheck size={19} />}
            <span><small>当前配置</small><strong>{loading ? "正在检查…" : statusLabel(status)}</strong></span>
          </div>
          {status?.connectionStatus === "connected" && <span className="status-pill success">连接正常</span>}
          {status?.connectionStatus === "failed" && <span className="status-pill error">连接失败</span>}
        </section>

        {loadError && !message && <div className="settings-message error" role="alert"><ShieldCheck size={17} /><span>{loadError}</span></div>}

        <form className="model-settings-form" onSubmit={handleSave}>
          <div className="settings-section-heading"><h3>接口配置</h3><p>支持 OpenAI 兼容接口及项目已有的 Anthropic Messages 兼容地址。</p></div>
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
              保存
            </button>
            <button className="secondary-button" type="button" onClick={handleTest} disabled={Boolean(action)}>
              {action === "test" ? <Loader2 className="spin" size={17} /> : <PlugZap size={17} />}
              测试连接
            </button>
            {status?.source === "web" && (
              <button className="text-button" type="button" onClick={handleClear} disabled={Boolean(action)}>
                {action === "clear" ? <Loader2 className="spin" size={16} /> : <RotateCcw size={16} />}
                恢复环境配置
              </button>
            )}
          </div>
        </form>

        <section className="settings-security-note">
          <ShieldCheck size={18} />
          <div><strong>密钥保护</strong><p>API Key 仅保存在当前后端进程内存中，不会写入项目文件、日志或报告。</p></div>
        </section>
      </main>
    </section>
  );
}
