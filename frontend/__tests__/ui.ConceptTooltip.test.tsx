import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ConceptTooltip from "../app/components/ui/ConceptTooltip";
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
});
