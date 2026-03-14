"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useDomain } from "../../contexts/DomainContext";
import { apiFetch } from "@/lib/api";
import { Analytics } from "@/lib/analytics";

const PAGE_SIZE = 50;

// ─── Types ────────────────────────────────────────────────────────────────────

interface Dimension {
  name: string;
  label: string;
  type: string;
  distinct_count: number;
}

interface CubeRow {
  values: Record<string, string>;
  count: number;
  pct: number;
}

interface CubeResult {
  domain_id: string;
  group_by: string[];
  filters: Record<string, string>;
  total: number;
  rows: CubeRow[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  string:  "text-blue-600 dark:text-blue-400",
  integer: "text-purple-600 dark:text-purple-400",
  float:   "text-amber-600 dark:text-amber-400",
  boolean: "text-green-600 dark:text-green-400",
  array:   "text-rose-600 dark:text-rose-400",
};

function PctBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 rounded-full bg-gray-100 dark:bg-gray-800 flex-shrink-0">
        <div
          className="h-2 rounded-full bg-blue-500 dark:bg-blue-400 transition-all duration-500"
          style={{ width: `${Math.min(value, 100)}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-gray-500 dark:text-gray-400 w-10 text-right">
        {value.toFixed(1)}%
      </span>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function OLAPExplorerPage() {
  const { activeDomain, activeDomainId } = useDomain();

  const [dimensions, setDimensions] = useState<Dimension[]>([]);
  const [loadingDims, setLoadingDims] = useState(true);

  const [primaryDim, setPrimaryDim] = useState<string>("");
  const [secondaryDim, setSecondaryDim] = useState<string>("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [filterInput, setFilterInput] = useState({ field: "", value: "" });

  const [result, setResult] = useState<CubeResult | null>(null);
  const [querying, setQuerying] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  // Load dimensions when domain changes
  useEffect(() => {
    if (!activeDomainId) return;
    setLoadingDims(true);
    setDimensions([]);
    setPrimaryDim("");
    setSecondaryDim("");
    setResult(null);
    setFilters({});
    setVisibleCount(PAGE_SIZE);

    apiFetch(`/cube/dimensions/${activeDomainId}`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((data: Dimension[]) => { setDimensions(data); if (data.length > 0) setPrimaryDim(data[0].name); })
      .catch(() => setError("Failed to load dimensions"))
      .finally(() => setLoadingDims(false));
  }, [activeDomainId]);

  const runQuery = useCallback(async () => {
    if (!primaryDim) return;
    setQuerying(true);
    setError(null);
    setVisibleCount(PAGE_SIZE);
    const group_by = secondaryDim && secondaryDim !== primaryDim
      ? [primaryDim, secondaryDim]
      : [primaryDim];

    try {
      const res = await apiFetch("/cube/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain_id: activeDomainId, group_by, filters }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Query failed" }));
        setError(err.detail ?? "Query failed");
      } else {
        const data: CubeResult = await res.json();
        setResult(data);
        Analytics.olapQuery(activeDomainId, group_by.length);
      }
    } catch {
      setError("Network error");
    } finally {
      setQuerying(false);
    }
  }, [primaryDim, secondaryDim, filters, activeDomainId]);

  const handleExport = async () => {
    if (!primaryDim) return;
    setExporting(true);
    try {
      const res = await apiFetch(`/cube/export/${activeDomainId}?dimension=${primaryDim}`);
      if (!res.ok) { setError("Export failed"); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `cube_${activeDomainId}_${primaryDim}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Export error");
    } finally {
      setExporting(false);
    }
  };

  const addFilter = () => {
    if (!filterInput.field || !filterInput.value) return;
    setFilters(f => ({ ...f, [filterInput.field]: filterInput.value }));
    setFilterInput({ field: "", value: "" });
  };

  const removeFilter = (key: string) => setFilters(f => { const n = { ...f }; delete n[key]; return n; });

  const primaryDimLabel = dimensions.find(d => d.name === primaryDim)?.label ?? primaryDim;
  const secondaryDimLabel = dimensions.find(d => d.name === secondaryDim)?.label ?? secondaryDim;
  const isCrossTab = result && result.group_by.length === 2;

