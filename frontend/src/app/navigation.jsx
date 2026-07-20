import { BarChart3, Database, GitBranch, History, Play } from "lucide-react";

export const NAV_ITEMS = [
  { id: "analysis", label: "分析任务", icon: Play },
  { id: "results", label: "查看结果", icon: BarChart3 },
  { id: "lineage", label: "血缘追溯", icon: GitBranch },
  { id: "history", label: "历史追问", icon: History },
  { id: "knowledge", label: "知识库", icon: Database },
];
