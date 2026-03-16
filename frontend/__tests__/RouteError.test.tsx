import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import RouteError from "../app/components/RouteError";

const baseError = new Error("Something exploded") as Error & { digest?: string };

describe("RouteError", () => {
  it("renders the default title when no title prop given", () => {
    render(<RouteError error={baseError} reset={vi.fn()} />);
    expect(screen.getByText("Failed to load this page")).toBeInTheDocument();
  });

  it("renders a custom title when provided", () => {
    render(<RouteError title="Entities failed to load" error={baseError} reset={vi.fn()} />);
    expect(screen.getByText("Entities failed to load")).toBeInTheDocument();
  });

  it("renders the error message", () => {
    render(<RouteError error={baseError} reset={vi.fn()} />);
    expect(screen.getByText("Something exploded")).toBeInTheDocument();
  });

  it("renders fallback message when error.message is empty", () => {
    const emptyError = new Error("") as Error & { digest?: string };
    render(<RouteError error={emptyError} reset={vi.fn()} />);
    expect(screen.getByText("An unexpected error occurred.")).toBeInTheDocument();
  });

  it("renders error digest when present", () => {
    const digestError = Object.assign(new Error("Oops"), { digest: "abc123" });
    render(<RouteError error={digestError} reset={vi.fn()} />);
    expect(screen.getByText(/abc123/)).toBeInTheDocument();
  });

  it("does not render digest element when digest is absent", () => {
    render(<RouteError error={baseError} reset={vi.fn()} />);
    expect(screen.queryByText(/ID:/)).not.toBeInTheDocument();
  });

  it("calls reset when Try again is clicked", () => {
    const reset = vi.fn();
    render(<RouteError error={baseError} reset={reset} />);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("renders Home link", () => {
    render(<RouteError error={baseError} reset={vi.fn()} />);
    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
  });
});
