import { Activity, FileText, Inbox, Loader2, Upload, X } from "lucide-react";
import { formatBytes } from "../utils/formatters";

function StatCard({ label, value, icon: Icon = Activity }) {
  return (
    <article className="stat-card">
      <span className="stat-icon">
        <Icon size={18} />
      </span>
      <div>
        <span className="stat-label">{label}</span>
        <strong>{value}</strong>
      </div>
    </article>
  );
}

function ViewLoading({ message = "正在加载内容" }) {
  return (
    <div className="view-loading" role="status">
      <Loader2 className="spin" size={22} />
      <strong>{message}</strong>
      <span>请稍候，内容准备好后会自动显示。</span>
    </div>
  );
}

function FileInput({ label, description, accept, multiple = false, files, onChange, onClear }) {
  return (
    <div className="file-field">
      <label className="file-drop">
        <input
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={(event) => onChange(Array.from(event.target.files || []))}
        />
        <Upload size={18} />
        <span>{label}</span>
      </label>
      {files?.length > 0 ? (
        <div className="file-chips">
          {files.map((file) => (
            <span className="file-chip" key={`${file.name}-${file.size}-${file.lastModified}`}>
              <FileText size={14} />
              <strong title={file.name}>{file.name}</strong>
              <em>{formatBytes(file.size)}</em>
            </span>
          ))}
          <button className="icon-button subtle" type="button" onClick={onClear} title="清空文件">
            <X size={14} />
          </button>
        </div>
      ) : (
        <small>{description}</small>
      )}
    </div>
  );
}

function EmptyState({ title, description, icon: Icon = Inbox, action = null }) {
  return (
    <div className="empty-state">
      <span><Icon size={22} /></span>
      <strong>{title}</strong>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}

export { EmptyState, FileInput, StatCard, ViewLoading };
