import { render, screen } from "@testing-library/react";
import { JournalSignalBadge } from "../app/components/JournalSignalBadge";

test("renders nothing when the signal is not ready", () => {
  const { container } = render(<JournalSignalBadge ready={false} />);
  expect(container).toBeEmptyDOMElement();
});

test("renders the NIF + Bayes label when ready", () => {
  render(<JournalSignalBadge ready />);
  expect(screen.getByText("NIF + Bayes")).toBeInTheDocument();
});

test("builds a tooltip with journal name, NIF and Bayes + interval", () => {
  render(
    <JournalSignalBadge
      ready
      journalName="Nature"
      nif={2.703}
      nifBayes={3.247}
      ciLow={3.23}
      ciHigh={3.26}
    />
  );
  const tip = screen.getByText("NIF + Bayes").closest("span[title]");
  expect(tip).toHaveAttribute(
    "title",
    "Nature · NIF 2.703 · NIF Bayes 3.247 (3.23–3.26)"
  );
});

test("omits the interval when CI bounds are missing", () => {
  render(<JournalSignalBadge ready nif={1.5} nifBayes={1.1} />);
  const tip = screen.getByText("NIF + Bayes").closest("span[title]");
  expect(tip).toHaveAttribute("title", "NIF 1.500 · NIF Bayes 1.100");
});
