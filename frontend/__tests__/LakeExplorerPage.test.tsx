import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import React from "react";
import LakeExplorerPage from "../app/dashboards/lake-explorer/page";
import { LanguageProvider } from "../app/contexts/LanguageContext";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
  API_BASE: "http://localhost:8000",
}));

import { apiFetch } from "@/lib/api";

const AXES = {
  axes: [
    { axis: "journal_scientometrics", views: ["v_journal_yearly", "v_journal_citation_trend"] },
    { axis: "collaboration_networks", views: ["v_coauthor_pairs", "v_institution_collab"] },
  ],
};

const QUERY_RESULT = {
  view: "v_journal_yearly",
  columns: ["issn_l", "publication_year", "works", "citations", "mean_citations", "oa_share"],
  rows: [
    ["0028-0836", 2015, 9, 168525, 18725.0, 0.4444],
    ["0028-0836", 2020, 6, 47284, 7880.666, 0.5],
  ],
  total: 2,
  limit: 50,
  offset: 0,
};

function jsonResponse(status: number, body: unknown) {
  return { status, ok: status >= 200 && status < 300, json: async () => body } as Response;
}

function mockRoutes(queryBody: unknown = QUERY_RESULT, status = 200) {
  vi.mocked(apiFetch).mockImplementation(async (path: string) => {
    if (path.startsWith("/admin/openalex-lake/views")) return jsonResponse(200, AXES);
    return jsonResponse(status, queryBody);
  });
}

function renderPage() {
  localStorage.setItem("app_lang", "en"); // LanguageProvider defaults to "es"
  return render(
    <LanguageProvider>
      <LakeExplorerPage />
    </LanguageProvider>
  );
}

afterEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

test("shows admin-required on 403", async () => {
  vi.mocked(apiFetch).mockResolvedValue(jsonResponse(403, {}));
  renderPage();
  await waitFor(() => expect(screen.getByText("Admin access required")).toBeInTheDocument());
});

test("renders the axis-grouped view picker and the result table", async () => {
  mockRoutes();
  renderPage();

  await waitFor(() => expect(screen.getByText("Journal scientometrics")).toBeInTheDocument());
  expect(screen.getByText("Collaboration networks")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "v_coauthor_pairs" })).toBeInTheDocument();

  // Table content: formatted numbers + row count badge.
  await waitFor(() => expect(screen.getByText("168,525")).toBeInTheDocument());
  expect(screen.getByText("2 rows")).toBeInTheDocument();
  expect(screen.getAllByText("0028-0836").length).toBeGreaterThan(0);
});

test("switching view re-queries with that view's endpoint", async () => {
  mockRoutes();
  renderPage();
  await waitFor(() => expect(screen.getByRole("button", { name: "v_coauthor_pairs" })).toBeInTheDocument());

  await userEvent.click(screen.getByRole("button", { name: "v_coauthor_pairs" }));
  await waitFor(() => {
    const calls = vi.mocked(apiFetch).mock.calls.map((c) => String(c[0]));
    expect(calls.some((p) => p.startsWith("/admin/openalex-lake/query/v_coauthor_pairs"))).toBe(true);
  });
});

test("shows the not-initialized state", async () => {
  mockRoutes({ lake: "not_initialized" });
  renderPage();
  await waitFor(() => expect(screen.getByText("The lake has no data yet")).toBeInTheDocument());
});

test("shows the locked state while a pull runs", async () => {
  mockRoutes({ lake: "locked" });
  renderPage();
  await waitFor(() => expect(screen.getByText("A pull is running right now")).toBeInTheDocument());
});

test("shows empty message when no rows match", async () => {
  mockRoutes({ ...QUERY_RESULT, rows: [], total: 0 });
  renderPage();
  await waitFor(() => expect(screen.getByText("No rows match these filters.")).toBeInTheDocument());
});
