"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useLanguage } from "../contexts/LanguageContext";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type DerivedStatus =
  | "missing"
  | "pending"
  | "processing"
  | "ready"
  | "stale"
  | "failed"
  | "unknown";

interface ResourceEntry {
  status: DerivedStatus;
  updated_at: string;
  source_count: number;
  derived_count: number;
  last_error: string | null;
  can_rebuild: boolean;
  rebuild_endpoint: string | null;
}

interface DerivedStatusBundle {
  domain_id: string;
  computed_at: string;
  resources: Record<string, ResourceEntry>;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ACTIVE_STATUSES: Set<DerivedStatus> = new Set(["pending", "processing"]);

const POLL_ACTIVE_MS  = 30_000;   // 30s while any resource is building
const POLL_PASSIVE_MS = 300_000;  // 5 min otherwise

const RESOURCE_LABELS: Record<string, string> = {
  enrichment:                   "Entity Enrichment",
  graph:                        "Knowledge Graph",
  semantic_keyword_signals:     "Keyword Signals",
  rag_index:                    "RAG Index",
  executive_dashboard_snapshot: "Dashboard Snapshot",
  report_readiness:             "Report Readiness",
};

const RESOURCE_TOOLTIP_KEYS: Record<string, string> = {
  semantic_keyword_signals: "derived_status.semantic_keyword_signals.tooltip",
};

const RESOURCE_ORDER = [
  "enrichment",
  "graph",
  "semantic_keyword_signals",
  "rag_index",
  "executive_dashboard_snapshot",
  "report_readiness",
];

// ---------------------------------------------------------------------------
// Badge helpers
// ---------------------------------------------------------------------------

function badgeClass(status: DerivedStatus): string {
  switch (status) {
    case "ready":      return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300";
    case "stale":      return "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300";
    case "missing":    return "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400";
    case "pending":    return "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 animate-pulse";
    case "processing": return "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 animate-pulse";
    case "failed":     return "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300";
    case "unknown":    return "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300";
    default:           return "bg-gray-100 text-gray-500";
  }
}

function statusDot(status: DerivedStatus): string {
  switch (status) {
    case "ready":      return "bg-emerald-500";
    case "stale":      return "bg-amber-400";
    case "missing":    return "bg-gray-400";
    case "pending":
    case "processing": return "bg-blue-500 animate-pulse";
    case "failed":     return "bg-red-500";
    case "unknown":    return "bg-orange-400";
    default:           return "bg-gray-400";
  }
}

// ---------------------------------------------------------------------------
// Relative time
// ---------------------------------------------------------------------------

function relativeTime(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const seconds = Math.floor(diff / 1000);
    if (seconds < 60)  return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60)  return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24)    return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  } catch {
    return "—";
  }
}

// ---------------------------------------------------------------------------
// ResourceRow
// ---------------------------------------------------------------------------

interface ResourceRowProps {
  resourceKey: string;
  entry: ResourceEntry;
  onRebuild: (endpoint: string, resourceKey: string) => Promise<void>;
  rebuilding: boolean;
  tooltip?: string;
}

