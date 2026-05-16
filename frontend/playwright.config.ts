import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "html",
  use: {
    baseURL: "http://localhost:3004",
    channel: "chrome",
    trace: "on-first-retry",
    launchOptions: {
      args: [
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
      ],
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "node node_modules/next/dist/bin/next dev -p 3004 --webpack",
    url: "http://localhost:3004",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
