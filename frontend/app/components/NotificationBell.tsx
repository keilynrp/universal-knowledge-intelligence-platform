"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { apiFetch } from "../../lib/api";

interface FeedEntry {
  id: number;
  action: string;
  icon: string;
  entity_type: string | null;
  entity_id: number | null;
  details: Record<string, unknown> | null;
  created_at: string | null;
}

const ACTION_LABELS: Record<string, string> = {
  "upload":              "File uploaded",
  "entity.update":       "Entity updated",
  "entity.delete":       "Entity deleted",
  "entity.bulk_delete":  "Entities bulk-deleted",
  "harmonization.apply": "Harmonization applied",
  "authority.confirm":   "Authority record confirmed",
  "authority.reject":    "Authority record rejected",
  "entity.merge":        "Entities merged",
};

const ACTION_COLOR: Record<string, string> = {
  "upload":              "bg-blue-500",
  "entity.update":       "bg-amber-500",
  "entity.delete":       "bg-red-500",
  "entity.bulk_delete":  "bg-red-600",
  "harmonization.apply": "bg-violet-500",
  "authority.confirm":   "bg-green-500",
  "authority.reject":    "bg-rose-500",
};

const LS_KEY = "ukip_notif_last_read";

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function entryDetail(entry: FeedEntry): string {
  const d = entry.details;
  if (!d) return "";
  if (entry.action === "upload")              return `${d.filename ?? ""} · ${d.rows} rows`;
  if (entry.action === "entity.update") {
    const fields = Array.isArray(d.fields) ? (d.fields as string[]).join(", ") : "";
    return fields ? `Fields: ${fields}` : `Entity #${entry.entity_id}`;
  }
  if (entry.action === "entity.bulk_delete")  return `${d.deleted} entities removed`;
  if (entry.action === "harmonization.apply") return `${d.step_name ?? d.step_id} · ${d.records_updated} records`;
  if (entry.action === "authority.confirm")   return `"${d.canonical_label}"${d.rule_created ? " + rule" : ""}`;
  return "";
}

export default function NotificationBell() {
  const [open, setOpen]       = useState(false);
  const [entries, setEntries] = useState<FeedEntry[]>([]);
  const [lastRead, setLastRead] = useState<number>(() => {
    if (typeof window === "undefined") return 0;
    return parseInt(localStorage.getItem(LS_KEY) ?? "0", 10);
  });
  const ref = useRef<HTMLDivElement>(null);

  const fetchFeed = useCallback(async () => {
    try {
      const res = await apiFetch("/audit/feed?limit=8");
      if (res.ok) setEntries(await res.json());
    } catch { /* non-critical */ }
  }, []);

  // Initial load + 60s polling
  useEffect(() => {
    fetchFeed();
    const t = setInterval(fetchFeed, 60_000);
    return () => clearInterval(t);
  }, [fetchFeed]);

  // Close on click-outside
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const unread = entries.filter(
    (e) => e.created_at && new Date(e.created_at).getTime() > lastRead
  ).length;

  function handleOpen() {
    setOpen((v) => !v);
    if (!open) {
      const now = Date.now();
      setLastRead(now);
      localStorage.setItem(LS_KEY, String(now));
    }
  }

  function markAllRead() {
    const now = Date.now();
    setLastRead(now);
    localStorage.setItem(LS_KEY, String(now));
  }

  return (
    <div ref={ref} className="relative">
      {/* Bell button */}
      <button
        onClick={handleOpen}
        className="relative flex h-10 w-10 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-500 transition-colors hover:bg-gray-50 hover:text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
        aria-label="Notifications"
      >
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
        </svg>
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-12 z-50 w-80 overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-xl dark:border-gray-700 dark:bg-gray-900">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3 dark:border-gray-800">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-gray-900 dark:text-white">Notifications</span>
              {unread > 0 && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700 dark:bg-blue-500/20 dark:text-blue-400">
                  {unread} new
                </span>
              )}
            </div>
            {unread > 0 && (
              <button
                onClick={markAllRead}
                className="text-xs text-blue-600 hover:underline dark:text-blue-400"
              >
                Mark all read
              </button>
            )}
          </div>

          {/* List */}
          <ul className="max-h-80 divide-y divide-gray-50 overflow-y-auto dark:divide-gray-800">
            {entries.length === 0 ? (
              <li className="flex flex-col items-center justify-center py-10">
                <svg className="h-8 w-8 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
                </svg>
                <p className="mt-2 text-sm text-gray-400 dark:text-gray-500">No notifications yet</p>
              </li>
            ) : (
              entries.map((entry) => {
                const isUnread = entry.created_at
                  ? new Date(entry.created_at).getTime() > lastRead
                  : false;
                const detail = entryDetail(entry);
                const dotColor = ACTION_COLOR[entry.action] ?? "bg-gray-400";
                return (
                  <li
                    key={entry.id}
                    className={`flex items-start gap-3 px-4 py-3 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/60 ${
                      isUnread ? "bg-blue-50/40 dark:bg-blue-500/5" : ""
                    }`}
                  >
                    {/* Icon dot */}
                    <div className={`mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${dotColor} bg-opacity-15`}>
                      <span className="text-sm leading-none">{entry.icon}</span>
                    </div>
                    {/* Text */}
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900 dark:text-white leading-snug">
                        {ACTION_LABELS[entry.action] ?? entry.action}
                      </p>
                      {detail && (
                        <p className="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">{detail}</p>
                      )}
                      <p className="mt-1 text-[11px] text-gray-400 dark:text-gray-500">
                        {entry.created_at ? timeAgo(entry.created_at) : ""}
                      </p>
                    </div>
                    {/* Unread dot */}
                    {isUnread && (
                      <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-blue-500" />
                    )}
                  </li>
                );
              })
            )}
          </ul>

          {/* Footer */}
          <div className="border-t border-gray-100 dark:border-gray-800">
            <Link
              href="/"
              onClick={() => setOpen(false)}
              className="flex w-full items-center justify-center gap-1.5 py-3 text-xs font-medium text-blue-600 transition-colors hover:bg-gray-50 dark:text-blue-400 dark:hover:bg-gray-800"
            >
              View all activity
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
