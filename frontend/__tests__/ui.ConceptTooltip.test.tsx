import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ConceptTooltip, { EntityConcept } from "../app/components/ui/ConceptTooltip";
import { LanguageProvider } from "../app/contexts/LanguageContext";

describe("ConceptTooltip", () => {
  it("shows the governed entity definition", () => {
    render(
      <LanguageProvider>
        <ConceptTooltip concept="entity">Entidades</ConceptTooltip>
      </LanguageProvider>,
    );

    fireEvent.click(screen.getByRole("button"));

    expect(screen.getByRole("tooltip")).toHaveTextContent("Entidad");
    expect(screen.getByRole("tooltip")).toHaveTextContent("unidad canónica");
    expect(screen.getByRole("tooltip")).toHaveTextContent("sin borrar su procedencia");
  });

  it("supports hover, focus, Escape, and an always-associated screen-reader definition", () => {
    render(
      <LanguageProvider>
        <EntityConcept>Total de Entidades</EntityConcept>
      </LanguageProvider>,
    );

    const trigger = screen.getByRole("button");
    const descriptionId = trigger.getAttribute("aria-describedby");

    expect(descriptionId).toBeTruthy();
    expect(document.getElementById(descriptionId!)).toHaveTextContent("unidad canónica");

    fireEvent.mouseEnter(trigger.parentElement!);
    expect(screen.getByRole("tooltip")).toBeVisible();

    fireEvent.mouseLeave(trigger.parentElement!);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    fireEvent.focus(trigger);
    expect(screen.getByRole("tooltip")).toBeVisible();

    fireEvent.keyDown(trigger, { key: "Escape" });
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });
});
