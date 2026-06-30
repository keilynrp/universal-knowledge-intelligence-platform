"use client";

import type { ReactElement } from "react";
import Badge from "./ui/Badge";

export interface JournalSignalBadgeProps {
  ready: boolean;
  nif?: number | null;
  nifBayes?: number | null;
  ciLow?: number | null;
  ciHigh?: number | null;
  journalName?: string | null;
  size?: "sm" | "md";
}

/**
 * JournalSignalBadge — per-record marker shown when the linked journal carries
 * both a field-normalized NIF and its Bayesian companion (nif_bayes). Mirrors
 * the "NIF + Bayes" badge in the journals ranking table so the same signal is
 * recognizable across the catalog cards, list rows and record detail.
 *
 * Renders nothing when the signal is absent, so callers can drop it inline.
 */
export function JournalSignalBadge({
  ready,
  nif,
  nifBayes,
  ciLow,
  ciHigh,
  journalName,
  size = "sm",
}: JournalSignalBadgeProps): ReactElement | null {
  if (!ready) return null;

  const parts: string[] = [];
  if (journalName) parts.push(journalName);
  if (nif != null) parts.push(`NIF ${nif.toFixed(3)}`);
  if (nifBayes != null) {
    const ci =
      ciLow != null && ciHigh != null
        ? ` (${ciLow.toFixed(2)}–${ciHigh.toFixed(2)})`
        : "";
    parts.push(`NIF Bayes ${nifBayes.toFixed(3)}${ci}`);
  }
  const tooltip = parts.join(" · ") || "Has normalized NIF and Bayesian NIF estimate";

  return (
    <span title={tooltip} aria-label={tooltip} className="inline-flex">
      <Badge variant="info" size={size} dot>
        NIF + Bayes
      </Badge>
    </span>
  );
}

export default JournalSignalBadge;
