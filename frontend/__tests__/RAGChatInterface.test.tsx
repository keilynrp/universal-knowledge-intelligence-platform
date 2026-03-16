import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RAGChatInterface from "../app/components/RAGChatInterface";
import { LanguageProvider } from "../app/contexts/LanguageContext";

// ── Mock dependencies ──────────────────────────────────────────────────────

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

vi.mock("../app/contexts/DomainContext", () => ({
  useDomain: () => ({ activeDomainId: "default", activeDomain: null }),
}));

// Stub scrollIntoView — not available in jsdom
Element.prototype.scrollIntoView = vi.fn();

// Wrap with LanguageProvider since RAGChatInterface uses useLanguage()
vi.stubGlobal("localStorage", {
  getItem: () => "en",
  setItem: () => {},
  removeItem: () => {},
});

function Wrapped() {
  return <LanguageProvider><RAGChatInterface /></LanguageProvider>;
}

import { apiFetch } from "@/lib/api";
const mockApiFetch = apiFetch as ReturnType<typeof vi.fn>;

// ── Tests ──────────────────────────────────────────────────────────────────

beforeEach(() => {
  mockApiFetch.mockReset();
  // Default: stats fetch returns 0 indexed
  mockApiFetch.mockResolvedValue({
    ok: true,
    json: async () => ({ total_indexed: 0 }),
  });
});

describe("RAGChatInterface", () => {
  it("renders the conversation log with role=log", async () => {
    render(<Wrapped />);
    expect(screen.getByRole("log")).toBeInTheDocument();
  });

  it("renders the system greeting message on mount", async () => {
    render(<Wrapped />);
    await waitFor(() => {
      expect(screen.getByText(/Semantic Assistant/i)).toBeInTheDocument();
    });
  });

  it("renders the question input with correct label", () => {
    render(<Wrapped />);
    expect(screen.getByLabelText(/ask a question/i)).toBeInTheDocument();
  });

  it("send button is disabled when input is empty", () => {
    render(<Wrapped />);
    const btn = screen.getByRole("button", { name: /send/i });
    expect(btn).toBeDisabled();
  });

  it("send button becomes enabled when input has text", async () => {
    render(<Wrapped />);
    const input = screen.getByLabelText(/ask a question/i);
    await userEvent.type(input, "hello");
    const btn = screen.getByRole("button", { name: /send/i });
    expect(btn).not.toBeDisabled();
  });

  it("submitting a query shows user message and assistant response", async () => {
    // First call: stats; subsequent call: query
    mockApiFetch
      .mockResolvedValueOnce({ ok: true, json: async () => ({ total_indexed: 5 }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ answer: "The answer is 42.", sources: [], provider: "openai", model: "gpt-4" }),
      });

    render(<Wrapped />);
    const input = screen.getByLabelText(/ask a question/i);

    await act(async () => {
      await userEvent.type(input, "What is the meaning of life?");
      await userEvent.keyboard("{Enter}");
    });

    await waitFor(() => {
      expect(screen.getByText("What is the meaning of life?")).toBeInTheDocument();
      expect(screen.getByText("The answer is 42.")).toBeInTheDocument();
    });
  });

  it("shows error message when fetch throws", async () => {
    mockApiFetch
      .mockResolvedValueOnce({ ok: true, json: async () => ({ total_indexed: 0 }) })
      .mockRejectedValueOnce(new Error("Network error"));

    render(<Wrapped />);
    const input = screen.getByLabelText(/ask a question/i);

    await act(async () => {
      await userEvent.type(input, "test question");
      await userEvent.keyboard("{Enter}");
    });

    await waitFor(() => {
      expect(screen.getByText(/Failed to connect/i)).toBeInTheDocument();
    });
  });

  it("clears the input after sending", async () => {
    mockApiFetch
      .mockResolvedValueOnce({ ok: true, json: async () => ({ total_indexed: 0 }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ answer: "Reply", sources: [] }),
      });

    render(<Wrapped />);
    const input = screen.getByLabelText(/ask a question/i) as HTMLInputElement;

    await act(async () => {
      await userEvent.type(input, "clear me");
      await userEvent.keyboard("{Enter}");
    });

    await waitFor(() => {
      expect(input.value).toBe("");
    });
  });
});
