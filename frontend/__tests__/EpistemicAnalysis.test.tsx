import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import EpistemicAnalysisPage from "../app/analytics/epistemic/page";
import { LanguageProvider } from "../app/contexts/LanguageContext";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/analytics/epistemic",
}));

vi.mock("../app/contexts/DomainContext", () => ({
  useDomain: () => ({
    activeDomain: {
      id: "science",
      name: "Science",
      description: "",
      primary_entity: "entity",
      icon: "",
      attributes: [],
    },
  }),
}));

let mockUserRole = "super_admin";
vi.mock("../app/contexts/AuthContext", () => ({
  useAuth: () => ({
    token: "test-token",
    user: { id: 1, username: "testadmin", role: mockUserRole, email: null, is_active: true },
    isAuthenticated: true,
    hydrated: true,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
    updateAvatarUrl: vi.fn(),
  }),
}));

vi.mock("../app/components/ui/Toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

// Mock recharts to avoid SVG rendering issues in JSDOM
vi.mock("recharts", () => ({
  PieChart: ({ children }: { children: React.ReactNode }) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => null,
  Cell: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AreaChart: ({ children }: { children: React.ReactNode }) => <div data-testid="area-chart">{children}</div>,
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Legend: () => null,
}));

let mockDistributionResponse: {
  status: number;
  data: unknown;
} = {
  status: 200,
  data: {
    domain_id: "science",
    total_classified: 0,
    total_unclassified: 0,
    paradigm_counts: {},
    paradigms: [],
    by_year: [],
  },
};

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn().mockImplementation(() =>
    Promise.resolve({
      ok: mockDistributionResponse.status === 200,
      status: mockDistributionResponse.status,
      json: () => Promise.resolve(mockDistributionResponse.data),
    })
  ),
}));

function renderPage() {
  return render(
    <LanguageProvider>
      <EpistemicAnalysisPage />
    </LanguageProvider>
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("EpistemicAnalysis Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("app_lang", "en");
    mockUserRole = "super_admin";
    mockDistributionResponse = {
      status: 200,
      data: {
        domain_id: "science",
        total_classified: 0,
        total_unclassified: 0,
        paradigm_counts: {},
        paradigms: [],
        by_year: [],
      },
    };
  });

  it("renders empty state when no entities classified", async () => {
    renderPage();
    expect(await screen.findByText(/No entities classified yet/i)).toBeInTheDocument();
  });

  it("renders no-config state when domain lacks epistemology", async () => {
    mockDistributionResponse = {
      status: 400,
      data: { detail: "No epistemology config" },
    };
    renderPage();
    expect(await screen.findByText(/not configured/i)).toBeInTheDocument();
  });

  it("renders charts with classified data", async () => {
    mockDistributionResponse = {
      status: 200,
      data: {
        domain_id: "science",
        total_classified: 100,
        total_unclassified: 20,
        paradigm_counts: { empiricist: 60, constructivist: 25, critical: 15 },
        paradigms: [
          { id: "empiricist", label: "Empiricist" },
          { id: "constructivist", label: "Constructivist" },
          { id: "critical", label: "Critical" },
        ],
        by_year: [
          { year: 2020, paradigm_counts: { empiricist: 30, constructivist: 15, critical: 5 } },
          { year: 2021, paradigm_counts: { empiricist: 30, constructivist: 10, critical: 10 } },
        ],
      },
    };

    renderPage();
    // Wait for data to load
    expect(await screen.findByText("100")).toBeInTheDocument(); // total classified
    expect(screen.getByText("20")).toBeInTheDocument(); // total unclassified
    expect(screen.getByText("Empiricist")).toBeInTheDocument();
    expect(screen.getByText("Constructivist")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByTestId("pie-chart")).toBeInTheDocument();
  });

  it("admin sees classify button", async () => {
    renderPage();
    expect(await screen.findByText(/Classify Entities/i)).toBeInTheDocument();
  });

  it("viewer does not see classify button", async () => {
    mockUserRole = "viewer";
    renderPage();
    // Wait for page to load
    await screen.findByText(/No entities classified yet/i);
    expect(screen.queryByText(/Classify Entities/i)).not.toBeInTheDocument();
  });
});
