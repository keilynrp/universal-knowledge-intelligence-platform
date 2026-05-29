import { test, expect } from "@playwright/test";
import { injectAuth, mockUserMe, API_BASE } from "./helpers";

/**
 * Visual regression baselines for the GraphDB-style coauthorship graph.
 *
 * Bootstrap baselines locally once with:
 *   pnpm playwright test e2e/network_graph_visual.spec.ts --update-snapshots
 *
 * The force layout is deterministic for a fixed dataset, but we still mask the
 * relaxing/updated chrome and wait for the simulation to settle to avoid
 * flake. Run in CI only after baselines are committed.
 */
const NETWORK = {
  domain_id: "default",
  nodes: [
    { id: "1", label: "Alice Researcher", degree: 3, centrality: 0.9, community_id: 0, total_publications: 8 },
    { id: "2", label: "Bob Scientist", degree: 2, centrality: 0.6, community_id: 0, total_publications: 4 },
    { id: "3", label: "Carol Scholar", degree: 2, centrality: 0.5, community_id: 1, total_publications: 3 },
    { id: "4", label: "Dan Author", degree: 1, centrality: 0.3, community_id: 1, total_publications: 2 },
    { id: "5", label: "Eve Writer", degree: 1, centrality: 0.2, community_id: 2, total_publications: 1 },
  ],
  edges: [
    { source: "1", target: "2", weight: 5 },
    { source: "1", target: "3", weight: 2 },
    { source: "3", target: "4", weight: 3 },
    { source: "2", target: "5", weight: 1 },
  ],
  computed_at: new Date("2026-05-01T00:00:00Z").toISOString(),
  stale: false,
  coverage_pct: 100,
};

const BREAKPOINTS = [
  { name: "mobile", width: 320, height: 720 },
  { name: "tablet", width: 768, height: 900 },
  { name: "desktop", width: 1280, height: 900 },
  { name: "wide", width: 1920, height: 1080 },
];

for (const theme of ["light", "dark"] as const) {
  for (const bp of BREAKPOINTS) {
    test(`coauthorship graph — ${theme} @ ${bp.name}`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: theme });
      await injectAuth(page);
      await page.route(`${API_BASE}/**`, (route) => route.fulfill({ json: [] }));
      await page.route(`${API_BASE}/analyzers/coauthorship/**`, (route) =>
        route.fulfill({ json: NETWORK }),
      );
      await page.route(`${API_BASE}/coauthorship/merge-suggestions**`, (route) =>
        route.fulfill({ json: [] }),
      );
      await mockUserMe(page);

      await page.setViewportSize({ width: bp.width, height: bp.height });
      await page.goto("/analytics/coauthorship");
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("button", { name: "Alice Researcher" }).first()).toBeVisible({
        timeout: 10_000,
      });
      // Let the d3-force simulation settle before snapshotting.
      await page.waitForTimeout(1500);

      await expect(page).toHaveScreenshot(`coauthorship-${theme}-${bp.name}.png`, {
        fullPage: true,
        maxDiffPixelRatio: 0.02,
        animations: "disabled",
      });
    });
  }
}
