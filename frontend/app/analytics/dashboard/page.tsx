"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { PageHeader, StatCard, ErrorBanner, SkeletonCard } from "../../components/ui";
import ConceptCloud from "../../components/ConceptCloud";
import { useDomain } from "../../contexts/DomainContext";
import { apiFetch } from "@/lib/api";
import { Analytics } from "@/lib/analytics";

const REFRESH_INTERVAL_SEC = 5 * 60; // 5 minutes

// ── Types ─────────────────────────────────────────────────────────────────────

interface DashboardData {
  domain_id: string;
  kpis: {
    total_entities: number;
    enriched_count: number;
    enrichment_pct: number;
    avg_citations: number;
    total_concepts: number;
  };
  entities_by_year: { year: number; count: number }[];
  brand_year_matrix: {
    brands: string[];
    years: number[];
    matrix: number[][];
  };
  top_concepts: { concept: string; count: number; pct: number }[];
  top_entities: {
    id: number;
    entity_name: string;
    brand: string | null;
    citation_count: number;
    source: string | null;
  }[];
  quality?: {
    average: number | null;
    distribution: { high: number; medium: number; low: number };
  };
}

// ── Heatmap cell with violet color scale ─────────────────────────────────────

function HeatCell({ value, max }: { value: number; max: number }) {
  const alpha = max > 0 ? 0.08 + (value / max) * 0.82 : 0.08;
  const isHigh = max > 0 && value / max > 0.6;
  return (
    <td
      className="border border-gray-100 px-3 py-2 text-center text-xs font-medium dark:border-gray-800"
      style={{ backgroundColor: `rgba(139,92,246,${alpha})` }}
    >
      <span className={isHigh ? "text-white" : "text-gray-700 dark:text-gray-200"}>
        {value > 0 ? value.toLocaleString() : "—"}
      </span>
    </td>
  );
}

// ── Source badge ──────────────────────────────────────────────────────────────

const SOURCE_COLORS: Record<string, string> = {
  openalex: "bg-violet-100 text-violet-700 dark:bg-violet-500/20 dark:text-violet-300",
  wos: "bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300",
  scholar: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300",
};

