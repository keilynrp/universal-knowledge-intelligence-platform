/**
 * Analytics wrapper — supports Google Analytics 4 (gtag) and a console fallback.
 * Set NEXT_PUBLIC_GA_ID in .env.local to enable GA4.
 */

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
    dataLayer?: unknown[];
  }
}

const GA_ID = process.env.NEXT_PUBLIC_GA_ID ?? "";

function gtag(...args: unknown[]) {
  if (typeof window !== "undefined" && typeof window.gtag === "function") {
    window.gtag(...args);
  }
}

/** Track a named event with optional parameters. */
export function trackEvent(
  eventName: string,
  params?: Record<string, string | number | boolean>
) {
  if (GA_ID) {
    gtag("event", eventName, params ?? {});
  } else if (process.env.NODE_ENV === "development") {
    console.debug("[analytics]", eventName, params);
  }
}

/** Track a page view — called automatically by the GA script on navigation,
 *  but exposed here for manual SPA route tracking if needed. */
export function trackPageView(path: string) {
  if (GA_ID) {
    gtag("config", GA_ID, { page_path: path });
  } else if (process.env.NODE_ENV === "development") {
    console.debug("[analytics] pageview", path);
  }
}

// ── Typed event helpers ────────────────────────────────────────────────────────

export const Analytics = {
  /** User exported a report */
  exportReport: (format: string, domain: string) =>
    trackEvent("export_report", { format, domain }),

  /** User ran an OLAP query */
  olapQuery: (domain: string, dimensions: number) =>
    trackEvent("olap_query", { domain, dimensions }),

  /** User seeded demo data */
  demoSeeded: () => trackEvent("demo_seed"),

  /** User completed the guided tour */
  tourCompleted: (steps: number) =>
    trackEvent("guided_tour_completed", { steps }),

  /** User skipped the guided tour */
  tourSkipped: (atStep: number) =>
    trackEvent("guided_tour_skipped", { at_step: atStep }),

  /** User performed a RAG query */
  ragQuery: (domain: string) => trackEvent("rag_query", { domain }),

  /** User uploaded a file */
  fileUploaded: (rows: number) => trackEvent("file_uploaded", { rows }),

  /** Dashboard PDF exported */
  dashboardExportPDF: (domain: string) =>
    trackEvent("dashboard_export_pdf", { domain }),
};
