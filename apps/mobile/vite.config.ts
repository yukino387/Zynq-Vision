import { defineConfig } from "vite";
import uni from "@dcloudio/vite-plugin-uni";
const plugin = uni as unknown as
  { default: () => import("vite").Plugin[] } | (() => import("vite").Plugin[]);
export default defineConfig({
  plugins: [typeof plugin === "function" ? plugin() : plugin.default()],
  optimizeDeps: { exclude: ["@vision/shared"] },
  server: {
    port: 5174,
    host: "0.0.0.0",
    proxy: {
      "/api": "http://localhost:3000",
      "/ws": { target: "ws://localhost:3000", ws: true },
    },
  },
  base: "/mobile/",
});
