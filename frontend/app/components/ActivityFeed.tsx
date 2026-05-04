"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "../../lib/api";
import { formatRelativeTime } from "../lib/dateFormat";
import { useLanguage } from "../contexts/LanguageContext";

interface FeedEntry {
  id: number;
  action: string;
  label?: string;
  icon: string;
  entity_type: string | null;
  entity_id: number | null;
  user_id: number | null;
  details: Record<string, unknown> | null;
  created_at: string | null;
}

const KNOWN_ACTION_TRANSLATION_KEYS: Record<string, string> = {
  upload: "page.notifications.action.upload",
  "entity.update": "page.notifications.action.entity_update",
  "entity.delete": "page.notifications.action.entity_delete",
  "entity.bulk_delete": "page.notifications.action.entity_bulk_delete",
  "harmonization.apply": "page.notifications.action.harmonization_apply",
  "authority.confirm": "page.notifications.action.authority_confirm",
  "authority.reject": "page.notifications.action.authority_reject",
  "entity.merge": "page.notifications.action.entity_merge",
  pull: "page.notifications.action.pull",
  scheduled_pull: "page.notifications.action.scheduled_pull",
};

const GENERIC_ACTION_TRANSLATION_KEYS: Record<string, string> = {
  CREATE: "page.notifications.generic.create",
  UPDATE: "page.notifications.generic.update",
  DELETE: "page.notifications.generic.delete",
};

function entryDetail(
  entry: FeedEntry,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  const d = entry.details;
  if (!d) return "";
  if (entry.action === "upload") return `${d.filename ?? ""} · ${t("page.notifications.rows_label", { count: Number(d.rows ?? 0) })}`;
  if (entry.action === "entity.update") {
    const fields = Array.isArray(d.fields) ? (d.fields as string[]).join(", ") : "";
    return fields ? t("page.notifications.fields_label", { fields }) : t("page.notifications.entity_label", { id: entry.entity_id ?? "?" });
  }
  if (entry.action === "entity.bulk_delete") return t("page.notifications.entities_removed", { count: Number(d.deleted ?? 0) });
  if (entry.action === "harmonization.apply") return `${d.step_name ?? d.step_id ?? ""} · ${t("page.notifications.records_label", { count: Number(d.records_updated ?? 0) })}`;
  if (entry.action === "authority.confirm") return `"${String(d.canonical_label ?? "")}"${d.rule_created ? ` ${t("page.notifications.plus_rule")}` : ""}`;
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
    return t(genericActionKey, {
      resource: t(`page.notifications.resource.${entry.entity_type}`),
    });
  }

  return entry.label || entry.action;
}

export default function ActivityFeed() {
  const { t, language } = useLanguage();
  const [entries, setEntries] = useState<FeedEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchFeed = useCallback(async () => {
    try {
      const res = await apiFetch("/notifications/center?limit=20");
      if (!res.ok) return;
      const data = await res.json();
      setEntries(data.items ?? []);
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
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">{t("dashboard.activity.title")}</h2>
        <button
          onClick={fetchFeed}
          className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-300"
          title={t("common.refresh")}
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
        <p className="py-6 text-center text-sm text-gray-400 dark:text-gray-500">{t("dashboard.activity.empty")}</p>
      ) : (
        <ol className="relative space-y-0 border-l border-gray-200 dark:border-gray-700">
          {entries.map((entry) => {
            const detail = entryDetail(entry, t);
            const label = localizedNotificationLabel(entry, t);
            return (
              <li key={entry.id} className="group ml-4 pb-5 last:pb-0">
                {/* dot */}
                <span className="absolute -left-1.5 mt-1 flex h-3 w-3 items-center justify-center rounded-full border-2 border-white bg-gray-300 dark:border-gray-900 dark:bg-gray-600" />
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 text-base leading-none">{entry.icon}</span>
                  <div className="min-w-0 flex-1">
                    <p className="break-words text-sm font-medium text-gray-900 dark:text-white">
                      {label}
                    </p>
                    {detail && (
                      <p className="truncate text-xs text-gray-500 dark:text-gray-400">{detail}</p>
                    )}
                  </div>
                  <time className="shrink-0 text-xs text-gray-400 dark:text-gray-500">
                    {formatRelativeTime(entry.created_at, language, t("page.notifications.time.now"))}
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
