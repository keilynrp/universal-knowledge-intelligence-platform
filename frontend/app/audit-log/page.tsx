"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { ErrorBanner, useToast } from "../components/ui";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

// ── Types ──────────────────────────────────────────────────────────────────────

interface AuditEntry {
  id:            number;
  username:      string | null;
  action:        string;
  resource_type: string | null;
  resource_id:   string | null;
  endpoint:      string | null;
  method:        string | null;
  status_code:   number | null;
  ip_address:    string | null;
  created_at:    string | null;
}

interface AuditPage {
  total: number;
  skip:  number;
  limit: number;
  items: AuditEntry[];
}

interface AuditStats {
  total:       number;
  by_action:   Record<string, number>;
  by_resource: Record<string, number>;
  top_users:   { username: string; count: number }[];
  last_7_days: { date: string; count: number }[];
}

// ── Constants ──────────────────────────────────────────────────────────────────

const ACTION_OPTIONS = ["", "CREATE", "UPDATE", "DELETE"];
const PAGE_SIZE      = 50;

const ACTION_STYLES: Record<string, string> = {
  CREATE: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  UPDATE: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  DELETE: "bg-red-100  text-red-700  dark:bg-red-900/30  dark:text-red-400",
};

const ACTION_DOT: Record<string, string> = {
  CREATE: "bg-green-500",
  UPDATE: "bg-amber-500",
  DELETE: "bg-red-500",
};

