import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.tsx"],
    include: ["**/__tests__/**/*.{test,spec}.{ts,tsx}"],
    pool: "threads",
    maxWorkers: 2,
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      include: ["app/components/**", "app/contexts/**"],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
