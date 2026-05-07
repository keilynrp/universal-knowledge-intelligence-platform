import { Page } from "@playwright/test";

export const API_BASE = "**/api/backend";

export const MOCK_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJzdXBlcl9hZG1pbiJ9.mock";

export const MOCK_USER = {
  id: 1,
  username: "admin",
  email: "admin@ukip.local",
  role: "super_admin",
  is_active: true,
};

/** Inject a valid auth token directly into localStorage so tests skip login. */
export async function injectAuth(page: Page) {
  await page.addInitScript((token) => {
    localStorage.setItem("ukip_token", token);
    localStorage.setItem("ukip_welcomed_v1", "1");
    localStorage.setItem("ukip_persona_v1", "research");
  }, MOCK_TOKEN);
  await page.goto("/login");
  await page.evaluate((token) => {
    localStorage.setItem("ukip_token", token);
    localStorage.setItem("ukip_welcomed_v1", "1");
    localStorage.setItem("ukip_persona_v1", "research");
  }, MOCK_TOKEN);
}

/** Mock the /users/me endpoint (called on hydration and after login). */
export async function mockUserMe(page: Page) {
  await page.route(`${API_BASE}/users/me`, (route) =>
    route.fulfill({ json: MOCK_USER })
  );
}

/** Mock minimal home-page endpoints so the dashboard renders without a backend. */
export async function mockHomeDashboard(page: Page) {
  await page.route(`${API_BASE}/stats`, (route) =>
    route.fulfill({ json: { total_entities: 120, indexed: 95, enriched: 80 } })
  );
  await page.route(`${API_BASE}/enrich/stats`, (route) =>
    route.fulfill({ json: { total: 120, enriched: 80, pending: 40, failed: 0 } })
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
}

export async function mockExecutiveDashboard(page: Page) {
  await page.route(`${API_BASE}/dashboard/summary**`, (route) =>
    route.fulfill({
      json: {
        domain_id: "default",
        kpis: {
          total_entities: 120,
          enriched_count: 80,
          enrichment_pct: 66.7,
          avg_citations: 12,
          total_concepts: 24,
        },
        entities_by_year: [{ year: 2026, count: 120 }],
        brand_year_matrix: {
          brands: ["OpenAlex"],
          years: [2026],
          matrix: [[120]],
        },
        top_concepts: [{ concept: "science", count: 12, pct: 10 }],
        emerging_topic_signals: {
          is_experimental: false,
          years_available: [2026],
          baseline_years: [],
          recent_years: [2026],
          signals: [],
        },
        top_entities: [],
        quality: {
          average: 0.73,
          distribution: { high: 8, medium: 3, low: 1 },
        },
        recommended_actions: [],
        institutional_benchmark: {
          profile_id: "default",
          profile_name: "Default",
          description: "E2E benchmark",
          region: "global",
          status: "watch",
          readiness_pct: 72,
          passed_rules: 3,
          total_rules: 4,
          top_gaps: [],
        },
      },
    })
  );
  await page.route(`${API_BASE}/analytics/benchmarks/profiles`, (route) =>
    route.fulfill({ json: [{ id: "default", name: "Default", is_default: true }] })
  );
}
