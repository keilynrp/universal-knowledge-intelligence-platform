/**
 * Task 5: Work type badge — table row + detail modal
 *
 * Tests that:
 * - A grid-mode entity card with enrichment_work_type="book" renders a
 *   localized "Book" badge.
 * - A grid-mode entity card with enrichment_work_type=null renders NO
 *   work-type badge.
 * - The detail modal header area shows a "Book" badge when the entity has
 *   enrichment_work_type="book".
 * - The detail modal shows no work-type badge when enrichment_work_type=null.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { LanguageProvider } from "../app/contexts/LanguageContext";

// ── Shared mock setup ─────────────────────────────────────────────────────────

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
  API_BASE: "http://localhost:8000",
}));

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

// Stub heavy sub-components used inside EntityTableContent
vi.mock("../app/components/RecordResultCard", () => ({
  default: ({
    statusRow,
    title,
  }: {
    statusRow: React.ReactNode;
    title: React.ReactNode;
  }) => (
    <article>
      <div data-testid="record-title">{title}</div>
      <div data-testid="status-row">{statusRow}</div>
    </article>
  ),
}));

vi.mock("../app/components/RecordListRow", () => ({
  default: ({ title, statusBadge }: { title: React.ReactNode; statusBadge: React.ReactNode }) => (
    <article>
      <div data-testid="record-title">{title}</div>
      <div data-testid="status-row">{statusBadge}</div>
    </article>
  ),
}));

vi.mock("../app/components/EnrichmentFailurePanel", () => ({
  EnrichmentFailureIcon: () => null,
  EnrichmentFailureDetails: () => null,
  FailureReasonBadge: () => null,
  parseEnrichmentFailure: () => null,
}));

vi.mock("../app/components/MonteCarloChart", () => ({
  default: () => <div data-testid="montecarlo-chart" />,
}));

vi.mock("../app/components/JournalMetricsSection", () => ({
  JournalMetricsSection: () => <div data-testid="journal-metrics" />,
}));

vi.mock("../app/components/ui", () => ({
  Badge: ({ children, variant }: { children: React.ReactNode; variant?: string }) => (
    <span data-testid="badge" data-variant={variant ?? "default"}>
      {children}
    </span>
  ),
  ErrorBanner: () => null,
  QualityBadge: () => null,
  EntityConcept: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

vi.mock("../app/contexts/DomainContext", () => ({
  useDomain: () => ({ activeDomain: null, activeDomainId: "default" }),
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderWithLang(ui: React.ReactElement, lang = "en") {
  localStorage.setItem("app_lang", lang);
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

function makeEntity(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    import_batch_id: null,
    primary_label: "Test Entity",
    secondary_label: null,
    canonical_id: null,
    entity_type: null,
    domain: "default",
    validation_status: "pending",
    enrichment_status: "none",
    enrichment_failure_reason: null,
    enrichment_citation_count: null,
    source: "user",
    attributes_json: null,
    normalized_json: null,
    quality_score: null,
    enrichment_work_type: null,
    ...overrides,
  };
}

// ── EntityTableContent (grid card) tests ──────────────────────────────────────

import EntityTableContent from "../app/components/EntityTableContent";

const BASE_CONTENT_PROPS = {
  activeDomain: null,
  entities: [] as ReturnType<typeof makeEntity>[],
  visibleEntities: [] as ReturnType<typeof makeEntity>[],
  loading: false,
  limit: 10,
  fetchError: null,
  shouldVirtualize: false,
  viewportHeight: 600,
  paddingTop: 0,
  paddingBottom: 0,
  selectedIds: new Set<number>(),
  editingId: null,
  editData: {
    primary_label: null,
    secondary_label: null,
    canonical_id: null,
    entity_type: null,
    domain: null,
    validation_status: null,
  },
  saving: false,
  deletingId: null,
  enrichingId: null,
  portalByBatchId: {},
  viewMode: "grid" as const,
  sortBy: "quality_score",
  sortOrder: "desc",
  scrollContainerRef: { current: null } as React.RefObject<HTMLDivElement | null>,
  onScrollTopChange: vi.fn(),
  onToggleSelectAll: vi.fn(),
  onToggleSelect: vi.fn(),
  onSortQuality: vi.fn(),
  onRetry: vi.fn(),
  onStartEdit: vi.fn(),
  onCancelEdit: vi.fn(),
  onSaveEdit: vi.fn(),
  onEditDataChange: vi.fn(),
  onSelectEntity: vi.fn(),
  onDeleteEntity: vi.fn(),
  onEnrichEntity: vi.fn(),
};

describe("EntityTableContent — work type badge in grid card", () => {
  it("shows a localized 'Book' badge when enrichment_work_type is 'book'", () => {
    const entity = makeEntity({ enrichment_work_type: "book" });
    renderWithLang(
      <EntityTableContent
        {...BASE_CONTENT_PROPS}
        entities={[entity]}
        visibleEntities={[entity]}
      />
    );

    // The Badge mock renders children as text; "Book" comes from page.work_type.book (EN)
    const statusRow = screen.getByTestId("status-row");
    expect(statusRow.textContent).toContain("Book");
  });

  it("does NOT show a work-type badge when enrichment_work_type is null", () => {
    const entity = makeEntity({ enrichment_work_type: null });
    renderWithLang(
      <EntityTableContent
        {...BASE_CONTENT_PROPS}
        entities={[entity]}
        visibleEntities={[entity]}
      />
    );

    const statusRow = screen.getByTestId("status-row");
    // The status row should NOT contain any of the known work-type labels
    expect(statusRow.textContent).not.toContain("Book");
    expect(statusRow.textContent).not.toContain("Article");
    expect(statusRow.textContent).not.toContain("Thesis");
    expect(statusRow.textContent).not.toContain("Preprint");
    expect(statusRow.textContent).not.toContain("Dataset");
    expect(statusRow.textContent).not.toContain("Other");
    // "Unclassified" must not appear either (null → no badge at all)
    expect(statusRow.textContent).not.toContain("Unclassified");
  });
});

// ── EntityTableDetailsModal tests ─────────────────────────────────────────────

import EntityTableDetailsModal from "../app/components/EntityTableDetailsModal";

describe("EntityTableDetailsModal — work type badge in header", () => {
  it("shows a localized 'Book' badge in the modal header when enrichment_work_type is 'book'", () => {
    const entity = makeEntity({ enrichment_work_type: "book" });
    renderWithLang(
      <EntityTableDetailsModal
        entity={entity}
        activeDomain={null}
        onClose={vi.fn()}
      />
    );

    // The modal should contain the localized label for "book"
    expect(screen.getByText("Book")).toBeInTheDocument();
  });

  it("does NOT show a work-type badge when enrichment_work_type is null", () => {
    const entity = makeEntity({ enrichment_work_type: null });
    renderWithLang(
      <EntityTableDetailsModal
        entity={entity}
        activeDomain={null}
        onClose={vi.fn()}
      />
    );

    // None of the work-type labels should appear
    expect(screen.queryByText("Book")).not.toBeInTheDocument();
    expect(screen.queryByText("Article")).not.toBeInTheDocument();
    expect(screen.queryByText("Unclassified")).not.toBeInTheDocument();
  });
});
