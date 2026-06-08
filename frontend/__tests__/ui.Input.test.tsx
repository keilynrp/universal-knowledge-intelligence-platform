import { render, screen } from "@testing-library/react";
import Input from "@/app/components/ui/Input";

describe("Input", () => {
  it("associates its label with the textbox", () => {
    render(<Input id="email" label="Email address" />);

    expect(screen.getByRole("textbox", { name: "Email address" })).toHaveAttribute("id", "email");
  });

  it("uses the name as the id and associates hint text", () => {
    render(<Input name="username" label="Username" hint="Use your public handle." />);

    const input = screen.getByRole("textbox", { name: "Username" });
    expect(input).toHaveAttribute("id", "username");
    expect(input).toHaveAttribute("aria-describedby", "username-hint");
    expect(screen.getByText("Use your public handle.")).toHaveAttribute("id", "username-hint");
  });

  it("gives errors precedence over hints", () => {
    render(
      <Input
        id="password"
        label="Password"
        hint="At least 12 characters."
        error="Password is required."
      />,
    );

    const input = screen.getByLabelText("Password");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", "password-error");
    expect(screen.getByText("Password is required.")).toHaveAttribute("id", "password-error");
    expect(screen.queryByText("At least 12 characters.")).not.toBeInTheDocument();
  });

  it("does not force invalid state and preserves caller-provided aria props", () => {
    render(
      <Input
        id="search"
        aria-label="Knowledge search"
        aria-invalid="grammar"
        aria-describedby="search-help"
        placeholder="Search"
      />,
    );

    const input = screen.getByRole("textbox", { name: "Knowledge search" });
    expect(input).toHaveAttribute("aria-invalid", "grammar");
    expect(input).toHaveAttribute("aria-describedby", "search-help");
    expect(input).toHaveAttribute("placeholder", "Search");
  });

  it("uses a generated id when accessible content exists without id or name", () => {
    render(<Input label="Organisation" hint="Enter the registered name." />);

    const input = screen.getByRole("textbox", { name: "Organisation" });
    const inputId = input.getAttribute("id");

    expect(inputId).toBeTruthy();
    expect(inputId).not.toContain("undefined");
    expect(input).toHaveAttribute("aria-describedby", `${inputId}-hint`);
    expect(screen.getByText("Enter the registered name.")).toHaveAttribute("id", `${inputId}-hint`);
  });

  it("preserves native props and extends the visual classes", () => {
    render(<Input aria-label="Age" type="number" disabled required className="custom-input" />);

    const input = screen.getByRole("spinbutton", { name: "Age" });
    expect(input).toBeDisabled();
    expect(input).toBeRequired();
    expect(input).toHaveClass("ukip-focus", "h-10", "custom-input");
  });
});
