import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EntityTable from "../app/components/EntityTable";
import { LanguageProvider } from "../app/contexts/LanguageContext";

// ── Mock all external dependencies ────────────────────────────────────────

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
  API_BASE: "http://localhost:8000",
}));

vi.mock("../app/contexts/DomainContext", () => ({
  useDomain: () => ({
    // null → component falls back to "Primary Label" column, showing primary_label text
    activeDomain: null,
    activeDomainId: "default",
  }),
}));

vi.mock("../app/components/ui", () => ({
  KpiSummaryCard: ({ label, value }: { label: React.ReactNode; value: React.ReactNode }) => (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  ),
  useToast: () => ({ toast: vi.fn() }),
}));

// FacetPanel is a heavy dependency — stub it out
vi.mock("../app/components/FacetPanel", () => ({
  default: () => (
    <div data-testid="facet-panel">FacetPanel</div>
  ),
}));

vi.mock("../app/components/EntityTableToolbar", () => ({
  default: ({ search, onSearchChange }: { search: string; onSearchChange: (value: string) => void }) => (
    <input
      aria-label="Search entities"
      placeholder="Search entities..."
      value={search}
      onChange={(event) => onSearchChange(event.currentTarget.value)}
    />
  ),
}));

vi.mock("../app/components/EntityTableContent", () => ({
  default: ({
    entities,
    loading,
    fetchError,
  }: {
    entities: typeof MOCK_ENTITIES;
    loading: boolean;
    fetchError: string | null;
  }) => {
    if (loading) return <div aria-hidden="true">Loading entities</div>;
    if (fetchError) return <div role="alert">{fetchError}</div>;
    if (!entities.length) return <div>No entities found</div>;

    return (
      <div>
        {entities.map((entity) => (
          <article key={entity.id}>
            <h3>{entity.primary_label}</h3>
            {typeof entity.quality_score === "number" ? (
              <span>{Math.round(entity.quality_score * 100)}%</span>
            ) : null}
          </article>
        ))}
      </div>
    );
  },
}));

vi.mock("../app/components/EntityTablePagination", () => ({
  default: () => <div data-testid="entity-pagination" />,
}));

vi.mock("../app/components/EntityTableBulkActions", () => ({
  default: () => <div data-testid="entity-bulk-actions" />,
}));

vi.mock("../app/components/EntityTableDetailsModal", () => ({
  default: () => null,
}));

// Stub window.confirm
vi.stubGlobal("confirm", vi.fn(() => true));

// Stub URL blob helpers for CSV export without replacing the URL constructor.
Object.defineProperty(URL, "createObjectURL", {
  configurable: true,
  value: vi.fn(() => "blob:url"),
});
Object.defineProperty(URL, "revokeObjectURL", {
  configurable: true,
  value: vi.fn(),
});

import { apiFetch } from "@/lib/api";
const mockApiFetch = apiFetch as ReturnType<typeof vi.fn>;

function renderWithLanguage(ui: React.ReactElement) {
  window.localStorage.setItem("app_lang", "en");
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

// ── Fixtures ───────────────────────────────────────────────────────────────

const MOCK_ENTITIES = [
  {
    id: 1,
    primary_label: "Einstein",
    secondary_label: "Albert Einstein",
    canonical_id: "Q937",
    entity_type: "person",
    domain: "default",
    validation_status: "confirmed",
    enrichment_status: "completed",
    enrichment_citation_count: 42,
    source: "user",
    attributes_json: null,
    normalized_json: null,
    quality_score: 0.9,
  },
  {
    id: 2,
    primary_label: "CERN",
    secondary_label: null,
    canonical_id: null,
    entity_type: "organization",
    domain: "default",
    validation_status: "pending",
    enrichment_status: "none",
    enrichment_citation_count: null,
    source: "user",
    attributes_json: null,
    normalized_json: null,
    quality_score: 0.4,
  },
];

function successResponse(data: unknown, headers?: Record<string, string>) {
  return {
    ok: true,
    headers: {
      get: (key: string) => (headers ?? {})[key] ?? null,
    },
    json: async () => data,
  };
}

function mockEntityTableResponses(entities: unknown = MOCK_ENTITIES, total = "2") {
  mockApiFetch.mockImplementation((url: string) => {
    if (url.startsWith("/catalogs")) {
      return Promise.resolve(successResponse([]));
    }
    return Promise.resolve(successResponse(entities, { "X-Total-Count": total }));
  });
}

// ── Tests ──────────────────────────────────────────────────────────────────

beforeEach(() => {
  mockApiFetch.mockReset();
});

describe("EntityTable", () => {
  it("shows skeleton loader while fetching", () => {
    mockApiFetch.mockImplementation((url: string) => {
      if (url.startsWith("/catalogs")) {
        return Promise.resolve(successResponse([]));
      }
      return new Promise((resolve) => {
        setTimeout(() => resolve(successResponse(MOCK_ENTITIES, { "X-Total-Count": "2" })), 100);
      });
    });
    renderWithLanguage(<EntityTable />);
    expect(document.querySelectorAll("[aria-hidden='true']").length).toBeGreaterThan(0);
  });

  it("renders entity rows after fetch", async () => {
    mockEntityTableResponses();
    renderWithLanguage(<EntityTable />);
    await waitFor(() => {
      expect(screen.getByText("Einstein")).toBeInTheDocument();
      expect(screen.getByText("CERN")).toBeInTheDocument();
    });
  });

  it("shows ErrorBanner on fetch failure", async () => {
    mockApiFetch.mockImplementation((url: string) => {
      if (url.startsWith("/catalogs")) {
        return Promise.resolve(successResponse([]));
      }
      return Promise.resolve({ ok: false, status: 500, headers: { get: () => null }, json: async () => ({}) });
    });
    renderWithLanguage(<EntityTable />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("displays quality score bar for entities with score", async () => {
    mockEntityTableResponses();
    renderWithLanguage(<EntityTable />);
    await waitFor(() => {
      // Einstein has score 0.9 → 90%
      expect(screen.getByText("90%")).toBeInTheDocument();
    });
  });

  it("renders search input", async () => {
    mockEntityTableResponses([], "0");
    renderWithLanguage(<EntityTable />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Search entities...")).toBeInTheDocument();
    });
  });

  it("typing in search triggers a new fetch", async () => {
    mockEntityTableResponses();
    renderWithLanguage(<EntityTable />);
    await waitFor(() => screen.getByPlaceholderText("Search entities..."));

    await act(async () => {
      await userEvent.type(screen.getByPlaceholderText("Search entities..."), "Ein");
      // Wait for the 500ms debounce + fetch
      await new Promise(r => setTimeout(r, 600));
    });

    // At least 2 calls: initial load + debounced search
    expect(mockApiFetch.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("shows FacetPanel", async () => {
    mockEntityTableResponses([], "0");
    renderWithLanguage(<EntityTable />);
    await waitFor(() => {
      expect(screen.getByTestId("facet-panel")).toBeInTheDocument();
    });
  });

  it("shows empty state message when no entities match", async () => {
    mockEntityTableResponses([], "0");
    renderWithLanguage(<EntityTable />);
    await waitFor(() => {
      expect(screen.getByText(/no entities/i)).toBeInTheDocument();
    });
  });
});
