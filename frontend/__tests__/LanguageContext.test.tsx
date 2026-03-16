import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { LanguageProvider, useLanguage } from "../app/contexts/LanguageContext";

// Helper component that exposes t() and setLanguage via DOM
function LangConsumer({ k }: { k: string }) {
  const { t, language, setLanguage } = useLanguage();
  return (
    <div>
      <span data-testid="val">{t(k)}</span>
      <span data-testid="lang">{language}</span>
      <button onClick={() => setLanguage("en")}>EN</button>
      <button onClick={() => setLanguage("es")}>ES</button>
    </div>
  );
}

function renderWithProvider(key: string, storageValue?: string) {
  const storage: Record<string, string> = storageValue
    ? { app_lang: storageValue }
    : {};

  vi.stubGlobal("localStorage", {
    getItem: (k: string) => storage[k] ?? null,
    setItem: (k: string, v: string) => { storage[k] = v; },
    removeItem: (k: string) => { delete storage[k]; },
  });

  return { result: render(<LanguageProvider><LangConsumer k={key} /></LanguageProvider>), storage };
}

describe("LanguageContext", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("returns Spanish translation when language is 'es'", async () => {
    renderWithProvider("common.save", "es");
    await waitFor(() => expect(screen.getByTestId("val")).toHaveTextContent("Guardar"));
  });

  it("returns English translation when language is 'en'", async () => {
    renderWithProvider("common.save", "en");
    await waitFor(() => expect(screen.getByTestId("val")).toHaveTextContent("Save"));
  });

  it("returns the key itself when the key does not exist", async () => {
    renderWithProvider("does.not.exist", "en");
    await waitFor(() => expect(screen.getByTestId("val")).toHaveTextContent("does.not.exist"));
  });

  it("defaults to 'es' when localStorage has no stored language", async () => {
    renderWithProvider("common.save");
    await waitFor(() => expect(screen.getByTestId("lang")).toHaveTextContent("es"));
  });

  it("switches language to 'en' when setLanguage('en') is called", async () => {
    renderWithProvider("common.save", "es");
    await waitFor(() => screen.getByTestId("val")); // wait for mount
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "EN" }));
    });
    expect(screen.getByTestId("val")).toHaveTextContent("Save");
  });

  it("switches language to 'es' from 'en'", async () => {
    renderWithProvider("common.cancel", "en");
    await waitFor(() => screen.getByTestId("val"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "ES" }));
    });
    expect(screen.getByTestId("val")).toHaveTextContent("Cancelar");
  });

  it("persists language choice to localStorage on setLanguage", async () => {
    const { storage } = renderWithProvider("common.save", "en");
    await waitFor(() => screen.getByTestId("val"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "ES" }));
    });
    expect(storage["app_lang"]).toBe("es");
  });

  it("loads language from localStorage on mount", async () => {
    renderWithProvider("common.delete", "en");
    await waitFor(() => expect(screen.getByTestId("lang")).toHaveTextContent("en"));
  });

  it("throws when useLanguage is used outside LanguageProvider", () => {
    // Suppress the expected error
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    function BareConsumer() {
      useLanguage();
      return null;
    }
    expect(() => render(<BareConsumer />)).toThrow(
      "useLanguage must be used within a LanguageProvider"
    );
    consoleSpy.mockRestore();
  });
});
