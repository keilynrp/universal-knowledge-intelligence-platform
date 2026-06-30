"use client";

import { type ReactElement } from "react";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import {
  JournalProvenanceBadge,
  formatApc,
} from "../../components/JournalProvenanceBadge";

// ── Types ──────────────────────────────────────────────────────────────────

export interface JournalRow {
  issn_l: string;
  display_name: string | null;
  nif_field: string | null;
  normalized_impact_factor: number | null;
  two_yr_mean_citedness: number | null;
  h_index: number | null;
  apc_usd: number | null;
  apc_currency: string | null;
  is_in_doaj: boolean | null;
  works_count: number | null;
  nif_bayes: number | null;
  nif_ci_low: number | null;
  nif_ci_high: number | null;
}

export interface JournalsRankingTableProps {
  journals: JournalRow[];
  sortBy: string;
  order: "asc" | "desc";
  onSort: (column: string) => void;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function formatNum(value: number | null | undefined): string {
  if (value == null) return "—";
  return value.toLocaleString("en-US");
}

function hasNifBayesSignal(journal: JournalRow): boolean {
  return journal.normalized_impact_factor != null && journal.nif_bayes != null;
}

function SortIcon({ active, order }: { active: boolean; order: "asc" | "desc" }): ReactElement {
  if (!active) {
    return (
      <svg
        aria-hidden="true"
        className="ml-1 inline-block h-3 w-3 text-[var(--ukip-muted-soft)]"
        viewBox="0 0 16 16"
        fill="currentColor"
      >
        <path d="M8 2L4 7h8L8 2zm0 12l4-5H4l4 5z" />
      </svg>
    );
  }
  return order === "asc" ? (
    <svg
      aria-hidden="true"
      className="ml-1 inline-block h-3 w-3 text-[var(--ukip-violet)]"
      viewBox="0 0 16 16"
      fill="currentColor"
    >
      <path d="M8 2L4 9h8L8 2z" />
    </svg>
  ) : (
    <svg
      aria-hidden="true"
      className="ml-1 inline-block h-3 w-3 text-[var(--ukip-violet)]"
      viewBox="0 0 16 16"
      fill="currentColor"
    >
      <path d="M8 14l4-7H4l4 7z" />
    </svg>
  );
}

// ── Shared cell classes ──────────────────────────────────────────────────────
// Single-line everywhere (no wrapped/stacked text), with the long text columns
// truncating and the numeric columns right-aligned for fast vertical scanning.

const TH_BASE =
  "whitespace-nowrap px-3 py-3 text-xs font-semibold uppercase tracking-wider text-[var(--ukip-muted)]";
const TH_LEFT = `${TH_BASE} px-4 text-left`;
const TH_NUM = `${TH_BASE} text-right`;
const TD_BASE = "whitespace-nowrap px-3 py-3.5 text-sm text-[var(--ukip-text)]";
const TD_TEXT = `${TD_BASE} px-4`;
const TD_NUM = `${TD_BASE} text-right tabular-nums`;

function SortableHeader({
  label,
  column,
  sortBy,
  order,
  onSort,
  badge = false,
}: {
  label: string;
  column: string;
  sortBy: string;
  order: "asc" | "desc";
  onSort: (column: string) => void;
  badge?: boolean;
}): ReactElement {
  return (
    <th className={TH_NUM}>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onSort(column)}
        aria-label={`Sort by ${label}`}
        className="ml-auto flex-nowrap gap-1.5 whitespace-nowrap px-1 text-xs font-semibold uppercase tracking-wider"
      >
        {label}
        {badge && <JournalProvenanceBadge />}
        <SortIcon active={sortBy === column} order={order} />
      </Button>
    </th>
  );
}

// ── Component ──────────────────────────────────────────────────────────────

