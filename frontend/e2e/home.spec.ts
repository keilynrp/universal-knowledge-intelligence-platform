import { test, expect } from "@playwright/test";
import { API_BASE, injectAuth, mockUserMe, mockHomeDashboard } from "./helpers";

test.describe("Home dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await injectAuth(page);
    await page.route(`${API_BASE}/**`, (route) => route.fulfill({ json: [] }));
    await mockUserMe(page);
    await mockHomeDashboard(page);
  });

  test("home page renders stat cards", async ({ page }) => {
    await page.goto("/");

    // Wait for the page to hydrate
    await expect(page.locator("h1")).toBeVisible({ timeout: 10_000 });

    await expect(page.getByText(/total de entidades/i)).toBeVisible();
    await expect(page.getByText(/pipeline ukip/i)).toBeVisible();
  });

  test("home page shows research intelligence heading", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", { name: "Inteligencia de Investigación", exact: true })
    ).toBeVisible({ timeout: 10_000 });
  });

  test("sidebar navigation links are visible", async ({ page }) => {
    await page.goto("/");

    // Sidebar should contain key navigation items
    await expect(page.getByRole("link", { name: /explorador de conocimiento/i }).first()).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByRole("link", { name: /asistente de importación/i }).first()).toBeVisible();
  });
});
