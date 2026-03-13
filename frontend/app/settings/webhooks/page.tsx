"use client";

import { useState, useEffect, useCallback } from "react";
import { PageHeader, StatCard, Badge, useToast } from "../../components/ui";
import { apiFetch } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

interface WebhookRecord {
    id: number;
    url: string;
    events: string[];
    is_active: boolean;
    created_at: string | null;
    last_triggered_at: string | null;
    last_status: number | null;
}

interface WebhookStats {
    total: number;
    active: number;
    inactive: number;
    failing: number;
    total_deliveries: number;
}

interface DeliveryRecord {
    id: number;
    webhook_id: number;
    event: string;
    url: string;
    status_code: number | null;
    response_body: string | null;
    latency_ms: number | null;
    error: string | null;
    success: boolean;
    created_at: string | null;
}

interface TestResult {
    delivery_id: number;
    status_code: number;
    latency_ms: number;
    success: boolean;
    error: string | null;
    response_preview: string | null;
}

// ── Constants ────────────────────────────────────────────────────────────────

const ALL_EVENTS = [
    "upload",
    "entity.update",
    "entity.delete",
    "entity.bulk_delete",
    "harmonization.apply",
    "authority.confirm",
    "authority.reject",
    "ping",
];

const EVENT_LABELS: Record<string, { label: string; color: string }> = {
    "upload":               { label: "Upload",            color: "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400" },
    "entity.update":        { label: "Entity Update",     color: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400" },
    "entity.delete":        { label: "Entity Delete",     color: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400" },
    "entity.bulk_delete":   { label: "Bulk Delete",       color: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400" },
    "harmonization.apply":  { label: "Harmonization",     color: "bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-400" },
    "authority.confirm":    { label: "Auth Confirm",      color: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400" },
    "authority.reject":     { label: "Auth Reject",       color: "bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-400" },
    "ping":                 { label: "Ping",              color: "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300" },
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function statusBadge(code: number | null) {
    if (code === null || code === undefined) return <Badge variant="default">—</Badge>;
    if (code >= 200 && code < 300) return <Badge variant="success">{code}</Badge>;
    if (code >= 400 && code < 500) return <Badge variant="warning">{code}</Badge>;
    return <Badge variant="error">{code || "ERR"}</Badge>;
}

function timeAgo(iso: string | null): string {
    if (!iso) return "Never";
    const diff = Date.now() - new Date(iso).getTime();
    const sec = Math.floor(diff / 1000);
    if (sec < 60) return `${sec}s ago`;
    const min = Math.floor(sec / 60);
    if (min < 60) return `${min}m ago`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr}h ago`;
    const days = Math.floor(hr / 24);
    return `${days}d ago`;
}

const inputClass = "h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none transition-colors focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:border-gray-700 dark:bg-gray-800 dark:text-white dark:focus:border-indigo-400";

// ── Icons ────────────────────────────────────────────────────────────────────

function WebhookIcon({ className = "h-5 w-5" }: { className?: string }) {
    return (
        <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
        </svg>
    );
}

function PlusIcon() {
    return (
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
    );
}

function CloseIcon() {
    return (
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
    );
}

function TrashIcon() {
    return (
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
        </svg>
    );
}

function ChevronIcon({ open }: { open: boolean }) {
    return (
        <svg className={`h-4 w-4 transition-transform duration-200 ${open ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
    );
}

function Spinner({ className = "h-4 w-4" }: { className?: string }) {
    return (
        <svg className={`${className} animate-spin`} fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
    );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function WebhooksPage() {
    const { toast } = useToast();
    const [hooks, setHooks] = useState<WebhookRecord[]>([]);
    const [stats, setStats] = useState<WebhookStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [showCreate, setShowCreate] = useState(false);
    const [expandedId, setExpandedId] = useState<number | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [hooksRes, statsRes] = await Promise.all([
                apiFetch("/webhooks"),
                apiFetch("/webhooks/stats"),
            ]);
            if (hooksRes.ok) setHooks(await hooksRes.json());
            if (statsRes.ok) setStats(await statsRes.json());
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    return (
        <div className="space-y-6">
            <PageHeader
                breadcrumbs={[
                    { label: "Home", href: "/" },
                    { label: "Settings", href: "/settings" },
                    { label: "Webhooks" },
                ]}
                title="Webhooks"
                description="Manage outbound HTTP callbacks fired on platform events"
            />

            {/* Stats cards */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <StatCard
                    icon={<WebhookIcon />}
                    iconColor="blue"
                    label="Total Webhooks"
                    value={stats?.total ?? "—"}
                />
                <StatCard
                    icon={
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    }
                    iconColor="emerald"
                    label="Active"
                    value={stats?.active ?? "—"}
                />
                <StatCard
                    icon={
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
                        </svg>
                    }
                    iconColor="red"
                    label="Failing"
                    value={stats?.failing ?? "—"}
                />
                <StatCard
                    icon={
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                        </svg>
                    }
                    iconColor="violet"
                    label="Total Deliveries"
                    value={stats?.total_deliveries ?? "—"}
                />
            </div>

            {/* Action bar */}
            <div className="flex items-center justify-between">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                    {hooks.filter(h => h.is_active).length} active · {hooks.filter(h => !h.is_active).length} inactive
                </p>
                <button
                    onClick={() => setShowCreate(s => !s)}
                    className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-indigo-700 hover:shadow-md active:scale-[0.98]"
                >
                    {showCreate ? <CloseIcon /> : <PlusIcon />}
                    {showCreate ? "Cancel" : "New Webhook"}
                </button>
            </div>

            {/* Create form */}
            {showCreate && (
                <CreateWebhookForm
                    onCreated={() => { setShowCreate(false); load(); }}
                    onCancel={() => setShowCreate(false)}
                    toast={toast}
                />
            )}

            {/* Webhook list */}
            {loading ? (
                <div className="flex items-center justify-center py-16">
                    <Spinner className="h-7 w-7 text-indigo-600" />
                </div>
            ) : hooks.length === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-gray-200 py-16 dark:border-gray-700">
                    <WebhookIcon className="h-12 w-12 text-gray-300 dark:text-gray-600" />
                    <p className="mt-4 text-sm font-medium text-gray-500 dark:text-gray-400">No webhooks configured yet</p>
                    <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">Create one to receive event notifications via HTTP</p>
                </div>
            ) : (
                <div className="space-y-3">
                    {hooks.map(hook => (
                        <WebhookCard
                            key={hook.id}
                            hook={hook}
                            expanded={expandedId === hook.id}
                            onToggleExpand={() => setExpandedId(expandedId === hook.id ? null : hook.id)}
                            onReload={load}
                            toast={toast}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

// ── Create Form ──────────────────────────────────────────────────────────────

function CreateWebhookForm({
    onCreated,
    onCancel,
    toast,
}: {
    onCreated: () => void;
    onCancel: () => void;
    toast: (msg: string, v?: "success" | "error" | "warning" | "info") => void;
}) {
    const [form, setForm] = useState({ url: "", secret: "", events: [] as string[] });
    const [saving, setSaving] = useState(false);

    const toggleEvent = (ev: string) =>
        setForm(f => ({
            ...f,
            events: f.events.includes(ev) ? f.events.filter(e => e !== ev) : [...f.events, ev],
        }));

    const selectAll = () => setForm(f => ({ ...f, events: [...ALL_EVENTS] }));
    const clearAll = () => setForm(f => ({ ...f, events: [] }));

    const handleCreate = async () => {
        if (!form.url || form.events.length === 0) {
            toast("URL and at least one event are required", "warning");
            return;
        }
        setSaving(true);
        try {
            const res = await apiFetch("/webhooks", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url: form.url, events: form.events, secret: form.secret || null }),
            });
            if (!res.ok) throw new Error(await res.text());
            toast("Webhook created", "success");
            onCreated();
        } catch {
            toast("Failed to create webhook", "error");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="animate-in slide-in-from-top-2 rounded-2xl border border-indigo-200 bg-gradient-to-br from-indigo-50/80 to-white p-6 shadow-sm dark:border-indigo-500/20 dark:from-indigo-500/5 dark:to-gray-900">
            <h3 className="mb-5 text-base font-semibold text-gray-900 dark:text-white">New Webhook</h3>
            <div className="space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div>
                        <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">Endpoint URL *</label>
                        <input
                            type="url"
                            value={form.url}
                            onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
                            placeholder="https://your-app.com/webhooks/ukip"
                            className={inputClass}
                        />
                    </div>
                    <div>
                        <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">
                            Secret <span className="font-normal text-gray-400">(HMAC-SHA256)</span>
                        </label>
                        <input
                            type="text"
                            value={form.secret}
                            onChange={e => setForm(f => ({ ...f, secret: e.target.value }))}
                            placeholder="optional-signing-key"
                            className={inputClass}
                        />
                    </div>
                </div>
                <div>
                    <div className="mb-2 flex items-center justify-between">
                        <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Events *</label>
                        <div className="flex gap-2">
                            <button onClick={selectAll} className="text-xs text-indigo-600 hover:underline dark:text-indigo-400">Select all</button>
                            <button onClick={clearAll} className="text-xs text-gray-400 hover:underline">Clear</button>
                        </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {ALL_EVENTS.filter(e => e !== "ping").map(ev => {
                            const info = EVENT_LABELS[ev] || { label: ev, color: "" };
                            const selected = form.events.includes(ev);
                            return (
                                <button
                                    key={ev}
                                    onClick={() => toggleEvent(ev)}
                                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                                        selected
                                            ? "bg-indigo-600 text-white shadow-sm ring-2 ring-indigo-600/30"
                                            : "border border-gray-200 bg-white text-gray-600 hover:border-indigo-300 hover:bg-indigo-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:border-indigo-500"
                                    }`}
                                >
                                    {info.label}
                                </button>
                            );
                        })}
                    </div>
                </div>
                <div className="flex items-center justify-end gap-2 pt-2">
                    <button
                        onClick={onCancel}
                        className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleCreate}
                        disabled={saving || !form.url || form.events.length === 0}
                        className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition-all hover:bg-indigo-700 disabled:opacity-50"
                    >
                        {saving && <Spinner />}
                        {saving ? "Creating…" : "Create Webhook"}
                    </button>
                </div>
            </div>
        </div>
    );
}

// ── Webhook Card ─────────────────────────────────────────────────────────────

function WebhookCard({
    hook,
    expanded,
    onToggleExpand,
    onReload,
    toast,
}: {
    hook: WebhookRecord;
    expanded: boolean;
    onToggleExpand: () => void;
    onReload: () => void;
    toast: (msg: string, v?: "success" | "error" | "warning" | "info") => void;
}) {
    const [testing, setTesting] = useState(false);
    const [testResult, setTestResult] = useState<TestResult | null>(null);
    const [editing, setEditing] = useState(false);
    const [editForm, setEditForm] = useState({ url: hook.url, events: [...hook.events], secret: "" });

    const handleToggleActive = async () => {
        const res = await apiFetch(`/webhooks/${hook.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_active: !hook.is_active }),
        });
        if (res.ok) {
            toast(hook.is_active ? "Webhook disabled" : "Webhook enabled", "success");
            onReload();
        } else {
            toast("Update failed", "error");
        }
    };

    const handleTest = async () => {
        setTesting(true);
        setTestResult(null);
        try {
            const res = await apiFetch(`/webhooks/${hook.id}/test`, { method: "POST" });
            if (res.ok) {
                const data = await res.json();
                setTestResult(data);
                toast(data.success ? "Test succeeded!" : "Test failed — see details", data.success ? "success" : "warning");
            } else {
                toast("Test request failed", "error");
            }
        } finally {
            setTesting(false);
        }
    };

    const handleDelete = async () => {
        if (!confirm(`Delete webhook for ${hook.url}? This cannot be undone.`)) return;
        const res = await apiFetch(`/webhooks/${hook.id}`, { method: "DELETE" });
        if (res.ok) {
            toast("Webhook deleted", "success");
            onReload();
        } else {
            toast("Delete failed", "error");
        }
    };

    const handleSaveEdit = async () => {
        const payload: Record<string, unknown> = {
            url: editForm.url,
            events: editForm.events,
        };
        if (editForm.secret) payload.secret = editForm.secret;
        const res = await apiFetch(`/webhooks/${hook.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (res.ok) {
            toast("Webhook updated", "success");
            setEditing(false);
            onReload();
        } else {
            toast("Update failed", "error");
        }
    };

    const statusIndicator = hook.last_status === null
        ? "bg-gray-300 dark:bg-gray-600"
        : hook.last_status >= 200 && hook.last_status < 300
        ? "bg-emerald-500"
        : "bg-red-500";

    return (
        <div className={`group rounded-2xl border transition-all duration-200 ${
            expanded
                ? "border-indigo-200 bg-white shadow-md dark:border-indigo-500/30 dark:bg-gray-900"
                : "border-gray-200 bg-white shadow-sm hover:shadow-md dark:border-gray-800 dark:bg-gray-900"
        }`}>
            {/* Header row */}
            <div
                className="flex cursor-pointer items-center gap-4 px-5 py-4"
                onClick={onToggleExpand}
            >
                {/* Status dot */}
                <div className="flex items-center gap-3">
                    <span className={`h-2.5 w-2.5 rounded-full ${statusIndicator} ${hook.is_active ? "animate-pulse" : ""}`} />
                    <div className="min-w-0">
                        <p className="truncate font-mono text-sm font-medium text-gray-900 dark:text-white">
                            {hook.url}
                        </p>
                        <div className="mt-1 flex flex-wrap items-center gap-1.5">
                            {hook.events.slice(0, 3).map(ev => {
                                const info = EVENT_LABELS[ev] || { label: ev, color: "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300" };
                                return (
                                    <span key={ev} className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${info.color}`}>
                                        {info.label}
                                    </span>
                                );
                            })}
                            {hook.events.length > 3 && (
                                <span className="text-[10px] text-gray-400">+{hook.events.length - 3} more</span>
                            )}
                        </div>
                    </div>
                </div>

                <div className="ml-auto flex items-center gap-3">
                    {/* Last status */}
                    <div className="hidden text-right sm:block">
                        <div className="text-xs text-gray-400 dark:text-gray-500">Last status</div>
                        {statusBadge(hook.last_status)}
                    </div>

                    {/* Last triggered */}
                    <div className="hidden text-right sm:block">
                        <div className="text-xs text-gray-400 dark:text-gray-500">Last triggered</div>
                        <div className="text-xs font-medium text-gray-600 dark:text-gray-300">
                            {timeAgo(hook.last_triggered_at)}
                        </div>
                    </div>

                    {/* Active toggle */}
                    <button
                        onClick={e => { e.stopPropagation(); handleToggleActive(); }}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                            hook.is_active ? "bg-indigo-600" : "bg-gray-300 dark:bg-gray-600"
                        }`}
                    >
                        <span className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
                            hook.is_active ? "translate-x-6" : "translate-x-1"
                        }`} />
                    </button>

                    <ChevronIcon open={expanded} />
                </div>
            </div>

            {/* Expanded detail */}
            {expanded && (
                <div className="border-t border-gray-100 dark:border-gray-800">
                    {/* Action bar */}
                    <div className="flex flex-wrap items-center gap-2 px-5 py-3">
                        <button
                            onClick={handleTest}
                            disabled={testing}
                            className="flex items-center gap-1.5 rounded-lg bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 transition-colors hover:bg-indigo-100 disabled:opacity-50 dark:bg-indigo-500/10 dark:text-indigo-400 dark:hover:bg-indigo-500/20"
                        >
                            {testing ? <Spinner /> : (
                                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                    <circle cx="12" cy="12" r="10" strokeWidth={1.5} />
                                </svg>
                            )}
                            {testing ? "Sending…" : "Send Test Ping"}
                        </button>
                        <button
                            onClick={() => { setEditing(!editing); setEditForm({ url: hook.url, events: [...hook.events], secret: "" }); }}
                            className="flex items-center gap-1.5 rounded-lg bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-100 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
                        >
                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                            {editing ? "Cancel Edit" : "Edit"}
                        </button>
                        <button
                            onClick={handleDelete}
                            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
                        >
                            <TrashIcon />
                            Delete
                        </button>
                    </div>

                    {/* Test result */}
                    {testResult && (
                        <div className={`mx-5 mb-3 rounded-xl border p-4 ${
                            testResult.success
                                ? "border-emerald-200 bg-emerald-50 dark:border-emerald-500/20 dark:bg-emerald-500/5"
                                : "border-red-200 bg-red-50 dark:border-red-500/20 dark:bg-red-500/5"
                        }`}>
                            <div className="flex items-center gap-3 text-sm">
                                <span className={`${testResult.success ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"} font-semibold`}>
                                    {testResult.success ? "✓ Delivered" : "✗ Failed"}
                                </span>
                                <span className="text-gray-400">•</span>
                                <span className="font-mono text-xs text-gray-600 dark:text-gray-300">HTTP {testResult.status_code}</span>
                                <span className="text-gray-400">•</span>
                                <span className="text-xs text-gray-500">{testResult.latency_ms}ms</span>
                            </div>
                            {testResult.error && (
                                <p className="mt-2 text-xs text-red-600 dark:text-red-400">{testResult.error}</p>
                            )}
                            {testResult.response_preview && (
                                <pre className="mt-2 max-h-20 overflow-auto rounded bg-white/60 px-2 py-1 text-[10px] text-gray-600 dark:bg-gray-900/50 dark:text-gray-400">
                                    {testResult.response_preview}
                                </pre>
                            )}
                        </div>
                    )}

                    {/* Edit form */}
                    {editing && (
                        <div className="mx-5 mb-3 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/50">
                            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                <div>
                                    <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">URL</label>
                                    <input
                                        type="url"
                                        value={editForm.url}
                                        onChange={e => setEditForm(f => ({ ...f, url: e.target.value }))}
                                        className={inputClass}
                                    />
                                </div>
                                <div>
                                    <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Secret (leave blank to keep)</label>
                                    <input
                                        type="text"
                                        value={editForm.secret}
                                        onChange={e => setEditForm(f => ({ ...f, secret: e.target.value }))}
                                        className={inputClass}
                                        placeholder="unchanged"
                                    />
                                </div>
                            </div>
                            <div className="mt-3">
                                <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Events</label>
                                <div className="flex flex-wrap gap-1.5">
                                    {ALL_EVENTS.filter(e => e !== "ping").map(ev => {
                                        const selected = editForm.events.includes(ev);
                                        const info = EVENT_LABELS[ev] || { label: ev, color: "" };
                                        return (
                                            <button
                                                key={ev}
                                                onClick={() => setEditForm(f => ({
                                                    ...f,
                                                    events: f.events.includes(ev) ? f.events.filter(e => e !== ev) : [...f.events, ev],
                                                }))}
                                                className={`rounded px-2 py-1 text-[11px] font-medium transition-all ${
                                                    selected
                                                        ? "bg-indigo-600 text-white"
                                                        : "border border-gray-200 bg-white text-gray-600 hover:border-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300"
                                                }`}
                                            >
                                                {info.label}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                            <div className="mt-3 flex justify-end">
                                <button
                                    onClick={handleSaveEdit}
                                    className="rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
                                >
                                    Save Changes
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Delivery history */}
                    <DeliveryHistory webhookId={hook.id} />
                </div>
            )}
        </div>
    );
}

// ── Delivery History ─────────────────────────────────────────────────────────

function DeliveryHistory({ webhookId }: { webhookId: number }) {
    const [deliveries, setDeliveries] = useState<DeliveryRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const size = 10;

    const loadDeliveries = useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiFetch(`/webhooks/${webhookId}/deliveries?page=${page}&size=${size}`);
            if (res.ok) {
                const data = await res.json();
                setDeliveries(data.items);
                setTotal(data.total);
            }
        } finally {
            setLoading(false);
        }
    }, [webhookId, page]);

    useEffect(() => { loadDeliveries(); }, [loadDeliveries]);

    const totalPages = Math.ceil(total / size);

    return (
        <div className="px-5 pb-5">
            <div className="mb-3 flex items-center justify-between">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Delivery History
                </h4>
                <span className="text-xs text-gray-400">{total} total</span>
            </div>

            {loading ? (
                <div className="flex justify-center py-6">
                    <Spinner className="h-5 w-5 text-gray-400" />
                </div>
            ) : deliveries.length === 0 ? (
                <p className="py-6 text-center text-xs text-gray-400 dark:text-gray-500">
                    No deliveries recorded yet
                </p>
            ) : (
                <>
                    <div className="space-y-1.5">
                        {deliveries.map(d => (
                            <div
                                key={d.id}
                                className="flex items-center gap-3 rounded-lg border border-gray-100 bg-gray-50/50 px-3 py-2 dark:border-gray-800 dark:bg-gray-800/30"
                            >
                                {/* Success indicator */}
                                <span className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold ${
                                    d.success
                                        ? "bg-emerald-100 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400"
                                        : "bg-red-100 text-red-600 dark:bg-red-500/15 dark:text-red-400"
                                }`}>
                                    {d.success ? "✓" : "✗"}
                                </span>

                                {/* Event */}
                                <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                                    (EVENT_LABELS[d.event] || { color: "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300" }).color
                                }`}>
                                    {(EVENT_LABELS[d.event] || { label: d.event }).label}
                                </span>

                                {/* Status code */}
                                <span className="font-mono text-[11px] text-gray-600 dark:text-gray-300">
                                    {d.status_code || "ERR"}
                                </span>

                                {/* Latency */}
                                <span className="text-[10px] text-gray-400">
                                    {d.latency_ms != null ? `${d.latency_ms}ms` : "—"}
                                </span>

                                {/* Error */}
                                {d.error && (
                                    <span className="max-w-[200px] truncate text-[10px] text-red-500" title={d.error}>
                                        {d.error}
                                    </span>
                                )}

                                {/* Time */}
                                <span className="ml-auto text-[10px] text-gray-400">
                                    {timeAgo(d.created_at)}
                                </span>
                            </div>
                        ))}
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                        <div className="mt-3 flex items-center justify-center gap-2">
                            <button
                                disabled={page <= 1}
                                onClick={() => setPage(p => p - 1)}
                                className="rounded-lg border border-gray-200 px-3 py-1 text-xs text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-40 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800"
                            >
                                ← Prev
                            </button>
                            <span className="text-xs text-gray-400">
                                Page {page} of {totalPages}
                            </span>
                            <button
                                disabled={page >= totalPages}
                                onClick={() => setPage(p => p + 1)}
                                className="rounded-lg border border-gray-200 px-3 py-1 text-xs text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-40 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800"
                            >
                                Next →
                            </button>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
