import { render, screen, fireEvent } from "@testing-library/react";
import { vi } from "vitest";
import { JournalsRankingTable } from "../app/analytics/journals/JournalsRankingTable";

const rows = [
  { issn_l: "0028-0836", display_name: "Nature", nif_field: "Genetics",
    normalized_impact_factor: 1.5, two_yr_mean_citedness: 17.4, h_index: 1200,
    apc_usd: 11690, apc_currency: "USD", is_in_doaj: false, works_count: 42 },
];

test("renders a row with journal name and APC", () => {
  render(<JournalsRankingTable journals={rows} sortBy="nif" order="desc" onSort={() => {}} />);
  expect(screen.getByText("Nature")).toBeInTheDocument();
  expect(screen.getByText(/11,690 USD/)).toBeInTheDocument();
});

test("clicking the NIF header calls onSort('nif')", () => {
  const onSort = vi.fn();
  render(<JournalsRankingTable journals={rows} sortBy="citedness" order="desc" onSort={onSort} />);
  fireEvent.click(screen.getByRole("button", { name: /NIF/i }));
  expect(onSort).toHaveBeenCalledWith("nif");
});

test("renders the works count", () => {
  render(<JournalsRankingTable journals={rows} sortBy="nif" order="desc" onSort={() => {}} />);
  expect(screen.getByText("42")).toBeInTheDocument();
});

test("renders empty state when no journals", () => {
  render(<JournalsRankingTable journals={[]} sortBy="nif" order="desc" onSort={() => {}} />);
  expect(screen.getByText(/no journals/i)).toBeInTheDocument();
});
