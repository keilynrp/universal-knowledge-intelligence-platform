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
        <table className="min-w-full divide-y divide-[var(--ukip-border)]">
          <thead className="sticky top-0 z-10 bg-[var(--ukip-panel)]">
            <tr>
              {/* Journal — non-sortable */}
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--ukip-muted)]">
                Journal
              </th>

              {/* Discipline (OpenAlex field) — non-sortable */}
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--ukip-muted)]">
                Discipline
              </th>

              {/* NIF — sortable */}
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--ukip-muted)]">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onSort("nif")}
                  aria-label="Sort by NIF"
                  className="gap-1 px-1 uppercase tracking-wider text-xs font-semibold"
                >
                  NIF
                  <JournalProvenanceBadge />
                  <SortIcon active={sortBy === "nif"} order={order} />
                </Button>
              </th>

              {/* Citedness — sortable */}
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--ukip-muted)]">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onSort("citedness")}
                  aria-label="Sort by Citedness"
                  className="px-1 uppercase tracking-wider text-xs font-semibold"
                >
                  Citedness
                  <SortIcon active={sortBy === "citedness"} order={order} />
                </Button>
              </th>

              {/* h-index — sortable */}
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--ukip-muted)]">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onSort("h_index")}
                  aria-label="Sort by h-index"
                  className="px-1 uppercase tracking-wider text-xs font-semibold"
                >
                  h-index
                  <SortIcon active={sortBy === "h_index"} order={order} />
                </Button>
              </th>

              {/* APC — sortable */}
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--ukip-muted)]">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onSort("apc")}
                  aria-label="Sort by APC"
                  className="px-1 uppercase tracking-wider text-xs font-semibold"
                >
                  APC
                  <SortIcon active={sortBy === "apc"} order={order} />
                </Button>
              </th>

              {/* Works — non-sortable */}
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--ukip-muted)]">
                Works
              </th>

              {/* OA — non-sortable */}
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--ukip-muted)]">
                OA
              </th>
            </tr>
          </thead>

          <tbody className="divide-y divide-[var(--ukip-border)]">
            {journals.map((journal) => (
              <tr
                key={journal.issn_l}
                className="transition-colors hover:bg-[var(--ukip-panel)]"
              >
                <td className="px-4 py-3 text-sm font-medium text-[var(--ukip-text)]">
                  {journal.display_name ?? journal.issn_l}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--ukip-muted)]">
                  {journal.nif_field ?? "—"}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--ukip-text)]">
                  {journal.normalized_impact_factor != null
                    ? journal.normalized_impact_factor.toFixed(3)
                    : "—"}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--ukip-text)]">
                  {journal.two_yr_mean_citedness != null
                    ? journal.two_yr_mean_citedness.toFixed(2)
                    : "—"}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--ukip-text)]">
                  {formatNum(journal.h_index)}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--ukip-text)]">
                  {formatApc(journal.apc_usd, journal.apc_currency)}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--ukip-text)]">
                  {journal.works_count ?? "—"}
                </td>
                <td className="px-4 py-3 text-sm">
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
