import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import LoginPage from "../app/login/page";

// The SSO callback redirects to /login?sso_code=<code> (issue 408). The page
// spends the code exactly once, and takes it out of the address bar first.

let searchParams = new URLSearchParams("");
const mockPush = vi.fn();
const mockLoginWithSsoCode = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => searchParams,
}));

vi.mock("../app/contexts/AuthContext", () => ({
  useAuth: () => ({
    login: vi.fn(),
    loginWithSsoCode: mockLoginWithSsoCode,
    isAuthenticated: false,
  }),
}));

vi.mock("../app/contexts/BrandingContext", () => ({
  useBranding: () => ({ branding: { platform_name: "UKIP" } }),
}));

const t = (key: string) => key;
vi.mock("../app/contexts/LanguageContext", () => ({
  useLanguage: () => ({ t, lang: "en", setLang: vi.fn() }),
}));

beforeEach(() => {
  mockPush.mockReset();
  mockLoginWithSsoCode.mockReset();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
  window.history.replaceState(null, "", "/login?sso_code=the-code");
  searchParams = new URLSearchParams("sso_code=the-code");
});

describe("Login page with an SSO code", () => {
  it("spends the code once, even under Strict Mode, and goes home", async () => {
    mockLoginWithSsoCode.mockResolvedValue(undefined);

    render(<StrictMode><LoginPage /></StrictMode>);

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/"));
    expect(mockLoginWithSsoCode).toHaveBeenCalledTimes(1);
    expect(mockLoginWithSsoCode).toHaveBeenCalledWith("the-code");
  });

  it("removes the code from the address bar before spending it", async () => {
    let urlAtExchange = "";
    mockLoginWithSsoCode.mockImplementation(async () => {
      urlAtExchange = window.location.href;
    });

    render(<LoginPage />);

    await waitFor(() => expect(mockLoginWithSsoCode).toHaveBeenCalled());
    expect(urlAtExchange).not.toContain("sso_code");
    expect(window.location.search).toBe("");
  });

  it("says the link expired when the code is refused", async () => {
    mockLoginWithSsoCode.mockRejectedValue(new Error("Invalid or expired SSO code"));

    render(<LoginPage />);

    expect(await screen.findByText("auth.login.sso_error")).toBeTruthy();
    expect(mockPush).not.toHaveBeenCalled();
  });
});
