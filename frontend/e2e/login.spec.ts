import { test, expect } from "@playwright/test";
import { API_BASE, MOCK_TOKEN, MOCK_USER } from "./helpers";

test.describe("Login flow", () => {
  const usernameInput = (page: import("@playwright/test").Page) => page.getByPlaceholder(/superadmin/i);
  const passwordInput = (page: import("@playwright/test").Page) => page.getByPlaceholder(/min\.?\s*8 caracteres/i);
  const submitButton = (page: import("@playwright/test").Page) => page.getByRole("button", { name: /entrar a ukip/i });

  test.beforeEach(async ({ page }) => {
    // Ensure no stored token so we land on the login page
    await page.addInitScript(() => localStorage.clear());
  });

  test("login page renders username and password inputs", async ({ page }) => {
    // Mock /users/me to return 401 so AuthContext treats user as unauthenticated
    await page.route(`${API_BASE}/users/me`, (route) =>
      route.fulfill({ status: 401, json: { detail: "Not authenticated" } })
    );

    await page.goto("/login");

    await expect(usernameInput(page)).toBeVisible();
    await expect(passwordInput(page)).toBeVisible();
    await expect(submitButton(page)).toBeVisible();
  });

  test("successful login redirects to home", async ({ page }) => {
    await page.route(`${API_BASE}/**`, (route) => route.fulfill({ json: [] }));
    await page.route(`${API_BASE}/auth/token`, (route) =>
      route.fulfill({
        json: { access_token: MOCK_TOKEN, token_type: "bearer" },
      })
    );
    await page.route(`${API_BASE}/users/me`, (route) =>
      route.fulfill({ json: MOCK_USER })
    );
    // Mock home page endpoints
    await page.route(`${API_BASE}/stats`, (route) =>
      route.fulfill({ json: { total_entities: 0, indexed: 0, enriched: 0 } })
    );
    await page.route(`${API_BASE}/enrich/stats`, (route) =>
      route.fulfill({ json: { total: 0, enriched: 0, pending: 0, failed: 0 } })
    );
    await page.route(`${API_BASE}/domains`, (route) =>
      route.fulfill({ json: [] })
    );
    await page.route(`${API_BASE}/demo/status`, (route) =>
      route.fulfill({ json: { demo_active: false, demo_entity_count: 0 } })
    );
    await page.route(`${API_BASE}/brands**`, (route) =>
      route.fulfill({ json: [] })
    );
    await page.route(`${API_BASE}/rag/stats`, (route) =>
      route.fulfill({ json: { total_indexed: 0 } })
    );

    await page.goto("/login");

    await usernameInput(page).fill("admin");
    await passwordInput(page).fill("password");
    await submitButton(page).click();

    await expect(page).toHaveURL("/");
  });

  test("invalid credentials show error message", async ({ page }) => {
    await page.route(`${API_BASE}/auth/token`, (route) =>
      route.fulfill({ status: 401, json: { detail: "Incorrect credentials" } })
    );
    await page.route(`${API_BASE}/users/me`, (route) =>
      route.fulfill({ status: 401, json: { detail: "Not authenticated" } })
    );

    await page.goto("/login");

    await usernameInput(page).fill("wrong");
    await passwordInput(page).fill("wrong");
    await submitButton(page).click();

    await expect(
      page.getByText(/invalid username or password/i)
    ).toBeVisible();
  });
});
