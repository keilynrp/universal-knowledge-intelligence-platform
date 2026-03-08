"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "../../lib/api";

interface FeedEntry {
  id: number;
  action: string;
  icon: string;
  entity_type: string | null;
  entity_id: number | null;
  user_id: number | null;
  details: Record<string, unknown> | null;
  created_at: string | null;
}

const ACTION_LABELS: Record<string, string> = {
  "upload": "File uploaded",
  "entity.update": "Entity updated",
  "entity.delete": "Entity deleted",
  "entity.bulk_delete": "Entities bulk-deleted",
  "harmonization.apply": "Harmonization applied",
  "authority.confirm": "Authority record confirmed",
  "authority.reject":  "Authority record rejected",
  "entity.merge":      "Entities merged",
};

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

function entryDetail(entry: FeedEntry): string {
  const d = entry.details;
  if (!d) return "";
  if (entry.action === "upload") return `${d.filename ?? ""} · ${d.rows} rows`;
  if (entry.action === "entity.update") {
    const fields = Array.isArray(d.fields) ? (d.fields as string[]).join(", ") : "";
    return fields ? `Fields: ${fields}` : `Entity #${entry.entity_id}`;
  }
  if (entry.action === "entity.bulk_delete") return `${d.deleted} entities removed`;
  if (entry.action === "harmonization.apply") return `${d.step_name ?? d.step_id} · ${d.records_updated} records`;
  if (entry.action === "authority.confirm") return `"${d.canonical_label}"${d.rule_created ? " + rule" : ""}`;
  return "";
}

export default function ActivityFeed() {
  const [entries, setEntries] = useState<FeedEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchFeed = useCallback(async () => {
    try {
      const res = await apiFetch("/audit/feed?limit=20");
      if (res.ok) setEntries(await res.json());
    } catch {
      // non-critical
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFeed();
    const interval = setInterval(fetchFeed, 30_000); // refresh every 30s
    return () => clearInterval(interval);
  }, [fetchFeed]);

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Recent Activity</h2>
        <button
          onClick={fetchFeed}
          className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-300"
          title="Refresh"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
          </svg>
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-8">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
        </div>
      ) : entries.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-400 dark:text-gray-500">No activity yet</p>
      ) : (
        <ol className="relative space-y-0 border-l border-gray-200 dark:border-gray-700">
          {entries.map((entry) => {
            const detail = entryDetail(entry);
            return (
              <li key={entry.id} className="group ml-4 pb-5 last:pb-0">
                {/* dot */}
                <span className="absolute -left-1.5 mt-1 flex h-3 w-3 items-center justify-center rounded-full border-2 border-white bg-gray-300 dark:border-gray-900 dark:bg-gray-600" />
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 text-base leading-none">{entry.icon}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 dark:text-white">
                      {ACTION_LABELS[entry.action] ?? entry.action}
                    </p>
                    {detail && (
                      <p className="truncate text-xs text-gray-500 dark:text-gray-400">{detail}</p>
                    )}
                  </div>
                  <time className="shrink-0 text-xs text-gray-400 dark:text-gray-500">
                    {entry.created_at ? timeAgo(entry.created_at) : ""}
                  </time>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
