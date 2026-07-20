import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import WorkspacePrototype from "./prototype/WorkspacePrototype.jsx";
import "./styles.css";
import "./prototype/workspace-prototype.css";

const prototypeVariant = new URLSearchParams(window.location.search).get("variant");

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    {prototypeVariant ? <WorkspacePrototype /> : <App />}
  </React.StrictMode>,
);
