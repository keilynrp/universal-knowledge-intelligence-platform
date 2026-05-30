import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

import ScoreBreakdown from "../app/components/ScoreBreakdown";

describe("ScoreBreakdown", () => {
  const breakdown = {
    identifiers: 0.9,
    name: 0.75,
    affiliation: 0.5,
    coauthorship: 0.0,
    topic: 0.0,
  };
  const evidence = [
    "source_quality:openalex=0.60",
    "name_score:0.750",
    "feedback_prior:+0.030",
  ];

  it("renders a labeled bar for each non-reserved signal", () => {
    render(<ScoreBreakdown breakdown={breakdown} evidence={evidence} />);
    expect(screen.getByText("Identifiers")).toBeInTheDocument();
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Affiliation")).toBeInTheDocument();
  });

  it("renders the numeric value for a signal", () => {
    render(<ScoreBreakdown breakdown={breakdown} evidence={evidence} />);
    // 0.9 identifiers shown as a percentage or decimal
    expect(screen.getByText(/0\.90|90%/)).toBeInTheDocument();
  });

  it("lists evidence lines", () => {
    render(<ScoreBreakdown breakdown={breakdown} evidence={evidence} />);
    expect(screen.getByText(/feedback_prior:\+0\.030/)).toBeInTheDocument();
    expect(screen.getByText(/source_quality:openalex=0\.60/)).toBeInTheDocument();
  });

  it("renders gracefully with no data", () => {
    const { container } = render(<ScoreBreakdown breakdown={null} evidence={null} />);
    expect(container).toBeTruthy();
    expect(screen.getByText(/sin desglose|no breakdown/i)).toBeInTheDocument();
  });

  it("omits reserved signals that are zero", () => {
    render(<ScoreBreakdown breakdown={breakdown} evidence={evidence} />);
    // coauthorship/topic are 0.0 reserved — should not render their own bar
    expect(screen.queryByText(/coauthorship/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/topic/i)).not.toBeInTheDocument();
  });
});
