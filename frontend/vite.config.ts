import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      // dev-mode parity with the nginx proxy in the container
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
