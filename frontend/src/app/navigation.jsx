import { BarChart3, BookOpenCheck, Database, GitBranch, History, Play, Settings } from "lucide-react";

export const NAV_ITEMS = [
  { id: "analysis", label: "分析任务", description: "创建任务、检查资料并确认分析方案", icon: Play },
  { id: "results", label: "查看结果", description: "阅读报告、审计过程与下载产物", icon: BarChart3 },
  { id: "lineage", label: "血缘追溯", description: "追踪字段、执行证据与报告结论", icon: GitBranch },
  { id: "history", label: "历史追问", description: "回看已有任务并继续提问", icon: History },
  { id: "knowledge", label: "知识库", description: "管理通用分析使用的本地资料", icon: Database },
  { id: "settings", label: "模型设置", description: "配置当前会话使用的模型服务", icon: Settings },
];

export function getNavigationItems(scenario = "general") {
  return NAV_ITEMS.map((item) => (
    item.id === "knowledge" && scenario === "modeling"
      ? { ...item, label: "竞赛案例库", description: "浏览已审核案例、方法、结论与来源", icon: BookOpenCheck }
      : item
  ));
}
