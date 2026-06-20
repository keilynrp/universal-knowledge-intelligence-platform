import { render, screen } from "@testing-library/react";
import { JournalProvenanceBadge, formatApc } from "../app/components/JournalProvenanceBadge";

test("badge shows open-proxy provenance text", () => {
  render(<JournalProvenanceBadge />);
  expect(screen.getByText(/open proxy/i)).toBeInTheDocument();
});

test("formatApc renders amount with currency, or em dash when null", () => {
  expect(formatApc(1500, "USD")).toBe("1,500 USD");
  expect(formatApc(null, null)).toBe("—");
});