const STATUS_COLOR = (code: number | null) => {
  if (!code) return "text-gray-400";
  if (code < 300) return "text-green-600 dark:text-green-400";
  if (code < 400) return "text-blue-600 dark:text-blue-400";
  if (code < 500) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
};

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    year: "2-digit", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    hour12: false,
  });
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function AuditLogPage() {
  const { toast } = useToast();
  // ── Filter state
  const [filterAction,   setFilterAction]   = useState("");
  const [filterResource, setFilterResource] = useState("");
  const [filterUser,     setFilterUser]     = useState("");
  const [filterFrom,     setFilterFrom]     = useState("");
  const [filterTo,       setFilterTo]       = useState("");

  // Applied filters (only update on Apply)
  const [applied, setApplied] = useState({
    action: "", resource: "", user: "", from: "", to: "",
  });

  // ── Data state
  const [page,  setPage]  = useState<AuditPage | null>(null);
  const [stats, setStats] = useState<AuditStats | null>(null);
  const [skip,  setSkip]  = useState(0);
  const [loading,      setLoading]      = useState(false);
  const [loadingStats, setLoadingStats] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Fetch helpers

  const fetchStats = useCallback(async () => {
    setLoadingStats(true);
    try {
      const res = await apiFetch("/audit-log/stats");
      if (res.ok) setStats(await res.json());
    } catch {
      // stats are informational — don't block the page
    } finally {
      setLoadingStats(false);
    }
  }, []);

  const fetchPage = useCallback(async (currentSkip: number, filters: typeof applied) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("skip",  String(currentSkip));
      params.set("limit", String(PAGE_SIZE));
      if (filters.action)   params.set("action",        filters.action);
      if (filters.resource) params.set("resource_type", filters.resource);
      if (filters.user)     params.set("username",      filters.user);
      if (filters.from)     params.set("from_date",     filters.from);
      if (filters.to)       params.set("to_date",       filters.to);
      const res = await apiFetch(`/audit-log?${params}`);
      if (!res.ok) { setError(await res.text()); return; }
      setPage(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load audit log");
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Effects

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    fetchPage(skip, applied);
  }, [skip, applied, fetchPage]);

  // ── Handlers

  function handleApply() {
    setSkip(0);
    setApplied({ action: filterAction, resource: filterResource, user: filterUser, from: filterFrom, to: filterTo });
  }

  function handleReset() {
    setFilterAction(""); setFilterResource(""); setFilterUser("");
    setFilterFrom(""); setFilterTo("");
    setSkip(0);
    setApplied({ action: "", resource: "", user: "", from: "", to: "" });
  }

  async function handleExport() {
    const params = new URLSearchParams();
    if (applied.action)   params.set("action",        applied.action);
    if (applied.resource) params.set("resource_type", applied.resource);
    if (applied.user)     params.set("username",      applied.user);
    if (applied.from)     params.set("from_date",     applied.from);
    if (applied.to)       params.set("to_date",       applied.to);
    const qs = params.toString();
    try {
      const res = await apiFetch(`/audit-log/export${qs ? "?" + qs : ""}`);
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ukip_audit_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast("Export failed", "error");
    }
  }

  // ── Pagination
  const totalPages = page ? Math.ceil(page.total / PAGE_SIZE) : 0;
  const currentPage = Math.floor(skip / PAGE_SIZE) + 1;

  // ── Render

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">

      {/* ── Stats bar ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-5">
        <StatCard
          label="Total events"
          value={loadingStats ? "…" : String(stats?.total ?? 0)}
          color="blue"
        />
        <StatCard
          label="Creates"
          value={loadingStats ? "…" : String(stats?.by_action?.CREATE ?? 0)}
          color="green"
        />
        <StatCard
          label="Updates"
          value={loadingStats ? "…" : String(stats?.by_action?.UPDATE ?? 0)}
          color="amber"
        />
        <StatCard
          label="Deletes"
          value={loadingStats ? "…" : String(stats?.by_action?.DELETE ?? 0)}
          color="red"
        />
        <StatCard
          label="Active users"
          value={loadingStats ? "…" : String(stats?.top_users?.length ?? 0)}
          color="purple"
        />
      </div>

      {/* ── 7-day sparkline + top users ───────────────────────────────────── */}
      {stats && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* Bar chart */}
          <div className="lg:col-span-2 rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
            <p className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
              Activity — last 7 days
            </p>
            {stats.last_7_days.length === 0 ? (
              <p className="text-sm text-gray-400">No activity data yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height={120}>
                <BarChart data={stats.last_7_days} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{ fontSize: 12, borderRadius: 6 }}
                    formatter={(v) => [Number(v) || 0, "Events"]}
                  />
                  <Bar dataKey="count" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Top users */}
          <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
            <p className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">Top users</p>
            {stats.top_users.length === 0 ? (
              <p className="text-sm text-gray-400">No user data yet.</p>
            ) : (
              <ul className="space-y-2">
                {stats.top_users.slice(0, 8).map((u) => (
                  <li key={u.username} className="flex items-center justify-between text-sm">
                    <span className="truncate font-medium text-gray-700 dark:text-gray-300">
                      {u.username}
                    </span>
                    <span className="ml-2 shrink-0 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                      {u.count}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {/* ── Filter bar ────────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
        <div className="flex flex-wrap items-end gap-3">
          {/* Action */}
          <div className="min-w-[130px]">
            <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">Action</label>
            <select
              value={filterAction}
              onChange={(e) => setFilterAction(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
            >
              {ACTION_OPTIONS.map((a) => (
                <option key={a} value={a}>{a || "All actions"}</option>
              ))}
            </select>
          </div>

          {/* Resource type */}
          <div className="min-w-[150px]">
            <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">Resource type</label>
            <input
              value={filterResource}
              onChange={(e) => setFilterResource(e.target.value)}
              placeholder="entity, rule, …"
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
            />
          </div>

          {/* Username */}
          <div className="min-w-[140px]">
            <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">Username</label>
            <input
              value={filterUser}
              onChange={(e) => setFilterUser(e.target.value)}
              placeholder="testadmin"
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
            />
          </div>

          {/* From date */}
          <div className="min-w-[160px]">
            <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">From</label>
            <input
              type="datetime-local"
              value={filterFrom}
              onChange={(e) => setFilterFrom(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
            />
          </div>

          {/* To date */}
          <div className="min-w-[160px]">
            <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">To</label>
            <input
              type="datetime-local"
              value={filterTo}
              onChange={(e) => setFilterTo(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
            />
          </div>

          {/* Buttons */}
          <div className="flex gap-2">
            <button
              onClick={handleApply}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Apply
            </button>
            <button
              onClick={handleReset}
              className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
            >
              Reset
            </button>
          </div>

          {/* Spacer + Export */}
          <div className="ml-auto">
            <button
              onClick={handleExport}
              className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              Export CSV
            </button>
          </div>
        </div>
      </div>

      {/* ── Timeline ──────────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900">
        {/* Header row */}
        <div className="grid grid-cols-[auto_1fr_auto] items-center gap-4 border-b border-gray-200 px-4 py-3 dark:border-gray-700">
          <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Audit Timeline
          </p>
          <span />
          {page && (
            <p className="text-xs text-gray-400">
              {page.total.toLocaleString()} total event{page.total !== 1 ? "s" : ""}
            </p>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="p-4">
            <ErrorBanner message={error} variant="inline" />
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="divide-y divide-gray-100 dark:divide-gray-800">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-start gap-4 px-4 py-3 animate-pulse">
                <div className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-gray-200 dark:bg-gray-700" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-3 w-1/3 rounded bg-gray-200 dark:bg-gray-700" />
                  <div className="h-3 w-2/3 rounded bg-gray-100 dark:bg-gray-800" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Entries */}
        {!loading && page && (
          <>
            {page.items.length === 0 ? (
              <div className="px-4 py-12 text-center">
                <svg className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                <p className="text-sm text-gray-500 dark:text-gray-400">No audit events match the current filters.</p>
              </div>
            ) : (
              <ul className="divide-y divide-gray-100 dark:divide-gray-800">
                {page.items.map((entry) => (
                  <li key={entry.id} className="flex items-start gap-4 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                    {/* Dot */}
                    <div className="mt-1.5 flex shrink-0 flex-col items-center">
                      <span className={`h-2.5 w-2.5 rounded-full ${ACTION_DOT[entry.action] ?? "bg-gray-400"}`} />
                    </div>

                    {/* Content */}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        {/* Action badge */}
                        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${ACTION_STYLES[entry.action] ?? "bg-gray-100 text-gray-600"}`}>
                          {entry.action}
                        </span>
                        {/* Resource */}
                        {entry.resource_type && (
                          <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                            {entry.resource_type}
                            {entry.resource_id && (
                              <span className="ml-1 text-gray-400">#{entry.resource_id}</span>
                            )}
                          </span>
                        )}
                        {/* Endpoint */}
                        {entry.endpoint && (
                          <code className="truncate rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-400 max-w-[260px]">
                            {entry.method} {entry.endpoint}
                          </code>
                        )}
                        {/* Status */}
                        {entry.status_code && (
                          <span className={`text-xs font-mono font-semibold ${STATUS_COLOR(entry.status_code)}`}>
                            {entry.status_code}
                          </span>
                        )}
                      </div>
                      {/* Secondary row */}
                      <div className="mt-0.5 flex flex-wrap items-center gap-3 text-xs text-gray-400 dark:text-gray-500">
                        {entry.username && (
                          <span className="flex items-center gap-1">
                            <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                            </svg>
                            {entry.username}
                          </span>
                        )}
                        {entry.ip_address && (
                          <span>{entry.ip_address}</span>
                        )}
                      </div>
                    </div>

                    {/* Timestamp */}
                    <div className="shrink-0 text-right">
                      <span className="text-xs text-gray-400 dark:text-gray-500 tabular-nums">
                        {fmtDate(entry.created_at)}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {/* Pagination */}
            {page.total > PAGE_SIZE && (
              <div className="flex items-center justify-between border-t border-gray-200 px-4 py-3 dark:border-gray-700">
                <button
                  onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
                  disabled={skip === 0}
                  className="flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                  Prev
                </button>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setSkip(skip + PAGE_SIZE)}
                  disabled={skip + PAGE_SIZE >= page.total}
                  className="flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                  Next
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

const COLOR_MAP: Record<string, string> = {
  blue:   "bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400",
  green:  "bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400",
  amber:  "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400",
  red:    "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400",
  purple: "bg-purple-50 text-purple-700 dark:bg-purple-900/20 dark:text-purple-400",
};

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className={`rounded-xl p-4 ${COLOR_MAP[color] ?? COLOR_MAP.blue}`}>
      <p className="text-xs font-medium opacity-70">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums">{value}</p>
    </div>
  );
}
