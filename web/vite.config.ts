import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The agent API runs on 8001; proxying keeps the browser on one origin (no CORS).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8001",
    },
  },
});
