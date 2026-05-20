import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import Header from "../app/components/Header";
import { LanguageProvider } from "../app/contexts/LanguageContext";

// Subvenciones (Mocks) para los contextos y dependencias
vi.mock("next/navigation", () => ({
  usePathname: () => "/analytics",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("../app/contexts/ThemeContext", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: vi.fn() }),
}));

vi.mock("../app/contexts/DomainContext", () => ({
  useDomain: () => ({
    domains: [{ id: "1", name: "Default Workspace", attributes: [] }],
    activeDomainId: "1",
    activeDomain: { id: "1", name: "Default Workspace", attributes: [] },
    setActiveDomainId: vi.fn(),
    isLoading: false,
  }),
  isAllScope: (scope: string) => scope === "all",
  isLegacyScope: (scope: string) => scope === "legacy_default",
  domainIdFromScope: (scope: string) => {
    if (scope === "all" || scope === "legacy_default") return null;
    if (scope.startsWith("domain:")) return scope.slice("domain:".length);
    return scope || null;
  },
}));

vi.mock("../app/contexts/BrandingContext", () => ({
  useBranding: () => ({
    branding: { platform_name: "UKIP" },
  }),
}));

vi.mock("../app/components/SidebarProvider", () => ({
  useSidebar: () => ({ isMobileOpen: false, toggleMobile: vi.fn() }),
}));

// Dummy components replacing the child dependencies
vi.mock("../app/components/NotificationBell", () => ({
  default: () => <div data-testid="notification-bell">Bell</div>,
}));
vi.mock("../app/components/UserMenu", () => ({
  default: () => <div data-testid="user-menu">User Context</div>,
}));

function renderWithLanguage(ui: React.ReactElement) {
  window.localStorage.setItem("app_lang", "en");
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

describe("Header Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the proper page title based on the pathname", () => {
    renderWithLanguage(<Header />);
    expect(screen.getByText("Analytics")).toBeInTheDocument();
  });

  it("displays the workspace selector with available domains", () => {
    renderWithLanguage(<Header />);
    expect(screen.getByRole("combobox", { name: /Active workspace domain/i })).toBeInTheDocument();
    expect(screen.getByText("Default Workspace")).toBeInTheDocument();
  });

  it("renders global elements: notification bell and user menu", () => {
    renderWithLanguage(<Header />);
    expect(screen.getByTestId("notification-bell")).toBeInTheDocument();
    expect(screen.getByTestId("user-menu")).toBeInTheDocument();
  });

  it("contains the global search input", () => {
    renderWithLanguage(<Header />);
    expect(screen.getByPlaceholderText(/Search/i)).toBeInTheDocument();
  });
});
