"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SourceHealthEntry {
  source: string;
  state: "CLOSED" | "OPEN" | "HALF_OPEN";
  failure_count: number;
  success_count: number;
  last_failure: number | null;
  last_used: number | null;
}

interface SourceHealthResponse {
  sources: SourceHealthEntry[];
}

interface SourceStatsEntry {
  enrichment_source: string | null;
  total: number;
  enriched: number;
  failed: number;
  failure_reasons: Record<string, number>;
}

interface SourceStatsResponse {
  domain_id: string | null;
  entries: SourceStatsEntry[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  CLOSED:    { bg: "bg-green-100",  text: "text-green-800",  label: "Healthy" },
  HALF_OPEN: { bg: "bg-amber-100",  text: "text-amber-800",  label: "Probing" },
  OPEN:      { bg: "bg-red-100",    text: "text-red-800",    label: "Open" },
};

const REASON_STYLES: Record<string, string> = {
  no_match:          "bg-gray-100 text-gray-700",
  circuit_open:      "bg-red-100 text-red-700",
  api_error:         "bg-orange-100 text-orange-700",
  rate_limited:      "bg-amber-100 text-amber-700",
  timeout:           "bg-yellow-100 text-yellow-700",
  all_sources_failed:"bg-red-100 text-red-800",
  unknown:           "bg-gray-100 text-gray-500",
};

function fmtEpoch(ts: number | null): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString();
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StateBadge({ state }: { state: string }) {
  const s = STATE_STYLES[state] ?? { bg: "bg-gray-100", text: "text-gray-700", label: state };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${s.bg} ${s.text}`}>
      {s.label}
    </span>
  );
}

function ReasonPill({ reason, count }: { reason: string; count: number }) {
  const cls = REASON_STYLES[reason] ?? REASON_STYLES.unknown;
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs ${cls}`}>
      {reason}
      <span className="font-bold">{count}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function EnrichmentSourceHealthCard() {
  const [health, setHealth] = useState<SourceHealthResponse | null>(null);
  const [stats, setStats] = useState<SourceStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [h, s] = await Promise.all([
        apiFetch("/enrichment/sources/health").then((r) => r.json()),
        apiFetch("/enrichment/sources/stats").then((r) => r.json()),
      ]);
      setHealth(h as SourceHealthResponse);
      setStats(s as SourceStatsResponse);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load source health");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 30_000);
    return () => clearInterval(id);
  }, []);

  // Build a map from source → stats entry for easy lookup
  const statsMap: Record<string, SourceStatsEntry> = {};
  if (stats) {
    for (const entry of stats.entries) {
      if (entry.enrichment_source) {
        statsMap[entry.enrichment_source] = entry;
      }
    }
  }

  const openCount = health?.sources.filter((s) => s.state === "OPEN").length ?? 0;
  const halfOpenCount = health?.sources.filter((s) => s.state === "HALF_OPEN").length ?? 0;
  const allHealthy = openCount === 0 && halfOpenCount === 0;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-lg">🔌</span>
          <h2 className="text-base font-semibold text-gray-800">Enrichment Source Health</h2>
          {!loading && (
            <span
              className={`ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                allHealthy
                  ? "bg-green-50 text-green-700"
                  : openCount > 0
                  ? "bg-red-50 text-red-700"
                  : "bg-amber-50 text-amber-700"
              }`}
            >
              {allHealthy
                ? "All healthy"
                : openCount > 0
                ? `${openCount} circuit${openCount > 1 ? "s" : ""} open`
                : `${halfOpenCount} probing`}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchData}
            disabled={loading}
            className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded border border-gray-200 hover:border-gray-300 transition-colors"
          >
            {loading ? "..." : "↻ Refresh"}
          </button>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded border border-gray-200 hover:border-gray-300 transition-colors"
          >
            {expanded ? "Collapse" : "Details"}
          </button>
        </div>
      </div>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 rounded p-3 mb-3">{error}</div>
      )}

      {loading && !health && (
        <div className="flex justify-center py-8">
          <div className="animate-spin h-6 w-6 rounded-full border-2 border-blue-500 border-t-transparent" />
        </div>
      )}

      {health && (
        <>
          {/* Compact grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
            {health.sources.map((src) => (
              <div
                key={src.source}
                className="flex flex-col gap-1 p-2 rounded-lg border border-gray-100 bg-gray-50"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-700 capitalize">{src.source}</span>
                  <StateBadge state={src.state} />
                </div>
                <div className="flex gap-2 text-xs text-gray-500">
                  <span>✓ {src.success_count}</span>
                  <span>✗ {src.failure_count}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Expanded details */}
          {expanded && (
            <div className="border-t border-gray-100 pt-4">
              <h3 className="text-sm font-medium text-gray-700 mb-3">Source Detail</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-gray-500 border-b border-gray-100">
                      <th className="text-left py-1.5 pr-3 font-medium">Source</th>
                      <th className="text-left py-1.5 pr-3 font-medium">State</th>
                      <th className="text-right py-1.5 pr-3 font-medium">Successes</th>
                      <th className="text-right py-1.5 pr-3 font-medium">Failures</th>
                      <th className="text-right py-1.5 pr-3 font-medium">Total</th>
                      <th className="text-right py-1.5 pr-3 font-medium">Enriched</th>
                      <th className="text-left py-1.5 font-medium">Failure Reasons</th>
                    </tr>
                  </thead>
                  <tbody>
                    {health.sources.map((src) => {
                      const st = statsMap[src.source];
                      return (
                        <tr
                          key={src.source}
                          className="border-b border-gray-50 hover:bg-gray-50"
                        >
                          <td className="py-2 pr-3 font-medium text-gray-700 capitalize">
                            {src.source}
                          </td>
                          <td className="py-2 pr-3">
                            <StateBadge state={src.state} />
                          </td>
                          <td className="py-2 pr-3 text-right text-green-700 font-medium">
                            {src.success_count}
                          </td>
                          <td className="py-2 pr-3 text-right text-red-600 font-medium">
                            {src.failure_count}
                          </td>
                          <td className="py-2 pr-3 text-right text-gray-600">
                            {st ? st.total : "—"}
                          </td>
                          <td className="py-2 pr-3 text-right text-gray-600">
                            {st ? (
                              <>
                                {st.enriched}
                                {st.total > 0 && (
                                  <span className="text-gray-400 ml-1">
                                    ({Math.round((st.enriched / st.total) * 100)}%)
                                  </span>
                                )}
                              </>
                            ) : (
                              "—"
                            )}
                          </td>
                          <td className="py-2">
                            {st && Object.keys(st.failure_reasons).length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {Object.entries(st.failure_reasons).map(([reason, cnt]) => (
                                  <ReasonPill key={reason} reason={reason} count={cnt} />
                                ))}
                              </div>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Failure stats section */}
              {stats && stats.entries.some((e) => e.failed > 0) && (
                <div className="mt-4">
                  <h3 className="text-sm font-medium text-gray-700 mb-3">Failure Reason Breakdown</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {stats.entries
                      .filter((e) => e.failed > 0 && e.enrichment_source)
                      .map((e) => (
                        <div
                          key={e.enrichment_source}
                          className="p-3 rounded-lg border border-gray-100 bg-gray-50"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-semibold text-gray-700 capitalize">
                              {e.enrichment_source}
                            </span>
                            <span className="text-xs text-red-600 font-medium">
                              {e.failed} failed / {e.total} total
                            </span>
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {Object.entries(e.failure_reasons).map(([reason, cnt]) => (
                              <ReasonPill key={reason} reason={reason} count={cnt} />
                            ))}
                          </div>
                          {/* Mini bar chart */}
                          <div className="mt-2 space-y-1">
                            {Object.entries(e.failure_reasons)
                              .sort(([, a], [, b]) => b - a)
                              .map(([reason, cnt]) => {
                                const pct = e.failed > 0 ? Math.round((cnt / e.failed) * 100) : 0;
                                const barCls = REASON_STYLES[reason]?.split(" ")[0] ?? "bg-gray-200";
                                return (
                                  <div key={reason} className="flex items-center gap-2">
                                    <span className="w-24 text-xs text-gray-500 truncate">{reason}</span>
                                    <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                                      <div
                                        className={`${barCls} h-1.5 rounded-full`}
                                        style={{ width: `${pct}%` }}
                                      />
                                    </div>
                                    <span className="text-xs text-gray-500 w-8 text-right">{pct}%</span>
                                  </div>
                                );
                              })}
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
