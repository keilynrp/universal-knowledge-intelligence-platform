"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useDomain } from "../../contexts/DomainContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { apiFetch } from "@/lib/api";
import { SkeletonList, ErrorBanner, EmptyState as UiEmptyState } from "../../components/ui";

// ── Types ────────────────────────────────────────────────────────────────────

interface TrendItem {
  concept: string;
  slope: number;
  classification: "emerging" | "declining" | "stable";
  total_count: number;
  yearly_counts: Record<string, number>;
}

interface TrendsResult {
  domain_id: string;
  total_analyzed: number;
  total_concepts: number;
  skipped_count: number;
  trends: TrendItem[];
}

// ── Classification colors ────────────────────────────────────────────────────

const CLASSIFICATION_BADGE: Record<string, string> = {
  emerging: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  declining: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  stable: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
};

const SLOPE_BAR_COLOR: Record<string, string> = {
  emerging: "bg-emerald-500",
  declining: "bg-red-500",
  stable: "bg-blue-400",
};

// ── Sparkline component ──────────────────────────────────────────────────────

function Sparkline({ counts }: { counts: Record<string, number> }) {
  const years = Object.keys(counts).sort();
  if (years.length < 2) return null;

  const values = years.map((y) => counts[y]);
  const max = Math.max(...values, 1);
  const width = 120;
  const height = 28;
  const stepX = width / (values.length - 1);

  const points = values.map((v, i) => `${i * stepX},${height - (v / max) * (height - 4)}`).join(" ");

  return (
    <svg width={width} height={height} className="shrink-0">
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
        className="text-gray-400 dark:text-gray-500"
      />
    </svg>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function TrendsPage() {
  const { activeDomainId } = useDomain();
  const { t } = useLanguage();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<TrendsResult | null>(null);
  const [expandedConcept, setExpandedConcept] = useState<string | null>(null);

  const fetchTrends = useCallback(async (domainId: string) => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch(`/analyzers/trends/${domainId}?limit=30`);
      if (!r.ok) throw new Error(`Server responded with ${r.status}`);
      setData(await r.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("page.trends.error_load"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchTrends(activeDomainId);
  }, [activeDomainId, fetchTrends]);

  const maxAbsSlope = data?.trends.length
    ? Math.max(...data.trends.map((tr) => Math.abs(tr.slope)), 0.01)
    : 1;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            {t("page.trends.title")}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("page.trends.subtitle")}
          </p>
        </div>
        <Link
          href="/analytics"
          className="text-sm text-blue-600 hover:underline dark:text-blue-400"
        >
          &larr; {t("nav.analytics")}
        </Link>
      </div>

      {loading && (
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900 overflow-hidden">
          <SkeletonList rows={10} />
        </div>
      )}

      {!loading && error && (
        <ErrorBanner
          message={t("page.trends.error_load")}
          detail={error}
          onRetry={() => fetchTrends(activeDomainId)}
        />
      )}

      {!loading && !error && data && (
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
          {/* Summary bar */}
          <div className="flex flex-wrap items-center gap-4 border-b border-gray-200 px-4 py-3 dark:border-gray-800">
            <span className="text-sm text-gray-600 dark:text-gray-400">
              <strong>{data.total_concepts}</strong> concepts across{" "}
              <strong>{data.total_analyzed}</strong> entities with year data
            </span>
            <div className="ml-auto flex gap-2">
              {(["emerging", "declining", "stable"] as const).map((cls) => {
                const count = data.trends.filter((tr) => tr.classification === cls).length;
                return (
                  <span
                    key={cls}
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${CLASSIFICATION_BADGE[cls]}`}
                  >
                    {t(`page.trends.${cls}`)} {count}
                  </span>
                );
              })}
            </div>
          </div>

          {data.trends.length === 0 ? (
            <UiEmptyState
              icon="sparkles"
              color="emerald"
              title={t("page.trends.empty_title")}
              description={t("page.trends.empty_description")}
              size="compact"
            />
          ) : (
            <>
              {/* Table header */}
              <div className="grid grid-cols-[2rem_1fr_7rem_6rem_auto_5rem] items-center gap-2 border-b border-gray-100 px-4 py-2 text-xs font-medium uppercase tracking-wide text-gray-400 dark:border-gray-800">
                <span>#</span>
                <span>{t("page.trends.concept")}</span>
                <span className="text-right">{t("page.trends.slope")}</span>
                <span className="text-center">{t("page.trends.classification")}</span>
                <span className="text-center">Trend</span>
                <span className="text-right">{t("page.trends.total")}</span>
              </div>

              {/* Rows */}
              <div className="divide-y divide-gray-100 dark:divide-gray-800">
                {data.trends.map((tr, i) => {
                  const barPct = Math.round((Math.abs(tr.slope) / maxAbsSlope) * 100);
                  const isExpanded = expandedConcept === tr.concept;
                  return (
                    <div key={tr.concept}>
                      <button
                        type="button"
                        onClick={() => setExpandedConcept(isExpanded ? null : tr.concept)}
                        className="grid w-full grid-cols-[2rem_1fr_7rem_6rem_auto_5rem] items-center gap-2 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50"
                      >
                        <span className="text-xs font-mono text-gray-400">{i + 1}</span>
                        <span className="truncate text-sm font-medium text-gray-800 dark:text-gray-200">
                          {tr.concept}
                        </span>
                        <span className="text-right">
                          <span className="inline-flex items-center gap-1">
                            <span className="h-1.5 rounded-full" style={{ width: `${barPct}%`, minWidth: 4 }}>
                              <span className={`block h-full rounded-full ${SLOPE_BAR_COLOR[tr.classification]}`} style={{ width: `${barPct}%`, minWidth: 4 }} />
                            </span>
                            <span className="text-xs tabular-nums font-mono text-gray-600 dark:text-gray-300">
                              {tr.slope > 0 ? "+" : ""}{tr.slope.toFixed(2)}
                            </span>
                          </span>
                        </span>
                        <span className="flex justify-center">
                          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${CLASSIFICATION_BADGE[tr.classification]}`}>
                            {t(`page.trends.${tr.classification}`)}
                          </span>
                        </span>
                        <span className="flex justify-center">
                          <Sparkline counts={tr.yearly_counts} />
                        </span>
                        <span className="text-right text-sm tabular-nums text-gray-700 dark:text-gray-300">
                          {tr.total_count}
                        </span>
                      </button>

                      {/* Expanded: yearly breakdown */}
                      {isExpanded && (
                        <div className="bg-gray-50 px-8 py-3 dark:bg-gray-800/40">
                          <p className="mb-2 text-xs font-medium text-gray-500 dark:text-gray-400">
                            {t("page.trends.yearly_counts")}
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {Object.entries(tr.yearly_counts)
                              .sort(([a], [b]) => Number(a) - Number(b))
                              .map(([year, count]) => (
                                <span
                                  key={year}
                                  className="rounded bg-white px-2 py-1 text-xs text-gray-700 shadow-sm dark:bg-gray-700 dark:text-gray-300"
                                >
                                  {year}: <strong>{count}</strong>
                                </span>
                              ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
