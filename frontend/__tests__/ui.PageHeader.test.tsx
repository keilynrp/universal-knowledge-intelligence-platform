import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PageHeader from "../app/components/ui/PageHeader";

describe("PageHeader", () => {
  it("renders the title as h1", () => {
    render(<PageHeader title="Knowledge Dashboard" />);
    expect(screen.getByRole("heading", { level: 1, name: "Knowledge Dashboard" })).toBeInTheDocument();
  });

  it("renders description when provided", () => {
    render(<PageHeader title="T" description="Manage all your entities here" />);
    expect(screen.getByText("Manage all your entities here")).toBeInTheDocument();
  });

  it("does not render description when omitted", () => {
    const { queryByText } = render(<PageHeader title="T" />);
    expect(queryByText("Manage all your entities here")).not.toBeInTheDocument();
  });

  it("renders breadcrumb labels", () => {
    render(
      <PageHeader
        title="T"
        breadcrumbs={[{ label: "Home" }, { label: "Analytics" }]}
      />
    );
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Analytics")).toBeInTheDocument();
  });

  it("renders breadcrumb item with href as a link", () => {
    render(
      <PageHeader
        title="T"
        breadcrumbs={[{ label: "Home", href: "/" }, { label: "Reports" }]}
      />
    );
    const link = screen.getByRole("link", { name: "Home" });
    expect(link).toHaveAttribute("href", "/");
  });

  it("renders breadcrumb item without href as plain text", () => {
    render(<PageHeader title="T" breadcrumbs={[{ label: "Current Page" }]} />);
    // no link, just a span
    expect(screen.queryByRole("link", { name: "Current Page" })).toBeNull();
    expect(screen.getByText("Current Page")).toBeInTheDocument();
  });

  it("renders actions slot", () => {
    render(
      <PageHeader
        title="T"
        actions={<button>Export</button>}
      />
    );
    expect(screen.getByRole("button", { name: "Export" })).toBeInTheDocument();
  });

  it("does not render nav when breadcrumbs are omitted", () => {
    const { container } = render(<PageHeader title="T" />);
    expect(container.querySelector("nav")).toBeNull();
  });
});
