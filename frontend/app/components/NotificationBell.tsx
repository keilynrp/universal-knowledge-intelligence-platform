"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { apiFetch } from "../../lib/api";
import { useLanguage } from "../contexts/LanguageContext";

interface FeedEntry {
  id: number;
  action: string;
  label: string;
  icon: string;
  entity_type: string | null;
  entity_id: number | null;
  href: string | null;
  details: Record<string, unknown> | null;
  created_at: string | null;
  is_read: boolean;
}

const KNOWN_ACTION_TRANSLATION_KEYS: Record<string, string> = {
  upload: "header.notifications.action.upload",
  "entity.update": "header.notifications.action.entity_update",
  "entity.delete": "header.notifications.action.entity_delete",
  "entity.bulk_delete": "header.notifications.action.entity_bulk_delete",
  "harmonization.apply": "header.notifications.action.harmonization_apply",
  "authority.confirm": "header.notifications.action.authority_confirm",
  "authority.reject": "header.notifications.action.authority_reject",
  "entity.merge": "header.notifications.action.entity_merge",
  pull: "header.notifications.action.pull",
  scheduled_pull: "header.notifications.action.scheduled_pull",
};

const GENERIC_ACTION_TRANSLATION_KEYS: Record<string, string> = {
  CREATE: "header.notifications.generic.create",
  UPDATE: "header.notifications.generic.update",
  DELETE: "header.notifications.generic.delete",
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

function localeForLanguage(language: string): string {
  return language === "es" ? "es-MX" : "en-US";
}

function relativeTimeFormatter(language: string): Intl.RelativeTimeFormat {
  return new Intl.RelativeTimeFormat(localeForLanguage(language), { numeric: "auto" });
}

function parseNotificationDate(iso: string): Date | null {
  const normalized = /([zZ]|[+-]\d{2}:\d{2})$/.test(iso) ? iso : `${iso}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

function timeAgo(
  iso: string,
  t: (key: string, params?: Record<string, string | number>) => string,
  language: string,
): string {
  const date = parseNotificationDate(iso);
  if (!date) return "";
  const diff = Math.max(0, Date.now() - date.getTime());
  const s = Math.floor(diff / 1000);
  if (s <= 0) return t("header.notifications.time.now");
  const rtf = relativeTimeFormatter(language);
  if (s < 60) return rtf.format(-s, "second");
  const m = Math.floor(s / 60);
  if (m < 60) return rtf.format(-m, "minute");
  const h = Math.floor(m / 60);
  if (h < 24) return rtf.format(-h, "hour");
  return rtf.format(-Math.floor(h / 24), "day");
}

function formatNotificationDateTime(iso: string, language: string): string {
  const date = parseNotificationDate(iso);
  if (!date) return "";
  return new Intl.DateTimeFormat(localeForLanguage(language), {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: language !== "es",
  }).format(date);
}

function entryDetail(entry: FeedEntry, t: (key: string, params?: Record<string, string | number>) => string): string {
  const d = entry.details;
  if (!d) return "";
  if (entry.action === "upload")              return t("header.notifications.detail.upload", { filename: String(d.filename ?? ""), rows: Number(d.rows ?? 0) });
  if (entry.action === "entity.update") {
    const fields = Array.isArray(d.fields) ? (d.fields as string[]).join(", ") : "";
    return fields
      ? t("header.notifications.detail.entity_update_fields", { fields })
      : t("header.notifications.detail.entity_update_entity", { id: entry.entity_id ?? "?" });
  }
  if (entry.action === "entity.bulk_delete")  return t("header.notifications.detail.entity_bulk_delete", { count: Number(d.deleted ?? 0) });
  if (entry.action === "harmonization.apply") return t("header.notifications.detail.harmonization_apply", { step: String(d.step_name ?? d.step_id ?? ""), count: Number(d.records_updated ?? 0) });
  if (entry.action === "authority.confirm")   return t("header.notifications.detail.authority_confirm", { label: String(d.canonical_label ?? ""), suffix: d.rule_created ? t("header.notifications.detail.rule_suffix") : "" });
  return "";
}

function localizedNotificationLabel(
  entry: FeedEntry,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  const knownActionKey = KNOWN_ACTION_TRANSLATION_KEYS[entry.action];
  if (knownActionKey) {
    return t(knownActionKey);
  }

  const genericActionKey = GENERIC_ACTION_TRANSLATION_KEYS[entry.action];
  if (genericActionKey && entry.entity_type) {
    const resourceKey = `header.notifications.resource.${entry.entity_type}`;
    const translatedResource = t(resourceKey);
    const fallbackResource = entry.entity_type.replaceAll("_", " ").replaceAll(".", " ");
    return t(genericActionKey, {
      resource: translatedResource === resourceKey ? fallbackResource : translatedResource,
    });
  }

  return entry.label || entry.action;
}

export default function NotificationBell() {
  const { t, language } = useLanguage();
  const [open, setOpen]       = useState(false);
  const [entries, setEntries] = useState<FeedEntry[]>([]);
  const [unread, setUnread] = useState(0);
  const [markingAll, setMarkingAll] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const fetchFeed = useCallback(async () => {
    try {
      const res = await apiFetch("/notifications/center?limit=8");
      if (!res.ok) return;
      const data = await res.json();
      setEntries(data.items ?? []);
      setUnread(data.unread_count ?? 0);
    } catch { /* non-critical */ }
  }, []);

  // Initial load + 60s polling
  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchFeed();
    }, 0);
    const t = setInterval(fetchFeed, 60_000);
    return () => {
      window.clearTimeout(timer);
      clearInterval(t);
    };
  }, [fetchFeed]);

  // Close on click-outside
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  function handleOpen() {
    setOpen((v) => {
      const next = !v;
      if (next) {
        void fetchFeed();
      }
      return next;
    });
  }

  async function markAllRead() {
    setMarkingAll(true);
    try {
      const res = await apiFetch("/notifications/center/read-all", { method: "POST" });
      if (res.ok) {
        await fetchFeed();
      }
    } finally {
      setMarkingAll(false);
    }
  }

  async function markEntryRead(entryId: number) {
    const res = await apiFetch(`/notifications/center/read/${entryId}`, { method: "POST" });
    if (!res.ok) return;
    setEntries((prev) => prev.map((entry) => (
      entry.id === entryId ? { ...entry, is_read: true } : entry
    )));
    setUnread((prev) => Math.max(0, prev - 1));
  }

  return (
    <div ref={ref} className="relative">
      {/* Bell button */}
      <button
        onClick={handleOpen}
        className="relative flex h-10 w-10 items-center justify-center rounded-xl text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-[var(--ukip-muted)] dark:hover:bg-[var(--ukip-panel-strong)] dark:hover:text-[var(--ukip-text-strong)]"
        aria-label={t("header.notifications.aria")}
      >
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
        </svg>
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 flex min-w-[1.1rem] h-[1.1rem] items-center justify-center rounded-full bg-violet-500 px-1 text-[10px] font-bold leading-none text-white ring-2 ring-white dark:ring-[var(--ukip-header-bg)]">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-12 z-50 w-[30rem] max-w-[min(30rem,calc(100vw-1rem))] overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-xl dark:border-gray-700 dark:bg-gray-900">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3 dark:border-gray-800">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-gray-900 dark:text-white">{t("header.notifications.title")}</span>
              {unread > 0 && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700 dark:bg-blue-500/20 dark:text-blue-400">
                  {t("header.notifications.new_count", { count: unread })}
                </span>
              )}
            </div>
            {unread > 0 && (
              <button
                onClick={() => { void markAllRead(); }}
                disabled={markingAll}
                className="text-xs text-blue-600 hover:underline dark:text-blue-400"
              >
                {t("header.notifications.mark_all_read")}
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
                <p className="mt-2 text-sm text-gray-400 dark:text-gray-500">{t("header.notifications.empty")}</p>
              </li>
            ) : (
              entries.map((entry) => {
                const isUnread = !entry.is_read;
                const detail = entryDetail(entry, t);
                const dotColor = ACTION_COLOR[entry.action] ?? "bg-gray-400";
                const label = localizedNotificationLabel(entry, t);
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
                        {label}
                      </p>
                      {detail && (
                        <p className="mt-0.5 break-words text-xs leading-relaxed text-gray-500 dark:text-gray-400">{detail}</p>
                      )}
                      <div className="mt-1 flex flex-wrap items-center gap-3">
                        <p className="text-[11px] text-gray-400 dark:text-gray-500">
                          {entry.created_at ? (
                            <span title={formatNotificationDateTime(entry.created_at, language)}>
                              {timeAgo(entry.created_at, t, language)}
                            </span>
                          ) : ""}
                        </p>
                        {entry.href && (
                          <Link
                            href={entry.href}
                            onClick={() => {
                              if (!entry.is_read) void markEntryRead(entry.id);
                              setOpen(false);
                            }}
                            className="text-[11px] font-medium text-blue-600 hover:underline dark:text-blue-400"
                          >
                            {t("header.notifications.view_item")}
                          </Link>
                        )}
                      </div>
                    </div>
                    {/* Unread controls */}
                    {isUnread && (
                      <div className="mt-1 flex shrink-0 flex-col items-end gap-2">
                        <span className="h-2 w-2 rounded-full bg-blue-500" />
                        <button
                          onClick={() => { void markEntryRead(entry.id); }}
                          className="text-[10px] font-medium text-gray-400 hover:text-blue-600 dark:hover:text-blue-400"
                        >
                          {t("header.notifications.mark_read")}
                        </button>
                      </div>
                    )}
                  </li>
                );
              })
            )}
          </ul>

          {/* Footer */}
          <div className="border-t border-gray-100 dark:border-gray-800">
            <Link
              href="/notifications"
              onClick={() => setOpen(false)}
              className="flex w-full items-center justify-center gap-1.5 py-3 text-xs font-medium text-blue-600 transition-colors hover:bg-gray-50 dark:text-blue-400 dark:hover:bg-gray-800"
            >
              {t("header.notifications.view_all")}
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
