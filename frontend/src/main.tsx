import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { AuthShell } from "./auth";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthShell>
      <App />
    </AuthShell>
  </StrictMode>,
);