export function JournalsRankingTable({
  journals,
  sortBy,
  order,
  onSort,
}: JournalsRankingTableProps): ReactElement {
  if (journals.length === 0) {
    return (
      <EmptyState
        icon="chart"
        title="No journals"
        description="Adjust filters or search to find journals."
        color="slate"
        size="card"
      />
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-[var(--ukip-border)] bg-[var(--ukip-surface)]">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[880px] divide-y divide-[var(--ukip-border)]">
          <thead className="sticky top-0 z-10 bg-[var(--ukip-panel)]">
            <tr>
              {/* Journal — non-sortable; sized by its truncating content */}
              <th className={TH_LEFT}>Journal</th>

              {/* Discipline (OpenAlex field) — non-sortable, truncates */}
              <th className={TH_LEFT}>Discipline</th>

              <SortableHeader label="NIF" column="nif" sortBy={sortBy} order={order} onSort={onSort} badge />
              <SortableHeader label="NIF (Bayes)" column="nif_bayes" sortBy={sortBy} order={order} onSort={onSort} badge />
              <SortableHeader label="Citedness" column="citedness" sortBy={sortBy} order={order} onSort={onSort} />
              <SortableHeader label="h-index" column="h_index" sortBy={sortBy} order={order} onSort={onSort} />
              <SortableHeader label="APC" column="apc" sortBy={sortBy} order={order} onSort={onSort} />

              {/* Works — non-sortable */}
              <th className={TH_NUM}>Works</th>

              {/* OA — non-sortable */}
              <th className={`${TH_BASE} text-center`}>OA</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-[var(--ukip-border)]">
            {journals.map((journal) => (
              <tr
                key={journal.issn_l}
                className="transition-colors hover:bg-[var(--ukip-panel)]"
              >
                <td className={`${TD_TEXT} font-medium`}>
                  <span className="flex min-w-0 items-center gap-2">
                    <span
                      className="block max-w-[11rem] truncate xl:max-w-[15rem]"
                      title={journal.display_name ?? journal.issn_l}
                    >
                      {journal.display_name ?? journal.issn_l}
                    </span>
                    {hasNifBayesSignal(journal) && (
                      <span
                        className="shrink-0"
                        title="Has normalized NIF and Bayesian NIF estimate with interval when available."
                        aria-label="Has normalized NIF and Bayesian NIF estimate"
                      >
                        <Badge variant="info" size="sm" dot>
                          NIF + Bayes
                        </Badge>
                      </span>
                    )}
                  </span>
                </td>
                <td className={`${TD_TEXT} text-[var(--ukip-muted)]`}>
                  <span className="block max-w-[7rem] truncate xl:max-w-[9rem]" title={journal.nif_field ?? undefined}>
                    {journal.nif_field ?? "—"}
                  </span>
                </td>
                <td className={TD_NUM}>
                  {journal.normalized_impact_factor != null
                    ? journal.normalized_impact_factor.toFixed(3)
                    : "—"}
                </td>
                <td className={TD_NUM}>
                  {journal.nif_bayes != null ? (
                    <span className="inline-flex flex-col items-end leading-tight">
                      <span>{journal.nif_bayes.toFixed(3)}</span>
                      {journal.nif_ci_low != null && journal.nif_ci_high != null && (
                        <span className="text-xs text-[var(--ukip-muted)]">
                          {journal.nif_ci_low.toFixed(2)}{"–"}{journal.nif_ci_high.toFixed(2)}
                        </span>
                      )}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className={TD_NUM}>
                  {journal.two_yr_mean_citedness != null
                    ? journal.two_yr_mean_citedness.toFixed(2)
                    : "—"}
                </td>
                <td className={TD_NUM}>
                  {formatNum(journal.h_index)}
                </td>
                <td className={TD_NUM}>
                  {formatApc(journal.apc_usd, journal.apc_currency)}
                </td>
                <td className={TD_NUM}>
                  {formatNum(journal.works_count)}
                </td>
                <td className={`${TD_NUM} text-center`}>
                  {journal.is_in_doaj ? (
                    <Badge variant="success" size="sm">
                      Open Access
                    </Badge>
                  ) : (
                    <span className="text-[var(--ukip-muted-soft)]">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
