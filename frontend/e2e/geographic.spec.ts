import { expect, test } from "@playwright/test";
import { API_BASE, injectAuth, mockUserMe } from "./helpers";

const GEO_RESULT = {
  domain_id: "default",
  coverage: 0.615,
  total_entities: 569,
  countries: [
    { country_code: "US", country_name: "United States", entity_count: 220, citation_sum: 12500, percentage: 38.7 },
    { country_code: "CN", country_name: "China", entity_count: 110, citation_sum: 9300, percentage: 19.3 },
    { country_code: "GB", country_name: "United Kingdom", entity_count: 60, citation_sum: 4200, percentage: 10.5 },
    { country_code: "DE", country_name: "Germany", entity_count: 45, citation_sum: 3100, percentage: 7.9 },
    { country_code: "JP", country_name: "Japan", entity_count: 30, citation_sum: 2700, percentage: 5.3 },
  ],
};

const US_TIMESERIES = {
  domain_id: "default",
  country_code: "US",
  country_name: "United States",
  total_entities: 220,
  total_citations: 12500,
  reference_year: 2024,
  years: 9,
  series: [
    { year: 2016, entity_count: 12, citation_sum: 800 },
    { year: 2017, entity_count: 18, citation_sum: 950 },
    { year: 2018, entity_count: 22, citation_sum: 1100 },
    { year: 2019, entity_count: 25, citation_sum: 1300 },
    { year: 2020, entity_count: 28, citation_sum: 1500 },
    { year: 2021, entity_count: 30, citation_sum: 1700 },
    { year: 2022, entity_count: 32, citation_sum: 1800 },
    { year: 2023, entity_count: 28, citation_sum: 1700 },
    { year: 2024, entity_count: 25, citation_sum: 1650 },
  ],
};

