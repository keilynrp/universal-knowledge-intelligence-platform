"use client";

import { useState, useEffect, useCallback } from "react";
import { PageHeader, StatCard, Badge, useToast } from "../../components/ui";
import { apiFetch } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

interface ScheduledImport {
    id: number;
    store_id: number;
    store_name?: string;
    name: string;
    interval_minutes: number;
    is_active: boolean;
    last_run_at: string | null;
    next_run_at: string | null;
    last_status: string | null;
    last_result: Record<string, unknown> | null;
    total_runs: number;
    total_entities_imported: number;
    created_at: string | null;
}

interface Stats {
    total: number;
    active: number;
    inactive: number;
    total_runs: number;
    total_entities_imported: number;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(iso: string | null): string {
    if (!iso) return "Never";
    const diff = Date.now() - new Date(iso).getTime();
    const sec = Math.floor(diff / 1000);
    if (sec < 60) return `${sec}s ago`;
    const min = Math.floor(sec / 60);
    if (min < 60) return `${min}m ago`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr}h ago`;
    return `${Math.floor(hr / 24)}d ago`;
}

function formatInterval(m: number): string {
    if (m < 60) return `${m} min`;
    if (m < 1440) return `${Math.floor(m / 60)}h ${m % 60 > 0 ? `${m % 60}m` : ""}`.trim();
    return `${Math.floor(m / 1440)}d`;
}

const INTERVALS = [
    { label: "Every 5 min",   value: 5 },
    { label: "Every 15 min",  value: 15 },
    { label: "Every 30 min",  value: 30 },
    { label: "Every hour",    value: 60 },
    { label: "Every 6 hours", value: 360 },
    { label: "Every 12 hours",value: 720 },
    { label: "Daily",         value: 1440 },
    { label: "Weekly",        value: 10080 },
];

const inputClass = "h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none transition-colors focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:border-gray-700 dark:bg-gray-800 dark:text-white dark:focus:border-indigo-400";

function Spinner({ className = "h-4 w-4" }: { className?: string }) {
    return (
        <svg className={`${className} animate-spin`} fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
    );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function ScheduledImportsPage() {
    const { toast } = useToast();
    const [items, setItems] = useState<ScheduledImport[]>([]);
    const [stats, setStats] = useState<Stats | null>(null);
    const [stores, setStores] = useState<{ id: number; name: string }[]>([]);
    const [loading, setLoading] = useState(true);
    const [showCreate, setShowCreate] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [iRes, sRes, stRes] = await Promise.all([
                apiFetch("/scheduled-imports"),
                apiFetch("/scheduled-imports/stats"),
                apiFetch("/stores"),
            ]);
            if (iRes.ok) setItems(await iRes.json());
            if (sRes.ok) setStats(await sRes.json());
            if (stRes.ok) setStores((await stRes.json()).map((s: { id: number; name: string }) => ({ id: s.id, name: s.name })));
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
                    { label: "Scheduled Imports" },
                ]}
                title="Scheduled Imports"
                description="Automate data ingestion from configured store connections"
            />

            {/* Stats */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <StatCard
                    icon={<svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>}
                    iconColor="blue"
                    label="Schedules"
                    value={stats?.total ?? "—"}
                />
                <StatCard
                    icon={<svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>}
                    iconColor="emerald"
                    label="Active"
                    value={stats?.active ?? "—"}
                />
                <StatCard
                    icon={<svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" /></svg>}
                    iconColor="violet"
                    label="Total Runs"
                    value={stats?.total_runs ?? "—"}
                />
                <StatCard
                    icon={<svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" /></svg>}
                    iconColor="amber"
                    label="Entities Imported"
                    value={stats?.total_entities_imported ?? "—"}
                />
            </div>

            {/* Action bar */}
            <div className="flex items-center justify-between">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                    {items.filter(i => i.is_active).length} active · {items.filter(i => !i.is_active).length} paused
                </p>
                <button
                    onClick={() => setShowCreate(s => !s)}
                    className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-indigo-700 active:scale-[0.98]"
                >
                    {showCreate ? "Cancel" : "+ New Schedule"}
                </button>
            </div>

            {/* Create form */}
            {showCreate && (
                <CreateScheduleForm
                    stores={stores}
                    onCreated={() => { setShowCreate(false); load(); }}
                    onCancel={() => setShowCreate(false)}
                    toast={toast}
                />
            )}

            {/* List */}
            {loading ? (
                <div className="flex items-center justify-center py-16">
                    <Spinner className="h-7 w-7 text-indigo-600" />
                </div>
            ) : items.length === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-gray-200 py-16 dark:border-gray-700">
                    <svg className="h-12 w-12 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    <p className="mt-4 text-sm font-medium text-gray-500 dark:text-gray-400">No scheduled imports yet</p>
                    <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">Set up automated ingestion from your connected stores</p>
                </div>
            ) : (
                <div className="space-y-3">
                    {items.map(item => (
                        <ScheduleCard key={item.id} item={item} onReload={load} toast={toast} />
                    ))}
                </div>
            )}
        </div>
    );
}

// ── Create Form ──────────────────────────────────────────────────────────────

function CreateScheduleForm({
    stores,
    onCreated,
    onCancel,
    toast,
}: {
    stores: { id: number; name: string }[];
    onCreated: () => void;
    onCancel: () => void;
    toast: (msg: string, v?: "success" | "error" | "warning" | "info") => void;
}) {
    const [form, setForm] = useState({ name: "", store_id: stores[0]?.id ?? 0, interval_minutes: 60 });
    const [saving, setSaving] = useState(false);

    const handleCreate = async () => {
        if (!form.name || !form.store_id) {
            toast("Name and store are required", "warning");
            return;
        }
        setSaving(true);
        try {
            const res = await apiFetch("/scheduled-imports", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(form),
            });
            if (!res.ok) throw new Error(await res.text());
            toast("Schedule created", "success");
            onCreated();
        } catch {
            toast("Failed to create schedule", "error");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="animate-in slide-in-from-top-2 rounded-2xl border border-indigo-200 bg-gradient-to-br from-indigo-50/80 to-white p-6 shadow-sm dark:border-indigo-500/20 dark:from-indigo-500/5 dark:to-gray-900">
            <h3 className="mb-5 text-base font-semibold text-gray-900 dark:text-white">New Scheduled Import</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div>
                    <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">Name *</label>
                    <input
                        type="text"
                        value={form.name}
                        onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                        placeholder="Nightly catalog sync"
                        className={inputClass}
                    />
                </div>
                <div>
                    <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">Store *</label>
                    <select
                        value={form.store_id}
                        onChange={e => setForm(f => ({ ...f, store_id: Number(e.target.value) }))}
                        className={inputClass}
                    >
                        {stores.length === 0 && <option value={0}>No stores available</option>}
                        {stores.map(s => (
                            <option key={s.id} value={s.id}>{s.name}</option>
                        ))}
                    </select>
                </div>
                <div>
                    <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">Interval</label>
                    <select
                        value={form.interval_minutes}
                        onChange={e => setForm(f => ({ ...f, interval_minutes: Number(e.target.value) }))}
                        className={inputClass}
                    >
                        {INTERVALS.map(i => (
                            <option key={i.value} value={i.value}>{i.label}</option>
                        ))}
                    </select>
                </div>
            </div>
            <div className="mt-4 flex items-center justify-end gap-2">
                <button onClick={onCancel} className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800">Cancel</button>
                <button onClick={handleCreate} disabled={saving || !form.name || !form.store_id} className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
                    {saving && <Spinner />}
                    {saving ? "Creating…" : "Create Schedule"}
                </button>
            </div>
        </div>
    );
}

// ── Schedule Card ────────────────────────────────────────────────────────────

function ScheduleCard({
    item,
    onReload,
    toast,
}: {
    item: ScheduledImport;
    onReload: () => void;
    toast: (msg: string, v?: "success" | "error" | "warning" | "info") => void;
}) {
    const [triggering, setTriggering] = useState(false);
    const [triggerResult, setTriggerResult] = useState<Record<string, unknown> | null>(null);

    const handleToggle = async () => {
        const res = await apiFetch(`/scheduled-imports/${item.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_active: !item.is_active }),
        });
        if (res.ok) {
            toast(item.is_active ? "Schedule paused" : "Schedule activated", "success");
            onReload();
        }
    };

    const handleTrigger = async () => {
        setTriggering(true);
        setTriggerResult(null);
        try {
            const res = await apiFetch(`/scheduled-imports/${item.id}/trigger`, { method: "POST" });
            if (res.ok) {
                const data = await res.json();
                setTriggerResult(data);
                toast(data.success ? "Import completed!" : "Import failed", data.success ? "success" : "warning");
                onReload();
            }
        } finally {
            setTriggering(false);
        }
    };

    const handleDelete = async () => {
        if (!confirm(`Delete schedule "${item.name}"?`)) return;
        const res = await apiFetch(`/scheduled-imports/${item.id}`, { method: "DELETE" });
        if (res.ok) {
            toast("Schedule deleted", "success");
            onReload();
        }
    };

    const statusColor = item.last_status === "success"
        ? "bg-emerald-500"
        : item.last_status === "error"
        ? "bg-red-500"
        : item.last_status === "running"
        ? "bg-amber-500 animate-pulse"
        : "bg-gray-300 dark:bg-gray-600";

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-4">
                {/* Status dot */}
                <span className={`h-3 w-3 rounded-full ${statusColor}`} />

                {/* Info */}
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                        <h3 className="truncate text-sm font-semibold text-gray-900 dark:text-white">{item.name}</h3>
                        <Badge variant={item.is_active ? "success" : "default"}>{item.is_active ? "Active" : "Paused"}</Badge>
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
                        <span className="flex items-center gap-1">
                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757" /></svg>
                            {item.store_name || `Store #${item.store_id}`}
                        </span>
                        <span className="flex items-center gap-1">
                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                            {formatInterval(item.interval_minutes)}
                        </span>
                        <span>Last: {timeAgo(item.last_run_at)}</span>
                        <span>Next: {item.is_active && item.next_run_at ? timeAgo(item.next_run_at) : "—"}</span>
                        <span>{item.total_runs} runs · {item.total_entities_imported} imported</span>
                    </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2">
                    <button
                        onClick={handleTrigger}
                        disabled={triggering}
                        className="flex items-center gap-1 rounded-lg bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 transition-colors hover:bg-indigo-100 disabled:opacity-50 dark:bg-indigo-500/10 dark:text-indigo-400"
                    >
                        {triggering ? <Spinner /> : (
                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /></svg>
                        )}
                        {triggering ? "Running…" : "Run Now"}
                    </button>
                    <button
                        onClick={handleToggle}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${item.is_active ? "bg-indigo-600" : "bg-gray-300 dark:bg-gray-600"}`}
                    >
                        <span className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${item.is_active ? "translate-x-6" : "translate-x-1"}`} />
                    </button>
                    <button
                        onClick={handleDelete}
                        className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10"
                    >
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>
                    </button>
                </div>
            </div>

            {/* Trigger result */}
            {triggerResult && (
                <div className={`mt-3 rounded-xl border p-3 text-xs ${
                    triggerResult.success
                        ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/5 dark:text-emerald-400"
                        : "border-red-200 bg-red-50 text-red-700 dark:border-red-500/20 dark:bg-red-500/5 dark:text-red-400"
                }`}>
                    {triggerResult.success ? (
                        <span>✓ Fetched {String(triggerResult.total_fetched ?? 0)} · {String(triggerResult.new_mappings ?? 0)} new mappings · {String(triggerResult.new_queue_items ?? 0)} queue items</span>
                    ) : (
                        <span>✗ {String(triggerResult.error || "Unknown error")}</span>
                    )}
                </div>
            )}

            {/* Last result summary */}
            {item.last_result && (
                <div className="mt-2 flex items-center gap-3 text-[10px] text-gray-400 dark:text-gray-500">
                    <span>Last result: {JSON.stringify(item.last_result)}</span>
                </div>
            )}
        </div>
    );
}
