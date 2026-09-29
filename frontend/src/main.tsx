import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { AppErrorBoundary } from "./components/errors/AppErrorBoundary";
import { GlobalErrorProvider } from "./components/errors/GlobalErrorProvider";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppErrorBoundary>
      <GlobalErrorProvider>
        <App />
      </GlobalErrorProvider>
    </AppErrorBoundary>
  </StrictMode>,
);

