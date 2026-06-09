import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Checkbox from "../app/components/ui/Checkbox";
import Input from "../app/components/ui/Input";
import Label from "../app/components/ui/Label";
import Radio from "../app/components/ui/Radio";
import Select from "../app/components/ui/Select";
import Switch from "../app/components/ui/Switch";
import Textarea from "../app/components/ui/Textarea";

describe("governed form controls", () => {
  it("connects input label, hint, and error semantics", () => {
    render(
      <Input
        label="Institution"
        hint="Use the canonical name."
        error="Institution is required."
        required
      />,
    );

    const input = screen.getByRole("textbox", { name: /Institution/ });
    const describedBy = input.getAttribute("aria-describedby") ?? "";

    expect(input).toBeRequired();
    expect(input).toHaveAttribute("aria-invalid", "true");
    // Error takes precedence over the hint: only the error is announced, and the
    // hint is suppressed (see ui.Input.test.tsx "gives errors precedence over hints").
    expect(describedBy).toContain("-error");
    expect(describedBy).not.toContain("-hint");
    expect(screen.queryByText("Use the canonical name.")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Institution is required.");
  });

  it("exposes a standalone governed label primitive", () => {
    render(
      <>
        <Label htmlFor="external-id" required>
          External ID
        </Label>
        <input id="external-id" />
      </>,
    );

    expect(screen.getByLabelText(/External ID/)).toBeInTheDocument();
  });

  it("provides equivalent semantics for select and textarea", () => {
    render(
      <>
        <Select label="Entity type" error="Choose a type.">
          <option value="">Choose…</option>
        </Select>
        <Textarea label="Review note" hint="Visible to reviewers." />
      </>,
    );

    expect(screen.getByRole("combobox", { name: "Entity type" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("textbox", { name: "Review note" })).toHaveAttribute("aria-describedby");
  });

  it("keeps checkbox and radio labels inside the control hit target", () => {
    render(
      <>
        <Checkbox label="Include provenance" />
        <Radio label="Canonical record" name="record-type" />
      </>,
    );

    expect(screen.getByRole("checkbox", { name: "Include provenance" }).closest("label")).not.toBeNull();
    expect(screen.getByRole("radio", { name: "Canonical record" }).closest("label")).not.toBeNull();
  });

  it("exposes switch state and toggles it through the governed callback", () => {
    const onCheckedChange = vi.fn();
    render(
      <Switch
        checked={false}
        label="Require review"
        description="Route uncertain records to the authority queue."
        onCheckedChange={onCheckedChange}
      />,
    );

    const control = screen.getByRole("switch", { name: "Require review" });
    expect(control).toHaveAttribute("aria-checked", "false");
    expect(control).toHaveAttribute("aria-describedby");
    fireEvent.click(control);
    expect(onCheckedChange).toHaveBeenCalledWith(true);
  });
});
