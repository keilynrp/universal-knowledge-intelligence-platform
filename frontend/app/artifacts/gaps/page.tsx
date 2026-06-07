"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { useDomain } from "../../contexts/DomainContext";
import { EntityConcept, PageHeader } from "../../components/ui";

// ── Types ──────────────────────────────────────────────────────────────────────

interface GapItem {
  category: "enrichment" | "authority" | "concepts" | "dimensions";
  severity: "critical" | "warning" | "ok";
  title: string;
  description: string;
  affected_count: number;
  total_count: number;
  pct: number;
  action: string;
}

interface GapReport {
  domain_id: string;
  generated_at: string;
  summary: { critical: number; warning: number; ok: number; total_entities: number };
  gaps: GapItem[];
}

// ── Category config ────────────────────────────────────────────────────────────

const CATEGORY_ICONS: Record<string, string> = {
  enrichment: "🔬",
  authority:  "🏛️",
  concepts:   "💡",
  dimensions: "📊",
};

const SEVERITY_STYLES: Record<string, { border: string; bg: string; badge: string; text: string }> = {
  critical: {
    border: "border-l-4 border-red-500",
    bg: "bg-red-50 dark:bg-red-900/10",
    badge: "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400",
    text: "text-red-700 dark:text-red-400",
  },
  warning: {
    border: "border-l-4 border-amber-500",
    bg: "bg-amber-50 dark:bg-amber-900/10",
    badge: "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400",
    text: "text-amber-700 dark:text-amber-400",
  },
  ok: {
    border: "border-l-4 border-green-500",
    bg: "bg-green-50 dark:bg-green-900/10",
    badge: "bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400",
    text: "text-green-700 dark:text-green-400",
  },
};

// ── Page ───────────────────────────────────────────────────────────────────────

export default function GapDetectorPage() {
  const { activeDomainId } = useDomain();
  const [report, setReport] = useState<GapReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchGaps = useCallback(async () => {
    if (!activeDomainId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/artifacts/gaps/${activeDomainId}`);
      if (!res.ok) {
        const msg = await res.text();
        setError(`Failed to load gap report: ${msg}`);
        return;
      }
      setReport(await res.json());
    } catch {
      setError("Network error loading gap report");
    } finally {
      setLoading(false);
    }
  }, [activeDomainId]);

  useEffect(() => { fetchGaps(); }, [fetchGaps]);

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumbs={[
          { label: "Home", href: "/" },
          { label: "Artifact Studio", href: "/artifacts" },
          { label: "Gap Detector" },
        ]}
        title="Knowledge Gap Detector"
        description="Identify and prioritize data quality issues in your domain"
        actions={
          <button
            onClick={fetchGaps}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800"
          >
            {loading ? (
              <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
            )}
            Refresh
          </button>
        }
      />

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && !report && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
          ))}
        </div>
      )}

      {report && (
        <>
          {/* Summary chips */}
          <div className="flex flex-wrap gap-3">
            <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-2 dark:border-red-800 dark:bg-red-900/10">
              <span className="text-lg font-bold text-red-600 dark:text-red-400">{report.summary.critical}</span>
              <span className="text-sm text-red-700 dark:text-red-400">Critical</span>
            </div>
            <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 dark:border-amber-800 dark:bg-amber-900/10">
              <span className="text-lg font-bold text-amber-600 dark:text-amber-400">{report.summary.warning}</span>
              <span className="text-sm text-amber-700 dark:text-amber-400">Warnings</span>
            </div>
            <div className="flex items-center gap-2 rounded-xl border border-green-200 bg-green-50 px-4 py-2 dark:border-green-800 dark:bg-green-900/10">
              <span className="text-lg font-bold text-green-600 dark:text-green-400">{report.summary.ok}</span>
              <span className="text-sm text-green-700 dark:text-green-400">OK</span>
            </div>
            <div className="ml-auto flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2 dark:border-gray-700 dark:bg-gray-900">
              <span className="text-sm text-gray-500 dark:text-gray-400">
                <EntityConcept>Total entities</EntityConcept>:
              </span>
              <span className="text-sm font-semibold text-gray-900 dark:text-white">{report.summary.total_entities.toLocaleString()}</span>
            </div>
          </div>

          {/* Gap cards */}
          {report.gaps.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-green-200 bg-green-50 py-16 dark:border-green-800 dark:bg-green-900/10">
              <span className="text-4xl">✅</span>
              <p className="mt-3 text-lg font-medium text-green-700 dark:text-green-400">No gaps detected</p>
              <p className="mt-1 text-sm text-green-600 dark:text-green-500">Your data looks great for domain &quot;{report.domain_id}&quot;</p>
            </div>
          ) : (
            <div className="space-y-3">
              {report.gaps.map((gap, idx) => {
                const style = SEVERITY_STYLES[gap.severity];
                const barPct = Math.min(100, gap.pct);
                return (
                  <div key={idx} className={`rounded-xl border border-gray-100 ${style.border} ${style.bg} p-5 dark:border-gray-800`}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-start gap-3 min-w-0">
                        <span className="text-2xl shrink-0">{CATEGORY_ICONS[gap.category] ?? "⚠️"}</span>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{gap.title}</h3>
                            <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium capitalize ${style.badge}`}>
                              {gap.severity}
                            </span>
                          </div>
                          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{gap.description}</p>
                        </div>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className={`text-2xl font-bold ${style.text}`}>{gap.pct.toFixed(1)}%</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {gap.affected_count.toLocaleString()} / {gap.total_count.toLocaleString()}
                        </p>
                      </div>
                    </div>
                    {/* Progress bar */}
                    <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                      <div
                        className={`h-full rounded-full ${gap.severity === "critical" ? "bg-red-500" : gap.severity === "warning" ? "bg-amber-500" : "bg-green-500"}`}
                        style={{ width: `${barPct}%` }}
                      />
                    </div>
                    {/* Action */}
                    <div className="mt-3 flex items-start gap-2">
                      <svg className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                      </svg>
                      <p className="text-xs text-indigo-700 dark:text-indigo-400">{gap.action}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <p className="text-xs text-gray-400 dark:text-gray-600 text-right">
            Generated {new Date(report.generated_at).toLocaleString()}
          </p>
        </>
      )}
    </div>
  );
}
