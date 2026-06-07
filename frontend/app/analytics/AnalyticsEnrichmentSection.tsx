"use client";

import ConceptCloud from "../components/ConceptCloud";
import { EntityConcept } from "../components/ui";

import { CitationBar, CoverageRing, ProgressBar, SectionDivider, StatusBadge } from "./AnalyticsPrimitives";
import type { EnrichStats } from "./analyticsTypes";

export function AnalyticsEnrichmentSection({
  enrichStats,
  enrichLoading,
  totalCount,
  bulkQueuing,
  bulkResult,
  onBulkEnrich,
  t,
}: {
  enrichStats: EnrichStats | null;
  enrichLoading: boolean;
  totalCount: number;
  bulkQueuing: boolean;
  bulkResult: { queued_records: number } | null;
  onBulkEnrich: () => void;
  t: (key: string) => string;
}) {
  const ciDistrib = enrichStats?.citations.distribution ?? {};
  const ciMax = Math.max(...Object.values(ciDistrib), 1);

  return (
    <>
      <SectionDivider label="UKIP Knowledge Hub — Semantic Enrichment" />

      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-600 via-blue-700 to-cyan-600 p-6 text-white shadow-lg">
        <div className="pointer-events-none absolute -right-8 -top-8 h-40 w-40 rounded-full bg-white/10" />
        <div className="pointer-events-none absolute -bottom-12 right-16 h-56 w-56 rounded-full bg-white/5" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="mb-1 flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-white/20 px-2 py-0.5 text-xs font-semibold uppercase tracking-wider">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-300" />
                Knowledge Core Active
              </span>
            </div>
            <h2 className="text-xl font-bold">Semantic Enrichment Engine</h2>
            <p className="mt-1 max-w-lg text-sm text-white/80">
              Transforming raw source records into rich domain entities using cross-referenced
              bibliometric data, NLP concepts, and global impact projections.
            </p>
          </div>
          <div className="flex flex-col items-start gap-2 sm:items-end">
            <button
              id="bulk-enrich-btn"
              type="button"
              onClick={onBulkEnrich}
              disabled={bulkQueuing}
              className="inline-flex items-center gap-2 rounded-xl bg-white px-5 py-2.5 text-sm font-semibold text-indigo-700 shadow transition-all hover:bg-indigo-50 disabled:opacity-60"
            >
              {bulkQueuing ? (
                <>
                  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  {t("page.analytics.enrichment_loading")}
                </>
              ) : (
                <>
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  {t("page.analytics.enrichment_button")}
                </>
              )}
            </button>
            {bulkResult && (
              <span className="rounded-full bg-white/20 px-3 py-1 text-xs font-medium">
                ✓ {bulkResult.queued_records.toLocaleString()} entities queued
              </span>
            )}
          </div>
        </div>
      </div>

      {enrichStats && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              {
                id: "enriched-entities",
                label: <EntityConcept>{t("page.analytics.stat_enriched_entities")}</EntityConcept>,
                value: enrichStats.enriched_count,
                color: "text-emerald-600 dark:text-emerald-400",
                bg: "bg-emerald-50 dark:bg-emerald-500/10",
              },
              {
                id: "connectivity",
                label: "Avg. Connectivity",
                value: enrichStats.citations.average,
                color: "text-violet-600 dark:text-violet-400",
                bg: "bg-violet-50 dark:bg-violet-500/10",
              },
              {
                id: "influence",
                label: "Max Influence",
                value: enrichStats.citations.max.toLocaleString(),
                color: "text-fuchsia-600 dark:text-fuchsia-400",
                bg: "bg-fuchsia-50 dark:bg-fuchsia-500/10",
              },
              {
                id: "knowledge-points",
                label: "Total Knowledge Points",
                value: enrichStats.citations.total.toLocaleString(),
                color: "text-blue-600 dark:text-blue-400",
                bg: "bg-blue-50 dark:bg-blue-500/10",
              },
            ].map((card) => (
              <div key={card.id} className={`rounded-2xl border border-gray-200 ${card.bg} p-5 dark:border-gray-800`}>
                <p className={`text-2xl font-bold ${card.color}`}>{card.value}</p>
                <p className="mt-1 text-xs font-medium text-gray-500 dark:text-gray-400">{card.label}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900 xl:col-span-1">
              <h3 className="mb-1 text-base font-semibold text-gray-900 dark:text-white">
                {t("page.analytics.coverage_title")}
              </h3>
              <p className="mb-5 text-xs text-gray-500 dark:text-gray-400">
                Percentage of repository mapped to global intelligence sources
              </p>
              <div className="flex items-center gap-6">
                <CoverageRing pct={enrichStats.enrichment_coverage_pct} />
                <div className="flex flex-col gap-2">
                  <StatusBadge status="completed" count={enrichStats.enriched_count} />
                  <StatusBadge status="pending" count={enrichStats.pending_count} />
                  <StatusBadge status="failed" count={enrichStats.failed_count} />
                  <StatusBadge status="none" count={enrichStats.none_count} />
                </div>
              </div>
              <div className="mt-5">
                <ProgressBar
                  value={enrichStats.enriched_count}
                  max={totalCount}
                  color="bg-gradient-to-r from-blue-500 to-indigo-500"
                />
              </div>
            </div>

            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900 xl:col-span-2">
              <h3 className="mb-1 text-base font-semibold text-gray-900 dark:text-white">Scientific Connectivity</h3>
              <p className="mb-6 text-xs text-gray-500 dark:text-gray-400">
                Distribution of intellectual connectivity / citations across the platform
              </p>
              {Object.values(ciDistrib).every((value) => value === 0) ? (
                <div className="flex h-24 items-center justify-center text-sm text-gray-400 dark:text-gray-500">
                  No connectivity data available. Trigger enrichment to map entities.
                </div>
              ) : (
                <div className="space-y-3">
                  {Object.entries(ciDistrib).map(([label, value]) => (
                    <CitationBar key={label} label={label} value={value} max={ciMax} />
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                  {t("page.analytics.concept_map_title")}
                </h3>
                <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                  Top domain concepts extracted via global APIs - size indicates conceptual density
                </p>
              </div>
              <span className="shrink-0 rounded-full bg-indigo-100 px-2.5 py-1 text-xs font-semibold text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400">
                {enrichStats.top_concepts.length} semantic tags
              </span>
            </div>
            <ConceptCloud concepts={enrichStats.top_concepts} />
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <h3 className="mb-1 text-base font-semibold text-gray-900 dark:text-white">
              UKIP Integration Roadmap
            </h3>
            <p className="mb-5 text-xs text-gray-500 dark:text-gray-400">
              Multi-source intelligence gathering strategy
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {[
                {
                  phase: "Source 1",
                  label: "Open Intelligence",
                  status: "active",
                  badge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
                  dot: "bg-emerald-500",
                  sources: ["OpenAlex API", "PubMed (NCBI)", "ORCID", "Unpaywall"],
                  desc: "Publicly accessible knowledge bases and open repositories.",
                },
                {
                  phase: "Source 2",
                  label: "Web Scraped Context",
                  status: "active",
                  badge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
                  dot: "bg-emerald-500",
                  sources: ["Google Scholar", "Semantic Scholar", "Altmetric"],
                  desc: "Domain-specific scraping for deepened entity context.",
                },
                {
                  phase: "Source 3",
                  label: "Proprietary Connectors",
                  status: "active",
                  badge: "bg-indigo-100 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400",
                  dot: "bg-indigo-500",
                  sources: ["WoS API", "Scopus (Elsevier)", "Custom REST Hubs"],
                  desc: "Enterprise-grade providers via Bring Your Own Key (BYOK).",
                },
              ].map((phase) => (
                <div
                  key={phase.phase}
                  className="relative rounded-xl border border-gray-100 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-800"
                >
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-bold text-gray-900 dark:text-white">{phase.phase}</span>
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${phase.badge}`}
                    >
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${phase.dot} ${
                          phase.status === "active" ? "animate-pulse" : ""
                        }`}
                      />
                      {phase.status === "active" ? "Active" : "Planned"}
                    </span>
                  </div>
                  <p className="mb-2 font-semibold text-gray-800 dark:text-gray-200">{phase.label}</p>
                  <p className="mb-3 text-xs text-gray-500 dark:text-gray-400">{phase.desc}</p>
                  <ul className="space-y-1">
                    {phase.sources.map((source) => (
                      <li
                        key={source}
                        className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400"
                      >
                        <span className="h-1 w-1 rounded-full bg-gray-400 dark:bg-gray-600" />
                        {source}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {enrichLoading && !enrichStats && (
        <div className="flex h-48 items-center justify-center rounded-2xl border border-dashed border-gray-200 dark:border-gray-800">
          <svg className="h-6 w-6 animate-spin text-indigo-500" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
      )}
    </>
  );
}
