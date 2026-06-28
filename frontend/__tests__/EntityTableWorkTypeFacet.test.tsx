import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import EntityTable from "../app/components/EntityTable";
import { LanguageProvider } from "../app/contexts/LanguageContext";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
  API_BASE: "http://localhost:8000",
}));

// File-local next/navigation mock: an active work_type facet is present in the URL.
// NOTE: useSearchParams must return a STABLE instance — returning a fresh
// URLSearchParams on every call changes `searchParams` identity each render and
// drives the controller's param-sync effect into an infinite render loop.
const stableSearchParams = new URLSearchParams("ft_work_type=report");
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => stableSearchParams,
}));

vi.mock("../app/contexts/DomainContext", () => ({
  useDomain: () => ({ activeDomain: null, activeDomainId: "all" }),
}));

vi.mock("../app/contexts/EnrichmentContext", () => ({
  useEnrichment: () => ({ startPolling: vi.fn() }),
}));

vi.mock("../app/components/ui", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

vi.mock("../app/components/FacetPanel", () => ({
  default: () => <div data-testid="facet-panel">FacetPanel</div>,
}));

vi.mock("../app/components/EntityTableToolbar", () => ({
  default: () => <div data-testid="entity-toolbar" />,
}));

vi.mock("../app/components/EntityTableContent", () => ({
  default: () => <div data-testid="entity-content" />,
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

import { apiFetch } from "@/lib/api";
const mockApiFetch = apiFetch as ReturnType<typeof vi.fn>;

function successResponse(data: unknown, headers?: Record<string, string>) {
  return {
    ok: true,
    headers: { get: (key: string) => (headers ?? {})[key] ?? null },
    json: async () => data,
  };
}

beforeEach(() => {
  mockApiFetch.mockReset();
  mockApiFetch.mockImplementation((url: string) => {
    if (url.startsWith("/catalogs")) return Promise.resolve(successResponse([]));
    return Promise.resolve(successResponse([], { "X-Total-Count": "0" }));
  });
});

function renderWithLanguage(ui: React.ReactElement) {
  window.localStorage.setItem("app_lang", "en");
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

describe("EntityTable work_type facet wiring", () => {
  it("forwards ft_work_type from the URL to the /entities list request", async () => {
    renderWithLanguage(<EntityTable />);
    await waitFor(() => screen.getByTestId("facet-panel"));

    const entityCalls = mockApiFetch.mock.calls
      .map(([url]) => String(url))
      .filter((url) => url.startsWith("/entities?"));

    expect(entityCalls.length).toBeGreaterThan(0);
    expect(entityCalls.some((url) => url.includes("ft_work_type=report"))).toBe(true);
  });
});
