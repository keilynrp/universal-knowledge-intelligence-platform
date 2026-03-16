import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import StatCard from "../app/components/ui/StatCard";

const icon = <svg data-testid="icon" />;

describe("StatCard", () => {
  it("renders the label", () => {
    render(<StatCard icon={icon} label="Total Entities" value="1,200" />);
    expect(screen.getByText("Total Entities")).toBeInTheDocument();
  });

  it("renders the value", () => {
    render(<StatCard icon={icon} label="Coverage" value="87%" />);
    expect(screen.getByText("87%")).toBeInTheDocument();
  });

  it("renders numeric value", () => {
    render(<StatCard icon={icon} label="Count" value={42} />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders subtitle when provided", () => {
    render(<StatCard icon={icon} label="L" value="V" subtitle="Powered by DuckDB" />);
    expect(screen.getByText("Powered by DuckDB")).toBeInTheDocument();
  });

  it("does not render subtitle when omitted", () => {
    render(<StatCard icon={icon} label="L" value="V" />);
    expect(screen.queryByText("Powered by DuckDB")).not.toBeInTheDocument();
  });

  it("renders trend value when provided", () => {
    render(
      <StatCard
        icon={icon}
        label="L"
        value="V"
        trend={{ value: "+12%", direction: "up", positive: true }}
      />
    );
    expect(screen.getByText("+12%")).toBeInTheDocument();
  });

  it("does not render trend badge when trend is omitted", () => {
    const { container } = render(<StatCard icon={icon} label="L" value="V" />);
    // trend badge uses rounded-full px-2 — check it's absent
    const trendBadge = container.querySelector("span.rounded-full");
    expect(trendBadge).toBeNull();
  });

  it("renders the icon slot", () => {
    render(<StatCard icon={icon} label="L" value="V" />);
    expect(screen.getByTestId("icon")).toBeInTheDocument();
  });
});