  const visibleRows = result?.rows.slice(0, visibleCount) ?? [];
  const hasMore = result ? visibleCount < result.rows.length : false;

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      {/* Top bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/analytics"
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
            </svg>
            Analytics
          </Link>
          <span className="text-gray-300 dark:text-gray-700">/</span>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">OLAP Cube Explorer</h2>
          {activeDomain && (
            <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
              {activeDomain.name}
            </span>
          )}
        </div>
        <button
          onClick={handleExport}
          disabled={!result || exporting}
          className="flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 disabled:opacity-40 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
          </svg>
          {exporting ? "Exporting…" : "Export Excel"}
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-4 rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
        {/* Primary dimension */}
        <div className="flex flex-col gap-1 min-w-[160px]">
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Primary Dimension</label>
          {loadingDims ? (
            <div className="h-9 w-40 animate-pulse rounded-lg bg-gray-100 dark:bg-gray-800" />
          ) : (
            <select
              value={primaryDim}
              onChange={e => setPrimaryDim(e.target.value)}
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {dimensions.map(d => (
                <option key={d.name} value={d.name}>
                  {d.label} ({d.distinct_count})
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Secondary dimension */}
        <div className="flex flex-col gap-1 min-w-[160px]">
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400">
            Second Dimension <span className="font-normal opacity-60">(optional)</span>
          </label>
          {loadingDims ? (
            <div className="h-9 w-40 animate-pulse rounded-lg bg-gray-100 dark:bg-gray-800" />
          ) : (
            <select
              value={secondaryDim}
              onChange={e => setSecondaryDim(e.target.value)}
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">— none —</option>
              {dimensions.filter(d => d.name !== primaryDim).map(d => (
                <option key={d.name} value={d.name}>
                  {d.label} ({d.distinct_count})
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Filters */}
        <div className="flex flex-col gap-1 min-w-[280px]">
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Add Filter</label>
          <div className="flex gap-2">
            <select
              value={filterInput.field}
              onChange={e => setFilterInput(f => ({ ...f, field: e.target.value }))}
              className="rounded-lg border border-gray-200 bg-white px-2 py-2 text-sm text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Field…</option>
              {dimensions.map(d => <option key={d.name} value={d.name}>{d.label}</option>)}
            </select>
            <input
              value={filterInput.value}
              onChange={e => setFilterInput(f => ({ ...f, value: e.target.value }))}
              onKeyDown={e => { if (e.key === "Enter") addFilter(); }}
              placeholder="Value…"
              className="w-28 rounded-lg border border-gray-200 px-2 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <button
              onClick={addFilter}
              disabled={!filterInput.field || !filterInput.value}
              className="rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700 disabled:opacity-40 transition-colors"
            >
              +
            </button>
          </div>
        </div>

        {/* Run */}
        <button
          onClick={runQuery}
          disabled={!primaryDim || querying}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors self-end"
        >
          {querying ? (
            <><svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/></svg> Running…</>
          ) : (
            <><svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3l14 9-14 9V3z" /></svg> Run Query</>
          )}
        </button>
      </div>

      {/* Active filters */}
      {Object.keys(filters).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(filters).map(([k, v]) => (
            <span key={k} className="flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 dark:bg-blue-900/20 dark:text-blue-400">
              {dimensions.find(d => d.name === k)?.label ?? k} = {v}
              <button onClick={() => removeFilter(k)} className="text-blue-400 hover:text-blue-600 dark:hover:text-blue-200">×</button>
            </span>
          ))}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="flex flex-col gap-3 flex-1 min-h-0">
          {/* Summary */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Showing{" "}
              <span className="font-semibold text-gray-900 dark:text-white">
                {Math.min(visibleCount, result.rows.length)}
              </span>{" "}
              of{" "}
              <span className="font-semibold text-gray-900 dark:text-white">{result.rows.length}</span>{" "}
              groups ·{" "}
              <span className="font-semibold text-gray-900 dark:text-white">{result.total.toLocaleString()}</span> total records
            </p>
            {isCrossTab && (
              <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                Cross-tab: {primaryDimLabel} × {secondaryDimLabel}
              </span>
            )}
          </div>

          {/* Table */}
          <div className="flex-1 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-gray-50 dark:bg-gray-800/80 backdrop-blur-sm">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    {primaryDimLabel}
                  </th>
                  {isCrossTab && (
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                      {secondaryDimLabel}
                    </th>
                  )}
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Count
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Distribution
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Drill-down
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {visibleRows.map((row, i) => (
                  <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors">
                    <td className="px-6 py-3 font-medium text-gray-900 dark:text-white">
                      {row.values[result.group_by[0]] ?? <span className="text-gray-400 italic">null</span>}
                    </td>
                    {isCrossTab && (
                      <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                        {row.values[result.group_by[1]] ?? <span className="text-gray-400 italic">null</span>}
                      </td>
                    )}
                    <td className="px-4 py-3 text-right tabular-nums text-gray-700 dark:text-gray-300">
                      {row.count.toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <PctBar value={row.pct} />
                    </td>
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => {
                          const field = result.group_by[0];
                          const value = row.values[field];
                          if (!value) return;
                          setFilters(f => ({ ...f, [field]: value }));
                          if (secondaryDim) setPrimaryDim(secondaryDim);
                          setSecondaryDim("");
                          setVisibleCount(PAGE_SIZE);
                        }}
                        className="rounded-md bg-gray-100 px-2 py-1 text-xs text-gray-600 hover:bg-blue-100 hover:text-blue-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-blue-900/30 dark:hover:text-blue-400 transition-colors"
                        title={`Drill down into ${row.values[result.group_by[0]]}`}
                      >
                        ↳ Drill
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {result.rows.length === 0 && (
              <div className="py-16 text-center text-gray-400 dark:text-gray-600">
                No data for the selected dimensions and filters.
              </div>
            )}
          </div>

          {/* Load more */}
          {hasMore && (
            <div className="flex items-center justify-center gap-3 py-2">
              <span className="text-xs text-gray-400">
                {result.rows.length - visibleCount} more rows not shown
              </span>
              <button
                onClick={() => setVisibleCount(v => v + PAGE_SIZE)}
                className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-xs font-medium text-gray-600 transition hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400 dark:hover:bg-gray-800"
              >
                Load {Math.min(PAGE_SIZE, result.rows.length - visibleCount)} more
              </button>
              <button
                onClick={() => setVisibleCount(result.rows.length)}
                className="text-xs text-blue-600 hover:underline dark:text-blue-400"
              >
                Show all
              </button>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!result && !querying && (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 text-gray-400 dark:text-gray-600">
          <svg className="w-16 h-16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={0.75} d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605" />
          </svg>
          <div className="text-center">
            <p className="font-medium text-gray-500 dark:text-gray-400">Select dimensions and run a query</p>
            <p className="text-sm mt-1">Group your data by any attribute to explore distributions</p>
          </div>
        </div>
      )}
    </div>
  );
}
