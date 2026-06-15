import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
//
// In development the browser talks only to this Vite server, which proxies the
// backend API paths to the FastAPI app (default http://localhost:8000). This
// avoids CORS entirely WITHOUT changing the backend. Override the target with
// VITE_BACKEND_URL in a local .env if the backend runs on another host/port.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backend = env.VITE_BACKEND_URL || "http://localhost:8000";

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/personal-context": { target: backend, changeOrigin: true },
        "^/api/contacts(?:/[^/?]+)?$": {
          target: backend,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
        "^/api/action-settings(?:/[^/?]+)?(?:\\?.*)?$": {
          target: backend,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
        "^/api/message-history(?:\\?.*)?$": {
          target: backend,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
        "^/api/dashboard-approvals(?:/[^/?]+)?(?:\\?.*)?$": {
          target: backend,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
        "^/api/dashboard-summary(?:\\?.*)?$": {
          target: backend,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
        "^/files/upload-dashboard$": { target: backend, changeOrigin: true },
        "^/files/dashboard-uploads$": { target: backend, changeOrigin: true },
        "^/files/dashboard-download(?:\\?.*)?$": {
          target: backend,
          changeOrigin: true,
        },
        "^/files/dashboard-upload(?:\\?.*)?$": {
          target: backend,
          changeOrigin: true,
        },
      },
    },
  };
});
