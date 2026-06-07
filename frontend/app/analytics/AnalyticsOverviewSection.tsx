"use client";

import Link from "next/link";

import { ConceptTooltip, StatCard } from "../components/ui";

import { ProgressBar, SectionDivider } from "./AnalyticsPrimitives";
import type { Stats } from "./analyticsTypes";

function asFiniteNumber(value: unknown, fallback = 0): number {
  const next = typeof value === "number" ? value : Number(value);
  return Number.isFinite(next) ? next : fallback;
}

export function AnalyticsOverviewSection({
  stats,
  totalCount,
  t,
}: {
  stats: Stats | null;
  totalCount: number;
  t: (key: string) => string;
}) {
  const ctas = [
    {
      href: "/analytics/olap",
      title: t("page.analytics.cta_olap_title"),
      description:
        "Multi-dimensional GROUP BY queries, cross-tabs, drill-down and Excel export - powered by DuckDB",
      button: t("page.analytics.cta_olap_button"),
      border: "border-blue-200 bg-blue-50 dark:border-blue-900/40 dark:bg-blue-900/10",
      iconWrap: "bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400",
      buttonClass: "bg-blue-600 hover:bg-blue-700",
      accent: null as string | null,
      icon: (
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605"
        />
      ),
    },
    {
      href: "/analytics/nlq",
      title: t("page.analytics.cta_nlq_title"),
      description: "Ask your data anything in plain English - AI translates it into an OLAP query instantly",
      button: t("page.analytics.cta_nlq_button"),
      border:
        "border-purple-200 bg-gradient-to-r from-violet-50 to-purple-50 dark:border-purple-900/40 dark:from-violet-900/10 dark:to-purple-900/10",
      iconWrap: "bg-violet-100 text-violet-600 dark:bg-violet-900/30 dark:text-violet-400",
      buttonClass: "bg-violet-600 hover:bg-violet-700",
      accent:
        "rounded-full bg-violet-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700 dark:bg-violet-500/30 dark:text-violet-300",
      icon: (
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"
        />
      ),
    },
    {
      href: "/analytics/topics",
      title: t("page.analytics.cta_topics_title"),
      description:
        "Concept frequency, co-occurrence, topic clusters, and Cramer's V field correlations",
      button: t("page.analytics.cta_topics_button"),
      border: "border-violet-200 bg-violet-50 dark:border-violet-900/40 dark:bg-violet-900/10",
      iconWrap: "bg-violet-100 text-violet-600 dark:bg-violet-900/30 dark:text-violet-400",
      buttonClass: "bg-violet-600 hover:bg-violet-700",
      accent: null,
      icon: (
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m1.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
        />
      ),
    },
    {
      href: "/analytics/roi",
      title: t("page.analytics.cta_roi_title"),
      description:
        "Monte Carlo I+D projection - adoption uncertainty, break-even probability and year-by-year ROI trajectory",
      button: t("page.analytics.cta_roi_button"),
      border: "border-emerald-200 bg-emerald-50 dark:border-emerald-900/40 dark:bg-emerald-900/10",
      iconWrap: "bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400",
      buttonClass: "bg-emerald-600 hover:bg-emerald-700",
      accent: null,
      icon: (
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941"
        />
      ),
    },
    {
      href: "/analytics/dashboard",
      title: t("page.analytics.cta_dashboard_title"),
      description:
        "KPI heatmap, impact timeline, concept cloud and top entities - full knowledge portfolio at a glance",
      button: t("page.analytics.cta_dashboard_button"),
      border: "border-purple-200 bg-purple-50 dark:border-purple-900/40 dark:bg-purple-900/10",
      iconWrap: "bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400",
      buttonClass: "bg-purple-600 hover:bg-purple-700",
      accent: null,
      icon: (
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6"
        />
      ),
    },
    {
      href: "/analytics/compare",
      title: t("page.analytics.cta_compare_title"),
      description:
        "Compare KPIs, entity types, concepts, and citation impact across 2-4 domains side by side",
      button: t("page.analytics.cta_compare_button"),
      border: "border-teal-200 bg-teal-50 dark:border-teal-900/40 dark:bg-teal-900/10",
      iconWrap: "bg-teal-100 text-teal-600 dark:bg-teal-900/30 dark:text-teal-400",
      buttonClass: "bg-teal-600 hover:bg-teal-700",
      accent: null,
      icon: (
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5"
        />
      ),
    },
  ];

  return (
    <>
      <SectionDivider label={t("page.analytics.section_overview")} />

      {stats && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label={<ConceptTooltip concept="entity">{t("page.analytics.metric_total_entities")}</ConceptTooltip>}
              value={totalCount.toLocaleString()}
              iconColor="blue"
              icon={
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
                  />
                </svg>
              }
              subtitle={t("page.analytics.metric_total_subtitle")}
            />
            <StatCard
              label={t("page.analytics.metric_active_domain")}
              value={stats.domain_name || "Catalog"}
              iconColor="violet"
              icon={
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z"
                  />
                </svg>
              }
              subtitle="Current OLAP Cube Context"
            />
            <StatCard
              label="Analytical Dimensions"
              value={Object.keys(stats.distributions || {}).length.toLocaleString()}
              iconColor="amber"
              icon={
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                  />
                </svg>
              }
              subtitle="DuckDB Extracted Dimensions"
            />
            <StatCard
              label="OLAP Engine"
              value="DuckDB"
              iconColor="emerald"
              icon={
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                  />
                </svg>
              }
              subtitle="Powered by Embedded DB"
            />
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            {Object.entries(stats.distributions || {}).map(([dimName, items]) => (
              <div
                key={dimName}
                className="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900"
              >
                <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 dark:border-gray-800">
                  <div>
                    <h3 className="text-base font-semibold text-gray-900 dark:text-white">{dimName}</h3>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Cube dimension</p>
                  </div>
                </div>
                <div className="divide-y divide-gray-100 dark:divide-gray-800">
                  {items.map((item, idx) => {
                    const itemValue = asFiniteNumber(item.value);
                    const pct = totalCount > 0 ? ((itemValue / totalCount) * 100).toFixed(1) : "0";
                    return (
                      <div
                        key={item.label || idx}
                        className="px-5 py-3 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50"
                      >
                        <div className="mb-1.5 flex items-center justify-between">
                          <span className="truncate pr-2 text-sm font-medium text-gray-900 dark:text-white">
                            {item.label || "Unknown"}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-400 dark:text-gray-500">{pct}%</span>
                            <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-500/10 dark:text-blue-400">
                              {itemValue.toLocaleString()}
                            </span>
                          </div>
                        </div>
                        <ProgressBar value={itemValue} max={totalCount} color="bg-blue-500" />
                      </div>
                    );
                  })}
                  {items.length === 0 && (
                    <div className="px-5 py-8 text-center text-sm text-gray-400 dark:text-gray-500">
                      No {dimName} data available
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {ctas.map((cta) => (
        <div
          key={cta.href}
          className={`flex items-center justify-between rounded-xl border px-5 py-3.5 ${cta.border}`}
        >
          <div className="flex items-center gap-3">
            <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${cta.iconWrap}`}>
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {cta.icon}
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-gray-900 dark:text-gray-200">{cta.title}</p>
                {cta.accent && <span className={cta.accent}>New</span>}
              </div>
              <p className="text-xs text-gray-600 dark:text-gray-400">{cta.description}</p>
            </div>
          </div>
          <Link
            href={cta.href}
            className={`flex flex-shrink-0 items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors ${cta.buttonClass}`}
          >
            {cta.button}
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </Link>
        </div>
      ))}
    </>
  );
}
