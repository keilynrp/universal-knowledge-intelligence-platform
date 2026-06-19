import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";

const apiFetch = vi.fn();
vi.mock("@/lib/api", () => ({ apiFetch: (...a: unknown[]) => apiFetch(...a) }));

let mockRole = "viewer";
vi.mock("../app/contexts/AuthContext", () => ({
  useAuth: () => ({ user: { username: "u", role: mockRole } }),
}));

vi.mock("../app/components/ui/Toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

import JournalsDashboardPage from "../app/analytics/journals/page";

function mockList() {
  return {
    ok: true,
    status: 200,
    headers: { get: () => "1" },
    json: async () => ([
      {
        issn_l: "0028-0836",
        display_name: "Nature",
        nif_field: "Genetics",
        normalized_impact_factor: 1.5,
        two_yr_mean_citedness: 17.4,
        h_index: 1200,
        apc_usd: 11690,
        apc_currency: "USD",
        is_in_doaj: false,
      },
    ]),
  };
}

function mockStats() {
  return {
    ok: true,
    status: 200,
    json: async () => ({
      apc_distribution: [{ currency: "USD", count: 1, min: 11690, max: 11690, median: 11690 }],
      open_access_share: { in_doaj: 0, total: 1, pct: 0.0 },
      nif_by_field: [],
    }),
  };
}

beforeEach(() => {
  apiFetch.mockReset();
  apiFetch.mockImplementation((path: string) =>
    Promise.resolve(path.includes("/stats") ? mockStats() : mockList())
  );
});

test("fetches journals + stats and renders the table", async () => {
  mockRole = "viewer";
  render(<JournalsDashboardPage />);
  await waitFor(() => expect(screen.getByText("Nature")).toBeInTheDocument());
});

test("admin sees Recompute button; viewer does not", async () => {
  mockRole = "viewer";
  const { unmount } = render(<JournalsDashboardPage />);
  await waitFor(() => expect(screen.getByText("Nature")).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: /recompute/i })).not.toBeInTheDocument();
  unmount();
  mockRole = "admin";
  render(<JournalsDashboardPage />);
  await waitFor(() => expect(screen.getByRole("button", { name: /recompute/i })).toBeInTheDocument());
});

test("clicking Recompute POSTs to /journals/normalize", async () => {
  mockRole = "admin";
  render(<JournalsDashboardPage />);
  await waitFor(() => expect(screen.getByRole("button", { name: /recompute/i })).toBeInTheDocument());
  apiFetch.mockImplementationOnce(() =>
    Promise.resolve({ ok: true, status: 200, json: async () => ({ updated: 3 }) })
  );
  fireEvent.click(screen.getByRole("button", { name: /recompute/i }));
  await waitFor(() =>
    expect(apiFetch).toHaveBeenCalledWith(
      "/journals/normalize",
      expect.objectContaining({ method: "POST" })
    )
  );
});
