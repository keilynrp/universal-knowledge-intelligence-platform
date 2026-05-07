import { test, expect } from "@playwright/test";
import { injectAuth, mockUserMe, API_BASE } from "./helpers";

test.describe("Import / Export page", () => {
  test.beforeEach(async ({ page }) => {
    await injectAuth(page);
    await mockUserMe(page);
    await page.route(`${API_BASE}/**`, (route) => route.fulfill({ json: [] }));
  });

  test("renders the page heading", async ({ page }) => {
    await page.goto("/import-export");

    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 10_000,
    });
  });

  test("shows Import tab content", async ({ page }) => {
    await page.goto("/import-export");

    await expect(
      page.getByRole("heading", { name: "Importar Datos", exact: true })
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows Export section", async ({ page }) => {
    await page.goto("/import-export");

    await expect(
      page.getByRole("heading", { name: "Exportar Datos", exact: true })
    ).toBeVisible({ timeout: 10_000 });
  });
});
