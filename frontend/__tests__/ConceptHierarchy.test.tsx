import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import ConceptHierarchyPage from "../app/analytics/concepts/page";
import { LanguageProvider } from "../app/contexts/LanguageContext";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/analytics/concepts",
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

let mockTreeResponse: { nodes: unknown[]; materialized_at: string | null } = {
  nodes: [],
  materialized_at: null,
};

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn().mockImplementation(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(mockTreeResponse),
    })
  ),
}));

function renderPage() {
  return render(
    <LanguageProvider>
      <ConceptHierarchyPage />
    </LanguageProvider>
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ConceptHierarchy Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("app_lang", "en");
    mockUserRole = "super_admin";
    mockTreeResponse = { nodes: [], materialized_at: null };
  });

  it("renders empty state when no concepts exist", async () => {
    renderPage();
    expect(await screen.findByText(/No concepts materialized yet/i)).toBeInTheDocument();
  });

  it("renders tree view with mock concept data", async () => {
    mockTreeResponse = {
      nodes: [
        {
          id: 1,
          name: "Computer Science",
          level: 0,
          entity_count: 50,
          openalex_id: "C41008148",
          children: [
            {
              id: 2,
              name: "Artificial Intelligence",
              level: 1,
              entity_count: 30,
              openalex_id: "C154945302",
              children: [],
            },
          ],
        },
      ],
      materialized_at: "2026-05-18T10:00:00+00:00",
    };

    renderPage();
    expect(await screen.findByText("Computer Science")).toBeInTheDocument();
    expect(screen.getByText("Artificial Intelligence")).toBeInTheDocument();
  });

  it("toggles between tree and sunburst views", async () => {
    mockTreeResponse = {
      nodes: [
        {
          id: 1,
          name: "Biology",
          level: 0,
          entity_count: 10,
          openalex_id: "C86803240",
          children: [],
        },
      ],
      materialized_at: "2026-05-18T10:00:00+00:00",
    };

    renderPage();
    // Wait for tree to load
    expect(await screen.findByText("Biology")).toBeInTheDocument();

    // Find and click sunburst toggle
    const sunburstBtn = screen.getByText("Sunburst");
    fireEvent.click(sunburstBtn);

    // SVG should be present (sunburst view renders an svg)
    const svgs = document.querySelectorAll("svg");
    expect(svgs.length).toBeGreaterThan(0);
  });

  it("admin sees refresh button, viewer does not", async () => {
    // Admin sees button
    renderPage();
    expect(await screen.findByText(/Refresh Hierarchy/i)).toBeInTheDocument();
  });

  it("viewer does not see refresh button", async () => {
    mockUserRole = "viewer";
    renderPage();
    // Wait for page to load
    await screen.findByText(/No concepts materialized yet/i);
    expect(screen.queryByText(/Refresh Hierarchy/i)).not.toBeInTheDocument();
  });
});
