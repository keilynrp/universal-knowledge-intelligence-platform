"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { PageHeader, StatCard, Badge } from "../components/ui";
import { useDomain } from "../contexts/DomainContext";
import { apiFetch } from "@/lib/api";
import ConceptCloud from "../components/ConceptCloud";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Stats {
    domain_id: string;
    domain_name: string;
    total_records: number;
    distributions: Record<string, { label: string; value: number }[]>;
    cube_metrics: Record<string, any>;
}

interface EnrichStats {
    total_entities: number;
    enriched_count: number;
    pending_count: number;
    failed_count: number;
    none_count: number;
    enrichment_coverage_pct: number;
    top_concepts: { concept: string; count: number }[];
    citations: {
        average: number;
        max: number;
        total: number;
        distribution: Record<string, number>;
    };
}

// ─── Small reusable components ─────────────────────────────────────────────────

function ProgressBar({ value, max, color }: { value: number; max: number; color: string }) {
    const pct = max > 0 ? (value / max) * 100 : 0;
    return (
        <div className="h-2 w-full rounded-full bg-gray-100 dark:bg-gray-800">
            <div className={`h-2 rounded-full transition-all duration-700 ${color}`} style={{ width: `${pct}%` }} />
        </div>
    );
}

function SectionDivider({ label }: { label: string }) {
    return (
        <div className="flex items-center gap-4 py-2">
            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-gray-200 to-transparent dark:via-gray-700" />
            <span className="text-xs font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500">
                {label}
            </span>
            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-gray-200 to-transparent dark:via-gray-700" />
        </div>
    );
}

// Status badge variant mapping
const STATUS_VARIANT: Record<string, "success" | "warning" | "error" | "default"> = {
    completed: "success",
    pending: "warning",
    failed: "error",
    none: "default",
};

function StatusBadge({ status, count }: { status: string; count: number }) {
    const variant = STATUS_VARIANT[status] ?? "default";
    return (
        <Badge variant={variant} dot dotPulse={status === "pending"} size="md">
            {status.charAt(0).toUpperCase() + status.slice(1)} · {count.toLocaleString()}
        </Badge>
    );
}

// Horizontal bar for citation distribution
function CitationBar({ label, value, max }: { label: string; value: number; max: number }) {
    const pct = max > 0 ? (value / max) * 100 : 0;
    const gradients: Record<string, string> = {
        "0": "from-gray-400 to-gray-500",
        "1-10": "from-blue-400 to-blue-500",
        "11-50": "from-violet-400 to-violet-500",
        "51-200": "from-purple-500 to-fuchsia-500",
        "200+": "from-fuchsia-500 to-pink-500",
    };
    const grad = gradients[label] ?? "from-blue-400 to-blue-500";
    return (
        <div className="flex items-center gap-3">
            <span className="w-12 shrink-0 text-right text-xs font-medium text-gray-500 dark:text-gray-400">{label}</span>
            <div className="relative h-5 flex-1 overflow-hidden rounded-md bg-gray-100 dark:bg-gray-800">
                <div
                    className={`h-full rounded-md bg-gradient-to-r ${grad} transition-all duration-700`}
                    style={{ width: `${pct}%` }}
                />
            </div>
            <span className="w-8 shrink-0 text-xs font-semibold text-gray-700 dark:text-gray-300">{value}</span>
        </div>
    );
}

// ─── Circular Donut ────────────────────────────────────────────────────────────

