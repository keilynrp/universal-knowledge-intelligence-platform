import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Button from "../app/components/ui/Button";
import IconButton from "../app/components/ui/IconButton";

describe("Button", () => {
  it("defaults to a non-submit button", () => {
    render(<Button>Inspect</Button>);
    expect(screen.getByRole("button", { name: "Inspect" })).toHaveAttribute("type", "button");
  });

  it("uses governed semantic tokens for the primary variant", () => {
    render(<Button>Save</Button>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(button.className).toContain("var(--ukip-primary)");
    expect(button.className).toContain("var(--ukip-on-primary)");
  });

  it("prevents duplicate actions while loading", () => {
    const onClick = vi.fn();
    render(
      <Button loading loadingLabel="Saving…" onClick={onClick}>
        Save
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Saving…" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("IconButton", () => {
  it("requires and exposes an accessible label", () => {
    render(<IconButton label="Open filters">+</IconButton>);
    expect(screen.getByRole("button", { name: "Open filters" })).toHaveAttribute("title", "Open filters");
  });
});
