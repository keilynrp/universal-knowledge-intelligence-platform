import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Button from "../app/components/ui/Button";

describe("Button", () => {
  it("defaults to type button", () => {
    render(<Button>Save</Button>);

    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute(
      "type",
      "button",
    );
  });

  it("forwards the disabled state", () => {
    render(<Button disabled>Save</Button>);

    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it.each([
    ["primary", "bg-[var(--ukip-primary)]"],
    ["danger", "bg-[var(--ukip-danger)]"],
  ] as const)("applies the %s semantic UKIP class", (variant, className) => {
    render(<Button variant={variant}>{variant}</Button>);

    expect(screen.getByRole("button", { name: variant })).toHaveClass(className);
  });

  it("renders optional left and right icons around its content", () => {
    render(
      <Button
        leftIcon={<span data-testid="left-icon">L</span>}
        rightIcon={<span data-testid="right-icon">R</span>}
      >
        Continue
      </Button>,
    );

    const button = screen.getByRole("button", { name: "LContinueR" });
    expect(button.firstElementChild).toBe(screen.getByTestId("left-icon"));
    expect(button.lastElementChild).toBe(screen.getByTestId("right-icon"));
  });

  it.each([
    ["sm", "h-8 px-3 text-xs"],
    ["md", "h-10 px-4 text-sm"],
    ["lg", "h-11 px-5 text-sm"],
    ["icon", "h-10 w-10 p-0"],
  ] as const)("applies the %s size classes", (size, className) => {
    render(
      <Button size={size} aria-label={size === "icon" ? "Settings" : undefined}>
        {size === "icon" ? null : size}
      </Button>,
    );

    expect(
      screen.getByRole("button", {
        name: size === "icon" ? "Settings" : size,
      }),
    ).toHaveClass(className);
  });

  it("accepts a non-empty aria-labelledby for icon-only buttons", () => {
    render(
      <>
        <span id="settings-label">Settings</span>
        <Button size="icon" aria-labelledby="settings-label">
          <span aria-hidden="true">X</span>
        </Button>
      </>,
    );

    expect(screen.getByRole("button", { name: "Settings" })).toBeInTheDocument();
  });

  it.each([
    [undefined, undefined],
    ["", ""],
    ["   ", "   "],
  ])(
    "requires a non-empty aria-label or aria-labelledby for icon-only buttons",
    (ariaLabel, ariaLabelledBy) => {
      expect(() =>
        render(
          <Button
            size="icon"
            aria-label={ariaLabel}
            aria-labelledby={ariaLabelledBy}
          >
            <span aria-hidden="true">X</span>
          </Button>,
        ),
      ).toThrow(/non-empty aria-label or aria-labelledby/i);
    },
  );

  it("does not block rendering an unlabeled icon button in production", () => {
    const originalNodeEnv = process.env.NODE_ENV;
    vi.stubEnv("NODE_ENV", "production");

    try {
      expect(() =>
        render(
          <Button size="icon">
            <span aria-hidden="true">X</span>
          </Button>,
        ),
      ).not.toThrow();
      expect(screen.getByRole("button")).toBeInTheDocument();
    } finally {
      vi.unstubAllEnvs();
    }

    expect(process.env.NODE_ENV).toBe(originalNodeEnv);
  });
});
