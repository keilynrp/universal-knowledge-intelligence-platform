import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TabNav from "../app/components/ui/TabNav";

const tabs = [
  { id: "overview", label: "Overview" },
  { id: "analytics", label: "Analytics" },
  { id: "settings", label: "Settings" },
];

describe("TabNav", () => {
  it("renders all tab labels", () => {
    render(<TabNav tabs={tabs} activeTab="overview" onTabChange={vi.fn()} />);
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Analytics")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("active tab has blue border class", () => {
    render(<TabNav tabs={tabs} activeTab="analytics" onTabChange={vi.fn()} />);
    const active = screen.getByRole("button", { name: "Analytics" });
    expect(active.className).toContain("border-blue-600");
  });

  it("inactive tab does not have blue border class", () => {
    render(<TabNav tabs={tabs} activeTab="overview" onTabChange={vi.fn()} />);
    const inactive = screen.getByRole("button", { name: "Analytics" });
    expect(inactive.className).not.toContain("border-blue-600");
  });

  it("calls onTabChange with correct id when tab is clicked", () => {
    const onChange = vi.fn();
    render(<TabNav tabs={tabs} activeTab="overview" onTabChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(onChange).toHaveBeenCalledWith("settings");
  });

  it("renders badge count when badge prop is provided", () => {
    const tabsWithBadge = [{ id: "queue", label: "Queue", badge: 5 }];
    render(<TabNav tabs={tabsWithBadge} activeTab="queue" onTabChange={vi.fn()} />);
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("does not render badge element when badge is absent", () => {
    render(<TabNav tabs={[{ id: "a", label: "A" }]} activeTab="a" onTabChange={vi.fn()} />);
    // No span with rounded-full (badge class) inside the button
    const btn = screen.getByRole("button", { name: "A" });
    expect(btn.querySelector("span")).toBeNull();
  });
});
