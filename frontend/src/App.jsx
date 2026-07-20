import WorkspaceShell from "./app/WorkspaceShell";
import { useWorkspaceController } from "./app/useWorkspaceController";

export default function App() {
  const controller = useWorkspaceController();
  return <WorkspaceShell controller={controller} />;
}
