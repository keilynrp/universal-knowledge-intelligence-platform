import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import Badge from "../app/components/ui/Badge";

const variants = [
  ["default", "bg-panel-strong", "text-muted", "bg-muted-soft"],
  ["success", "bg-success-soft", "text-success", "bg-success"],
  ["warning", "bg-warning-soft", "text-warning", "bg-warning"],
  ["error", "bg-danger-soft", "text-danger", "bg-danger"],
  ["info", "bg-info-soft", "text-info", "bg-info"],
  ["purple", "bg-primary-soft", "text-violet", "bg-violet"],
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
      "bg-success",
    );
    expect(within(badge).getByTestId("badge-dot")).toHaveClass("bg-success");
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
