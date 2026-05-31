import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

import ResearcherCard from "../app/analytics/researchers/components/ResearcherCard";
import type { Researcher } from "../app/analytics/researchers/researchersTypes";

const researcher: Researcher = {
  name: "Brian A. Nosek",
  orcid: "0000-0001-2345-6789",
  openalex_id: null,
  records_count: 12,
  citation_count: 340,
  topic_score: 82,
  drivers: {
    topic_match: 90, publication_signal: 70, citation_signal: 85,
    recency_signal: 60, authority_signal: 75, quality_signal: 65,
  },
  evidence: [{ entity_id: 1, title: "Open Science", secondary_label: null, citations: 120 }],
};

describe("ResearcherCard", () => {
  it("renders rank, name, score and core metrics", () => {
    render(<ResearcherCard researcher={researcher} rank={1} />);
    expect(screen.getByText("Brian A. Nosek")).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();   // records
    expect(screen.getByText("340")).toBeInTheDocument();  // citations
    expect(screen.getByText(/ORCID/i)).toBeInTheDocument();
  });
});
