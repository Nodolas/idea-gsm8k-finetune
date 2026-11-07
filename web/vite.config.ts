/// <reference types="vitest/config" />
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Vitest checks that jsdom is installed by resolving it from the project folder's parent chain,
// which reaches a package.json above this folder (rule 8: never read there) and fails on it.
// jsdom is a pinned devDependency here, so that check is skipped.
process.env.VITEST_SKIP_INSTALL_CHECKS ??= "1";

const webDir =fileURLToPath(new URL(".", import.meta.url));
const projectRoot = fileURLToPath(new URL("..", import.meta.url));
const srcDir = fileURLToPath(new URL("./src", import.meta.url));

export default defineConfig({
  root: webDir,
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": srcDir },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: false },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  test: {
    root: projectRoot,
    environment: "jsdom",
    globals: true,
    include: ["tests/web/**/*.test.{ts,tsx}"],
    setupFiles: ["web/src/test/setup.ts"],
    css: false,
  },
});
