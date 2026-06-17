import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import path from "path"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: process.env["VITE_BASE"] ?? "/",
  resolve: {
    alias: {
      "@ei-fe/core": path.resolve(__dirname, "../core/src"),
      "@ei-fe/api": path.resolve(__dirname, "../api/src"),
      "@ei-fe/ui": path.resolve(__dirname, "../ui/src"),
      "@ei-fe/features": path.resolve(__dirname, "../features/src"),
    },
  },
  build: {
    target: "es2022",
  },
  server: {
    watch: {
      usePolling: true,
      interval: 300,
    },
    proxy: {
      "/api/v1": {
        target: process.env["VITE_BACKEND_URL"] ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
})