function CoverageRing({ pct }: { pct: number }) {
    const r = 44;
    const circ = 2 * Math.PI * r;
    const offset = circ - (pct / 100) * circ;
    return (
        <div className="relative flex h-28 w-28 items-center justify-center">
            <svg className="absolute inset-0 -rotate-90" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r={r} fill="none" strokeWidth="10" className="stroke-gray-100 dark:stroke-gray-800" />
                <circle
                    cx="50" cy="50" r={r} fill="none" strokeWidth="10"
                    strokeLinecap="round"
                    className="stroke-violet-500 transition-all duration-1000"
                    strokeDasharray={circ}
                    strokeDashoffset={offset}
                />
            </svg>
            <div className="flex flex-col items-center">
                <span className="text-2xl font-bold text-gray-900 dark:text-white">{pct}%</span>
                <span className="text-[10px] font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider">covered</span>
            </div>
        </div>
    );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
    const { activeDomainId } = useDomain();
    const [stats, setStats] = useState<Stats | null>(null);
    const [enrichStats, setEnrichStats] = useState<EnrichStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [enrichLoading, setEnrichLoading] = useState(true);
    const [bulkQueuing, setBulkQueuing] = useState(false);
    const [bulkResult, setBulkResult] = useState<{ queued_records: number } | null>(null);

    const fetchStats = useCallback(async () => {
        try {
            const res = await apiFetch(`/olap/${activeDomainId}`);
            if (!res.ok) throw new Error("Failed");
            setStats(await res.json());
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    }, [activeDomainId]);

    const fetchEnrichStats = useCallback(async () => {
        try {
            const res = await apiFetch("/enrich/stats");
            if (!res.ok) throw new Error("Failed");
            setEnrichStats(await res.json());
        } catch (e) {
            console.error(e);
        } finally {
            setEnrichLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchStats();
        fetchEnrichStats();
    }, [fetchStats, fetchEnrichStats]);

    const handleBulkEnrich = async () => {
        setBulkQueuing(true);
        setBulkResult(null);
        try {
            const res = await apiFetch("/enrich/bulk?limit=500", { method: "POST" });
            if (!res.ok) throw new Error("Failed");
            const data = await res.json();
            setBulkResult(data);
            // Refresh enrichment stats after a short delay
            setTimeout(fetchEnrichStats, 1500);
        } catch (e) {
            console.error(e);
        } finally {
            setBulkQueuing(false);
        }
    };

    // ── Loading state ──
    if (loading && enrichLoading) {
        return (
            <div className="flex h-64 items-center justify-center">
                <svg className="h-8 w-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
            </div>
        );
    }

    const totalCount = stats?.total_records ?? 0;
    const ciDistrib = enrichStats?.citations.distribution ?? {};
    const ciMax = Math.max(...Object.values(ciDistrib), 1);

    return (
        <div className="space-y-8">

            <PageHeader
                breadcrumbs={[{ label: "Home", href: "/" }, { label: "Analytics" }]}
                title="Intelligence Dashboard"
                description="Key metrics, enrichment pipeline, and data quality insights"
            />

            {/* ═══ SECTION 1: Data Hub Overview ════════════════════════════════ */}
            <SectionDivider label="Data Hub Overview" />

            {/* Metric cards */}
            {stats && (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    <StatCard
                        label="Total Entities"
                        value={totalCount.toLocaleString()}
                        iconColor="blue"
                        icon={
                            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                            </svg>
                        }
                        subtitle="Records in repository"
                    />
                    <StatCard
                        label="Active Domain"
                        value={stats.domain_name || "Catalog"}
                        iconColor="violet"
                        icon={
                            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z" />
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
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
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
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                            </svg>
                        }
                        subtitle="Powered by Embedded DB"
                    />
                </div>
            )}

            {/* Multidimensional Dynamic Grids */}
            {stats && (
                <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
                    {Object.entries(stats.distributions || {}).map(([dimName, items]) => (
                        <div key={dimName} className="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
                            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 dark:border-gray-800">
                                <div>
                                    <h3 className="text-base font-semibold text-gray-900 dark:text-white">{dimName}</h3>
                                    <p className="text-xs text-gray-500 dark:text-gray-400">Cube dimension</p>
                                </div>
                            </div>
                            <div className="divide-y divide-gray-100 dark:divide-gray-800">
                                {items.map((item, idx) => {
                                    const pct = totalCount > 0 ? ((item.value / totalCount) * 100).toFixed(1) : "0";
                                    return (
                                        <div key={item.label || idx} className="px-5 py-3 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50">
                                            <div className="mb-1.5 flex items-center justify-between">
                                                <span className="text-sm font-medium text-gray-900 dark:text-white truncate pr-2">{item.label || "Unknown"}</span>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-gray-400 dark:text-gray-500">{pct}%</span>
                                                    <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-500/10 dark:text-blue-400">{item.value.toLocaleString()}</span>
                                                </div>
                                            </div>
                                            <ProgressBar value={item.value} max={totalCount} color="bg-blue-500" />
                                        </div>
                                    );
                                })}
                                {items.length === 0 && <div className="px-5 py-8 text-center text-sm text-gray-400 dark:text-gray-500">No {dimName} data available</div>}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* OLAP Explorer CTA */}
            <div className="flex items-center justify-between rounded-xl border border-blue-200 bg-blue-50 px-5 py-3.5 dark:border-blue-900/40 dark:bg-blue-900/10">
                <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605" />
                        </svg>
                    </div>
                    <div>
                        <p className="text-sm font-medium text-blue-900 dark:text-blue-200">OLAP Cube Explorer</p>
                        <p className="text-xs text-blue-600 dark:text-blue-400">Multi-dimensional GROUP BY queries, cross-tabs, drill-down and Excel export — powered by DuckDB</p>
                    </div>
                </div>
                <Link
                    href="/analytics/olap"
                    className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors flex-shrink-0"
                >
                    Open Explorer
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                    </svg>
                </Link>
            </div>

            {/* Topic Modeling CTA */}
            <div className="flex items-center justify-between rounded-xl border border-violet-200 bg-violet-50 px-5 py-3.5 dark:border-violet-900/40 dark:bg-violet-900/10">
                <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-100 text-violet-600 dark:bg-violet-900/30 dark:text-violet-400">
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m1.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                    </div>
                    <div>
                        <p className="text-sm font-medium text-violet-900 dark:text-violet-200">Topic Modeling</p>
                        <p className="text-xs text-violet-600 dark:text-violet-400">Concept frequency, co-occurrence, topic clusters, and Cramér&apos;s V field correlations</p>
                    </div>
                </div>
                <Link
                    href="/analytics/topics"
                    className="flex items-center gap-1.5 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 transition-colors flex-shrink-0"
                >
                    Explore Topics
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                    </svg>
                </Link>
            </div>

            {/* ROI Calculator CTA */}
            <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-3.5 dark:border-emerald-900/40 dark:bg-emerald-900/10">
                <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400">
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
                        </svg>
                    </div>
                    <div>
                        <p className="text-sm font-medium text-emerald-900 dark:text-emerald-200">ROI Calculator</p>
                        <p className="text-xs text-emerald-600 dark:text-emerald-400">Monte Carlo I+D projection — adoption uncertainty, break-even probability and year-by-year ROI trajectory</p>
                    </div>
                </div>
                <Link
                    href="/analytics/roi"
                    className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors flex-shrink-0"
                >
                    Open Calculator
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                    </svg>
                </Link>
            </div>

            {/* Executive Dashboard CTA */}
            <div className="flex items-center justify-between rounded-xl border border-purple-200 bg-purple-50 px-5 py-3.5 dark:border-purple-900/40 dark:bg-purple-900/10">
                <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400">
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6" />
                        </svg>
                    </div>
                    <div>
                        <p className="text-sm font-medium text-purple-900 dark:text-purple-200">Executive Dashboard</p>
                        <p className="text-xs text-purple-600 dark:text-purple-400">KPI heatmap, impact timeline, concept cloud and top entities — full knowledge portfolio at a glance</p>
                    </div>
                </div>
                <Link
                    href="/analytics/dashboard"
                    className="flex items-center gap-1.5 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 transition-colors flex-shrink-0"
                >
                    Open Dashboard
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                    </svg>
                </Link>
            </div>

            {/* ═══ SECTION 2: AI Knowledge Hub — Predictive Enrichment ═══════════ */}
            <SectionDivider label="UKIP Knowledge Hub — Semantic Enrichment" />

            {/* Hero Banner */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-600 via-blue-700 to-cyan-600 p-6 text-white shadow-lg">
                {/* Decorative circles */}
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
                            Transforming raw product records into rich domain entities using cross-referenced bibliometric data, NLP concepts, and global impact projections.
                        </p>
                    </div>
                    {/* Bulk Enrich CTA */}
                    <div className="flex flex-col items-start gap-2 sm:items-end">
                        <button
                            id="bulk-enrich-btn"
                            onClick={handleBulkEnrich}
                            disabled={bulkQueuing}
                            className="inline-flex items-center gap-2 rounded-xl bg-white px-5 py-2.5 text-sm font-semibold text-indigo-700 shadow transition-all hover:bg-indigo-50 disabled:opacity-60"
                        >
                            {bulkQueuing ? (
                                <>
                                    <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                    </svg>
                                    Enriching Hub…
                                </>
                            ) : (
                                <>
                                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                    </svg>
                                    Trigger Hub Enrichment
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

            {/* Enrichment Stats Grid */}
            {enrichStats && (
                <>
                    {/* Top row: KPI cards */}
                    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                        {[
                            { label: "Enriched Entities", value: enrichStats.enriched_count, color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-500/10" },
                            { label: "Avg. Connectivity", value: enrichStats.citations.average, color: "text-violet-600 dark:text-violet-400", bg: "bg-violet-50 dark:bg-violet-500/10" },
                            { label: "Max Influence", value: enrichStats.citations.max.toLocaleString(), color: "text-fuchsia-600 dark:text-fuchsia-400", bg: "bg-fuchsia-50 dark:bg-fuchsia-500/10" },
                            { label: "Total Knowledge Points", value: enrichStats.citations.total.toLocaleString(), color: "text-blue-600 dark:text-blue-400", bg: "bg-blue-50 dark:bg-blue-500/10" },
                        ].map((card) => (
                            <div key={card.label} className={`rounded-2xl border border-gray-200 ${card.bg} p-5 dark:border-gray-800`}>
                                <p className={`text-2xl font-bold ${card.color}`}>{card.value}</p>
                                <p className="mt-1 text-xs font-medium text-gray-500 dark:text-gray-400">{card.label}</p>
                            </div>
                        ))}
                    </div>

                    {/* Middle row: Coverage ring + Status pills + Citation Distribution */}
                    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">

                        {/* Coverage & Status */}
                        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900 xl:col-span-1">
                            <h3 className="mb-1 text-base font-semibold text-gray-900 dark:text-white">Knowledge Hub Coverage</h3>
                            <p className="mb-5 text-xs text-gray-500 dark:text-gray-400">Percentage of repository mapped to global intelligence sources</p>
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

                        {/* Citation Distribution */}
                        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900 xl:col-span-2">
                            <h3 className="mb-1 text-base font-semibold text-gray-900 dark:text-white">Scientific Connectivity</h3>
                            <p className="mb-6 text-xs text-gray-500 dark:text-gray-400">
                                Distribution of intellectual connectivity / citations across the platform
                            </p>
                            {Object.values(ciDistrib).every((v) => v === 0) ? (
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

                    {/* Concept Cloud */}
                    <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <div className="mb-4 flex items-start justify-between">
                            <div>
                                <h3 className="text-base font-semibold text-gray-900 dark:text-white">Ontological Concept Map</h3>
                                <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                                    Top domain concepts extracted via global APIs — size indicates conceptual density
                                </p>
                            </div>
                            <span className="shrink-0 rounded-full bg-indigo-100 px-2.5 py-1 text-xs font-semibold text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400">
                                {enrichStats.top_concepts.length} semantic tags
                            </span>
                        </div>
                        <ConceptCloud concepts={enrichStats.top_concepts} />
                    </div>

                    {/* Phase Roadmap */}
                    <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <h3 className="mb-1 text-base font-semibold text-gray-900 dark:text-white">UKIP Integration Roadmap</h3>
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
                                        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${phase.badge}`}>
                                            <span className={`h-1.5 w-1.5 rounded-full ${phase.dot} ${phase.status === "active" ? "animate-pulse" : ""}`} />
                                            {phase.status === "active" ? "Active" : "Planned"}
                                        </span>
                                    </div>
                                    <p className="mb-2 font-semibold text-gray-800 dark:text-gray-200">{phase.label}</p>
                                    <p className="mb-3 text-xs text-gray-500 dark:text-gray-400">{phase.desc}</p>
                                    <ul className="space-y-1">
                                        {phase.sources.map((src) => (
                                            <li key={src} className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400">
                                                <span className="h-1 w-1 rounded-full bg-gray-400 dark:bg-gray-600" />
                                                {src}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            ))}
                        </div>
                    </div>
                </>
            )}

            {/* Loading state for enrich panel */}
            {enrichLoading && !enrichStats && (
                <div className="flex h-48 items-center justify-center rounded-2xl border border-dashed border-gray-200 dark:border-gray-800">
                    <svg className="h-6 w-6 animate-spin text-indigo-500" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                </div>
            )}
        </div>
    );
}
