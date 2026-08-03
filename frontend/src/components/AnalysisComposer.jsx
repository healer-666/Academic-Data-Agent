import { useRef } from "react";
import { ArrowUp, FileSpreadsheet, FileText, Loader2, Paperclip, X } from "lucide-react";
import { formatBytes } from "../utils/formatters";

function FilePickerMenu({ groups, disabled }) {
  const detailsRef = useRef(null);

  return (
    <details className="file-picker-menu" ref={detailsRef}>
      <summary className="composer-tool-button" aria-label="添加文件" title="添加文件">
        <Paperclip size={18} />
        <span>添加文件</span>
      </summary>
      <div className="file-picker-popover">
        {groups.map((group) => (
          <label key={group.id} className="file-picker-option">
            {group.id.includes("data") ? <FileSpreadsheet size={17} /> : <FileText size={17} />}
            <span>
              <strong>{group.label}</strong>
              <small>{group.hint}</small>
            </span>
            <input
              type="file"
              accept={group.accept}
              multiple={group.multiple}
              disabled={disabled}
              onChange={(event) => {
                group.onSelect(Array.from(event.target.files || []));
                event.target.value = "";
                detailsRef.current?.removeAttribute("open");
              }}
            />
          </label>
        ))}
      </div>
    </details>
  );
}

function FileAttachmentList({ groups }) {
  const attachments = groups.flatMap((group) => (
    (group.files || []).map((file, index) => ({ file, index, group }))
  ));

  if (!attachments.length) return null;

  return (
    <div className="attachment-list" aria-label="已添加文件">
      {attachments.map(({ file, index, group }) => (
        <div className="attachment-row" key={`${group.id}-${file.name}-${file.size}-${file.lastModified}`}>
          <span className="attachment-file-icon" aria-hidden="true">
            {group.id.includes("data") ? <FileSpreadsheet size={17} /> : <FileText size={17} />}
          </span>
          <strong title={file.name}>{file.name}</strong>
          <span className="attachment-kind">{group.shortLabel || group.label}</span>
          <span className="attachment-size">{formatBytes(file.size)}</span>
          <span className="attachment-status">已添加</span>
          <button type="button" className="icon-button subtle" onClick={() => group.onRemove(index)} aria-label={`移除 ${file.name}`}>
            <X size={15} />
          </button>
        </div>
      ))}
    </div>
  );
}

export default function AnalysisComposer({
  value,
  onChange,
  placeholder,
  fileGroups,
  disabled,
  busy,
  actionLabel,
  busyLabel,
  onSubmit,
}) {
  const fileCount = fileGroups.reduce((total, group) => total + (group.files?.length || 0), 0);

  const handleKeyDown = (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && !disabled) {
      event.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className={`analysis-composer ${busy ? "is-busy" : ""}`}>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={5}
        aria-label="分析问题"
      />
      <FileAttachmentList groups={fileGroups} />
      <div className="composer-footer">
        <div className="composer-tools">
          <FilePickerMenu groups={fileGroups} disabled={busy} />
          {fileCount > 0 && <span className="attachment-count">{fileCount} 个文件</span>}
        </div>
        <div className="composer-submit-group">
          <span className="shortcut-hint">Ctrl ↵</span>
          <button
            type="button"
            className="composer-submit"
            disabled={disabled}
            onClick={onSubmit}
            aria-label={busy ? busyLabel : actionLabel}
            title={busy ? busyLabel : actionLabel}
          >
            {busy ? <Loader2 className="spin" size={18} /> : <ArrowUp size={19} />}
          </button>
        </div>
      </div>
    </div>
  );
}

export { FileAttachmentList, FilePickerMenu };
