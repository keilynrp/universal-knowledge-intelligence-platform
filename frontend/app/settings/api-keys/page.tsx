"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { formatDate } from "../../lib/dateFormat";
import { useLanguage } from "../../contexts/LanguageContext";
import { useToast } from "../../components/ui";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ApiKey {
  id: number;
  name: string;
  key_prefix: string;
  key?: string;         // only present on creation
  scopes: string[];
  is_active: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  created_at: string | null;
}

interface ScopeDef {
  id: string;
  label: string;
  description: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const SCOPE_COLORS: Record<string, string> = {
  read:  "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  write: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  admin: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
};

function fmtDate(iso: string | null): string {
  return formatDate(iso, undefined, { dateStyle: "medium" }, "Never");
}

// ── Copy helper ───────────────────────────────────────────────────────────────

function CopyButton({ text, idleLabel, doneLabel }: { text: string; idleLabel: string; doneLabel: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <button
      onClick={copy}
      className="ml-2 rounded px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
    >
      {copied ? doneLabel : idleLabel}
    </button>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ApiKeysPage() {
  const { t } = useLanguage();
  const { toast } = useToast();
  const [keys, setKeys]         = useState<ApiKey[]>([]);
  const [scopes, setScopes]     = useState<ScopeDef[]>([]);
  const [loading, setLoading]   = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [newKey, setNewKey]     = useState<ApiKey | null>(null);  // shown once after creation
  const [form, setForm]         = useState({
    name: "",
    scopes: ["read"] as string[],
    expires_days: "" as string,
  });
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState<string | null>(null);
  // null = unknown (probe failed). Only an explicit `false` warns, so a
  // transient /health failure never claims scopes are unenforced.
  const [scopesEnforced, setScopesEnforced] = useState<boolean | null>(null);
  const tr = useCallback((key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  }, [t]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [kRes, sRes, hRes] = await Promise.all([
        apiFetch("/api-keys"),
        apiFetch("/api-keys/scopes"),
        apiFetch("/health"),
      ]);
      if (kRes.ok) setKeys(await kRes.json());
      if (sRes.ok) setScopes(await sRes.json());
      if (hRes.ok) {
        const health = await hRes.json();
        const enforced = health?.features?.api_key_scopes_enforced;
        setScopesEnforced(typeof enforced === "boolean" ? enforced : null);
      }
    } catch {
      toast(tr("page.settings_api_keys.toast.load_failed", "Could not load API keys right now."), "error");
    }
    setLoading(false);
  }, [toast, tr]);

  useEffect(() => { load(); }, [load]);

  function toggleScope(id: string) {
    setForm((f) => ({
      ...f,
      scopes: f.scopes.includes(id) ? f.scopes.filter((s) => s !== id) : [...f.scopes, id],
    }));
  }

  async function handleCreate() {
    setError(null);
    setSaving(true);
    const body: Record<string, unknown> = {
      name: form.name.trim(),
      scopes: form.scopes,
    };
    if (form.expires_days) body.expires_days = Number(form.expires_days);

    try {
      const res = await apiFetch("/api-keys", { method: "POST", body: JSON.stringify(body) });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail ?? `Error ${res.status}`);
        return;
      }
      const created: ApiKey = await res.json();
      setNewKey(created);
      setShowForm(false);
      setForm({ name: "", scopes: ["read"], expires_days: "" });
      toast(tr("page.settings_api_keys.toast.created", "API key created. Copy it now before you leave this screen."), "success");
      await load();
    } catch {
      const message = tr("page.settings_api_keys.error.network", "Network error");
      setError(message);
      toast(message, "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleRevoke(id: number, name: string) {
    if (!confirm(tr("page.settings_api_keys.confirm.revoke", `Revoke key "${name}"? Any script or integration using it will lose access immediately.`))) return;
    const res = await apiFetch(`/api-keys/${id}`, { method: "DELETE" });
    if (res.ok) {
      toast(tr("page.settings_api_keys.toast.revoked", `Key "${name}" revoked.`), "warning");
      await load();
      return;
    }
    toast(tr("page.settings_api_keys.toast.revoke_failed", "Could not revoke this key."), "error");
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">API Keys</h2>
          <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
            {tr("page.settings_api_keys.subtitle", "Long-lived tokens for programmatic access to the UKIP API.")}
          </p>
        </div>
        <button
          onClick={() => { setShowForm(true); setError(null); }}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          {tr("page.settings_api_keys.create", "Generate Key")}
        </button>
      </div>

      {/* Security notice */}
      <div className="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 dark:border-blue-800/40 dark:bg-blue-900/10">
        <svg className="mt-0.5 h-4 w-4 shrink-0 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
        <p className="text-sm text-blue-700 dark:text-blue-300">
          {tr("page.settings_api_keys.notice", "API keys are shown once at creation. Store them securely because they cannot be recovered later.")}{" "}
          {tr("page.settings_api_keys.notice_auth", "Use")} <code className="rounded bg-blue-100 px-1 text-xs dark:bg-blue-900/40">Authorization: Bearer &lt;key&gt;</code> {tr("page.settings_api_keys.notice_requests", "in your requests.")}
        </p>
      </div>

      {/* New key reveal banner */}
      {newKey?.key && (
        <div className="rounded-xl border border-green-200 bg-green-50 p-4 dark:border-green-800/40 dark:bg-green-900/10">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-green-700 dark:text-green-300">
              {tr("page.settings_api_keys.created_title", "✓ Key created — copy it now, it won’t be shown again")}
            </p>
            <button onClick={() => setNewKey(null)} className="text-green-600 hover:text-green-800 dark:text-green-400">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </div>
          <div className="mt-2 flex items-center">
            <code className="flex-1 rounded-lg bg-white px-3 py-2 font-mono text-sm text-gray-900 dark:bg-gray-900 dark:text-gray-100 break-all">
              {newKey.key}
            </code>
            <CopyButton
              text={newKey.key}
              idleLabel={tr("page.settings_api_keys.copy", "Copy")}
              doneLabel={tr("page.settings_api_keys.copied", "✓ Copied")}
            />
          </div>
        </div>
      )}

      {/* Keys table */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => <div key={i} className="h-14 animate-pulse rounded-lg bg-gray-100 dark:bg-gray-800" />)}
        </div>
      ) : keys.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-200 py-16 text-center dark:border-gray-700">
          <svg className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">{tr("page.settings_api_keys.empty_title", "No API keys yet")}</p>
          <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
            {tr("page.settings_api_keys.empty_body", "Create one when you need scripts, automations, or external services to call the UKIP API.")}
          </p>
          <button onClick={() => setShowForm(true)} className="mt-3 text-sm font-medium text-blue-600 hover:underline dark:text-blue-400">
            {tr("page.settings_api_keys.empty_cta", "Generate your first key →")}
          </button>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-700">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800/60">
              <tr>
                {["Name", "Key prefix", "Scopes", "Last used", "Expires", "Created", ""].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {keys.map((k) => (
                <tr key={k.id} className={`hover:bg-gray-50 dark:hover:bg-gray-800/40 ${!k.is_active ? "opacity-50" : ""}`}>
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                    {k.name}
                    {!k.is_active && <span className="ml-2 text-xs text-gray-400">(revoked)</span>}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500 dark:text-gray-400">
                    {k.key_prefix}…
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {k.scopes.map((s) => (
                        <span key={s} className={`rounded px-1.5 py-0.5 text-xs font-semibold ${SCOPE_COLORS[s] ?? ""}`}>
                          {s}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{fmtDate(k.last_used_at)}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                    {k.expires_at
                      ? <span className={new Date(k.expires_at) < new Date() ? "text-red-500" : ""}>{fmtDate(k.expires_at)}</span>
                      : <span className="text-gray-400">Never</span>
                    }
                  </td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{fmtDate(k.created_at)}</td>
                  <td className="px-4 py-3">
                    {k.is_active && (
                      <button
                        onClick={() => handleRevoke(k.id, k.name)}
                        className="rounded-lg border border-red-200 px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 dark:border-red-800/40 dark:text-red-400 dark:hover:bg-red-900/20"
                      >
                        {tr("page.settings_api_keys.revoke", "Revoke")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create form modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl dark:bg-gray-900">
            <div className="mb-5 flex items-center justify-between">
              <h3 className="text-base font-semibold text-gray-900 dark:text-white">{tr("page.settings_api_keys.modal_title", "Generate API Key")}</h3>
              <button onClick={() => setShowForm(false)} className="rounded p-1 text-gray-400 hover:text-gray-600">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>

            {error && <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">{error}</div>}

            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">{tr("page.settings_api_keys.name", "Key Name")} <span className="text-red-500">*</span></label>
                <input
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder={tr("page.settings_api_keys.name_placeholder", "e.g. CI/CD Pipeline, Partner Integration")}
                  className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 outline-none focus:border-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300">{tr("page.settings_api_keys.scopes", "Scopes")}</label>
                {scopesEnforced === false && (
                  <p className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-500/10 dark:text-amber-300">
                    {tr(
                      "page.settings_api_keys.scopes_warn_mode",
                      "Scope enforcement is off on this deployment. Scopes are recorded and violations are audited, but they do not yet restrict what a key can do.",
                    )}
                  </p>
                )}
                <div className="space-y-2">
                  {scopes.map((s) => (
                    <label key={s.id} className="flex items-start gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={form.scopes.includes(s.id)}
                        onChange={() => toggleScope(s.id)}
                        className="mt-0.5 h-4 w-4 rounded border-gray-300 text-blue-600"
                      />
                      <div>
                        <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{s.label}</p>
                        <p className="text-xs text-gray-400">{s.description}</p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                  {tr("page.settings_api_keys.expiry", "Expiry")} <span className="font-normal text-gray-400">{tr("page.settings_api_keys.expiry_hint", "(days, optional)")}</span>
                </label>
                <input
                  type="number"
                  value={form.expires_days}
                  onChange={(e) => setForm((f) => ({ ...f, expires_days: e.target.value }))}
                  placeholder={tr("page.settings_api_keys.expiry_placeholder", "e.g. 90 — leave blank for no expiry")}
                  min={1}
                  max={3650}
                  className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 outline-none focus:border-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                />
              </div>
            </div>

            <div className="mt-5 flex items-center justify-end gap-3">
              <button onClick={() => setShowForm(false)} className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300">{tr("common.cancel", "Cancel")}</button>
              <button
                onClick={handleCreate}
                disabled={saving || !form.name.trim() || form.scopes.length === 0}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? tr("page.settings_api_keys.generating", "Generating…") : tr("page.settings_api_keys.create", "Generate Key")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Code example */}
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/40">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Usage Example</p>
        <pre className="overflow-x-auto rounded-lg bg-gray-900 p-3 text-xs text-green-400">
{`curl -H "Authorization: Bearer ukip_<your_key>" \\
     "${typeof window !== "undefined" ? (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000") : "http://localhost:8000"}/entities?domain_id=default"`}
        </pre>
      </div>
    </div>
  );
}
