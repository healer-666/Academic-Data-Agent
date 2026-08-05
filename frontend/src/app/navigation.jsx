import { Library, SquarePen, Settings } from "lucide-react";

export const NAV_ITEMS = [
  { id: "analysis", label: "新建分析", description: "开始一个新的分析任务", icon: SquarePen },
  { id: "knowledge", label: "资料库", description: "查看通用资料与竞赛案例", icon: Library },
  { id: "settings", label: "模型设置", description: "配置当前会话使用的模型服务", icon: Settings },
];

export function getNavigationItems() {
  return NAV_ITEMS;
}
