"use client";

/**
 * JournalProvenanceBadge — Inline provenance label for NIF/APC journal metrics.
 *
 * NIF displayed in the UI is an OPEN PROXY (OpenAlex 2-yr mean citedness,
 * field-normalized) — explicitly NOT Clarivate's proprietary Journal Impact
 * Factor (JIF). This badge must accompany every NIF display to avoid
 * misrepresentation.
 */

import Badge from "./ui/Badge";

const TOOLTIP =
  "Open proxy: OpenAlex 2-yr mean citedness, field-normalized — not Clarivate JIF.";

export function JournalProvenanceBadge(): JSX.Element {
  // Wrap the governed Badge primitive (token-based colors) so we don't add
  // direct palette classes; the wrapper carries the explanatory tooltip.
  return (
    <span title={TOOLTIP} aria-label={TOOLTIP} className="inline-flex">
      <Badge variant="warning" size="sm">
        open proxy
      </Badge>
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
