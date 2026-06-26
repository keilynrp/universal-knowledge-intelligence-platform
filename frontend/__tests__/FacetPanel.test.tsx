import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import FacetPanel from "../app/components/FacetPanel";
import { LanguageProvider } from "../app/contexts/LanguageContext";

// ── Mock apiFetch ─────────────────────────────────────────────────────────────

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
  API_BASE: "http://localhost:8000",
}));

// ── Mock ui (EntityConcept used inside FacetPanel) ────────────────────────────

vi.mock("../app/components/ui", () => ({
  EntityConcept: ({ children }: { children: React.ReactNode }) => (
    <span>{children}</span>
  ),
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderWithLanguage(ui: React.ReactElement, lang = "en") {
  localStorage.setItem("app_lang", lang);
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("FacetPanel — work_type facet", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("renders the 'Work type' label and 'Book' value in English when facetsData includes work_type", async () => {
    const facetsData = {
      work_type: [{ value: "book", count: 3 }],
    };

    renderWithLanguage(
      <FacetPanel
        activeFacets={{}}
        onFacetChange={vi.fn()}
        facetsData={facetsData}
      />,
      "en"
    );

    await waitFor(() => {
      expect(screen.getByText("Work type")).toBeInTheDocument();
    });
    expect(screen.getByText("Book")).toBeInTheDocument();
  });

  it("renders 'Tipo de obra' label and 'Libro' value in Spanish", async () => {
    const facetsData = {
      work_type: [{ value: "book", count: 3 }],
    };

    renderWithLanguage(
      <FacetPanel
        activeFacets={{}}
        onFacetChange={vi.fn()}
        facetsData={facetsData}
      />,
      "es"
    );

    await waitFor(() => {
      expect(screen.getByText("Tipo de obra")).toBeInTheDocument();
    });
    expect(screen.getByText("Libro")).toBeInTheDocument();
  });

  it("calls onFacetChange('work_type', 'book') when the book value is clicked", async () => {
    const onFacetChange = vi.fn();
    const facetsData = {
      work_type: [{ value: "book", count: 3 }],
    };

    renderWithLanguage(
      <FacetPanel
        activeFacets={{}}
        onFacetChange={onFacetChange}
        facetsData={facetsData}
      />,
      "en"
    );

    await waitFor(() => expect(screen.getByText("Book")).toBeInTheDocument());

    await userEvent.click(screen.getByText("Book"));

    expect(onFacetChange).toHaveBeenCalledWith("work_type", "book");
  });
});
