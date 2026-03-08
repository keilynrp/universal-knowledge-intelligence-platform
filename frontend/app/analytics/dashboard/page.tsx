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
import { PageHeader, StatCard, Badge } from "../../components/ui";
import ConceptCloud from "../../components/ConceptCloud";
import { useDomain } from "../../contexts/DomainContext";
import { apiFetch } from "@/lib/api";

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

// ── Loading skeleton ──────────────────────────────────────────────────────────

function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded-lg bg-gray-100 dark:bg-gray-800 ${className}`} />
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ExecutiveDashboardPage() {
  const { activeDomainId } = useDomain();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
          <button
            onClick={fetchDashboard}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
            Refresh
          </button>
        }
      />

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/10 dark:text-red-400">
          {error}
        </div>
      )}

      {/* ── Section 1: Hero KPIs ── */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)
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
          <Skeleton className="h-52" />
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
                formatter={(v: number | undefined) => [(v ?? 0).toLocaleString(), "Entities"]}
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
          Top Brands by Year
        </h3>
        <p className="mb-5 text-xs text-gray-500 dark:text-gray-400">
          Entity count per brand × year — darker violet = higher volume
        </p>

        {loading ? (
          <Skeleton className="h-40" />
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
                    Brand
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
          <Skeleton className="h-32" />
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
          <Skeleton className="h-48" />
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
                  <th className="pb-3 pr-4 text-xs font-semibold uppercase tracking-wide text-gray-500">Brand</th>
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
