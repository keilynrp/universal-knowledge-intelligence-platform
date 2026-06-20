import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { JournalMetricsSection } from "../app/components/JournalMetricsSection";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));
import { apiFetch } from "@/lib/api";

test("does not fetch when issn_l absent", () => {
  render(<JournalMetricsSection issnL={null} />);
  expect(apiFetch).not.toHaveBeenCalled();
});

test("renders NIF + APC when journal found", async () => {
  (apiFetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true, status: 200, json: async () => ({
    issn_l: "0028-0836", display_name: "Nature", normalized_impact_factor: 1.5,
    two_yr_mean_citedness: 17.4, h_index: 1200, apc_usd: 11690, apc_currency: "USD",
    is_in_doaj: false, nif_field: "Genetics" }) });
  render(<JournalMetricsSection issnL="0028-0836" />);
  await waitFor(() => expect(screen.getByText(/Nature/)).toBeInTheDocument());
  expect(screen.getByText(/1\.5/)).toBeInTheDocument();
});

test("404 shows subtle not-yet-enriched note", async () => {
  (apiFetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: false, status: 404, json: async () => ({}) });
  render(<JournalMetricsSection issnL="X" />);
  await waitFor(() => expect(screen.getByText(/not yet/i)).toBeInTheDocument());
});
