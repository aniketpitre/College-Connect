import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against the real backend and a seeded demo database:
 *   cd backend && MONGODB_DB=collegeconnect_e2e python -m scripts.seed_demo --erp
 *   cd frontend && MONGODB_DB=collegeconnect_e2e npx playwright test
 * E2E_PYTHON picks the Python that runs the backend; E2E_CHROMIUM uses an installed Chromium.
 */
export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  retries: 0,
  workers: 1,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
    launchOptions: process.env.E2E_CHROMIUM ? { executablePath: process.env.E2E_CHROMIUM } : {},
  },
  webServer: [
    {
      command: `${process.env.E2E_PYTHON ?? "python"} -m uvicorn app.main:app --port 8000`,
      cwd: "../backend",
      url: "http://localhost:8000/api/v1/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm run dev -- --port 5173 --strictPort",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
