"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "../../lib/api";
import { useLanguage } from "../contexts/LanguageContext";
import { formatDate } from "../lib/dateFormat";

// ── Types ──────────────────────────────────────────────────────────────────

type WidgetType = "entity_stats" | "top_concepts" | "recent_entities" | "quality_score";

interface Widget {
  id: number;
  name: string;
  widget_type: WidgetType;
  config: Record<string, unknown>;
  public_token: string;
  allowed_origins: string;
  is_active: boolean;
  view_count: number;
  created_at: string | null;
  last_viewed_at: string | null;
}

// ── Constants ──────────────────────────────────────────────────────────────

function getWidgetMeta(t: (key: string, params?: Record<string, string | number>) => string): Record<WidgetType, { label: string; description: string; color: string; icon: string }> {
  return {
    entity_stats: {
      label: t("page.widgets.type.entity_stats.label"),
      description: t("page.widgets.type.entity_stats.description"),
      color: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
      icon: "📊",
    },
    top_concepts: {
      label: t("page.widgets.type.top_concepts.label"),
      description: t("page.widgets.type.top_concepts.description"),
      color: "bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-300",
      icon: "🏷️",
    },
    recent_entities: {
      label: t("page.widgets.type.recent_entities.label"),
      description: t("page.widgets.type.recent_entities.description"),
      color: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
      icon: "⚡",
    },
    quality_score: {
      label: t("page.widgets.type.quality_score.label"),
      description: t("page.widgets.type.quality_score.description"),
      color: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
      icon: "⭐",
    },
  };
}

// ── Widget form ────────────────────────────────────────────────────────────

