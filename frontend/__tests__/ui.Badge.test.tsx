import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import Badge from "../app/components/ui/Badge";

const variants = [
  ["default", "bg-[var(--ukip-panel-strong)]", "text-[var(--ukip-muted)]", "bg-[var(--ukip-muted-soft)]"],
  ["success", "bg-[var(--ukip-success-soft)]", "text-[var(--ukip-success)]", "bg-[var(--ukip-success)]"],
  ["warning", "bg-[var(--ukip-warning-soft)]", "text-[var(--ukip-warning)]", "bg-[var(--ukip-warning)]"],
  ["error", "bg-[var(--ukip-danger-soft)]", "text-[var(--ukip-danger)]", "bg-[var(--ukip-danger)]"],
  ["info", "bg-[var(--ukip-info-soft)]", "text-[var(--ukip-info)]", "bg-[var(--ukip-info)]"],
  ["purple", "bg-[var(--ukip-primary-soft)]", "text-[var(--ukip-violet)]", "bg-[var(--ukip-violet)]"],
] as const;

describe("Badge", () => {
  it("renders children text", () => {
    render(<Badge>Active</Badge>);

    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it.each(variants)(
    "uses semantic tokens for the %s variant",
    (variant, backgroundClass, textClass) => {
      render(<Badge variant={variant}>{variant}</Badge>);

      expect(screen.getByText(variant)).toHaveClass(backgroundClass, textClass);
    },
  );

  it.each(variants)(
    "uses the matching semantic foreground token for the %s dot",
    (variant, _backgroundClass, _textClass, dotClass) => {
      render(
        <Badge variant={variant} dot>
          {variant}
        </Badge>,
      );

      const badge = screen.getByText(variant);
      const dots = within(badge).getAllByTestId("badge-dot");
      expect(dots).toHaveLength(1);
      expect(dots[0]).toHaveClass(dotClass);
    },
  );

  it("renders a pulsing dot with the same semantic token", () => {
    render(
      <Badge variant="success" dot dotPulse>
        Live
      </Badge>,
    );

    const badge = screen.getByText("Live");
    expect(within(badge).getByTestId("badge-dot-pulse")).toHaveClass(
      "animate-ping",
      "bg-[var(--ukip-success)]",
    );
    expect(within(badge).getByTestId("badge-dot")).toHaveClass("bg-[var(--ukip-success)]");
  });

  it("does not render dot elements unless dot is enabled", () => {
    render(<Badge dotPulse>Quiet</Badge>);

    const badge = screen.getByText("Quiet");
    expect(within(badge).queryByTestId("badge-dot")).not.toBeInTheDocument();
    expect(within(badge).queryByTestId("badge-dot-pulse")).not.toBeInTheDocument();
  });

  it.each([
    ["sm", "px-2", "py-0.5", "text-xs"],
    ["md", "px-2.5", "py-1", "text-sm"],
  ] as const)("preserves the %s size classes", (size, paddingX, paddingY, textSize) => {
    render(<Badge size={size}>{size}</Badge>);

    expect(screen.getByText(size)).toHaveClass(paddingX, paddingY, textSize);
  });
});
