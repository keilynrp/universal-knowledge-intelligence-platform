"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "../contexts/AuthContext";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SchedulerState {
  enabled: boolean;
  interval_seconds: number;
  last_run_at: string | null;
  next_run_at: string | null;
  domains_monitored: number;
  total_queued_last_run: number;
}

interface PolicyData {
  id: number;
  domain_id: string;
  enabled: boolean;
  min_enrichment_pct: number;
  max_budget_per_run: number;
  staleness_threshold_days: number;
}

interface DomainStaleness {
  domain_id: string;
  policy: PolicyData | null;
  current_enrichment_pct: number;
  total_entities: number;
  enriched_entities: number;
  stale_entities: number;
  last_run: { queued_count: number; started_at: string | null; triggered_by: string } | null;
  is_stale: boolean;
}

interface PolicyFormState {
  enabled: boolean;
  min_enrichment_pct: number;
  max_budget_per_run: number;
  staleness_threshold_days: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTs(ts: string | null): string {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function fmtPct(pct: number): string {
  return pct.toFixed(1) + "%";
}

const ADMIN_ROLES = new Set(["admin", "super_admin"]);

// ---------------------------------------------------------------------------
// Policy Edit Modal
// ---------------------------------------------------------------------------

function PolicyModal({
  domain_id,
  initial,
  onClose,
  onSaved,
}: {
  domain_id: string;
  initial: PolicyFormState;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<PolicyFormState>({ ...initial });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validationError = (): string | null => {
    if (form.min_enrichment_pct < 0 || form.min_enrichment_pct > 100)
      return "Min enrichment % must be between 0 and 100";
    if (form.max_budget_per_run < 1 || form.max_budget_per_run > 10000)
      return "Max budget must be between 1 and 10000";
    if (form.staleness_threshold_days < 1 || form.staleness_threshold_days > 3650)
      return "Staleness threshold must be between 1 and 3650 days";
    return null;
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const ve = validationError();
    if (ve) { setError(ve); return; }
    setSaving(true);
    setError(null);
    try {
      await apiFetch(`/enrichment/schedule/${domain_id}/policy`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      onSaved();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save policy");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">
          Edit Policy — <span className="font-mono text-indigo-600">{domain_id}</span>
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Enabled toggle */}
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
              className="h-4 w-4 rounded border-slate-300 accent-indigo-600"
            />
            <span className="text-sm text-slate-700">Scheduler enabled for this domain</span>
          </label>

          {/* min_enrichment_pct */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Min Enrichment % (0–100)
            </label>
            <input
              type="number"
              min={0}
              max={100}
              step={0.1}
              value={form.min_enrichment_pct}
              onChange={(e) => setForm({ ...form, min_enrichment_pct: parseFloat(e.target.value) })}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* max_budget_per_run */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Max Budget per Run (1–10,000)
            </label>
            <input
              type="number"
              min={1}
              max={10000}
              value={form.max_budget_per_run}
              onChange={(e) => setForm({ ...form, max_budget_per_run: parseInt(e.target.value, 10) })}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* staleness_threshold_days */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Staleness Threshold (days, 1–3650)
            </label>
            <input
              type="number"
              min={1}
              max={3650}
              value={form.staleness_threshold_days}
              onChange={(e) =>
                setForm({ ...form, staleness_threshold_days: parseInt(e.target.value, 10) })
              }
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save Policy"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function EnrichmentSchedulerCard() {
  const { user } = useAuth();
  const isAdmin = user ? ADMIN_ROLES.has(user.role) : false;

  const [state, setState] = useState<SchedulerState | null>(null);
  const [domainReports, setDomainReports] = useState<DomainStaleness[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Toast state
  const [toast, setToast] = useState<string | null>(null);

  // Triggering state per domain
  const [triggering, setTriggering] = useState<Record<string, boolean>>({});

  // Edit modal
  const [editDomain, setEditDomain] = useState<string | null>(null);
  const [editInitial, setEditInitial] = useState<PolicyFormState | null>(null);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  }, []);

  const fetchData = useCallback(async () => {
    try {
      setError(null);
      const sched = await apiFetch<SchedulerState>("/enrichment/schedule");
      setState(sched);

      // Fetch per-domain reports from scheduler state — use the monitored policies
      // We get the list of domains from the policy table via the state endpoint
      // and then fetch individual reports. For now, we query them in bulk via domains.
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load scheduler data");
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch domain reports independently
  const fetchDomainReports = useCallback(async () => {
    try {
      // First get list of monitored domains from policy list
      const policies = await apiFetch<{ items: { domain_id: string }[] }>("/enrichment/schedule")
        .then(async () => {
          // Get all domain IDs from the policy endpoint
          // We use the /domains endpoint to get known domains
          const domainsResp = await apiFetch<{ id: string; name: string }[]>("/domains");
          return domainsResp;
        });

      if (!Array.isArray(policies)) return;

      const reports = await Promise.allSettled(
        policies.map((d: { id: string }) =>
          apiFetch<DomainStaleness>(`/enrichment/schedule/${d.id}`)
        )
      );

      const resolved = reports
        .filter((r): r is PromiseFulfilledResult<DomainStaleness> => r.status === "fulfilled")
        .map((r) => r.value);

      setDomainReports(resolved);
    } catch {
      // silently ignore if domains fetch fails — don't override the main error
    }
  }, []);

  useEffect(() => {
    fetchData();
    fetchDomainReports();
  }, [fetchData, fetchDomainReports]);

  const handleTrigger = useCallback(
    async (domain_id: string) => {
      setTriggering((prev) => ({ ...prev, [domain_id]: true }));
      try {
        const result = await apiFetch<{ queued_count: number }>(`/enrichment/schedule/${domain_id}/trigger`, {
          method: "POST",
        });
        showToast(`Queued ${result.queued_count} entities for enrichment in "${domain_id}"`);
        fetchDomainReports();
      } catch (err: unknown) {
        showToast(
          `Failed to trigger: ${err instanceof Error ? err.message : "Unknown error"}`
        );
      } finally {
        setTriggering((prev) => ({ ...prev, [domain_id]: false }));
      }
    },
    [showToast, fetchDomainReports]
  );

  const openEditModal = useCallback((report: DomainStaleness) => {
    setEditInitial({
      enabled: report.policy?.enabled ?? true,
      min_enrichment_pct: report.policy?.min_enrichment_pct ?? 80,
      max_budget_per_run: report.policy?.max_budget_per_run ?? 100,
      staleness_threshold_days: report.policy?.staleness_threshold_days ?? 30,
    });
    setEditDomain(report.domain_id);
  }, []);

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  const badgeClass = (stale: boolean) =>
    stale
      ? "inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700"
      : "inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700";

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 h-5 w-48 animate-pulse rounded bg-slate-200" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-10 animate-pulse rounded bg-slate-100" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6">
        <p className="text-sm text-red-600">Enrichment Scheduler: {error}</p>
      </div>
    );
  }

  const isSchedulerRunning = state?.enabled ?? false;

  return (
    <>
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        {/* ── Header ── */}
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="text-xl">🗓️</span>
            <h2 className="text-base font-semibold text-slate-900">Enrichment Scheduler</h2>
          </div>
          <span
            className={
              isSchedulerRunning
                ? "inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700"
                : "inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-700"
            }
          >
            <span
              className={`h-2 w-2 rounded-full ${isSchedulerRunning ? "bg-emerald-500" : "bg-amber-500"}`}
            />
            {isSchedulerRunning ? "Running" : "Scheduler paused"}
          </span>
        </div>

        {/* ── Global stats row ── */}
        {state && (
          <div className="grid grid-cols-2 gap-4 border-b border-slate-100 px-6 py-4 sm:grid-cols-4">
            <div>
              <p className="text-xs font-medium text-slate-500">Interval</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                {state.interval_seconds}s
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500">Domains Monitored</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                {state.domains_monitored}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500">Last Run</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                {formatTs(state.last_run_at)}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500">Next Run</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                {formatTs(state.next_run_at)}
              </p>
            </div>
          </div>
        )}

        {/* ── Per-domain staleness table ── */}
        {domainReports.length === 0 ? (
          <div className="px-6 py-8 text-center text-sm text-slate-400">
            No domain policies configured yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100">
              <thead>
                <tr className="bg-slate-50">
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">Domain</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">Enrichment</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">Stale Entities</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">Last Run</th>
                  {isAdmin && (
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500">
                      Actions
                    </th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {domainReports.map((report) => (
                  <tr key={report.domain_id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <span className="font-mono text-sm font-medium text-slate-800">
                        {report.domain_id}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-200">
                          <div
                            className="h-full rounded-full bg-indigo-500"
                            style={{ width: `${Math.min(report.current_enrichment_pct, 100)}%` }}
                          />
                        </div>
                        <span className="text-sm text-slate-700">
                          {fmtPct(report.current_enrichment_pct)}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-700">
                      {report.stale_entities.toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <span className={badgeClass(report.is_stale)}>
                        {report.is_stale ? "Stale" : "Healthy"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {report.last_run
                        ? `${formatTs(report.last_run.started_at)} (${report.last_run.queued_count} queued)`
                        : "—"}
                    </td>
                    {isAdmin && (
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleTrigger(report.domain_id)}
                            disabled={triggering[report.domain_id]}
                            className="rounded-lg bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                          >
                            {triggering[report.domain_id] ? (
                              <span className="inline-flex items-center gap-1.5">
                                <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
                                  <circle
                                    className="opacity-25"
                                    cx="12"
                                    cy="12"
                                    r="10"
                                    stroke="currentColor"
                                    strokeWidth="4"
                                  />
                                  <path
                                    className="opacity-75"
                                    fill="currentColor"
                                    d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                                  />
                                </svg>
                                Running…
                              </span>
                            ) : (
                              "Run Now"
                            )}
                          </button>
                          <button
                            onClick={() => openEditModal(report)}
                            className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-200"
                          >
                            Edit Policy
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Toast ── */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 rounded-xl bg-slate-900 px-5 py-3 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}

      {/* ── Policy Edit Modal ── */}
      {editDomain && editInitial && (
        <PolicyModal
          domain_id={editDomain}
          initial={editInitial}
          onClose={() => { setEditDomain(null); setEditInitial(null); }}
          onSaved={() => fetchDomainReports()}
        />
      )}
    </>
  );
}
