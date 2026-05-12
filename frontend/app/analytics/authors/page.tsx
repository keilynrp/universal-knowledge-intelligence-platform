"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useDomain } from "../../contexts/DomainContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { apiFetch } from "@/lib/api";
import { SkeletonList, ErrorBanner, EmptyState as UiEmptyState } from "../../components/ui";

// ── Types ────────────────────────────────────────────────────────────────────

interface Author {
  canonical_label: string;
  record_id: number;
  h_index: number;
  total_publications: number;
  total_citations: number;
  avg_citations: number;
  publications_per_year: Record<string, number>;
}

interface AuthorsResult {
  domain_id: string;
  total_analyzed: number;
  authors: Author[];
}

interface AuthorDetail {
  record_id: number;
  canonical_label: string;
  domain_id: string;
  h_index: number;
  total_publications: number;
  total_citations: number;
  avg_citations: number;
  publications_per_year: Record<string, number>;
  top_entities: { entity_id: number; primary_label: string; citations: number }[];
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const SORT_OPTIONS = [
  { value: "h_index", labelKey: "page.authors.h_index" },
  { value: "total_publications", labelKey: "page.authors.publications" },
  { value: "total_citations", labelKey: "page.authors.citations" },
] as const;

function BarChart({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).sort(([a], [b]) => Number(a) - Number(b));
  if (entries.length === 0) return null;
  const max = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <div className="flex items-end gap-1" style={{ height: 80 }}>
      {entries.map(([year, count]) => (
        <div key={year} className="flex flex-col items-center gap-1" style={{ flex: 1, minWidth: 20 }}>
          <span className="text-[10px] tabular-nums text-gray-500">{count}</span>
          <div
            className="w-full rounded-t bg-blue-500"
            style={{ height: `${(count / max) * 60}px`, minHeight: 2 }}
          />
          <span className="text-[10px] text-gray-400">{year}</span>
        </div>
      ))}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function AuthorsPage() {
  const { activeDomainId } = useDomain();
  const { t } = useLanguage();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AuthorsResult | null>(null);
  const [sortBy, setSortBy] = useState<string>("h_index");

  // Detail view
  const [detail, setDetail] = useState<AuthorDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchAuthors = useCallback(async (domainId: string, sort: string) => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch(`/analyzers/authors/${domainId}?sort_by=${sort}&limit=50`);
      if (!r.ok) throw new Error(`Server responded with ${r.status}`);
      setData(await r.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("page.authors.error_load"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  const fetchDetail = useCallback(async (domainId: string, recordId: number) => {
    setDetailLoading(true);
    try {
      const r = await apiFetch(`/analyzers/authors/${domainId}/${recordId}`);
      if (!r.ok) throw new Error(`Server responded with ${r.status}`);
      setDetail(await r.json());
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    setDetail(null);
    fetchAuthors(activeDomainId, sortBy);
  }, [activeDomainId, sortBy, fetchAuthors]);

  // ── Detail view ────────────────────────────────────────────────────────────
  if (detail) {
    return (
      <div className="space-y-6 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              {detail.canonical_label}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {t("page.authors.detail_title")}
            </p>
          </div>
          <button
            onClick={() => setDetail(null)}
            className="text-sm text-blue-600 hover:underline dark:text-blue-400"
          >
            &larr; {t("page.authors.back_to_list")}
          </button>
        </div>

        {/* KPI cards */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            { label: t("page.authors.h_index"), value: detail.h_index },
            { label: t("page.authors.publications"), value: detail.total_publications },
            { label: t("page.authors.citations"), value: detail.total_citations },
            { label: t("page.authors.avg_citations"), value: detail.avg_citations },
          ].map((kpi) => (
            <div
              key={kpi.label}
              className="rounded-xl border border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-900"
            >
              <p className="text-xs text-gray-500 dark:text-gray-400">{kpi.label}</p>
              <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{kpi.value}</p>
            </div>
          ))}
        </div>

        {/* Publications per year */}
        {Object.keys(detail.publications_per_year).length > 0 && (
          <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
            <h3 className="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">
              {t("page.authors.pubs_per_year")}
            </h3>
            <BarChart data={detail.publications_per_year} />
          </div>
        )}

        {/* Top cited works */}
        {detail.top_entities.length > 0 && (
          <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
            <div className="border-b border-gray-200 px-4 py-3 dark:border-gray-800">
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {t("page.authors.top_cited")}
              </h3>
            </div>
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              {detail.top_entities.map((e) => (
                <div key={e.entity_id} className="flex items-center justify-between px-4 py-3">
                  <span className="truncate text-sm text-gray-800 dark:text-gray-200 pr-4">
                    {e.primary_label}
                  </span>
                  <span className="shrink-0 rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
                    {e.citations} cit.
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── List view ──────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            {t("page.authors.title")}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("page.authors.subtitle")}
          </p>
        </div>
        <Link
          href="/analytics"
          className="text-sm text-blue-600 hover:underline dark:text-blue-400"
        >
          &larr; {t("nav.analytics")}
        </Link>
      </div>

      {/* Sort control */}
      <div className="flex items-center gap-2">
        <label className="text-sm text-gray-600 dark:text-gray-400">
          {t("page.authors.sort_by")}:
        </label>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="rounded border border-gray-300 bg-white px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {t(opt.labelKey)}
            </option>
          ))}
        </select>
      </div>

      {loading && (
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900 overflow-hidden">
          <SkeletonList rows={10} />
        </div>
      )}

      {!loading && error && (
        <ErrorBanner
          message={t("page.authors.error_load")}
          detail={error}
          onRetry={() => fetchAuthors(activeDomainId, sortBy)}
        />
      )}

      {!loading && !error && data && (
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
          <div className="border-b border-gray-200 px-4 py-3 dark:border-gray-800">
            <span className="text-sm text-gray-600 dark:text-gray-400">
              <strong>{data.total_analyzed}</strong> authors analyzed
            </span>
          </div>

          {data.authors.length === 0 ? (
            <UiEmptyState
              icon="users"
              color="blue"
              title={t("page.authors.empty_title")}
              description={t("page.authors.empty_description")}
              size="compact"
            />
          ) : (
            <>
              {/* Table header */}
              <div className="grid grid-cols-[2rem_1fr_5rem_5rem_5rem_6rem] items-center gap-2 border-b border-gray-100 px-4 py-2 text-xs font-medium uppercase tracking-wide text-gray-400 dark:border-gray-800">
                <span>#</span>
                <span>{t("page.authors.author")}</span>
                <span className="text-right">{t("page.authors.h_index")}</span>
                <span className="text-right">{t("page.authors.publications")}</span>
                <span className="text-right">{t("page.authors.citations")}</span>
                <span className="text-right">{t("page.authors.avg_citations")}</span>
              </div>

              <div className="divide-y divide-gray-100 dark:divide-gray-800">
                {data.authors.map((a, i) => (
                  <button
                    key={a.record_id}
                    type="button"
                    onClick={() => fetchDetail(activeDomainId, a.record_id)}
                    className="grid w-full grid-cols-[2rem_1fr_5rem_5rem_5rem_6rem] items-center gap-2 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50"
                  >
                    <span className="text-xs font-mono text-gray-400">{i + 1}</span>
                    <span className="truncate text-sm font-medium text-blue-600 dark:text-blue-400">
                      {a.canonical_label}
                    </span>
                    <span className="text-right text-sm tabular-nums font-bold text-gray-800 dark:text-gray-200">
                      {a.h_index}
                    </span>
                    <span className="text-right text-sm tabular-nums text-gray-700 dark:text-gray-300">
                      {a.total_publications}
                    </span>
                    <span className="text-right text-sm tabular-nums text-gray-700 dark:text-gray-300">
                      {a.total_citations}
                    </span>
                    <span className="text-right text-sm tabular-nums text-gray-500 dark:text-gray-400">
                      {a.avg_citations}
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {detailLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20">
          <div className="rounded-xl bg-white p-6 shadow-xl dark:bg-gray-900">
            <SkeletonList rows={3} />
          </div>
        </div>
      )}
    </div>
  );
}
