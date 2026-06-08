import { render, screen } from "@testing-library/react";
import Select from "@/app/components/ui/Select";

describe("Select", () => {
  it("associates its label with the combobox", () => {
    render(
      <Select id="country" label="Country">
        <option value="mx">Mexico</option>
      </Select>,
    );

    expect(screen.getByRole("combobox", { name: "Country" })).toHaveAttribute("id", "country");
  });

  it("uses the name as the id and associates hint text", () => {
    render(
      <Select name="language" label="Language" hint="Choose your preferred language.">
        <option value="en">English</option>
      </Select>,
    );

    const select = screen.getByRole("combobox", { name: "Language" });
    expect(select).toHaveAttribute("id", "language");
    expect(select).toHaveAttribute("aria-describedby", "language-hint");
    expect(screen.getByText("Choose your preferred language.")).toHaveAttribute("id", "language-hint");
  });

  it("gives errors precedence over hints", () => {
    render(
      <Select
        id="category"
        label="Category"
        hint="Choose the closest match."
        error="Category is required."
      >
        <option value="">Select one</option>
      </Select>,
    );

    const select = screen.getByRole("combobox", { name: "Category" });
    expect(select).toHaveAttribute("aria-invalid", "true");
    expect(select).toHaveAttribute("aria-describedby", "category-error");
    expect(screen.getByText("Category is required.")).toHaveAttribute("id", "category-error");
    expect(screen.queryByText("Choose the closest match.")).not.toBeInTheDocument();
  });

  it("merges and normalizes caller description references with the internal id", () => {
    render(
      <Select
        id="topic"
        aria-label="Topic"
        aria-describedby="  topic-context   topic-hint  topic-context "
        hint="Choose a precise topic."
      >
        <option value="science">Science</option>
      </Select>,
    );

    expect(screen.getByRole("combobox", { name: "Topic" })).toHaveAttribute(
      "aria-describedby",
      "topic-context topic-hint",
    );
  });

  it("preserves caller-provided invalid state without an error", () => {
    render(
      <Select aria-label="Status" aria-invalid="grammar" aria-describedby="status-help">
        <option value="draft">Draft</option>
      </Select>,
    );

    const select = screen.getByRole("combobox", { name: "Status" });
    expect(select).toHaveAttribute("aria-invalid", "grammar");
    expect(select).toHaveAttribute("aria-describedby", "status-help");
  });

  it("uses a generated id when accessible content exists without id or name", () => {
    render(
      <Select label="Organisation" hint="Choose the registered organisation.">
        <option value="one">Organisation One</option>
      </Select>,
    );

    const select = screen.getByRole("combobox", { name: "Organisation" });
    const selectId = select.getAttribute("id");

    expect(selectId).toBeTruthy();
    expect(selectId).not.toContain("undefined");
    expect(select).toHaveAttribute("aria-describedby", `${selectId}-hint`);
    expect(screen.getByText("Choose the registered organisation.")).toHaveAttribute(
      "id",
      `${selectId}-hint`,
    );
  });

  it("preserves children, native props, and extends the visual classes", () => {
    render(
      <Select aria-label="Priority" disabled required defaultValue="high" className="custom-select">
        <option value="low">Low</option>
        <option value="high">High</option>
      </Select>,
    );

    const select = screen.getByRole("combobox", { name: "Priority" });
    expect(select).toBeDisabled();
    expect(select).toBeRequired();
    expect(select).toHaveValue("high");
    expect(select).toHaveClass("ukip-focus", "h-10", "custom-select");
    expect(screen.getByRole("option", { name: "High" })).toBeInTheDocument();
  });
});
