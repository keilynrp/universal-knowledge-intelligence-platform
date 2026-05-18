import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import DisambiguationTool from "../app/components/DisambiguationTool";
import { LanguageProvider } from "../app/contexts/LanguageContext";

vi.mock("../app/contexts/DomainContext", () => ({
  useDomain: () => ({
    activeDomain: {
      id: "default",
      name: "Default",
      description: "",
      primary_entity: "entity",
      icon: "",
      attributes: [
        { name: "name", type: "string", label: "Name", required: false, is_core: true },
      ],
    },
  }),
}));

vi.mock("../app/contexts/AuthContext", () => ({
  useAuth: () => ({
    token: "test-token",
    user: { id: 1, username: "testadmin", role: "superadmin", email: null, is_active: true },
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

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ total_groups: 0, items: [] })
  }),
}));

function renderTool() {
  return render(
    <LanguageProvider>
      <DisambiguationTool />
    </LanguageProvider>
  );
}

describe("DisambiguationTool Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("app_lang", "en");
  });

  it("renders correctly with controls based on context", async () => {
    renderTool();
    expect(await screen.findByText(/Knowledge Attribute to Analyze/i)).toBeInTheDocument();
    expect(screen.getByText(/Threshold:/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Find Inconsistencies/i })).toBeInTheDocument();
  });

  it("presents available clustering algorithms", async () => {
    renderTool();
    expect(await screen.findByText(/Algorithm/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Token Sort/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Fingerprint/i })).toBeInTheDocument();
  });
});
