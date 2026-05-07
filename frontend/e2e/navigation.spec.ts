import { test, expect } from "@playwright/test";
import { injectAuth, mockUserMe, mockHomeDashboard, mockExecutiveDashboard, API_BASE } from "./helpers";

test.describe("Sidebar navigation", () => {
  test.beforeEach(async ({ page }) => {
    await injectAuth(page);
    await page.route(`${API_BASE}/**`, (route) => {
      route.fulfill({ json: [] });
    });
    await mockUserMe(page);
    await mockHomeDashboard(page);
    await mockExecutiveDashboard(page);
  });

  test("navigates to Import/Export page", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.getByRole("link", { name: /sincronización de entidades/i }).first().click();
    await expect(page).toHaveURL(/import-export/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 10_000,
    });
  });

  test("navigates to Analytics page", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.locator('a[href="/analytics/dashboard"]').first().click();
    await expect(page).toHaveURL(/analytics\/dashboard/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 10_000,
    });
  });

  test("navigates to RAG Chat page", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.getByRole("link", { name: /respuestas/i }).first().click();
    await expect(page).toHaveURL(/rag/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 10_000,
    });
  });
});
