"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { apiFetch } from "../../lib/api";
import { EmptyState } from "../components/ui";
import { useLanguage } from "../contexts/LanguageContext";

// ── Types ─────────────────────────────────────────────────────────────────────

interface NotifEntry {
  id: number;
  action: string;
  label: string;
  icon: string;
  entity_type: string | null;
  entity_id: number | null;
  username: string | null;
  details: Record<string, unknown> | null;
  href: string | null;
  created_at: string | null;
  is_read: boolean;
}

interface FeedPage {
  total: number;
  unread_count: number;
  skip: number;
  limit: number;
  last_read_at: string | null;
  items: NotifEntry[];
}

// ── Constants ─────────────────────────────────────────────────────────────────

const ACTION_COLOR: Record<string, string> = {
  "upload":              "bg-blue-500",
  "entity.update":       "bg-amber-500",
  "entity.delete":       "bg-red-500",
  "entity.bulk_delete":  "bg-red-600",
  "harmonization.apply": "bg-violet-500",
  "authority.confirm":   "bg-green-500",
  "authority.reject":    "bg-rose-500",
  "entity.merge":        "bg-indigo-500",
};

const ACTION_FILTERS = [
  { key: "",                    label: "All" },
  { key: "upload",              label: "Uploads" },
  { key: "entity.update",       label: "Updates" },
  { key: "entity.delete",       label: "Deletes" },
  { key: "entity.bulk_delete",  label: "Bulk Deletes" },
  { key: "harmonization.apply", label: "Harmonization" },
  { key: "authority.confirm",   label: "Authority ✓" },
  { key: "authority.reject",    label: "Authority ✗" },
];

const PAGE_SIZE = 30;

// ── Helpers ───────────────────────────────────────────────────────────────────

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}

function entryDetail(entry: NotifEntry): string {
  const d = entry.details;
  if (!d) return "";
  if (entry.action === "upload")              return `${d.filename ?? ""} · ${d.rows ?? ""} rows`;
  if (entry.action === "entity.update") {
    const fields = Array.isArray(d.fields) ? (d.fields as string[]).join(", ") : "";
    return fields ? `Fields: ${fields}` : entry.entity_id ? `Entity #${entry.entity_id}` : "";
  }
  if (entry.action === "entity.bulk_delete")  return `${d.deleted ?? ""} entities removed`;
  if (entry.action === "harmonization.apply") return `${d.step_name ?? d.step_id ?? ""} · ${d.records_updated ?? ""} records`;
  if (entry.action === "authority.confirm")   return `"${d.canonical_label}"${d.rule_created ? " + rule" : ""}`;
  return "";
}

// ── Local per-item overrides (entries marked read beyond last_read_at) ────────
const LS_READ_IDS = "ukip_notif_read_ids";

function getLocalReadIds(): Set<number> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(LS_READ_IDS);
    return raw ? new Set(JSON.parse(raw) as number[]) : new Set();
  } catch {
    return new Set();
  }
}

function addLocalReadId(id: number) {
  const ids = getLocalReadIds();
  ids.add(id);
  // Keep at most 500 IDs to avoid unbounded growth
  const arr = Array.from(ids).slice(-500);
  localStorage.setItem(LS_READ_IDS, JSON.stringify(arr));
}

function clearLocalReadIds() {
  localStorage.removeItem(LS_READ_IDS);
}

// ── Page component ────────────────────────────────────────────────────────────