function WidgetForm({
  initial,
  onSave,
  onCancel,
}: {
  initial?: Partial<Widget>;
  onSave: (data: object) => void;
  onCancel: () => void;
}) {
  const { t } = useLanguage();
  const [name, setName] = useState(initial?.name ?? "");
  const [type, setType] = useState<WidgetType>(initial?.widget_type ?? "entity_stats");
  const initialConfig = (initial?.config as Record<string, string>) ?? {};
  const [domain, setDomain] = useState(initialConfig.domain_id ?? initialConfig.domain ?? "");
  const [limit, setLimit] = useState((initial?.config as Record<string, number>)?.limit ?? 10);
  const [origins, setOrigins] = useState(initial?.allowed_origins ?? "*");
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const widgetMeta = getWidgetMeta(t);

  const handleSave = () => {
    if (!name.trim()) return;
    const config: Record<string, unknown> = {};
    if (domain) config.domain_id = domain;
    if (type === "top_concepts" || type === "recent_entities") config.limit = limit;
    onSave({ name, widget_type: type, config, allowed_origins: origins, is_active: isActive });
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">{t("page.widgets.form.name")}</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("page.widgets.form.name_placeholder")}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">{t("page.widgets.form.widget_type")}</label>
          <select
            value={type}
            onChange={(e) => setType(e.target.value as WidgetType)}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            {Object.entries(widgetMeta).map(([v, m]) => (
              <option key={v} value={v}>{m.icon} {m.label}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">{t("page.widgets.form.domain_filter")} <span className="text-slate-400 dark:text-slate-500">({t("common.optional").toLowerCase()})</span></label>
          <input
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder={t("page.widgets.form.domain_placeholder")}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500"
          />
        </div>
        {(type === "top_concepts" || type === "recent_entities") && (
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">{t("page.widgets.form.item_limit")}</label>
            <input
              type="number"
              value={limit}
              min={1} max={50}
              onChange={(e) => setLimit(parseInt(e.target.value) || 10)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </div>
        )}
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
          {t("page.widgets.form.allowed_origins")} <span className="text-slate-400 dark:text-slate-500">({t("page.widgets.form.allowed_origins_help")})</span>
        </label>
        <input
          value={origins}
          onChange={(e) => setOrigins(e.target.value)}
          placeholder={t("page.widgets.form.allowed_origins_placeholder")}
          className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500"
        />
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
          {t("page.widgets.form.allowed_origins_scope_note")}
        </p>
      </div>
      <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
        <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} className="h-4 w-4 rounded accent-violet-600" />
        {t("page.widgets.form.is_active")}
      </label>
      <div className="flex justify-end gap-3 border-t border-slate-200 pt-2 dark:border-slate-800">
        <button onClick={onCancel} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100">{t("common.cancel")}</button>
        <button
          onClick={handleSave}
          disabled={!name.trim()}
          className="px-5 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700 disabled:opacity-50"
        >
          {t("page.widgets.form.save")}
        </button>
      </div>
    </div>
  );
}

// ── Embed code panel ───────────────────────────────────────────────────────

function EmbedPanel({ widget, apiBase, onClose }: { widget: Widget; apiBase: string; onClose: () => void }) {
  const { t } = useLanguage();
  const [tab, setTab] = useState<"iframe" | "js">("iframe");
  const [copied, setCopied] = useState(false);
  const token = widget.public_token;

  const iframeCode = `<iframe\n  src="${apiBase}/embed/${token}/frame"\n  width="480" height="320"\n  frameborder="0"\n  title="${widget.name}"\n></iframe>`;
  const jsCode = `<div id="ukip-widget-${token.slice(0, 8)}"></div>\n<script>\n  fetch('${apiBase}/embed/${token}/data')\n    .then(r => r.json())\n    .then(d => {\n      document.getElementById('ukip-widget-${token.slice(0, 8)}').textContent =\n        JSON.stringify(d.data, null, 2);\n    });\n</script>`;

  const code = tab === "iframe" ? iframeCode : jsCode;

  const copy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-2xl rounded-xl bg-white shadow-2xl dark:border dark:border-slate-800 dark:bg-slate-950">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 dark:border-slate-800">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{t("page.widgets.embed.title", { name: widget.name })}</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-6 space-y-4">
          {/* Public data URL */}
          <div>
            <p className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400">{t("page.widgets.embed.public_data_url")}</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 truncate rounded bg-slate-100 px-3 py-2 text-xs font-mono text-slate-700 dark:bg-slate-900 dark:text-slate-300">
                {apiBase}/embed/{token}/data
              </code>
              <button
                onClick={() => { navigator.clipboard.writeText(`${apiBase}/embed/${token}/data`); }}
                className="whitespace-nowrap text-xs text-violet-600 hover:text-violet-800 dark:text-violet-400 dark:hover:text-violet-300"
              >
                {t("page.widgets.embed.copy_url")}
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex w-fit gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-900">
            {(["iframe", "js"] as const).map((tabOption) => (
              <button
                key={tabOption}
                onClick={() => setTab(tabOption)}
                className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${tab === tabOption ? "bg-white text-slate-900 shadow dark:bg-slate-800 dark:text-slate-100" : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"}`}
              >
                {tabOption === "iframe" ? "iFrame" : t("page.widgets.embed.javascript")}
              </button>
            ))}
          </div>

          {/* Code block */}
          <div className="relative">
            <pre className="rounded-lg bg-slate-900 text-slate-100 p-4 text-xs font-mono overflow-x-auto whitespace-pre-wrap">
              {code}
            </pre>
            <button
              onClick={copy}
              className="absolute top-2 right-2 rounded px-2 py-1 text-xs bg-slate-700 text-slate-200 hover:bg-slate-600"
            >
              {copied ? t("page.widgets.embed.copied") : t("common.copy")}
            </button>
          </div>

          <p className="text-xs text-slate-400 dark:text-slate-500">
            {t("page.widgets.embed.replace_localhost_prefix")} <code className="rounded bg-slate-100 px-1 dark:bg-slate-900">localhost:8000</code> {t("page.widgets.embed.replace_localhost_suffix")}
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────

export default function WidgetsPage() {
  const { t } = useLanguage();
  const [widgets, setWidgets] = useState<Widget[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<Widget | null>(null);
  const [embedFor, setEmbedFor] = useState<Widget | null>(null);
  const [error, setError] = useState("");
  const widgetMeta = getWidgetMeta(t);

  const apiBase = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

  const load = useCallback(() => {
    setLoading(true);
    apiFetch("/widgets")
      .then((r) => r.json())
      .then((d) => setWidgets(d.items || []))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (data: object) => {
    try {
      const resp = await apiFetch("/widgets", { method: "POST", body: JSON.stringify(data) });
      if (!resp.ok) throw new Error(await resp.text());
      setShowCreate(false);
      load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : t("page.widgets.error_create")); }
  };

  const handleUpdate = async (data: object) => {
    if (!editing) return;
    try {
      const resp = await apiFetch(`/widgets/${editing.id}`, { method: "PUT", body: JSON.stringify(data) });
      if (!resp.ok) throw new Error(await resp.text());
      setEditing(null);
      load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : t("page.widgets.error_update")); }
  };

  const handleDelete = async (id: number) => {
    if (!confirm(t("page.widgets.delete_confirm"))) return;
    try {
      await apiFetch(`/widgets/${id}`, { method: "DELETE" });
      load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : t("page.widgets.error_delete")); }
  };

  const handleToggle = async (w: Widget) => {
    try {
      const resp = await apiFetch(`/widgets/${w.id}`, { method: "PUT", body: JSON.stringify({ is_active: !w.is_active }) });
      if (!resp.ok) throw new Error(await resp.text());
      load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : t("page.widgets.error_toggle")); }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-violet-50 p-6 dark:from-slate-950 dark:to-slate-900">
      <div className="mx-auto max-w-5xl space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">{t("page.widgets.title")}</h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {t("page.widgets.subtitle")}
            </p>
          </div>
          <button
            onClick={() => { setShowCreate(true); setEditing(null); }}
            className="flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-violet-700 shadow-sm"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            {t("page.widgets.new_widget")}
          </button>
        </div>

        {error && (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/30 dark:bg-rose-950/20 dark:text-rose-300">
            {error}
          </div>
        )}

        {/* Form */}
        {(showCreate || editing) && (
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <h2 className="mb-5 text-lg font-semibold text-slate-900 dark:text-slate-100">
              {editing ? t("page.widgets.edit_widget") : t("page.widgets.new_widget")}
            </h2>
            <WidgetForm
              initial={editing ?? undefined}
              onSave={editing ? handleUpdate : handleCreate}
              onCancel={() => { setShowCreate(false); setEditing(null); }}
            />
          </div>
        )}

        {/* Widget grid */}
        {loading ? (
          <div className="py-16 text-center text-slate-400 dark:text-slate-500">{t("page.widgets.loading")}</div>
        ) : widgets.length === 0 && !showCreate ? (
          <div className="rounded-xl border border-slate-200 bg-white p-16 text-center dark:border-slate-800 dark:bg-slate-950">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-violet-100 text-3xl dark:bg-violet-900/30">
              🧩
            </div>
            <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100">{t("page.widgets.empty_title")}</h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{t("page.widgets.empty_description")}</p>
            <button
              onClick={() => setShowCreate(true)}
              className="mt-4 rounded-lg bg-violet-600 px-5 py-2 text-sm font-medium text-white hover:bg-violet-700"
            >
              {t("page.widgets.create_widget")}
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {widgets.map((w) => {
              const meta = widgetMeta[w.widget_type];
              return (
                <div
                  key={w.id}
                  className={`rounded-xl border bg-white p-5 shadow-sm transition-opacity dark:bg-slate-950 ${w.is_active ? "border-slate-200 dark:border-slate-800" : "border-slate-100 opacity-60 dark:border-slate-900"}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="text-xl">{meta?.icon}</span>
                        <h3 className="truncate font-semibold text-slate-900 dark:text-slate-100">{w.name}</h3>
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${meta?.color || "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"}`}>
                          {meta?.label}
                        </span>
                        {!w.is_active && (
                          <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                            {t("common.inactive")}
                          </span>
                        )}
                      </div>
                      <p className="mb-2 text-xs text-slate-400 dark:text-slate-500">{meta?.description}</p>
                      <div className="flex items-center gap-3 text-xs text-slate-400 dark:text-slate-500">
                        <span>{t("page.widgets.views", { count: w.view_count })}</span>
                        {w.last_viewed_at && (
                          <span>{t("page.widgets.last_viewed", { date: formatDate(w.last_viewed_at) })}</span>
                        )}
                        {w.allowed_origins !== "*" && (
                          <span className="truncate max-w-[120px]" title={w.allowed_origins}>
                            🔒 {w.allowed_origins}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Active toggle */}
                    <button
                      onClick={() => handleToggle(w)}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors shrink-0 ${w.is_active ? "bg-violet-600" : "bg-slate-300"}`}
                    >
                      <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${w.is_active ? "translate-x-4" : "translate-x-1"}`} />
                    </button>
                  </div>

                  {/* Token */}
                  <div className="mt-3 flex items-center gap-2 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-900/80">
                    <code className="flex-1 truncate text-xs font-mono text-slate-500 dark:text-slate-400">{w.public_token}</code>
                    <button
                      onClick={() => navigator.clipboard.writeText(w.public_token)}
                      className="whitespace-nowrap text-xs text-violet-500 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300"
                    >
                      {t("common.copy")}
                    </button>
                  </div>

                  {/* Actions */}
                  <div className="mt-3 flex items-center justify-end gap-2">
                    <button
                      onClick={() => setEmbedFor(w)}
                      className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:border-violet-200 hover:text-violet-600 dark:border-slate-800 dark:text-slate-300 dark:hover:border-violet-700 dark:hover:text-violet-300"
                    >
                      <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
                      </svg>
                      {t("page.widgets.embed.button")}
                    </button>
                    <button
                      onClick={() => { setEditing(w); setShowCreate(false); }}
                      aria-label={t("common.edit")}
                      className="rounded-lg border border-slate-200 p-1.5 text-slate-500 hover:border-violet-300 hover:text-violet-600 dark:border-slate-800 dark:text-slate-400 dark:hover:border-violet-700 dark:hover:text-violet-300"
                    >
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                      </svg>
                    </button>
                    <button
                      onClick={() => handleDelete(w.id)}
                      aria-label={t("common.delete")}
                      className="rounded-lg border border-slate-200 p-1.5 text-slate-500 hover:border-rose-200 hover:text-rose-600 dark:border-slate-800 dark:text-slate-400 dark:hover:border-rose-800 dark:hover:text-rose-300"
                    >
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                      </svg>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {embedFor && (
        <EmbedPanel widget={embedFor} apiBase={apiBase} onClose={() => setEmbedFor(null)} />
      )}
    </div>
  );
}
