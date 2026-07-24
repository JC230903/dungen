import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev-time proxy: the frontend talks to axios baseURL "/api", Vite forwards
// it to the FastAPI backend on :8000 so there's no CORS dance during
// `npm run dev`. In production, set VITE_API_BASE to wherever the backend
// actually lives instead.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
