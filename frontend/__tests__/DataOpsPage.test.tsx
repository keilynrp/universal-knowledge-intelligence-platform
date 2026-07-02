import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import React from "react";
import DataOpsPage from "../app/dashboards/data-ops/page";
import { LanguageProvider } from "../app/contexts/LanguageContext";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
  API_BASE: "http://localhost:8000",
}));

import { apiFetch } from "@/lib/api";

function renderPage() {
  localStorage.setItem("app_lang", "en"); // LanguageProvider defaults to "es"
  return render(
    <LanguageProvider>
      <DataOpsPage />
    </LanguageProvider>
  );
}

function jsonResponse(status: number, body: unknown) {
  return { status, ok: status >= 200 && status < 300, json: async () => body } as Response;
}

afterEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

test("shows the admin-required message on 403", async () => {
  vi.mocked(apiFetch).mockResolvedValue(jsonResponse(403, {}));
  renderPage();
  await waitFor(() => expect(screen.getByText("Admin access required")).toBeInTheDocument());
});

test("shows the not-initialized state before any pull has run", async () => {
  vi.mocked(apiFetch).mockResolvedValue(
    jsonResponse(200, { lake: "not_initialized", hint: "run: python -m backend.openalex_lake.pull_works" })
  );
  renderPage();
  await waitFor(() => expect(screen.getByText("No pull has run yet")).toBeInTheDocument());
  expect(screen.getByText("run: python -m backend.openalex_lake.pull_works")).toBeInTheDocument();
});

test("shows the locked state while a pull is running", async () => {
  vi.mocked(apiFetch).mockResolvedValue(jsonResponse(200, { lake: "locked" }));
  renderPage();
  await waitFor(() => expect(screen.getByText("A pull is running right now")).toBeInTheDocument());
});

test("shows last-known progress while locked, from the sidecar snapshot", async () => {
  vi.mocked(apiFetch).mockResolvedValue(
    jsonResponse(200, {
      lake: "locked",
      hint: "a pull is currently running; re-check once it finishes",
      last_known: {
        phase: "backfill",
        backfill_journals_done: 5,
        backfill_total_issns: 270,
        journals: 49,
        tables: { fact_works: 214573 },
        rate_limit: { limit: 10000, remaining: 9800, captured_at: new Date().toISOString() },
        snapshot_captured_at: new Date().toISOString(),
      },
    })
  );
  renderPage();
  await waitFor(() => expect(screen.getByText("pull running now")).toBeInTheDocument());
  expect(
    screen.getByText(
      "Showing the last progress snapshot the pull saved on its own — the lake file is locked while it writes."
    )
  ).toBeInTheDocument();
  expect(screen.getByText("5 / 270")).toBeInTheDocument();
  expect(screen.getByText("214,573")).toBeInTheDocument();
  // The bare "come back later" empty state must NOT show once real progress is available.
  expect(screen.queryByText("A pull is running right now")).not.toBeInTheDocument();
});

test("renders backfill progress, quota, and table counts on the happy path", async () => {
  vi.mocked(apiFetch).mockResolvedValue(
    jsonResponse(200, {
      phase: "backfill",
      works_watermark: null,
      backfill_journals_done: 134,
      backfill_total_issns: 270,
      journals: 134,
      year_min: 2010,
      year_max: 2025,
      tables: { fact_works: 48213, dim_author: 9012 },
      rate_limit: {
        limit: 10000,
        remaining: 9412,
        prepaid_remaining_usd: 1.87,
        last_request_cost_usd: 0.0001,
        captured_at: new Date().toISOString(),
      },
    })
  );
  renderPage();

  await waitFor(() => expect(screen.getByText("Backfill in progress")).toBeInTheDocument());
  expect(screen.getByText("134 / 270")).toBeInTheDocument();
  expect(screen.getByText("9,412 / 10,000")).toBeInTheDocument();
  expect(screen.getByText("$1.8700")).toBeInTheDocument();
  expect(screen.getByText("48,213")).toBeInTheDocument();
  // Captured just now (< 5 min window) -> "active" freshness badge, no extra request made to check it.
  expect(screen.getByText("just now")).toBeInTheDocument();
  expect(screen.getByText("pull likely active")).toBeInTheDocument();
});

test("marks a stale quota snapshot instead of an active one", async () => {
  const tenMinutesAgo = new Date(Date.now() - 10 * 60_000).toISOString();
  vi.mocked(apiFetch).mockResolvedValue(
    jsonResponse(200, {
      phase: "backfill",
      backfill_journals_done: 1,
      backfill_total_issns: 270,
      journals: 1,
      tables: { fact_works: 5 },
      rate_limit: { limit: 10000, remaining: 9999, captured_at: tenMinutesAgo },
    })
  );
  renderPage();
  await waitFor(() => expect(screen.getByText("last known — no recent pull")).toBeInTheDocument());
  expect(screen.getByText("10 min ago")).toBeInTheDocument();
  expect(screen.queryByText("pull likely active")).not.toBeInTheDocument();
});

test("renders the incremental phase badge once the backfill is complete", async () => {
  vi.mocked(apiFetch).mockResolvedValue(
    jsonResponse(200, {
      phase: "incremental",
      works_watermark: "2026-07-01",
      backfill_journals_done: 0,
      backfill_total_issns: 270,
      journals: 270,
      year_min: 2010,
      year_max: 2025,
      tables: { fact_works: 200000 },
      rate_limit: null,
    })
  );
  renderPage();
  await waitFor(() => expect(screen.getByText("Incremental (up to date)")).toBeInTheDocument());
  expect(screen.getByText("2026-07-01")).toBeInTheDocument();
});

test("shows a retry banner when the request fails", async () => {
  vi.mocked(apiFetch).mockRejectedValue(new Error("network down"));
  renderPage();
  await waitFor(() => expect(screen.getByText("network down")).toBeInTheDocument());
});
