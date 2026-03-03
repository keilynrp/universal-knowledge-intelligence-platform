"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import MetricCard from "../components/MetricCard";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Stats {
    total_products: number;
    unique_brands: number;
    unique_models: number;
    unique_product_types: number;
    products_with_variants: number;
    unique_products_with_variants: number;
    validation_status: Record<string, number>;
    identifier_coverage: {
        with_sku: number;
        with_barcode: number;
        with_gtin: number;
        total: number;
    };
    top_brands: { name: string; count: number }[];
    type_distribution: { name: string; count: number }[];
    classification_distribution: { name: string; count: number }[];
    status_distribution: { name: string; count: number }[];
}

interface EnrichStats {
    total_products: number;
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

// Enrichment status pill with animated dot
function StatusBadge({ status, count }: { status: string; count: number }) {
    const cfg: Record<string, { dot: string; text: string; bg: string }> = {
        completed: { dot: "bg-emerald-500", text: "text-emerald-700 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-500/10" },
        pending: { dot: "bg-amber-400 animate-pulse", text: "text-amber-700 dark:text-amber-400", bg: "bg-amber-50 dark:bg-amberald-500/10" },
        failed: { dot: "bg-red-500", text: "text-red-700 dark:text-red-400", bg: "bg-red-50 dark:bg-red-500/10" },
        none: { dot: "bg-gray-400", text: "text-gray-600 dark:text-gray-400", bg: "bg-gray-100 dark:bg-gray-800" },
    };
    const c = cfg[status] ?? cfg.none;
    return (
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${c.bg} ${c.text}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
            {status.charAt(0).toUpperCase() + status.slice(1)} · {count.toLocaleString()}
        </span>
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

// ─── Concept Cloud ─────────────────────────────────────────────────────────────

function ConceptCloud({ concepts }: { concepts: { concept: string; count: number }[] }) {
    if (!concepts.length) return (
        <div className="flex h-32 items-center justify-center text-sm text-gray-400 dark:text-gray-500">
            No concepts extracted yet. Run enrichment to populate this view.
        </div>
    );

    const maxCount = Math.max(...concepts.map((c) => c.count));
    const palette = [
        "text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 hover:bg-blue-100 dark:hover:bg-blue-500/20",
        "text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-500/10 hover:bg-violet-100 dark:hover:bg-violet-500/20",
        "text-fuchsia-600 dark:text-fuchsia-400 bg-fuchsia-50 dark:bg-fuchsia-500/10 hover:bg-fuchsia-100 dark:hover:bg-fuchsia-500/20",
        "text-cyan-600 dark:text-cyan-400 bg-cyan-50 dark:bg-cyan-500/10 hover:bg-cyan-100 dark:hover:bg-cyan-500/20",
        "text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 hover:bg-emerald-100 dark:hover:bg-emerald-500/20",
        "text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10 hover:bg-amber-100 dark:hover:bg-amber-500/20",
    ];

    return (
        <div className="flex flex-wrap gap-2">
            {concepts.map((c, i) => {
                const ratio = c.count / maxCount;
                const size = ratio > 0.75 ? "text-base px-3 py-1.5" : ratio > 0.4 ? "text-sm px-2.5 py-1" : "text-xs px-2 py-0.5";
                const colorClass = palette[i % palette.length];
                return (
                    <span
                        key={c.concept}
                        className={`inline-flex cursor-default items-center gap-1 rounded-full font-medium transition-colors ${size} ${colorClass}`}
                        title={`${c.count} record${c.count !== 1 ? "s" : ""}`}
                    >
                        {c.concept}
                        <span className="opacity-60">·{c.count}</span>
                    </span>
                );
            })}
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
    const [stats, setStats] = useState<Stats | null>(null);
    const [enrichStats, setEnrichStats] = useState<EnrichStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [enrichLoading, setEnrichLoading] = useState(true);
    const [bulkQueuing, setBulkQueuing] = useState(false);
    const [bulkResult, setBulkResult] = useState<{ queued_records: number } | null>(null);

    const fetchStats = useCallback(async () => {
        try {
            const res = await fetch("http://localhost:8000/stats");
            if (!res.ok) throw new Error("Failed");
            setStats(await res.json());
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    }, []);

    const fetchEnrichStats = useCallback(async () => {
        try {
            const res = await fetch("http://localhost:8000/enrich/stats");
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
            const res = await fetch("http://localhost:8000/enrich/bulk?limit=500", { method: "POST" });
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

    const validCount = stats?.validation_status["valid"] ?? 0;
    const invalidCount = stats?.validation_status["invalid"] ?? 0;
    const pendingCount = stats?.validation_status["pending"] ?? 0;
    const validPct = stats && stats.total_products > 0
        ? ((validCount / stats.total_products) * 100).toFixed(1)
        : "0";
    const ciDistrib = enrichStats?.citations.distribution ?? {};
    const ciMax = Math.max(...Object.values(ciDistrib), 1);

    return (
        <div className="space-y-8">

            {/* ═══ SECTION 1: Catalog Overview ════════════════════════════════ */}
            <SectionDivider label="Catalog Overview" />

            {/* Metric cards */}
            {stats && (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
                    <MetricCard
                        label="Total Products"
                        value={stats.total_products.toLocaleString()}
                        icon={
                            <svg className="h-5 w-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                            </svg>
                        }
                        subtitle="Records in database"
                    />
                    <MetricCard
                        label="Unique Brands"
                        value={stats.unique_brands.toLocaleString()}
                        icon={
                            <svg className="h-5 w-5 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z" />
                            </svg>
                        }
                        subtitle="Distinct brand names"
                    />
                    <MetricCard
                        label="Product Types"
                        value={stats.unique_product_types.toLocaleString()}
                        icon={
                            <svg className="h-5 w-5 text-amber-600 dark:text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                            </svg>
                        }
                        subtitle="Category classifications"
                    />
                    <MetricCard
                        label="Validated"
                        value={`${validPct}%`}
                        icon={
                            <svg className="h-5 w-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        }
                        trend={Number(validPct) >= 50 ? { value: `${validCount} records`, positive: true } : { value: `${pendingCount} pending`, positive: false }}
                        subtitle={`${validCount} valid of ${stats.total_products}`}
                    />
                    <MetricCard
                        label="Product Variants"
                        value={stats.unique_products_with_variants.toLocaleString()}
                        icon={
                            <svg className="h-5 w-5 text-cyan-600 dark:text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                            </svg>
                        }
                        trend={{ value: `${stats.products_with_variants} variant entries`, positive: true }}
                        subtitle="Products with multiple variants"
                    />
                </div>
            )}

            {/* Validation + Identifier rows */}
            {stats && (
                <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
                    <div className="xl:col-span-5">
                        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
                            <h3 className="text-base font-semibold text-gray-900 dark:text-white">Validation Status</h3>
                            <p className="mb-5 text-xs text-gray-500 dark:text-gray-400">Product data quality overview</p>
                            <div className="space-y-4">
                                {[
                                    { label: "Valid", value: validCount, color: "bg-green-500", dotColor: "bg-green-500" },
                                    { label: "Pending", value: pendingCount, color: "bg-amber-500", dotColor: "bg-amber-500" },
                                    { label: "Invalid", value: invalidCount, color: "bg-red-500", dotColor: "bg-red-500" },
                                ].map((item) => (
                                    <div key={item.label}>
                                        <div className="mb-1.5 flex items-center justify-between text-sm">
                                            <div className="flex items-center gap-2">
                                                <span className={`h-2.5 w-2.5 rounded-full ${item.dotColor}`} />
                                                <span className="text-gray-700 dark:text-gray-300">{item.label}</span>
                                            </div>
                                            <span className="font-medium text-gray-900 dark:text-white">{item.value.toLocaleString()}</span>
                                        </div>
                                        <ProgressBar value={item.value} max={stats.total_products} color={item.color} />
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                    <div className="xl:col-span-7">
                        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
                            <h3 className="text-base font-semibold text-gray-900 dark:text-white">Identifier Coverage</h3>
                            <p className="mb-5 text-xs text-gray-500 dark:text-gray-400">How well products are identified across systems</p>
                            <div className="space-y-4">
                                {[
                                    { label: "SKU", value: stats.identifier_coverage.with_sku, color: "bg-blue-500" },
                                    { label: "Barcode", value: stats.identifier_coverage.with_barcode, color: "bg-purple-500" },
                                    { label: "GTIN", value: stats.identifier_coverage.with_gtin, color: "bg-cyan-500" },
                                ].map((item) => {
                                    const pct = stats.total_products > 0 ? ((item.value / stats.total_products) * 100).toFixed(1) : "0";
                                    return (
                                        <div key={item.label}>
                                            <div className="mb-1.5 flex items-center justify-between text-sm">
                                                <div className="flex items-center gap-2">
                                                    <span className={`h-2.5 w-2.5 rounded-full ${item.color}`} />
                                                    <span className="text-gray-700 dark:text-gray-300">{item.label}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-gray-400 dark:text-gray-500">{pct}%</span>
                                                    <span className="font-medium text-gray-900 dark:text-white">{item.value.toLocaleString()}</span>
                                                </div>
                                            </div>
                                            <ProgressBar value={item.value} max={stats.total_products} color={item.color} />
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Top Brands / Types / Classifications */}
            {stats && (
                <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
                    {/* Top Brands */}
                    <div className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
                        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 dark:border-gray-800">
                            <div>
                                <h3 className="text-base font-semibold text-gray-900 dark:text-white">Top Brands</h3>
                                <p className="text-xs text-gray-500 dark:text-gray-400">Most represented brands</p>
                            </div>
                            <Link href="/brands" className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400">View All</Link>
                        </div>
                        <div className="divide-y divide-gray-100 dark:divide-gray-800">
                            {stats.top_brands.map((brand, idx) => (
                                <div key={brand.name} className="flex items-center justify-between px-5 py-3 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50">
                                    <div className="flex items-center gap-3">
                                        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gray-100 text-xs font-semibold text-gray-500 dark:bg-gray-800 dark:text-gray-400">{idx + 1}</span>
                                        <span className="text-sm font-medium text-gray-900 dark:text-white">{brand.name}</span>
                                    </div>
                                    <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300">{brand.count.toLocaleString()}</span>
                                </div>
                            ))}
                            {stats.top_brands.length === 0 && <div className="px-5 py-8 text-center text-sm text-gray-400 dark:text-gray-500">No brand data available</div>}
                        </div>
                    </div>
                    {/* Product Types */}
                    <div className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
                        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 dark:border-gray-800">
                            <div>
                                <h3 className="text-base font-semibold text-gray-900 dark:text-white">Product Types</h3>
                                <p className="text-xs text-gray-500 dark:text-gray-400">Distribution by category</p>
                            </div>
                            <Link href="/product-types" className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400">View All</Link>
                        </div>
                        <div className="divide-y divide-gray-100 dark:divide-gray-800">
                            {stats.type_distribution.map((type) => {
                                const pct = stats.total_products > 0 ? ((type.count / stats.total_products) * 100).toFixed(1) : "0";
                                return (
                                    <div key={type.name} className="px-5 py-3 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50">
                                        <div className="mb-1.5 flex items-center justify-between">
                                            <span className="text-sm font-medium text-gray-900 dark:text-white">{type.name}</span>
                                            <div className="flex items-center gap-2">
                                                <span className="text-xs text-gray-400 dark:text-gray-500">{pct}%</span>
                                                <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-500/10 dark:text-blue-400">{type.count.toLocaleString()}</span>
                                            </div>
                                        </div>
                                        <ProgressBar value={type.count} max={stats.total_products} color="bg-blue-500" />
                                    </div>
                                );
                            })}
                            {stats.type_distribution.length === 0 && <div className="px-5 py-8 text-center text-sm text-gray-400 dark:text-gray-500">No product type data</div>}
                        </div>
                    </div>
                    {/* Classifications */}
                    <div className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
                        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 dark:border-gray-800">
                            <div>
                                <h3 className="text-base font-semibold text-gray-900 dark:text-white">Classifications</h3>
                                <p className="text-xs text-gray-500 dark:text-gray-400">Distribution by group</p>
                            </div>
                            <Link href="/classifications" className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400">View All</Link>
                        </div>
                        <div className="divide-y divide-gray-100 dark:divide-gray-800">
                            {(stats.classification_distribution || []).map((item) => {
                                const pct = stats.total_products > 0 ? ((item.count / stats.total_products) * 100).toFixed(1) : "0";
                                return (
                                    <div key={item.name} className="px-5 py-3 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50">
                                        <div className="mb-1.5 flex items-center justify-between">
                                            <span className="text-sm font-medium text-gray-900 dark:text-white">{item.name || "Unclassified"}</span>
                                            <div className="flex items-center gap-2">
                                                <span className="text-xs text-gray-400 dark:text-gray-500">{pct}%</span>
                                                <span className="inline-flex items-center rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-500/10 dark:text-purple-400">{item.count.toLocaleString()}</span>
                                            </div>
                                        </div>
                                        <ProgressBar value={item.count} max={stats.total_products} color="bg-purple-500" />
                                    </div>
                                );
                            })}
                            {stats.classification_distribution.length === 0 && <div className="px-5 py-8 text-center text-sm text-gray-400 dark:text-gray-500">No classification data</div>}
                        </div>
                    </div>
                </div>
            )}

            {/* Product Status */}
            {stats && stats.status_distribution.length > 0 && (
                <div className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
                    <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
                        <h3 className="text-base font-semibold text-gray-900 dark:text-white">Product Status</h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">Active vs inactive product records</p>
                    </div>
                    <div className="grid grid-cols-2 gap-4 p-5 sm:grid-cols-3 lg:grid-cols-4">
                        {stats.status_distribution.map((s) => (
                            <div key={s.name} className="rounded-xl border border-gray-100 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-800">
                                <p className="text-2xl font-bold text-gray-900 dark:text-white">{s.count.toLocaleString()}</p>
                                <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{s.name}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* ═══ SECTION 2: Scientometric / Predictive Dashboard ═══════════ */}
            <SectionDivider label="OpenAlex — Predictive Enrichment Dashboard" />

            {/* Hero Banner */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-violet-600 via-purple-600 to-fuchsia-600 p-6 text-white shadow-lg">
                {/* Decorative circles */}
                <div className="pointer-events-none absolute -right-8 -top-8 h-40 w-40 rounded-full bg-white/10" />
                <div className="pointer-events-none absolute -bottom-12 right-16 h-56 w-56 rounded-full bg-white/5" />
                <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <div className="mb-1 flex items-center gap-2">
                            <span className="inline-flex items-center gap-1 rounded-full bg-white/20 px-2 py-0.5 text-xs font-semibold uppercase tracking-wider">
                                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-300" />
                                Phase 1 — OpenAlex Active
                            </span>
                        </div>
                        <h2 className="text-xl font-bold">Cienciometric Enrichment Engine</h2>
                        <p className="mt-1 max-w-lg text-sm text-white/80">
                            Automatically enrich product records with bibliometric metadata from OpenAlex — citations, concepts, DOIs and open-access status.
                        </p>
                    </div>
                    {/* Bulk Enrich CTA */}
                    <div className="flex flex-col items-start gap-2 sm:items-end">
                        <button
                            id="bulk-enrich-btn"
                            onClick={handleBulkEnrich}
                            disabled={bulkQueuing}
                            className="inline-flex items-center gap-2 rounded-xl bg-white px-5 py-2.5 text-sm font-semibold text-violet-700 shadow transition-all hover:bg-violet-50 disabled:opacity-60"
                        >
                            {bulkQueuing ? (
                                <>
                                    <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                    </svg>
                                    Queuing…
                                </>
                            ) : (
                                <>
                                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                    </svg>
                                    Queue Bulk Enrichment
                                </>
                            )}
                        </button>
                        {bulkResult && (
                            <span className="rounded-full bg-white/20 px-3 py-1 text-xs font-medium">
                                ✓ {bulkResult.queued_records.toLocaleString()} records queued
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
                            { label: "Enriched Records", value: enrichStats.enriched_count, color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-500/10" },
                            { label: "Avg. Citations", value: enrichStats.citations.average, color: "text-violet-600 dark:text-violet-400", bg: "bg-violet-50 dark:bg-violet-500/10" },
                            { label: "Max Citations", value: enrichStats.citations.max.toLocaleString(), color: "text-fuchsia-600 dark:text-fuchsia-400", bg: "bg-fuchsia-50 dark:bg-fuchsia-500/10" },
                            { label: "Total Citations", value: enrichStats.citations.total.toLocaleString(), color: "text-blue-600 dark:text-blue-400", bg: "bg-blue-50 dark:bg-blue-500/10" },
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
                        <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-900 xl:col-span-1">
                            <h3 className="mb-1 text-base font-semibold text-gray-900 dark:text-white">Enrichment Coverage</h3>
                            <p className="mb-5 text-xs text-gray-500 dark:text-gray-400">Percentage of records enriched via OpenAlex</p>
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
                                    max={enrichStats.total_products}
                                    color="bg-gradient-to-r from-violet-500 to-fuchsia-500"
                                />
                            </div>
                        </div>

                        {/* Citation Distribution */}
                        <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-900 xl:col-span-2">
                            <h3 className="mb-1 text-base font-semibold text-gray-900 dark:text-white">Citation Distribution</h3>
                            <p className="mb-6 text-xs text-gray-500 dark:text-gray-400">
                                How citations are distributed across enriched records
                            </p>
                            {Object.values(ciDistrib).every((v) => v === 0) ? (
                                <div className="flex h-24 items-center justify-center text-sm text-gray-400 dark:text-gray-500">
                                    No citation data yet. Run enrichment to populate.
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
                    <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-900">
                        <div className="mb-4 flex items-start justify-between">
                            <div>
                                <h3 className="text-base font-semibold text-gray-900 dark:text-white">Knowledge Concept Map</h3>
                                <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                                    Top concepts extracted by OpenAlex NLP — size indicates frequency across enriched records
                                </p>
                            </div>
                            <span className="shrink-0 rounded-full bg-violet-100 px-2.5 py-1 text-xs font-semibold text-violet-700 dark:bg-violet-500/10 dark:text-violet-400">
                                {enrichStats.top_concepts.length} concepts
                            </span>
                        </div>
                        <ConceptCloud concepts={enrichStats.top_concepts} />
                    </div>

                    {/* Phase Roadmap */}
                    <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-900">
                        <h3 className="mb-1 text-base font-semibold text-gray-900 dark:text-white">Enrichment Source Roadmap</h3>
                        <p className="mb-5 text-xs text-gray-500 dark:text-gray-400">
                            Three-phase strategy for integrating scientometric data sources
                        </p>
                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                            {[
                                {
                                    phase: "Phase 1",
                                    label: "Open Sources",
                                    status: "active",
                                    badge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
                                    dot: "bg-emerald-500",
                                    sources: ["OpenAlex API", "PubMed (NCBI)", "ORCID", "Unpaywall"],
                                    desc: "Free APIs with no rate-limit paywall. Currently processing.",
                                },
                                {
                                    phase: "Phase 2",
                                    label: "Restricted Scraping",
                                    status: "active",
                                    badge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
                                    dot: "bg-emerald-500",
                                    sources: ["Google Scholar (Scholarly)", "Altmetric.com"],
                                    desc: "Scholarly adapter configured with rotating free proxies avoiding IP bans.",
                                },
                                {
                                    phase: "Phase 3",
                                    label: "Premium APIs (BYOK)",
                                    status: "active",
                                    badge: "bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400",
                                    dot: "bg-blue-500",
                                    sources: ["Web of Science (Clarivate)", "Scopus (Elsevier)"],
                                    desc: "Integrated BYOK architecture. Activate by exporting WOS_API_KEY.",
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
                                            {phase.status === "active" ? "Active" : phase.status === "planned" ? "Planned" : "Future"}
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
                    <svg className="h-6 w-6 animate-spin text-violet-500" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                </div>
            )}
        </div>
    );
}
