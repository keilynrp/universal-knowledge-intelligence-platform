import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";

vi.mock("recharts", () => ({
  LineChart: ({ children }: { children?: React.ReactNode }) => <div data-testid="line-chart">{children}</div>,
  Line: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
  ResponsiveContainer: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("../app/contexts/DomainContext", () => ({
  useDomain: () => ({
    activeDomain: { id: "science", name: "Science" },
  }),
}));

const mockApiFetch = vi.fn();
vi.mock("@/lib/api", () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}));

import DomainHealthPage from "../app/analytics/domain-health/page";
import { LanguageProvider } from "../app/contexts/LanguageContext";

function renderPage() {
  return render(
    <LanguageProvider>
      <DomainHealthPage />
    </LanguageProvider>
  );
}

describe("DomainHealthPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("app_lang", "en");
  });

  it("renders empty state when all metrics are null", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          gini_authorship: { value: null, label: "insufficient_data", by_year: [] },
          international_collaboration_rate: { value: null, label: "insufficient_data", by_year: [] },
          open_access_rate: { value: null, label: "insufficient_data", by_year: [] },
          epistemic_diversity: { value: null, label: "insufficient_data", by_year: [] },
          newcomer_rate: { value: null, label: "insufficient_data", by_year: [] },
        }),
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/insufficient data/i)).toBeInTheDocument();
    });
  });

  it("renders metric cards when data is present", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          gini_authorship: { value: 0.35, label: "moderate_concentration", by_year: [{ year: 2023, value: 0.35 }] },
          international_collaboration_rate: { value: 0.25, label: "low", by_year: [{ year: 2023, value: 0.25 }] },
          open_access_rate: { value: 0.6, label: "high", by_year: [{ year: 2023, value: 0.6 }] },
          epistemic_diversity: { value: 0.78, label: "good_diversity", by_year: [{ year: 2023, value: 0.78 }] },
          newcomer_rate: { value: 0.4, label: "moderate", by_year: [{ year: 2023, value: 0.4 }] },
        }),
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("0.350")).toBeInTheDocument();
    });

    expect(screen.getByText("25.0%")).toBeInTheDocument();
    expect(screen.getByText("60.0%")).toBeInTheDocument();
    expect(screen.getByText("0.780")).toBeInTheDocument();
    expect(screen.getByText("40.0%")).toBeInTheDocument();
  });

  it("renders no-config state on 400 response", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      status: 400,
      json: () => Promise.resolve({ detail: "no discourse community" }),
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/not configured/i)).toBeInTheDocument();
    });
  });

  it("shows low sample warning when flagged", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          gini_authorship: { value: 0.2, label: "moderate_concentration", low_sample: true, by_year: [] },
          international_collaboration_rate: { value: null, label: "insufficient_data", by_year: [] },
          open_access_rate: { value: null, label: "insufficient_data", by_year: [] },
          epistemic_diversity: { value: null, label: "insufficient_data", by_year: [] },
          newcomer_rate: { value: null, label: "insufficient_data", by_year: [] },
        }),
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/small sample/i)).toBeInTheDocument();
    });
  });
});