function ResourceRow({ resourceKey, entry, onRebuild, rebuilding, tooltip }: ResourceRowProps) {
  const label = RESOURCE_LABELS[resourceKey] ?? resourceKey;
  const isActive = ACTIVE_STATUSES.has(entry.status);

  return (
    <div className="flex items-center gap-3 py-2.5 px-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
      {/* Status dot */}
      <span className={`h-2.5 w-2.5 flex-shrink-0 rounded-full ${statusDot(entry.status)}`} />

      {/* Label */}
      <span className="flex w-44 flex-shrink-0 items-center gap-1.5 text-sm font-medium text-gray-700 dark:text-gray-200">
        {label}
        {tooltip && (
          <span
            aria-label={tooltip}
            className="inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full border border-blue-200 bg-blue-50 text-[10px] font-bold leading-none text-blue-700 dark:border-blue-700/60 dark:bg-blue-900/30 dark:text-blue-200"
            role="img"
            tabIndex={0}
            title={tooltip}
          >
            i
          </span>
        )}
      </span>

      {/* Badge */}
      <span
        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${badgeClass(entry.status)}`}
        title={entry.last_error ?? undefined}
      >
        {entry.status}
      </span>

      {/* Counts */}
      <span className="ml-2 text-xs text-gray-400 dark:text-gray-500 tabular-nums">
        {entry.derived_count.toLocaleString()} / {entry.source_count.toLocaleString()}
      </span>

      {/* Updated at */}
      <span className="ml-auto text-xs text-gray-400 dark:text-gray-500 flex-shrink-0">
        {relativeTime(entry.updated_at)}
      </span>

      {/* Error tooltip */}
      {entry.last_error && (
        <span
          className="ml-1 text-orange-500 cursor-help text-xs"
          title={entry.last_error}
        >
          ⚠
        </span>
      )}

      {/* Rebuild button */}
      {entry.can_rebuild && entry.rebuild_endpoint && !isActive && (
        <button
          disabled={rebuilding}
          onClick={() => onRebuild(entry.rebuild_endpoint!, resourceKey)}
          className="ml-2 flex-shrink-0 rounded px-2 py-0.5 text-xs font-medium bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-600 dark:text-gray-300 disabled:opacity-50 transition-colors"
        >
          {rebuilding ? "…" : "Rebuild"}
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DerivedStatusPanel
// ---------------------------------------------------------------------------

interface DerivedStatusPanelProps {
  domainId: string;
}

export default function DerivedStatusPanel({ domainId }: DerivedStatusPanelProps) {
  const { t } = useLanguage();
  const [bundle, setBundle]   = useState<DerivedStatusBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [rebuilding, setRebuilding] = useState<Record<string, boolean>>({});

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await apiFetch(`/derived-status/${encodeURIComponent(domainId)}`);
      if (!res.ok) {
        setError(`Failed to fetch status (HTTP ${res.status})`);
        return;
      }
      const data: DerivedStatusBundle = await res.json();
      setBundle(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [domainId]);

  const scheduleNextPoll = useCallback((data: DerivedStatusBundle | null) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    const hasActive = data
      ? Object.values(data.resources).some((r) => ACTIVE_STATUSES.has(r.status))
      : false;
    const delay = hasActive ? POLL_ACTIVE_MS : POLL_PASSIVE_MS;
    timerRef.current = setTimeout(async () => {
      await fetchStatus();
    }, delay);
  }, [fetchStatus]);

  // Initial fetch
  useEffect(() => {
    setLoading(true);
    void fetchStatus();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [fetchStatus]);

  // Schedule next poll when bundle updates
  useEffect(() => {
    if (!loading) scheduleNextPoll(bundle);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [bundle, loading, scheduleNextPoll]);

  const handleRebuild = useCallback(async (endpoint: string, resourceKey: string) => {
    setRebuilding((prev) => ({ ...prev, [resourceKey]: true }));
    try {
      const res = await apiFetch(endpoint, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      // Trigger immediate refresh after rebuild kick-off
      await fetchStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rebuild failed");
      // Revert optimistic state — next poll will restore real state
    } finally {
      setRebuilding((prev) => ({ ...prev, [resourceKey]: false }));
    }
  }, [fetchStatus]);

  if (loading) {
    return (
      <div className="flex h-20 items-center justify-center">
        <span className="text-sm text-gray-400 dark:text-gray-500">Loading data readiness…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
        Could not load data readiness: {error}
      </div>
    );
  }

  if (!bundle) return null;

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100 dark:border-gray-800">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200">Data Readiness</h3>
        <span className="text-xs text-gray-400 dark:text-gray-500">
          Updated {relativeTime(bundle.computed_at)}
        </span>
      </div>

      {/* Resource rows */}
      <div className="divide-y divide-gray-50 dark:divide-gray-800/60 px-1 py-1">
        {RESOURCE_ORDER.map((key) => {
          const entry = bundle.resources[key];
          if (!entry) return null;
          return (
            <ResourceRow
              key={key}
              resourceKey={key}
              entry={entry}
              onRebuild={handleRebuild}
              rebuilding={!!rebuilding[key]}
              tooltip={RESOURCE_TOOLTIP_KEYS[key] ? t(RESOURCE_TOOLTIP_KEYS[key]) : undefined}
            />
          );
        })}
      </div>
    </div>
  );
}