export default function NotificationsPage() {
  const { t } = useLanguage();
  const [page, setPage]             = useState<FeedPage | null>(null);
  const [items, setItems]           = useState<NotifEntry[]>([]);
  const [skip, setSkip]             = useState(0);
  const [action, setAction]         = useState("");
  const [loading, setLoading]       = useState(false);
  const [markingAll, setMarkingAll] = useState(false);
  const [localRead, setLocalRead]   = useState<Set<number>>(new Set());
  const hasMounted = useRef(false);

  // Load local read overrides on mount
  useEffect(() => {
    setLocalRead(getLocalReadIds());
    hasMounted.current = true;
  }, []);

  const fetchPage = useCallback(async (newSkip: number, newAction: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        skip:  String(newSkip),
        limit: String(PAGE_SIZE),
      });
      if (newAction) params.set("action", newAction);
      const res = await apiFetch(`/notifications/center?${params}`);
      if (!res.ok) return;
      const data: FeedPage = await res.json();
      setPage(data);
      if (newSkip === 0) {
        setItems(data.items);
      } else {
        setItems((prev) => [...prev, ...data.items]);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load and on filter change
  useEffect(() => {
    setSkip(0);
    setItems([]);
    fetchPage(0, action);
  }, [action, fetchPage]);

  async function handleMarkAllRead() {
    setMarkingAll(true);
    try {
      const res = await apiFetch("/notifications/center/read-all", { method: "POST" });
      if (res.ok) {
        clearLocalReadIds();
        setLocalRead(new Set());
        // Re-fetch from beginning to update is_read flags
        setSkip(0);
        setItems([]);
        await fetchPage(0, action);
      }
    } finally {
      setMarkingAll(false);
    }
  }

  function handleMarkItemRead(id: number) {
    addLocalReadId(id);
    setLocalRead((prev) => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  }

  function handleLoadMore() {
    const next = skip + PAGE_SIZE;
    setSkip(next);
    fetchPage(next, action);
  }

  const hasMore = page ? items.length < page.total : false;
  const unreadCount = page
    ? Math.max(0, page.unread_count - localRead.size)
    : 0;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      {/* ── Page header ──────────────────────────────────────────────────── */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            {t('page.notifications.title')}
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {page
              ? `${page.total} total · ${unreadCount} unread`
              : t('page.notifications.loading')}
          </p>
        </div>

        {/* Bulk mark-all-read */}
        {unreadCount > 0 && (
          <button
            onClick={handleMarkAllRead}
            disabled={markingAll}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
          >
            {markingAll ? (
              <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            )}
            {t('page.notifications.mark_all_read_button')}
          </button>
        )}
      </div>

      {/* ── Action type filter tabs ───────────────────────────────────────── */}
      <div className="mb-5 flex flex-wrap gap-1.5">
        {ACTION_FILTERS.map((f) => {
          const filterLabel =
            f.key === ""             ? t('page.notifications.filter_all') :
            f.key === "upload"       ? t('page.notifications.filter_uploads') :
            f.key === "entity.update" ? t('page.notifications.filter_updates') :
            f.label;
          return (
            <button
              key={f.key}
              onClick={() => setAction(f.key)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                action === f.key
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              }`}
            >
              {filterLabel}
            </button>
          );
        })}
      </div>

      {/* ── List ──────────────────────────────────────────────────────────── */}
      {loading && items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <svg className="mb-3 h-8 w-8 animate-spin" aria-hidden="true" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-sm">Loading notifications…</p>
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon="bell"
          title={t('page.notifications.empty_title')}
          description={t('page.notifications.empty_description')}
          size="page"
          cta={action ? [{ label: "Clear filter", onClick: () => setAction("") }] : undefined}
        />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900">
          <ul className="divide-y divide-gray-100 dark:divide-gray-800">
            {items.map((entry) => {
              const isRead = entry.is_read || localRead.has(entry.id);
              const detail = entryDetail(entry);
              const dotColor = ACTION_COLOR[entry.action] ?? "bg-gray-400";

              return (
                <li
                  key={entry.id}
                  className={`group flex items-start gap-4 px-5 py-4 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/60 ${
                    isRead ? "" : "bg-blue-50/50 dark:bg-blue-500/5"
                  }`}
                >
                  {/* Icon */}
                  <div
                    className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${dotColor} bg-opacity-15`}
                  >
                    <span className="text-base leading-none">{entry.icon}</span>
                  </div>

                  {/* Content */}
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <span className="text-sm font-semibold text-gray-900 dark:text-white">
                        {entry.label}
                      </span>
                      {entry.username && (
                        <span className="text-xs text-gray-400 dark:text-gray-500">
                          by {entry.username}
                        </span>
                      )}
                    </div>
                    {detail && (
                      <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400 truncate">
                        {detail}
                      </p>
                    )}
                    <div className="mt-1 flex flex-wrap items-center gap-3">
                      <span className="text-[11px] text-gray-400 dark:text-gray-500">
                        {entry.created_at ? timeAgo(entry.created_at) : ""}
                      </span>

                      {/* Action link */}
                      {entry.href && (
                        <Link
                          href={entry.href}
                          className="text-[11px] font-medium text-blue-600 hover:underline dark:text-blue-400"
                        >
                          View →
                        </Link>
                      )}
                    </div>
                  </div>

                  {/* Right: unread dot + mark-read button */}
                  <div className="flex shrink-0 flex-col items-end gap-2 pt-1">
                    {!isRead && (
                      <>
                        <span className="h-2.5 w-2.5 rounded-full bg-blue-500" />
                        <button
                          onClick={() => handleMarkItemRead(entry.id)}
                          className="hidden text-[10px] font-medium text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 group-hover:block"
                          title="Mark as read"
                        >
                          {t('page.notifications.mark_read_button')}
                        </button>
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>

          {/* Load more */}
          {hasMore && (
            <div className="border-t border-gray-100 dark:border-gray-800">
              <button
                onClick={handleLoadMore}
                disabled={loading}
                className="flex w-full items-center justify-center gap-2 py-3.5 text-sm font-medium text-blue-600 transition-colors hover:bg-gray-50 disabled:opacity-50 dark:text-blue-400 dark:hover:bg-gray-800"
              >
                {loading ? (
                  <>
                    <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    {t('page.notifications.loading')}
                  </>
                ) : (
                  <>
                    {t('page.notifications.load_more_button')}
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                      {page!.total - items.length} remaining
                    </span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
