"use client";

/**
 * JournalProvenanceBadge — Inline provenance label for NIF/APC journal metrics.
 *
 * NIF displayed in the UI is an OPEN PROXY (OpenAlex 2-yr mean citedness,
 * field-normalized) — explicitly NOT Clarivate's proprietary Journal Impact
 * Factor (JIF). This badge must accompany every NIF display to avoid
 * misrepresentation.
 */

const TOOLTIP =
  "Open proxy: OpenAlex 2-yr mean citedness, field-normalized — not Clarivate JIF.";

export function JournalProvenanceBadge(): JSX.Element {
  return (
    <span
      className="inline-flex items-center font-medium rounded border bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-300 dark:border-amber-500/30 px-1.5 py-0.5 text-[10px] gap-1"
      title={TOOLTIP}
      aria-label={TOOLTIP}
    >
      open proxy
    </span>
  );
}

/**
 * formatApc — Format an APC amount + currency code for display.
 *
 * Returns "—" (em dash) when amount is null/undefined.
 * Returns the formatted number alone when currency is null/undefined.
 * Otherwise returns e.g. "1,500 USD".
 */
export function formatApc(
  amount: number | null | undefined,
  currency: string | null | undefined
): string {
  if (amount == null) return "—";
  const formatted = Number(amount).toLocaleString("en-US");
  return currency != null ? `${formatted} ${currency}` : formatted;
}
