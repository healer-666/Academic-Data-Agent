import { Inbox, Loader2 } from "lucide-react";

function ViewLoading({ message = "正在加载内容" }) {
  return (
    <div className="view-loading" role="status">
      <Loader2 className="spin" size={22} />
      <strong>{message}</strong>
      <span>请稍候，内容准备好后会自动显示。</span>
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

export { EmptyState, ViewLoading };
