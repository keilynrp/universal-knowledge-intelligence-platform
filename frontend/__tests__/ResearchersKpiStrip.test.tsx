import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

import KpiStrip from "../app/analytics/researchers/components/KpiStrip";

describe("KpiStrip", () => {
  it("renders all KPI labels and values", () => {
    render(
      <KpiStrip
        topic="open science"
        researcherCount={7}
        totalCitations={1200}
        networkDensity={42}
        confidence={88}
        topResearcherName="Brian A. Nosek"
      />,
    );
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("1200")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("88")).toBeInTheDocument();
    expect(screen.getByText("Brian A. Nosek")).toBeInTheDocument();
    expect(screen.getByText(/Investigadores/i)).toBeInTheDocument();
  });
});
