"use client";

import { useCallback, useEffect, useState, type ReactElement } from "react";
import { apiFetch } from "@/lib/api";
import { Badge, Button, EmptyState, ErrorBanner, Input, PageHeader, Select, SkeletonCard } from "../../components/ui";
import { useLanguage } from "../../contexts/LanguageContext";

// ── Types (mirror backend/openalex_lake/explore.py) ─────────────────────────

interface AxisEntry {
  axis: string;
  views: string[];
}

interface QueryResult {
  lake?: "not_initialized" | "locked";
  hint?: string;
  view?: string;
  columns?: string[];
  rows?: (string | number | boolean | null)[][];
  total?: number;
  limit?: number;
  offset?: number;
}

const PAGE_SIZE = 50;

// Default sort per view so the first render is immediately meaningful.
const DEFAULT_ORDER_BY: Record<string, string> = {
  v_journal_yearly: "citations",
  v_journal_citation_trend: "citations",
  v_coauthor_pairs: "collaborations",
  v_institution_collab: "collaborations",
  v_topic_yearly: "works",
  v_field_yearly: "works",
  v_source_coverage: "works",
  v_work_keys: "publication_year",
};

function formatCell(value: string | number | boolean | null): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toLocaleString("en-US") : value.toFixed(3);
  }
  return String(value);
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function LakeExplorerPage(): ReactElement {
  const { t } = useLanguage();
  const tr = useCallback((key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  }, [t]);

  const [axes, setAxes] = useState<AxisEntry[]>([]);
  const [view, setView] = useState<string>("v_journal_yearly");
  const [issnL, setIssnL] = useState("");
  const [yearMin, setYearMin] = useState("");
  const [yearMax, setYearMax] = useState("");
  const [orderBy, setOrderBy] = useState<string>(DEFAULT_ORDER_BY.v_journal_yearly);
  const [descending, setDescending] = useState(true);
  const [offset, setOffset] = useState(0);

  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  useEffect(() => {
    apiFetch("/admin/openalex-lake/views")
      .then(async (res) => {
        if (res.status === 403) { setForbidden(true); return; }
        if (res.ok) setAxes((await res.json()).axes ?? []);
      })
      .catch(() => {});
  }, []);

  const runQuery = useCallback(async (opts?: { resetOffset?: boolean }) => {
    const effectiveOffset = opts?.resetOffset ? 0 : offset;
    if (opts?.resetOffset) setOffset(0);
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(effectiveOffset),
        order: descending ? "desc" : "asc",
      });
      if (orderBy) params.set("order_by", orderBy);
      if (issnL.trim()) params.set("issn_l", issnL.trim());
      if (yearMin) params.set("year_min", yearMin);
      if (yearMax) params.set("year_max", yearMax);
      const res = await apiFetch(`/admin/openalex-lake/query/${view}?${params}`);
      if (res.status === 403) { setForbidden(true); return; }
      if (res.status === 422) {
        // order_by no longer valid for this view — retry without it.
        setOrderBy("");
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : tr("lake_explorer.load_failed", "Unable to query the lake."));
    } finally {
      setLoading(false);
    }
  }, [view, orderBy, descending, issnL, yearMin, yearMax, offset, tr]);

  // Re-query on view/sort/pagination change (filters apply on submit).
  useEffect(() => {
    void runQuery();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, orderBy, descending, offset]);

  const selectView = (next: string) => {
    setView(next);
    setOrderBy(DEFAULT_ORDER_BY[next] ?? "");
    setOffset(0);
  };

  const axisLabel = (axis: string) =>
    tr(`lake_explorer.axis.${axis}`, axis.replaceAll("_", " "));

  const total = result?.total ?? 0;
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  return (
    <div className="space-y-6">
      <PageHeader
        title={tr("lake_explorer.title", "OpenAlex Lake — Explorer")}
        description={tr(
          "lake_explorer.subtitle",
          "Browse the historical analysis views built over the ingested OpenAlex subset: journal scientometrics, collaboration networks, topic trends, and cross-source coverage.",
        )}
      />

      {forbidden && (
        <EmptyState
          icon="key"
          color="amber"
          title={tr("lake_explorer.forbidden_title", "Admin access required")}
          description={tr("lake_explorer.forbidden_body", "This page is restricted to admin/super_admin roles.")}
        />
      )}

      {!forbidden && (
        <>
          {/* View picker grouped by axis */}
          <section className="rounded-2xl border border-[var(--ukip-border)] bg-[var(--ukip-surface)] p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--ukip-muted)]">
              {tr("lake_explorer.pick_view", "Analysis view")}
            </p>
            <div className="mt-3 flex flex-wrap gap-4">
              {axes.map((entry) => (
                <div key={entry.axis} className="min-w-[12rem]">
                  <p className="text-[11px] font-semibold text-[var(--ukip-muted)]">{axisLabel(entry.axis)}</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {entry.views.map((v) => (
                      <Button
                        key={v}
                        onClick={() => selectView(v)}
                        variant={v === view ? "outline" : "ghost"}
                        size="sm"
                        aria-pressed={v === view}
                        className="font-mono"
                      >
                        {v}
                      </Button>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Filters */}
            <div className="mt-4 flex flex-wrap items-end gap-3 border-t border-[var(--ukip-border)] pt-4">
              <Input
                label="ISSN-L"
                value={issnL}
                onChange={(e) => setIssnL(e.target.value)}
                placeholder="0028-0836"
                className="w-36 font-mono"
              />
              <Input
                label={tr("lake_explorer.year_from", "Year from")}
                value={yearMin}
                onChange={(e) => setYearMin(e.target.value.replace(/\D/g, ""))}
                placeholder="2010"
                inputMode="numeric"
                className="w-24 font-mono"
              />
              <Input
                label={tr("lake_explorer.year_to", "Year to")}
                value={yearMax}
                onChange={(e) => setYearMax(e.target.value.replace(/\D/g, ""))}
                placeholder="2025"
                inputMode="numeric"
                className="w-24 font-mono"
              />
              {result?.columns && (
                <Select
                  label={tr("lake_explorer.order_by", "Order by")}
                  value={orderBy}
                  onChange={(e) => { setOrderBy(e.target.value); setOffset(0); }}
                  className="font-mono"
                >
                  <option value="">—</option>
                  {result.columns.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </Select>
              )}
              <Button
                onClick={() => { setDescending(!descending); setOffset(0); }}
                variant="outline"
                title={tr("lake_explorer.toggle_order", "Toggle sort direction")}
              >
                {descending ? "↓ desc" : "↑ asc"}
              </Button>
              <Button onClick={() => void runQuery({ resetOffset: true })} variant="primary">
                {tr("lake_explorer.apply", "Apply filters")}
              </Button>
            </div>
          </section>

          {error && <ErrorBanner message={error} onRetry={() => void runQuery()} variant="card" />}

          {!error && loading && <SkeletonCard />}

          {!error && !loading && result?.lake === "not_initialized" && (
            <EmptyState
              icon="document"
              color="slate"
              title={tr("lake_explorer.not_initialized_title", "The lake has no data yet")}
              description={tr("lake_explorer.not_initialized_body", "Run the first pull from the backend container, then come back.")}
            />
          )}

          {!error && !loading && result?.lake === "locked" && (
            <EmptyState
              icon="bolt"
              color="violet"
              title={tr("lake_explorer.locked_title", "A pull is running right now")}
              description={tr("lake_explorer.locked_body", "The lake file is locked while it writes. Try again in a moment.")}
            />
          )}

          {!error && !loading && result && !result.lake && (
            <section className="overflow-hidden rounded-2xl border border-[var(--ukip-border)] bg-[var(--ukip-surface)]">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--ukip-border)] px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-semibold text-[var(--ukip-text)]">{result.view}</span>
                  <Badge variant="info" size="sm">
                    {total.toLocaleString("en-US")} {tr("lake_explorer.rows", "rows")}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 text-sm text-[var(--ukip-muted)]">
                  <Button
                    onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                    disabled={!canPrev}
                    variant="outline"
                    size="sm"
                  >
                    ← {tr("lake_explorer.prev", "Prev")}
                  </Button>
                  <span className="font-mono text-xs">
                    {offset + 1}–{Math.min(offset + PAGE_SIZE, total)}
                  </span>
                  <Button
                    onClick={() => setOffset(offset + PAGE_SIZE)}
                    disabled={!canNext}
                    variant="outline"
                    size="sm"
                  >
                    {tr("lake_explorer.next", "Next")} →
                  </Button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full divide-y divide-[var(--ukip-border)]">
                  <thead className="bg-[var(--ukip-panel)]">
                    <tr>
                      {result.columns?.map((c) => (
                        <th key={c} className="whitespace-nowrap px-4 py-2.5 text-left font-mono text-[11px] font-semibold uppercase tracking-wider text-[var(--ukip-muted)]">
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--ukip-border)]">
                    {result.rows?.length === 0 ? (
                      <tr>
                        <td colSpan={result.columns?.length ?? 1} className="px-4 py-8 text-center text-sm text-[var(--ukip-muted)]">
                          {tr("lake_explorer.empty", "No rows match these filters.")}
                        </td>
                      </tr>
                    ) : (
                      result.rows?.map((row, i) => (
                        <tr key={i} className="transition-colors hover:bg-[var(--ukip-panel)]">
                          {row.map((cell, j) => (
                            <td key={j} className="whitespace-nowrap px-4 py-2 font-mono text-sm tabular-nums text-[var(--ukip-text)]">
                              {formatCell(cell)}
                            </td>
                          ))}
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
