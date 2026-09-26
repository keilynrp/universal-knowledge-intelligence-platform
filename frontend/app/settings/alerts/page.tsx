"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { formatDate } from "../../lib/dateFormat";
import { useLanguage } from "../../contexts/LanguageContext";
import { Input, useToast } from "../../components/ui";

// ── Types ─────────────────────────────────────────────────────────────────────

type ChannelType = "slack" | "teams" | "discord" | "webhook" | "pushover";

interface AlertChannel {
  id: number;
  name: string;
  type: ChannelType;
  events: string[];
  is_active: boolean;
  last_fired_at: string | null;
  last_fire_status: string | null;
  total_fired: number;
  created_at: string | null;
}

interface AlertEvent {
  id: string;
  label: string;
  description: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const TYPE_LABELS: Record<string, string> = {
  slack:   "Slack",
  teams:   "Microsoft Teams",
  discord: "Discord",
  webhook: "Generic Webhook",
  pushover: "Pushover (pages a phone)",
};

const TYPE_COLORS: Record<string, string> = {
  slack:   "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  teams:   "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  discord: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400",
  webhook: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  pushover: "bg-[var(--ukip-danger-soft)] text-[var(--ukip-danger)]",
};

const TYPE_ICONS: Record<string, string> = {
  slack:   "M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 00-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0020 4.77 5.07 5.07 0 0019.91 1S18.73.65 16 2.48a13.38 13.38 0 00-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 005 4.77a5.44 5.44 0 00-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 009 18.13V22",
  teams:   "M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8zM23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75",
  discord: "M20.317 4.37a19.791 19.791 0 00-4.885-1.515.074.074 0 00-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 00-5.487 0 12.64 12.64 0 00-.617-1.25.077.077 0 00-.079-.037A19.736 19.736 0 003.677 4.37a.07.07 0 00-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 00.031.057 19.9 19.9 0 005.993 3.03.078.078 0 00.084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 00-.041-.106 13.107 13.107 0 01-1.872-.892.077.077 0 01-.008-.128 10.2 10.2 0 00.372-.292.074.074 0 01.077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 01.078.01c.12.098.246.198.373.292a.077.077 0 01-.006.127 12.299 12.299 0 01-1.873.892.077.077 0 00-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 00.084.028 19.839 19.839 0 006.002-3.03.077.077 0 00.032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 00-.031-.03z",
  webhook: "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1",
  pushover: "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9",
};

const EMPTY_FORM = {
  name: "",
  type: "slack" as ChannelType,
  webhook_url: "",
  pushover_token: "",
  pushover_user: "",
  events: [] as string[],
};

// ── Main component ────────────────────────────────────────────────────────────

export default function AlertsPage() {
  const { t } = useLanguage();
  const { toast } = useToast();
  const [channels, setChannels]   = useState<AlertChannel[]>([]);
  const [events, setEvents]       = useState<AlertEvent[]>([]);
  const [loading, setLoading]     = useState(true);
  const [showForm, setShowForm]   = useState(false);
  const [editId, setEditId]       = useState<number | null>(null);
  const [form, setForm]           = useState({ ...EMPTY_FORM });
  const [saving, setSaving]       = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [testing, setTesting]     = useState<number | null>(null);
  const [testResult, setTestResult] = useState<Record<number, boolean | null>>({});
  const tr = useCallback((key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  }, [t]);

  const load = useCallback(async () => {
    setLoading(true);
    const [cRes, eRes] = await Promise.all([
      apiFetch("/alert-channels"),
      apiFetch("/alert-channels/events"),
    ]);
    if (cRes.ok) setChannels(await cRes.json());
    if (eRes.ok) setEvents(await eRes.json());
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  function openCreate() {
    setEditId(null);
    setForm({ ...EMPTY_FORM });
    setError(null);
    setShowForm(true);
  }

  function openEdit(c: AlertChannel) {
    setEditId(c.id);
    setForm({ ...EMPTY_FORM, name: c.name, type: c.type, events: c.events });
    setError(null);
    setShowForm(true);
  }

  function toggleEvent(id: string) {
    setForm((f) => ({
      ...f,
      events: f.events.includes(id) ? f.events.filter((e) => e !== id) : [...f.events, id],
    }));
  }

  async function handleSave() {
    setError(null);
    setSaving(true);
    const body: Record<string, unknown> = {
      name: form.name.trim(),
      type: form.type,
      events: form.events,
    };
    if (form.type === "pushover") {
      if (form.pushover_token) body.pushover_token = form.pushover_token.trim();
      if (form.pushover_user) body.pushover_user = form.pushover_user.trim();
    } else if (form.webhook_url) {
      body.webhook_url = form.webhook_url;
    }

    try {
      const res = editId !== null
        ? await apiFetch(`/alert-channels/${editId}`, { method: "PUT", body: JSON.stringify(body) })
        : await apiFetch("/alert-channels", { method: "POST", body: JSON.stringify(body) });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail ?? `Error ${res.status}`);
        return;
      }
      setShowForm(false);
      await load();
    } catch {
      setError(tr("page.settings_alerts.error.network", "Network error"));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm(tr("page.settings_alerts.confirm.delete", "Delete this alert channel?"))) return;
    const res = await apiFetch(`/alert-channels/${id}`, { method: "DELETE" });
    if (res.ok) {
      toast(tr("page.settings_alerts.toast.deleted", "Alert channel deleted"), "warning");
      await load();
      return;
    }
    toast(tr("page.settings_alerts.toast.delete_failed", "Could not delete this alert channel"), "error");
  }

  async function handleToggle(c: AlertChannel) {
    const res = await apiFetch(`/alert-channels/${c.id}`, {
      method: "PUT",
      body: JSON.stringify({ is_active: !c.is_active }),
    });
    if (res.ok) {
      toast(c.is_active ? tr("page.settings_alerts.toast.paused", "Channel paused") : tr("page.settings_alerts.toast.activated", "Channel activated"), "success");
      await load();
      return;
    }
    toast(tr("page.settings_alerts.toast.toggle_failed", "Could not update this channel"), "error");
  }

  async function handleTest(id: number) {
    setTesting(id);
    setTestResult((prev) => ({ ...prev, [id]: null }));
    try {
      const res = await apiFetch(`/alert-channels/${id}/test`, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      setTestResult((prev) => ({ ...prev, [id]: data.success === true }));
      toast(data.success ? tr("page.settings_alerts.toast.test_sent", "Test sent") : tr("page.settings_alerts.toast.test_failed", "Test failed"), data.success ? "success" : "warning");
    } finally {
      setTesting(null);
    }
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">{tr("page.settings_alerts.title", "Alert Channels")}</h2>
          <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
            {tr("page.settings_alerts.subtitle", "Push platform events to Slack, Teams, Discord, or any webhook.")}
          </p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          {tr("page.settings_alerts.add_channel", "Add Channel")}
        </button>
      </div>

      {/* Channel cards */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => <div key={i} className="h-24 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />)}
        </div>
      ) : channels.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-200 py-16 text-center dark:border-gray-700">
          <svg className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">{tr("page.settings_alerts.empty_title", "No alert channels configured")}</p>
          <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">{tr("page.settings_alerts.empty_body", "Create one when you want external teams or systems to react to key platform events.")}</p>
          <button onClick={openCreate} className="mt-3 text-sm font-medium text-blue-600 hover:underline dark:text-blue-400">
            {tr("page.settings_alerts.empty_cta", "Add your first channel →")}
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {channels.map((c) => (
            <div
              key={c.id}
              className={`rounded-xl border bg-white p-4 shadow-sm dark:bg-gray-900 ${c.is_active ? "border-gray-200 dark:border-gray-700" : "border-gray-100 opacity-60 dark:border-gray-800"}`}
            >
              <div className="flex items-start gap-4">
                {/* Icon */}
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-800">
                  <svg className="h-5 w-5 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={TYPE_ICONS[c.type] ?? TYPE_ICONS.webhook} />
                  </svg>
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-gray-900 dark:text-white">{c.name}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${TYPE_COLORS[c.type]}`}>
                      {TYPE_LABELS[c.type]}
                    </span>
                    {!c.is_active && (
                      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500 dark:bg-gray-800">
                        Paused
                      </span>
                    )}
                    {c.last_fire_status === "error" && (
                      <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-600 dark:bg-red-900/30 dark:text-red-400">
                        Last: error
                      </span>
                    )}
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {c.events.length === 0
                      ? <span className="text-xs text-gray-400">No events subscribed</span>
                      : c.events.map((e) => (
                          <span key={e} className="rounded px-1.5 py-0.5 text-[10px] bg-violet-50 text-violet-600 dark:bg-violet-900/20 dark:text-violet-400">
                            {e}
                          </span>
                        ))
                    }
                  </div>
                  <p className="mt-1 text-xs text-gray-400">
                    {c.total_fired} alerts fired
                    {c.last_fired_at && ` · last ${formatDate(c.last_fired_at)}`}
                  </p>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1.5 shrink-0">
                  {testResult[c.id] === true && <span className="text-xs text-green-600 dark:text-green-400">✓ sent</span>}
                  {testResult[c.id] === false && <span className="text-xs text-red-600 dark:text-red-400">✗ failed</span>}
                  <button
                    onClick={() => handleTest(c.id)}
                    disabled={testing === c.id}
                    title="Send test"
                    className="rounded-lg border border-gray-200 px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-40 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800"
                  >
                    {testing === c.id ? "…" : "Test"}
                  </button>
                  <button
                    onClick={() => handleToggle(c)}
                    title={c.is_active ? "Pause" : "Resume"}
                    className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-700"
                  >
                    {c.is_active
                      ? <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      : <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    }
                  </button>
                  <button onClick={() => openEdit(c)} title="Edit" className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-700">
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                  </button>
                  <button onClick={() => handleDelete(c.id)} title="Delete" className="rounded p-1.5 text-red-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20">
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create / Edit slide-over */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex">
          <div className="fixed inset-0 bg-black/40" onClick={() => setShowForm(false)} />
          <div className="relative ml-auto flex h-full w-full max-w-lg flex-col bg-white shadow-xl dark:bg-gray-900">
            <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
              <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                {editId !== null ? "Edit Channel" : "Add Alert Channel"}
              </h3>
              <button onClick={() => setShowForm(false)} className="rounded p-1 text-gray-400 hover:text-gray-600">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
              {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">{error}</div>}

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Name <span className="text-red-500">*</span></label>
                <input
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. #engineering-alerts"
                  className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 outline-none focus:border-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Channel Type</label>
                <div className="grid grid-cols-2 gap-2">
                  {(["slack", "teams", "discord", "webhook", "pushover"] as const).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, type: t }))}
                      className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${form.type === t ? "border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300" : "border-gray-200 text-gray-600 hover:border-blue-300 dark:border-gray-700 dark:text-gray-400"}`}
                    >
                      {TYPE_LABELS[t]}
                    </button>
                  ))}
                </div>
              </div>

              {form.type === "pushover" ? (
                <div className="space-y-3">
                  <Input
                    id="pushover-token"
                    label={tr("page.settings_alerts.pushover_token", "Pushover application token")}
                    type="password"
                    autoComplete="off"
                    value={form.pushover_token}
                    onChange={(e) => setForm((f) => ({ ...f, pushover_token: e.target.value }))}
                    hint={editId !== null ? tr("page.settings_alerts.keep_existing", "Leave both blank to keep the existing keys") : undefined}
                  />
                  <Input
                    id="pushover-user"
                    label={tr("page.settings_alerts.pushover_user", "Pushover user key")}
                    type="password"
                    autoComplete="off"
                    value={form.pushover_user}
                    onChange={(e) => setForm((f) => ({ ...f, pushover_user: e.target.value }))}
                  />
                  <p className="text-xs text-[var(--ukip-muted)]">
                    {tr(
                      "page.settings_alerts.pushover_hint",
                      "Critical database or migration failures page this phone at emergency priority: it breaks through Do Not Disturb and repeats until acknowledged. Test sends a real emergency that stops after a minute; try it with the phone in Do Not Disturb.",
                    )}
                  </p>
                </div>
              ) : (
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Webhook URL {editId === null && <span className="text-red-500">*</span>}
                  {editId !== null && <span className="text-gray-400 font-normal"> (leave blank to keep existing)</span>}
                </label>
                <input
                  value={form.webhook_url}
                  onChange={(e) => setForm((f) => ({ ...f, webhook_url: e.target.value }))}
                  placeholder={form.type === "slack" ? "https://hooks.slack.com/services/…" : form.type === "teams" ? "https://outlook.office.com/webhook/…" : "https://…"}
                  className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-mono text-gray-800 outline-none focus:border-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                />
              </div>
              )}

              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Subscribe to Events
                </label>
                <div className="space-y-2">
                  {events.map((e) => (
                    <label key={e.id} className="flex items-start gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={form.events.includes(e.id)}
                        onChange={() => toggleEvent(e.id)}
                        className="mt-0.5 h-4 w-4 rounded border-gray-300 text-blue-600"
                      />
                      <div>
                        <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{e.label}</p>
                        <p className="text-xs text-gray-400">{e.description}</p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-700">
              <button onClick={() => setShowForm(false)} className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300">Cancel</button>
              <button
                onClick={handleSave}
                disabled={
                  saving
                  || !form.name.trim()
                  || (editId === null && form.type !== "pushover" && !form.webhook_url)
                  || (editId === null && form.type === "pushover" && (!form.pushover_token || !form.pushover_user))
                }
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? "Saving…" : editId !== null ? "Save Changes" : "Add Channel"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