test.describe("Geographic intelligence panel", () => {
  const filteredResult = {
    ...GEO_RESULT,
    total_entities: 80,
    coverage: 0.42,
    countries: GEO_RESULT.countries.slice(0, 2),
  };

  const collabResult = {
    ...GEO_RESULT,
    collaboration_rate: 18.4,
    top_country_pairs: [
      {
        country_a: "US",
        country_b: "CN",
        country_a_name: "United States",
        country_b_name: "China",
        count: 42,
      },
      {
        country_a: "GB",
        country_b: "DE",
        country_a_name: "United Kingdom",
        country_b_name: "Germany",
        count: 21,
      },
    ],
  };

  test.beforeEach(async ({ page }) => {
    await mockUserMe(page);
    // Single route with conditional body to avoid Playwright's route-precedence ambiguity.
    await page.route(`${API_BASE}/**`, (route) => {
      const url = route.request().url();
      if (url.includes("/analyzers/geographic/") && url.includes("/country/")) {
        // Specific stubs for tests that exercise non-US country drilldowns.
        if (url.includes("/country/MN")) {
          return route.fulfill({
            json: {
              domain_id: "default",
              country_code: "MN",
              country_name: "Mongolia",
              total_entities: 0,
              total_citations: 0,
              reference_year: 2024,
              years: 9,
              series: Array.from({ length: 9 }, (_, i) => ({
                year: 2016 + i,
                entity_count: 0,
                citation_sum: 0,
              })),
            },
          });
        }
        return route.fulfill({ json: US_TIMESERIES });
      }
      if (url.includes("/analyzers/geographic/")) {
        if (url.includes("include_collaboration=true")) {
          return route.fulfill({ json: collabResult });
        }
        // Echo a filtered payload when year_from is set so we can assert KPIs respond.
        if (url.includes("year_from=2020")) {
          return route.fulfill({ json: filteredResult });
        }
        return route.fulfill({ json: GEO_RESULT });
      }
      if (url.includes("/users/me")) {
        return route.fulfill({ json: { id: 1, username: "admin", role: "super_admin", is_active: true } });
      }
      return route.fulfill({ json: [] });
    });
    await injectAuth(page);
  });

  const gotoGeo = async (page: import("@playwright/test").Page) => {
    await page.goto("/analytics/geographic", { waitUntil: "domcontentloaded" });
  };

  test("renders 4 KPI cards with computed values", async ({ page }) => {
    await gotoGeo(page);
    await expect(page.getByText("569", { exact: true })).toBeVisible();
    // 5 visible (non-OTHER) countries
    await expect(page.getByText("5", { exact: true }).first()).toBeVisible();
    // 61.5% coverage
    await expect(page.getByText("61.5%")).toBeVisible();
    // total citations = 12500+9300+4200+3100+2700 = 31800
    await expect(page.getByText("31,800")).toBeVisible();
  });

  test("table shows flag, ISO code, and bar for each country", async ({ page }) => {
    await gotoGeo(page);
    await expect(page.getByText("United States")).toBeVisible();
    // ISO code chips
    await expect(page.locator("text=/^US$/").first()).toBeVisible();
    await expect(page.locator("text=/^CN$/").first()).toBeVisible();
    // Distribution bar (one per visible country row + table column header bars)
    await expect(page.locator(".bg-blue-500").first()).toBeVisible();
  });

  test("clicking a row opens detail panel with sparkline", async ({ page }) => {
    await gotoGeo(page);
    // Hint copy — accept either Spanish or English locale.
    await expect(page.getByText(/Pick a country|Selecciona un país/)).toBeVisible();

    await page.getByRole("button", { name: /United States/ }).click();

    await expect(page.getByText(/Citations · last 9 years|Citas · últimos 9 años/)).toBeVisible();
    await expect(page.getByText(/38\.7%\s+(of total|del total)/)).toBeVisible();

    // Recharts area chart present
    await expect(page.locator(".recharts-area").first()).toBeVisible();

    // Reset view button appears
    await expect(page.getByRole("button", { name: /Reset view|Restablecer vista/ })).toBeVisible();
  });

  test("year filter triggers refetch and updates KPI totals", async ({ page }) => {
    await gotoGeo(page);
    // Initial KPI: total_entities = 569
    await expect(page.getByText("569", { exact: true })).toBeVisible();

    // Apply year_from = 2020
    await page.getByLabel(/Year from|Año desde/).fill("2020");

    // Filtered KPI: total_entities = 80, coverage = 42.0%
    await expect(page.getByText("80", { exact: true })).toBeVisible();
    await expect(page.getByText("42.0%")).toBeVisible();

    // Clear filters → back to original
    await page.getByRole("button", { name: /Clear filters|Limpiar filtros/ }).click();
    await expect(page.getByText("569", { exact: true })).toBeVisible();
  });

  test("collaboration toggle adds 5th KPI + pairs section", async ({ page }) => {
    await gotoGeo(page);

    // Pairs section is hidden by default
    await expect(page.getByTestId("collab-pairs")).toHaveCount(0);

    // Toggle on
    await page.locator("#geo-show-collab").check();

    // 5th KPI: Collaboration rate = 18.4%
    await expect(page.getByText("18.4%")).toBeVisible();

    // Pairs section becomes visible and lists both pairs
    await expect(page.getByTestId("collab-pairs")).toBeVisible();
    const pairs = page.getByTestId("collab-pairs");
    await expect(pairs.getByText("United States")).toBeVisible();
    await expect(pairs.getByText("China")).toBeVisible();
    await expect(pairs.getByText("United Kingdom")).toBeVisible();
    await expect(pairs.getByText(/42\s+(shared|compartidas)/)).toBeVisible();

    // Toggle off → KPI disappears
    await page.locator("#geo-show-collab").uncheck();
    await expect(page.getByText("18.4%")).toHaveCount(0);
    await expect(page.getByTestId("collab-pairs")).toHaveCount(0);
  });

  test("clicking a country polygon opens the detail panel", async ({ page }) => {
    await gotoGeo(page);
    // Wait for the world atlas chunk to load and render a US polygon.
    const usPath = page.locator('path[data-iso="US"]');
    await expect(usPath).toBeVisible({ timeout: 10_000 });

    // Sanity: detail panel shows the placeholder before any selection.
    await expect(page.getByText(/Pick a country|Selecciona un país/)).toBeVisible();

    // Click straight on the US polygon (not on a marker / table row).
    await usPath.click();

    // Detail panel now populated.
    await expect(page.getByText(/Citations · last 9 years|Citas · últimos 9 años/)).toBeVisible();
    await expect(page.getByText(/38\.7%\s+(of total|del total)/)).toBeVisible();
    await expect(page.locator(".recharts-area").first()).toBeVisible();
  });

  test("clicking a country with no data still opens the panel", async ({ page }) => {
    await gotoGeo(page);
    const mn = page.locator('path[data-iso="MN"]');
    await expect(mn).toBeVisible({ timeout: 10_000 });
    await mn.click();

    // Panel opens with country name + "no data" hint, even with no row in table.
    await expect(page.getByRole("heading", { name: "Mongolia" })).toBeVisible();
    await expect(
      page.getByText(/No entities match the current filters|Ninguna entidad coincide/),
    ).toBeVisible();
  });

  test("drag-to-pan shifts the map and shows grab cursor", async ({ page }) => {
    await gotoGeo(page);
    const svg = page.locator("svg.cursor-grab").first();
    await expect(svg).toBeVisible();

    const box = await svg.boundingBox();
    if (!box) throw new Error("map bounding box unavailable");

    // Drag from a blank area near the top-left (not on a marker).
    const startX = box.x + 80;
    const startY = box.y + 80;
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + 120, startY + 60, { steps: 10 });

    // While dragging, cursor class swaps to grabbing.
    const grabbing = page.locator("svg.cursor-grabbing").first();
    await expect(grabbing).toBeVisible();

    await page.mouse.up();

    // After release, the map group has a non-identity translate from manual pan.
    const mapGroup = page.locator('svg g[transform*="scale"]').first();
    const transform = (await mapGroup.getAttribute("transform")) || "";
    expect(transform).not.toMatch(/translate\(0 0\)/);

    // Reset clears it.
    await page.getByRole("button", { name: /Reset zoom|Restablecer zoom/ }).click();
    await expect(mapGroup).toHaveAttribute("transform", /translate\(0 0\) scale\(1\)/);
  });

  test("manual zoom in / out controls update the map transform", async ({ page }) => {
    await gotoGeo(page);
    const mapGroup = page.locator('svg g[transform*="scale"]').first();
    await expect(mapGroup).toHaveAttribute("transform", /scale\(1\)/);

    const zoomIn = page.getByRole("button", { name: /Zoom in|Acercar/ });
    await zoomIn.click();
    // 1 × 1.4 = 1.4 → still rendered
    await expect(mapGroup).toHaveAttribute("transform", /scale\(1\.4/);

    // Click zoom in 3 more times → 1.4^4 ≈ 3.84
    await zoomIn.click();
    await zoomIn.click();
    await zoomIn.click();
    const after = (await mapGroup.getAttribute("transform")) || "";
    const match = after.match(/scale\(([0-9.]+)\)/);
    const z = match ? parseFloat(match[1]) : 0;
    expect(z).toBeGreaterThan(3);

    // Reset button appears + clears the zoom
    await page.getByRole("button", { name: /Reset zoom|Restablecer zoom/ }).click();
    await expect(mapGroup).toHaveAttribute("transform", /scale\(1\)/);
  });

  test("map zooms when country selected (transform changes)", async ({ page }) => {
    await gotoGeo(page);
    // Map root <g> uses translate+scale; pre-selection it's identity scale(1).
    const mapGroup = page
      .locator('svg g[transform*="scale"]')
      .first();
    const initial = (await mapGroup.getAttribute("transform")) || "";
    expect(initial).toContain("scale(1)");

    await page.getByRole("button", { name: /United States/ }).click();
    await expect(mapGroup).not.toHaveAttribute("transform", initial);
    const after = (await mapGroup.getAttribute("transform")) || "";
    expect(after).toContain("scale(3)");
  });
});
