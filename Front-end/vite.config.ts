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
        "/files": { target: backend, changeOrigin: true },
      },
    },
  };
});
