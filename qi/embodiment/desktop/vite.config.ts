import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = dirname(fileURLToPath(import.meta.url));
const host = process.env.TAURI_DEV_HOST;
const pkgVersion = JSON.parse(
  readFileSync(resolve(rootDir, "package.json"), "utf-8"),
).version as string;

export default defineConfig({
  plugins: [vue()],
  clearScreen: false,
  define: {
    "import.meta.env.VITE_QI_VERSION": JSON.stringify(pkgVersion),
  },
  optimizeDeps: {
    include: ["three", "@pixiv/three-vrm"],
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(rootDir, "index.html"),
        pet: resolve(rootDir, "pet.html"),
      },
    },
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
