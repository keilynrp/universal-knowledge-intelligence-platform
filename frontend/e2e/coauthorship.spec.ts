import { test, expect } from "@playwright/test";
import { injectAuth, mockUserMe, API_BASE } from "./helpers";

const NETWORK = {
  domain_id: "default",
  nodes: [
    { id: "1", label: "Alice Researcher", degree: 2, centrality: 0.9, community_id: 0, total_publications: 5 },
    { id: "2", label: "Bob Scientist", degree: 1, centrality: 0.5, community_id: 0, total_publications: 3 },
    { id: "3", label: "Carol Scholar", degree: 1, centrality: 0.3, community_id: 1, total_publications: 2 },
  ],
  edges: [
    { source: "1", target: "2", weight: 4 },
    { source: "1", target: "3", weight: 1 },
  ],
  computed_at: new Date().toISOString(),
  stale: false,
  coverage_pct: 100,
};

const AUTHOR_DETAIL = {
  author_id: 1,
  display_name: "Alice Researcher",
  orcid: "0000-0002-1825-0097",
  aliases: ["Alice Researcher", "A. Researcher"],
  metrics: { degree: 2, centrality: 0.9, community_id: 0, publication_count: 5 },
  publications: [{ entity_id: 10, title: "A Landmark Study", year: 2022 }],
  collaborators: [{ author_id: 2, name: "Bob Scientist", weight: 4 }],
};

const MERGE_SUGGESTIONS = [
  {
    id: 1,
    author_a_id: 2,
    author_a_name: "Bob Scientist",
    author_b_id: 9,
    author_b_name: "B. Scientist",
    reason: "last+initial",
    status: "pending",
    created_at: new Date().toISOString(),
  },
];

test.describe("Coauthorship V2 graph", () => {
  test.beforeEach(async ({ page }) => {
    await injectAuth(page);
    await page.route(`${API_BASE}/**`, (route) => route.fulfill({ json: [] }));
    // Register specific routes AFTER the catch-all so they take precedence.
    await page.route(`${API_BASE}/analyzers/coauthorship/**`, (route) =>
      route.fulfill({ json: NETWORK }),
    );
    await page.route(`${API_BASE}/analyzers/coauthorship/**/author/**`, (route) =>
      route.fulfill({ json: AUTHOR_DETAIL }),
    );
    await page.route(`${API_BASE}/coauthorship/merge-suggestions**`, (route) =>
      route.fulfill({ json: MERGE_SUGGESTIONS }),
    );
    await mockUserMe(page);
  });

  test("renders the graph and hydrates the properties panel on click", async ({ page }) => {
    await page.goto("/analytics/coauthorship");
    await page.waitForLoadState("networkidle");

    // Graph nodes render as accessible buttons labeled by author name.
    const aliceNode = page.getByRole("button", { name: "Alice Researcher" }).first();
    await expect(aliceNode).toBeVisible({ timeout: 10_000 });

    await aliceNode.click();

    // Properties panel hydrates with the author's detail.
    const panel = page.getByTestId("node-panel");
    await expect(panel).toBeVisible();
    await expect(panel.getByText("A Landmark Study")).toBeVisible();
    await expect(panel.getByText("Bob Scientist")).toBeVisible();
    await expect(panel.getByText(/ORCID/)).toBeVisible();
  });

  test("zoom controls respond", async ({ page }) => {
    await page.goto("/analytics/coauthorship");
    await page.waitForLoadState("networkidle");
    const zoomIn = page.getByRole("button", { name: "Zoom in" });
    await expect(zoomIn).toBeVisible({ timeout: 10_000 });
    await zoomIn.click();
    await zoomIn.click();
    await expect(page.getByText(/×/)).toBeVisible();
  });

  test("admin sees the merge-suggestions review queue", async ({ page }) => {
    await page.goto("/analytics/coauthorship");
    await page.waitForLoadState("networkidle");
    const panel = page.getByTestId("merge-suggestions");
    await expect(panel).toBeVisible({ timeout: 10_000 });
    await expect(panel.getByText(/Bob Scientist/)).toBeVisible();
    await expect(panel.getByRole("button", { name: "Merge" })).toBeVisible();
  });
});
