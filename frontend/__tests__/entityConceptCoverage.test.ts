import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const REQUIRED_SURFACES: Record<string, number> = {
  "app/page.tsx": 2,
  "app/analytics/AnalyticsOverviewSection.tsx": 1,
  "app/analytics/AnalyticsEnrichmentSection.tsx": 1,
  "app/analytics/compare/page.tsx": 2,
  "app/analytics/dashboard/page.tsx": 4,
  "app/analytics/geographic/page.tsx": 3,
  "app/artifacts/gaps/page.tsx": 1,
  "app/authority/ReviewQueueControls.tsx": 1,
  "app/catalogs/page.tsx": 1,
  "app/catalogs/[slug]/record/[id]/page.tsx": 1,
  "app/components/DisambiguationTool.tsx": 1,
  "app/components/EnrichmentSchedulerCard.tsx": 1,
  "app/components/EntityTableDetailsModal.tsx": 1,
  "app/components/FacetPanel.tsx": 1,
  "app/components/RelationshipManager.tsx": 1,
  "app/context/ContextPanels.tsx": 1,
  "app/context/DiffTab.tsx": 1,
  "app/dashboards/page.tsx": 4,
  "app/dashboards/widgets.tsx": 3,
  "app/demo/sales/page.tsx": 2,
  "app/domains/page.tsx": 2,
  "app/embed/[token]/page.tsx": 1,
  "app/entities/bulk-edit/page.tsx": 1,
  "app/entities/link/page.tsx": 1,
  "app/harmonization/page.tsx": 1,
  "app/settings/DataFixesTab.tsx": 1,
  "app/settings/scheduled-imports/page.tsx": 1,
  "app/workflows/WorkflowDialogs.tsx": 1,
};

describe("entity concept coverage", () => {
  for (const [relativePath, minimumUses] of Object.entries(REQUIRED_SURFACES)) {
    it(`${relativePath} keeps its governed entity definition`, () => {
      const source = readFileSync(resolve(__dirname, "..", relativePath), "utf8");
      const uses = source.match(/<EntityConcept(?:\s|>)/g)?.length ?? 0;

      expect(uses).toBeGreaterThanOrEqual(minimumUses);
    });
  }
});
