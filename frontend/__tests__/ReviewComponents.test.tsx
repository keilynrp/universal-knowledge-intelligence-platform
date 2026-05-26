import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import React from "react";

// Mock apiFetch before importing components
const mockApiFetch = vi.fn();
vi.mock("@/lib/api", () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}));

// Mock LanguageContext
vi.mock("../app/contexts/LanguageContext", () => ({
  useLanguage: () => ({
    t: (key: string) => key,
    lang: "en",
    setLang: vi.fn(),
  }),
}));

import MappingSuggestionReview from "../app/components/MappingSuggestionReview";
import AuthorityReadinessCard from "../app/components/AuthorityReadinessCard";

beforeEach(() => {
  mockApiFetch.mockReset();
});

describe("MappingSuggestionReview", () => {
  const suggestions = [
    {
      id: 1,
      source_field: "auth_name",
      canonical_target: "author.name",
      confidence: 0.92,
      status: "review_required",
      evidence_samples: ["John Doe", "Jane Smith"],
      rationale: "High string similarity",
      semantic_concept: "person_name",
      identifier_scheme: null,
      evidence: ["semantic_role"],
      requires_review: true,
    },
    {
      id: 2,
      source_field: "pub_year",
      canonical_target: "publication.year",
      confidence: 0.78,
      status: "auto_acceptable",
      evidence_samples: ["2024"],
      rationale: "",
      semantic_concept: null,
      identifier_scheme: null,
      evidence: [],
      requires_review: false,
    },
  ];

  it("shows loading state initially", () => {
    mockApiFetch.mockReturnValue(new Promise(() => {})); // never resolves
    render(<MappingSuggestionReview />);
    expect(screen.getByText("Loading suggestions...")).toBeInTheDocument();
  });

  it("shows empty message when no suggestions", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    await act(async () => {
      render(<MappingSuggestionReview />);
    });
    expect(screen.getByText("No mapping suggestions to review.")).toBeInTheDocument();
  });

  it("renders suggestions with source and target fields", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => suggestions,
    });
    await act(async () => {
      render(<MappingSuggestionReview />);
    });
    expect(screen.getByText("auth_name")).toBeInTheDocument();
    expect(screen.getByText("author.name")).toBeInTheDocument();
    expect(screen.getByText("pub_year")).toBeInTheDocument();
    expect(screen.getByText("publication.year")).toBeInTheDocument();
  });

  it("shows evidence samples", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => suggestions,
    });
    await act(async () => {
      render(<MappingSuggestionReview />);
    });
    expect(screen.getByText("John Doe")).toBeInTheDocument();
    expect(screen.getByText("Jane Smith")).toBeInTheDocument();
  });

  it("shows field correspondence governance metadata", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => suggestions,
    });
    await act(async () => {
      render(<MappingSuggestionReview />);
    });
    expect(screen.getByText("person_name")).toBeInTheDocument();
    expect(screen.getByText("semantic_role")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
  });

  it("shows accept and reject buttons for review_required", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => suggestions,
    });
    await act(async () => {
      render(<MappingSuggestionReview />);
    });
    const acceptButtons = screen.getAllByText("Accept");
    const rejectButtons = screen.getAllByText("Reject");
    // Both suggestions (review_required + auto_acceptable) should show buttons
    expect(acceptButtons.length).toBe(2);
    expect(rejectButtons.length).toBe(2);
  });

  it("calls accept endpoint on accept click", async () => {
    mockApiFetch
      .mockResolvedValueOnce({ ok: true, json: async () => suggestions })
      .mockResolvedValueOnce({ ok: true }) // accept call
      .mockResolvedValueOnce({ ok: true, json: async () => [] }); // refresh

    const onUpdate = vi.fn();
    await act(async () => {
      render(<MappingSuggestionReview onUpdate={onUpdate} />);
    });

    await act(async () => {
      fireEvent.click(screen.getAllByText("Accept")[0]);
    });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/mapping-suggestions/1/accept",
      { method: "POST" },
    );
  });

  it("shows reject rationale input on reject click", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => suggestions,
    });
    await act(async () => {
      render(<MappingSuggestionReview />);
    });

    await act(async () => {
      fireEvent.click(screen.getAllByText("Reject")[0]);
    });

    expect(screen.getByPlaceholderText("Rationale for rejection...")).toBeInTheDocument();
    expect(screen.getByText("Confirm")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  it("passes status filter to API", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    await act(async () => {
      render(<MappingSuggestionReview statusFilter="review_required" />);
    });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/mapping-suggestions?status=review_required",
    );
  });
});

describe("AuthorityReadinessCard", () => {
  const readinessData = {
    dataset_id: "ds-001",
    state: "partially_resolved",
    families: {
      person: {
        extracted: 80,
        resolved: 40,
        review_required: 10,
        rejected: 5,
        failed: 0,
        stale: 2,
      },
      institution: {
        extracted: 30,
        resolved: 25,
        review_required: 0,
        rejected: 0,
        failed: 0,
        stale: 0,
      },
    },
  };

  it("shows loading skeleton initially", () => {
    mockApiFetch.mockReturnValue(new Promise(() => {}));
    render(<AuthorityReadinessCard datasetId="ds-001" />);
    // Loading skeleton should have animate-pulse
    const container = document.querySelector(".animate-pulse");
    expect(container).toBeTruthy();
  });

  it("renders null when data fetch fails", async () => {
    mockApiFetch.mockResolvedValue({ ok: false });
    const { container } = await act(async () => {
      return render(<AuthorityReadinessCard datasetId="ds-001" />);
    });
    // After failed fetch, component returns null (empty)
    expect(container.querySelector(".rounded-lg")).toBeNull();
  });

  it("displays state label", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => readinessData,
    });
    await act(async () => {
      render(<AuthorityReadinessCard datasetId="ds-001" />);
    });
    expect(screen.getByText("Partially resolved")).toBeInTheDocument();
  });

  it("displays family names and resolution percentages", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => readinessData,
    });
    await act(async () => {
      render(<AuthorityReadinessCard datasetId="ds-001" />);
    });
    // person: 40/(80+40) = 33%
    expect(screen.getByText("33%")).toBeInTheDocument();
    // institution: 25/(30+25) = 45%
    expect(screen.getByText("45%")).toBeInTheDocument();
    expect(screen.getByText("person")).toBeInTheDocument();
    expect(screen.getByText("institution")).toBeInTheDocument();
  });

  it("shows stale count when > 0", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => readinessData,
    });
    await act(async () => {
      render(<AuthorityReadinessCard datasetId="ds-001" />);
    });
    expect(screen.getByText("2 stale")).toBeInTheDocument();
  });

  it("shows review_required count when > 0", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => readinessData,
    });
    await act(async () => {
      render(<AuthorityReadinessCard datasetId="ds-001" />);
    });
    expect(screen.getByText("10 rev")).toBeInTheDocument();
  });

  it("fetches from correct endpoint with dataset ID", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => readinessData,
    });
    await act(async () => {
      render(<AuthorityReadinessCard datasetId="ds-001" />);
    });
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/governance/authority-readiness/ds-001",
    );
  });

  it("shows Authority Readiness heading", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => readinessData,
    });
    await act(async () => {
      render(<AuthorityReadinessCard datasetId="ds-001" />);
    });
    expect(screen.getByText("Authority Readiness")).toBeInTheDocument();
  });
});
