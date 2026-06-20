import { render, screen } from "@testing-library/react";
import { JournalsCharts } from "../app/analytics/journals/JournalsCharts";

const stats = {
  apc_distribution: [{ currency: "USD", count: 2, min: 1000, max: 3000, median: 2000 }],
  open_access_share: { in_doaj: 2, total: 3, pct: 66.7 },
  nif_by_field: [{ nif_field: "Genetics", journal_count: 2, mean_nif: 1.5 }],
};

test("renders the open-access share figure", () => {
  render(<JournalsCharts stats={stats} />);
  expect(screen.getByText(/66\.7/)).toBeInTheDocument();
});

test("renders chart section headings", () => {
  render(<JournalsCharts stats={stats} />);
  expect(screen.getByText(/APC/i)).toBeInTheDocument();
  expect(screen.getByText(/discipline|subfield|field/i)).toBeInTheDocument();
});

test("renders empty state when stats null", () => {
  render(<JournalsCharts stats={null} />);
  expect(screen.getByText(/no data|not available|no journals/i)).toBeInTheDocument();
});
