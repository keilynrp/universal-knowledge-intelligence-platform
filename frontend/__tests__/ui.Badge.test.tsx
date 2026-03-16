import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Badge from "../app/components/ui/Badge";

describe("Badge", () => {
  it("renders children text", () => {
    render(<Badge>Active</Badge>);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("default variant includes gray background class", () => {
    const { container } = render(<Badge>Default</Badge>);
    const el = container.querySelector("span");
    expect(el?.className).toContain("bg-gray-100");
  });

  it("success variant includes emerald background class", () => {
    const { container } = render(<Badge variant="success">OK</Badge>);
    const el = container.querySelector("span");
    expect(el?.className).toContain("bg-emerald-50");
  });

  it("error variant includes red background class", () => {
    const { container } = render(<Badge variant="error">Fail</Badge>);
    const el = container.querySelector("span");
    expect(el?.className).toContain("bg-red-50");
  });

  it("warning variant includes amber background class", () => {
    const { container } = render(<Badge variant="warning">Warn</Badge>);
    const el = container.querySelector("span");
    expect(el?.className).toContain("bg-amber-50");
  });

  it("info variant includes blue background class", () => {
    const { container } = render(<Badge variant="info">Info</Badge>);
    const el = container.querySelector("span");
    expect(el?.className).toContain("bg-blue-50");
  });

  it("renders dot indicator when dot=true", () => {
    const { container } = render(<Badge dot>Live</Badge>);
    // dot renders a nested <span> with relative flex
    const dots = container.querySelectorAll("span > span");
    expect(dots.length).toBeGreaterThan(0);
  });

  it("md size has larger padding than sm", () => {
    const { container: sm } = render(<Badge size="sm">S</Badge>);
    const { container: md } = render(<Badge size="md">M</Badge>);
    const smClass = sm.querySelector("span")?.className ?? "";
    const mdClass = md.querySelector("span")?.className ?? "";
    expect(smClass).toContain("px-2 py-0.5 text-xs");
    expect(mdClass).toContain("px-2.5 py-1 text-sm");
  });
});
