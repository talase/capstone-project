/* ============================================================
   Aegis · Entry point
   ------------------------------------------------------------
   The first file the browser runs. It imports the global
   stylesheets (tokens then base), then mounts the React app into
   the #root element from index.html. The whole app is wrapped in
   ThemeProvider so every component can read the current theme,
   and StrictMode to surface potential bugs during development.
   ============================================================ */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./styles/tokens.css";
import "./styles/base.css";

import App from "./App";
import { ThemeProvider } from "./context/ThemeContext";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </StrictMode>
);
