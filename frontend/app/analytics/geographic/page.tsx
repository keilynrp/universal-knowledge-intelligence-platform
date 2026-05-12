"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useDomain } from "../../contexts/DomainContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { apiFetch } from "@/lib/api";
import { SkeletonList, ErrorBanner, EmptyState as UiEmptyState } from "../../components/ui";

// ── Types ────────────────────────────────────────────────────────────────────

interface Country {
  country_code: string;
  country_name: string;
  entity_count: number;
  citation_sum: number;
  percentage: number;
}

interface CollabPair {
  country_a: string;
  country_b: string;
  country_a_name: string;
  country_b_name: string;
  count: number;
}

interface GeoResult {
  domain_id: string;
  coverage: number;
  total_entities: number;
  countries: Country[];
  collaboration_rate?: number;
  top_country_pairs?: CollabPair[];
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const SORT_OPTIONS = [
  { value: "entity_count", labelKey: "page.geographic.entities" },
  { value: "citation_sum", labelKey: "page.geographic.citations" },
] as const;

function PctBar({ value, max, color = "bg-blue-500" }: { value: number; max: number; color?: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="h-2 w-full rounded-full bg-gray-100 dark:bg-gray-800">
      <div
        className={`h-2 rounded-full transition-all ${color}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function GeographicPage() {
  const { activeDomainId } = useDomain();
  const { t } = useLanguage();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<GeoResult | null>(null);
  const [sortBy, setSortBy] = useState<string>("entity_count");
  const [showCollab, setShowCollab] = useState(false);

  const fetchGeo = useCallback(async (domainId: string, sort: string, collab: boolean) => {
    setLoading(true);
    setError(null);
    try {
      let url = `/analyzers/geographic/${domainId}?sort_by=${sort}&limit=30`;
      if (collab) url += "&include_collaboration=true";
      const r = await apiFetch(url);
      if (!r.ok) throw new Error(`Server responded with ${r.status}`);
      setData(await r.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("page.geographic.error_load"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchGeo(activeDomainId, sortBy, showCollab);
  }, [activeDomainId, sortBy, showCollab, fetchGeo]);

  const maxEntityCount = data?.countries.length ? Math.max(...data.countries.map((c) => c.entity_count), 1) : 1;
  const maxCitationSum = data?.countries.length ? Math.max(...data.countries.map((c) => c.citation_sum), 1) : 1;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            {t("page.geographic.title")}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("page.geographic.subtitle")}
          </p>
        </div>
        <Link
          href="/analytics"
          className="text-sm text-blue-600 hover:underline dark:text-blue-400"
        >
          &larr; {t("nav.analytics")}
        </Link>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600 dark:text-gray-400">
            {t("page.geographic.sort_by")}:
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
        <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
          <input
            type="checkbox"
            checked={showCollab}
            onChange={(e) => setShowCollab(e.target.checked)}
            className="rounded"
          />
          {t("page.geographic.collab_title")}
        </label>
      </div>

      {loading && (
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900 overflow-hidden">
          <SkeletonList rows={10} />
        </div>
      )}

      {!loading && error && (
        <ErrorBanner
          message={t("page.geographic.error_load")}
          detail={error}
          onRetry={() => fetchGeo(activeDomainId, sortBy, showCollab)}
        />
      )}

      {!loading && !error && data && (
        <>
          {/* KPI row */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-xl border border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-900">
              <p className="text-xs text-gray-500 dark:text-gray-400">{t("page.geographic.entities")}</p>
              <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{data.total_entities}</p>
            </div>
            <div className="rounded-xl border border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-900">
              <p className="text-xs text-gray-500 dark:text-gray-400">Countries</p>
              <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
                {data.countries.filter((c) => c.country_code !== "OTHER").length}
              </p>
            </div>
            <div className="rounded-xl border border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-900">
              <p className="text-xs text-gray-500 dark:text-gray-400">Coverage</p>
              <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
                {(data.coverage * 100).toFixed(1)}%
              </p>
            </div>
            {data.collaboration_rate !== undefined && (
              <div className="rounded-xl border border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-900">
                <p className="text-xs text-gray-500 dark:text-gray-400">{t("page.geographic.collab_rate")}</p>
                <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
                  {data.collaboration_rate}%
                </p>
              </div>
            )}
          </div>

          {data.countries.length === 0 ? (
            <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
              <UiEmptyState
                icon="globe"
                color="blue"
                title={t("page.geographic.empty_title")}
                description={t("page.geographic.empty_description")}
                size="compact"
              />
            </div>
          ) : (
            <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
              {/* Table header */}
              <div className="grid grid-cols-[2rem_1fr_8rem_5rem_5rem_4rem] items-center gap-2 border-b border-gray-100 px-4 py-2 text-xs font-medium uppercase tracking-wide text-gray-400 dark:border-gray-800">
                <span>#</span>
                <span>{t("page.geographic.country")}</span>
                <span>Bar</span>
                <span className="text-right">{t("page.geographic.entities")}</span>
                <span className="text-right">{t("page.geographic.citations")}</span>
                <span className="text-right">{t("page.geographic.percentage")}</span>
              </div>

              <div className="divide-y divide-gray-100 dark:divide-gray-800">
                {data.countries.map((c, i) => (
                  <div
                    key={c.country_code}
                    className="grid grid-cols-[2rem_1fr_8rem_5rem_5rem_4rem] items-center gap-2 px-4 py-3"
                  >
                    <span className="text-xs font-mono text-gray-400">{i + 1}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-800 dark:text-gray-200">
                        {c.country_name}
                      </span>
                      <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-mono text-gray-500 dark:bg-gray-800 dark:text-gray-400">
                        {c.country_code}
                      </span>
                    </div>
                    <div>
                      <PctBar
                        value={sortBy === "citation_sum" ? c.citation_sum : c.entity_count}
                        max={sortBy === "citation_sum" ? maxCitationSum : maxEntityCount}
                        color={c.country_code === "OTHER" ? "bg-gray-400" : "bg-blue-500"}
                      />
                    </div>
                    <span className="text-right text-sm tabular-nums text-gray-700 dark:text-gray-300">
                      {c.entity_count.toLocaleString()}
                    </span>
                    <span className="text-right text-sm tabular-nums text-gray-700 dark:text-gray-300">
                      {c.citation_sum.toLocaleString()}
                    </span>
                    <span className="text-right text-xs text-gray-400">
                      {c.percentage.toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Collaboration pairs */}
          {showCollab && data.top_country_pairs && data.top_country_pairs.length > 0 && (
            <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
              <div className="border-b border-gray-200 px-4 py-3 dark:border-gray-800">
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {t("page.geographic.top_pairs")}
                </h3>
              </div>
              <div className="divide-y divide-gray-100 dark:divide-gray-800">
                {data.top_country_pairs.map((pair, i) => (
                  <div key={`${pair.country_a}-${pair.country_b}`} className="flex items-center gap-3 px-4 py-3">
                    <span className="w-6 text-right text-xs font-mono text-gray-400">{i + 1}</span>
                    <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                      {pair.country_a_name}
                    </span>
                    <span className="text-gray-300 dark:text-gray-600">&harr;</span>
                    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                      {pair.country_b_name}
                    </span>
                    <span className="ml-auto rounded bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                      {pair.count} shared
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
