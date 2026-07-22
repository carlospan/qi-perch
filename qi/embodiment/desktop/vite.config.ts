import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const host = process.env.TAURI_DEV_HOST;

/** 强制单一 @pixi/* 实例，避免 Live2DModel 落在 Container2 上导致永不 _render */
const pixiPackages = [
  "pixi.js",
  "@pixi/app",
  "@pixi/constants",
  "@pixi/core",
  "@pixi/display",
  "@pixi/extensions",
  "@pixi/loaders",
  "@pixi/math",
  "@pixi/runner",
  "@pixi/settings",
  "@pixi/sprite",
  "@pixi/ticker",
  "@pixi/utils",
];

export default defineConfig({
  plugins: [vue()],
  clearScreen: false,
  resolve: {
    dedupe: pixiPackages,
  },
  optimizeDeps: {
    // 不预打包 live2d，让它直接吃到与 pixi.js 同一份 @pixi/*
    exclude: ["pixi-live2d-display"],
    include: pixiPackages,
  },
  server: {
    port: 5173,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 5174,
        }
      : undefined,
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
});