function SourceBadge({ source }: { source: string | null }) {
  if (!source) return <span className="text-xs text-gray-400">—</span>;
  const cls = SOURCE_COLORS[source.toLowerCase()] ??
    "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {source}
    </span>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ExecutiveDashboardPage() {
  const { activeDomainId } = useDomain();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL_SEC);
  const [exporting, setExporting] = useState(false);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/dashboard/summary?domain_id=${activeDomainId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e: any) {
      setError(e.message ?? "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, [activeDomainId]);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  // Auto-refresh countdown
  useEffect(() => {
    if (!autoRefresh) { setCountdown(REFRESH_INTERVAL_SEC); return; }
    const tick = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) { fetchDashboard(); return REFRESH_INTERVAL_SEC; }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(tick);
  }, [autoRefresh, fetchDashboard]);

  const mm = String(Math.floor(countdown / 60)).padStart(2, "0");
  const ss = String(countdown % 60).padStart(2, "0");

  const handleExportPDF = async () => {
    if (!data) return;
    setExporting(true);
    Analytics.dashboardExportPDF(activeDomainId);
    try {
      const res = await apiFetch("/exports/pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain_id: activeDomainId,
          sections: ["entity_stats", "enrichment_coverage", "top_brands", "topic_clusters"],
          title: "Executive Dashboard Report",
        }),
      });
      if (!res.ok) { setError("PDF export failed (WeasyPrint may not be installed)"); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `dashboard_${activeDomainId}_${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("PDF export error");
    } finally {
      setExporting(false);
    }
  };

  // Compute heatmap max for scaling
  const heatMax = data
    ? Math.max(1, ...data.brand_year_matrix.matrix.flat())
    : 1;

  return (
    <div className="flex flex-col gap-6 pb-10">
      <PageHeader
        title="Executive Dashboard"
        description="High-level KPIs, temporal trends, and concept landscape for decision makers"
        breadcrumbs={[
          { label: "Analytics", href: "/analytics" },
          { label: "Executive Dashboard" },
        ]}
        actions={
          <div className="flex items-center gap-2">
            {/* Auto-refresh toggle */}
            <button
              onClick={() => setAutoRefresh(v => !v)}
              title={autoRefresh ? `Auto-refresh on — next in ${mm}:${ss}` : "Enable auto-refresh every 5 min"}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium shadow-sm transition ${
                autoRefresh
                  ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400"
                  : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              }`}
            >
              <svg className={`h-3.5 w-3.5 ${autoRefresh ? "animate-spin" : ""}`} aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
              <span className="tabular-nums">{autoRefresh ? `${mm}:${ss}` : "Auto"}</span>
            </button>

            {/* Manual refresh */}
            <button
              onClick={fetchDashboard}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
            >
              <svg className="h-4 w-4" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
              Refresh
            </button>

            {/* Export Dashboard PDF */}
            <button
              onClick={handleExportPDF}
              disabled={exporting || loading || !data}
              className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-violet-700 disabled:opacity-50"
            >
              {exporting ? (
                <svg className="h-4 w-4 animate-spin" aria-hidden="true" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
              ) : (
                <svg className="h-4 w-4" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
              )}
              {exporting ? "Exporting…" : "Export PDF"}
            </button>
          </div>
        }
      />

      {error && <ErrorBanner message={error} onRetry={fetchDashboard} variant="card" />}

      {/* ── Section 1: Hero KPIs ── */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
        {loading ? (
          Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} lines={2} />)
        ) : data ? (
          <>
            <StatCard
              iconColor="blue"
              icon={
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                </svg>
              }
              label="Total Entities"
              value={data.kpis.total_entities.toLocaleString()}
            />
            <StatCard
              iconColor="emerald"
              icon={
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              }
              label="Enrichment Coverage"
              value={`${data.kpis.enrichment_pct}%`}
              trend={{
                value: `${data.kpis.enriched_count.toLocaleString()} enriched`,
                direction: "up",
                positive: true,
              }}
            />
            <StatCard
              iconColor="violet"
              icon={
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
                </svg>
              }
              label="Avg Citations"
              value={data.kpis.avg_citations}
            />
            <StatCard
              iconColor="amber"
              icon={
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              }
              label="Distinct Concepts"
              value={data.kpis.total_concepts.toLocaleString()}
            />
            {/* Quality KPI */}
            <div className="rounded-2xl border border-indigo-100 bg-white p-5 shadow-sm dark:border-indigo-500/20 dark:bg-gray-900">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-50 dark:bg-indigo-500/10">
                  <svg className="h-5 w-5 text-indigo-600 dark:text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                  </svg>
                </div>
                <div className="min-w-0">
                  <p className="text-xs text-gray-500 dark:text-gray-400">Avg Quality</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {data.quality?.average != null ? `${Math.round(data.quality.average * 100)}%` : "—"}
                  </p>
                </div>
              </div>
              {data.quality?.distribution && (
                <div className="mt-3 flex gap-1" title="High / Medium / Low quality distribution">
                  {(() => {
                    const { high, medium, low } = data.quality.distribution;
                    const total = high + medium + low;
                    if (total === 0) return <span className="text-xs text-gray-400">No scored entities</span>;
                    return (
                      <div className="flex w-full overflow-hidden rounded-full h-2 gap-px">
                        {high > 0 && <div className="bg-emerald-500 h-2 rounded-l-full" style={{ width: `${(high / total) * 100}%` }} title={`High: ${high}`} />}
                        {medium > 0 && <div className="bg-amber-400 h-2" style={{ width: `${(medium / total) * 100}%` }} title={`Medium: ${medium}`} />}
                        {low > 0 && <div className="bg-red-500 h-2 rounded-r-full" style={{ width: `${(low / total) * 100}%` }} title={`Low: ${low}`} />}
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>
          </>
        ) : null}
      </div>

      {/* ── Section 2: Impact Over Time ── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <h3 className="mb-1 text-base font-semibold text-gray-900 dark:text-white">
          Entities Over Time
        </h3>
        <p className="mb-5 text-xs text-gray-500 dark:text-gray-400">
          Entity creation by year — extracted from <code>creation_date</code>
        </p>
        {loading ? (
          <SkeletonCard lines={4} />
        ) : !data || data.entities_by_year.length === 0 ? (
          <div className="flex h-52 items-center justify-center text-sm text-gray-400">
            No date data available — upload entities with a <code>creation_date</code> field.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={data.entities_by_year} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gradEntities" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
              <XAxis dataKey="year" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "#6b7280" }} />
              <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "#6b7280" }} />
              <Tooltip
                contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)", fontSize: "12px" }}
                formatter={(v) => [(Number(v) || 0).toLocaleString(), "Entities"]}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#8b5cf6"
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#gradEntities)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ── Section 3: Brand × Year Heatmap ── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <h3 className="mb-1 text-base font-semibold text-gray-900 dark:text-white">
          Top Primary Labels by Year
        </h3>
        <p className="mb-5 text-xs text-gray-500 dark:text-gray-400">
          Entity count per label × year — darker violet = higher volume
        </p>
        {loading ? (
          <SkeletonCard lines={3} />
        ) : !data || data.brand_year_matrix.brands.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-sm text-gray-400">
            No brand data available.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr>
                  <th className="border border-gray-100 bg-gray-50 px-3 py-2 text-xs font-semibold text-gray-500 dark:border-gray-800 dark:bg-gray-800 dark:text-gray-400">
                    Label
                  </th>
                  {data.brand_year_matrix.years.map((yr) => (
                    <th
                      key={yr}
                      className="border border-gray-100 bg-gray-50 px-3 py-2 text-center text-xs font-semibold text-gray-500 dark:border-gray-800 dark:bg-gray-800 dark:text-gray-400"
                    >
                      {yr}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.brand_year_matrix.brands.map((brand, bi) => (
                  <tr key={brand}>
                    <td className="border border-gray-100 px-3 py-2 text-xs font-semibold text-gray-700 dark:border-gray-800 dark:text-gray-200">
                      {brand}
                    </td>
                    {data.brand_year_matrix.matrix[bi].map((val, yi) => (
                      <HeatCell key={yi} value={val} max={heatMax} />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Section 4: Concept Cloud ── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
              Knowledge Concept Map
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Top concepts extracted from enriched entities — size reflects frequency
            </p>
          </div>
          {data && (
            <Link
              href="/analytics/topics"
              className="text-xs font-medium text-violet-600 hover:text-violet-700 dark:text-violet-400"
            >
              Full analysis →
            </Link>
          )}
        </div>
        {loading ? (
          <SkeletonCard lines={2} />
        ) : (
          <ConceptCloud concepts={data?.top_concepts ?? []} maxItems={40} />
        )}
      </div>

      {/* ── Section 5: Top Entities by Citations ── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
              Top Entities by Impact
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Highest citation count among enriched entities
            </p>
          </div>
          <Link
            href="/"
            className="text-xs font-medium text-violet-600 hover:text-violet-700 dark:text-violet-400"
          >
            View all →
          </Link>
        </div>
        {loading ? (
          <SkeletonCard lines={4} />
        ) : !data || data.top_entities.length === 0 ? (
          <div className="flex h-32 items-center justify-center text-sm text-gray-400">
            No enriched entities yet. Run enrichment to populate this table.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-800">
                  <th className="pb-3 pr-4 text-xs font-semibold uppercase tracking-wide text-gray-500">#</th>
                  <th className="pb-3 pr-4 text-xs font-semibold uppercase tracking-wide text-gray-500">Entity</th>
                  <th className="pb-3 pr-4 text-xs font-semibold uppercase tracking-wide text-gray-500">Primary Label</th>
                  <th className="pb-3 pr-4 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">Citations</th>
                  <th className="pb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                {data.top_entities.map((e, i) => (
                  <tr key={e.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                    <td className="py-3 pr-4 text-xs font-bold text-gray-400">{i + 1}</td>
                    <td className="py-3 pr-4">
                      <Link
                        href={`/entities/${e.id}`}
                        className="text-sm font-medium text-gray-900 hover:text-violet-600 dark:text-white dark:hover:text-violet-400"
                      >
                        {e.entity_name ?? `Entity #${e.id}`}
                      </Link>
                    </td>
                    <td className="py-3 pr-4 text-sm text-gray-500 dark:text-gray-400">
                      {e.brand ?? "—"}
                    </td>
                    <td className="py-3 pr-4 text-right">
                      <span className="text-sm font-bold text-violet-600 dark:text-violet-400">
                        {e.citation_count.toLocaleString()}
                      </span>
                    </td>
                    <td className="py-3">
                      <SourceBadge source={e.source} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
