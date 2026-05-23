"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { PageHeader, TabNav, Badge } from "../../components/ui";
import { formatDate, formatDateTime } from "../../lib/dateFormat";

interface StoreDetail {
    id: number; name: string; platform: string; base_url: string; is_active: boolean;
    last_sync_at: string | null; created_at: string | null; entity_count: number;
    sync_direction: string; notes: string | null;
    has_api_key: boolean; has_api_secret: boolean; has_access_token: boolean;
}

interface Mapping {
    id: number; local_entity_id: number | null; remote_entity_id: string | null;
    canonical_url: string; remote_sku: string | null; remote_name: string | null;
    remote_price: string | null; remote_stock: string | null; remote_status: string | null;
    sync_status: string; last_synced_at: string | null;
}

interface QueueItem {
    id: number; mapping_id: number | null; direction: string; entity_name: string | null;
    canonical_url: string | null; field: string; local_value: string | null;
    remote_value: string | null; status: string; created_at: string | null; resolved_at: string | null;
}

interface LogEntry {
    id: number; action: string; status: string; records_affected: number;
    details: string | null; executed_at: string | null;
}

type Tab = "queue" | "mappings" | "logs";

export default function StoreDetailPage() {
    const params = useParams();
    const storeId = params.id as string;

    const [store, setStore] = useState<StoreDetail | null>(null);
    const [tab, setTab] = useState<Tab>("queue");
    const [loading, setLoading] = useState(true);

    // Queue state
    const [queue, setQueue] = useState<QueueItem[]>([]);
    const [queueTotal, setQueueTotal] = useState(0);
    const [queueFilter, setQueueFilter] = useState("pending");

    // Mappings state
    const [mappings, setMappings] = useState<Mapping[]>([]);
    const [mappingsTotal, setMappingsTotal] = useState(0);

    // Logs state
    const [logs, setLogs] = useState<LogEntry[]>([]);

    // Action states
    const [testing, setTesting] = useState(false);
    const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
    const [pulling, setPulling] = useState(false);
    const [pullResult, setPullResult] = useState<{ message: string; new_mappings: number; new_queue_items: number } | null>(null);

    const fetchStore = useCallback(async () => {
        try {
            const res = await apiFetch(`/stores/${storeId}`);
            if (!res.ok) throw new Error("Not found");
            setStore(await res.json());
        } catch { setStore(null); }
        finally { setLoading(false); }
    }, [storeId]);

    const fetchQueue = useCallback(async () => {
        const res = await apiFetch(`/stores/${storeId}/queue?status=${queueFilter}&limit=50`);
        if (res.ok) { const data = await res.json(); setQueue(data.items); setQueueTotal(data.total); }
    }, [storeId, queueFilter]);

    const fetchMappings = useCallback(async () => {
        const res = await apiFetch(`/stores/${storeId}/mappings?limit=50`);
        if (res.ok) { const data = await res.json(); setMappings(data.mappings); setMappingsTotal(data.total); }
    }, [storeId]);

    const fetchLogs = useCallback(async () => {
        const res = await apiFetch(`/stores/${storeId}/logs?limit=30`);
        if (res.ok) setLogs(await res.json());
    }, [storeId]);

    useEffect(() => { fetchStore(); }, [fetchStore]);
    useEffect(() => { if (tab === "queue") fetchQueue(); }, [tab, fetchQueue]);
    useEffect(() => { if (tab === "mappings") fetchMappings(); }, [tab, fetchMappings]);
    useEffect(() => { if (tab === "logs") fetchLogs(); }, [tab, fetchLogs]);

    async function handleTest() {
        setTesting(true); setTestResult(null);
        try {
            const res = await apiFetch(`/stores/${storeId}/test`, { method: "POST" });
            setTestResult(await res.json());
        } catch (e) { setTestResult({ success: false, message: String(e) }); }
        finally { setTesting(false); }
    }

    async function handlePull() {
        setPulling(true); setPullResult(null);
        try {
            const res = await apiFetch(`/stores/${storeId}/pull`, { method: "POST" });
            if (!res.ok) { const err = await res.json(); setPullResult({ message: err.detail || "Error", new_mappings: 0, new_queue_items: 0 }); return; }
            const data = await res.json();
            setPullResult(data);
            fetchQueue(); fetchMappings(); fetchStore();
        } catch (e) { setPullResult({ message: String(e), new_mappings: 0, new_queue_items: 0 }); }
        finally { setPulling(false); }
    }

    async function handleQueueAction(itemId: number, action: "approve" | "reject") {
        await apiFetch(`/stores/queue/${itemId}/${action}`, { method: "POST" });
        fetchQueue();
    }

    async function handleBulkAction(action: "bulk-approve" | "bulk-reject") {
        if (!confirm(`${action === "bulk-approve" ? "Approve" : "Reject"} all pending items?`)) return;
        await apiFetch(`/stores/queue/${action}?store_id=${storeId}`, { method: "POST" });
        fetchQueue();
    }

    if (loading) return (
        <div className="flex h-96 items-center justify-center">
            <svg className="h-8 w-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
        </div>
    );

    if (!store) return (
        <div className="p-8">
            <p className="text-gray-500 dark:text-gray-400">Store not found.</p>
            <Link href="/integrations" className="text-blue-600 hover:underline text-sm">← Back to Integrations</Link>
        </div>
    );

    const statusBadgeVariant = (status: string) =>
        status === "approved" || status === "synced" || status === "success" ? "success" as const :
        status === "rejected" || status === "error" ? "error" as const :
        status === "pending" ? "warning" as const :
        status === "applied" ? "info" as const : "default" as const;

    return (
        <div className="space-y-6">
            <PageHeader
                breadcrumbs={[
                    { label: "Home", href: "/" },
                    { label: "Integrations", href: "/integrations" },
                    { label: store.name },
                ]}
                title={store.name}
                description={store.base_url}
                actions={
                    <div className="flex items-center gap-2">
                        <button onClick={handleTest} disabled={testing}
                            className="flex items-center gap-2 rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                        >
                            {testing ? <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg> : null}
                            Test Connection
                        </button>
                        <button onClick={handlePull} disabled={pulling || !store.is_active}
                            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                        >
                            {pulling ? <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg> : <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>}
                            Pull Records
                        </button>
                    </div>
                }
            />

            {/* Test / Pull result banners */}
            {testResult && (
                <div className={`rounded-xl border p-4 ${testResult.success ? "border-green-200 bg-green-50 dark:border-green-500/20 dark:bg-green-500/5" : "border-red-200 bg-red-50 dark:border-red-500/20 dark:bg-red-500/5"}`}>
                    <div className="flex items-center gap-2">
                        {testResult.success ?
                            <svg className="h-5 w-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg> :
                            <svg className="h-5 w-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        }
                        <span className={`text-sm font-medium ${testResult.success ? "text-green-800 dark:text-green-400" : "text-red-800 dark:text-red-400"}`}>
                            {testResult.message}
                        </span>
                        <button onClick={() => setTestResult(null)} className="ml-auto text-gray-400 hover:text-gray-600">×</button>
                    </div>
                </div>
            )}

            {pullResult && (
                <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 dark:border-blue-500/20 dark:bg-blue-500/5">
                    <p className="text-sm font-medium text-blue-800 dark:text-blue-400">{pullResult.message}</p>
                    <p className="mt-1 text-xs text-blue-600 dark:text-blue-500">
                        {pullResult.new_mappings} new mappings · {pullResult.new_queue_items} items queued for review
                    </p>
                    <button onClick={() => setPullResult(null)} className="mt-1 text-xs text-blue-500 hover:underline">Dismiss</button>
                </div>
            )}

            {/* Stat cards */}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                {[
                    { label: "Mapped Records", value: store.entity_count || mappingsTotal, icon: "📦" },
                    { label: "Pending Review", value: queueFilter === "pending" ? queueTotal : "...", icon: "⏳" },
                    { label: "Sync Direction", value: store.sync_direction === "bidirectional" ? "↔ Both" : store.sync_direction === "pull" ? "← Pull" : "Push →", icon: "🔄" },
                    { label: "Last Sync", value: store.last_sync_at ? formatDate(store.last_sync_at) : "Never", icon: "🕐" },
                ].map((s) => (
                    <div key={s.label} className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <p className="text-xs text-gray-500 dark:text-gray-400">{s.icon} {s.label}</p>
                        <p className="mt-1 text-lg font-bold text-gray-900 dark:text-white">{s.value}</p>
                    </div>
                ))}
            </div>

            <TabNav
                tabs={[
                    { id: "queue", label: "Review Queue", badge: queueTotal },
                    { id: "mappings", label: "Mappings", badge: mappingsTotal },
                    { id: "logs", label: "Sync Logs" },
                ]}
                activeTab={tab}
                onTabChange={(id) => setTab(id as Tab)}
            />

            {/* Tab Content */}
            {tab === "queue" && (
                <div>
                    <div className="mb-4 flex items-center justify-between">
                        <div className="flex gap-2">
                            {["pending", "approved", "rejected", "all"].map((f) => (
                                <button key={f} onClick={() => setQueueFilter(f)}
                                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${queueFilter === f ? "bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400" : "text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"}`}
                                >{f.charAt(0).toUpperCase() + f.slice(1)}</button>
                            ))}
                        </div>
                        {queueFilter === "pending" && queueTotal > 0 && (
                            <div className="flex gap-2">
                                <button onClick={() => handleBulkAction("bulk-approve")} className="rounded-lg bg-green-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-green-700">Approve All</button>
                                <button onClick={() => handleBulkAction("bulk-reject")} className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-700">Reject All</button>
                            </div>
                        )}
                    </div>

                    {queue.length === 0 ? (
                        <div className="rounded-xl border border-dashed border-gray-300 py-12 text-center dark:border-gray-700">
                            <p className="text-gray-500 dark:text-gray-400">No {queueFilter !== "all" ? queueFilter : ""} items in queue</p>
                            <p className="mt-1 text-xs text-gray-400">Pull records from this adapter to populate the review queue</p>
                        </div>
                    ) : (
                        <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800">
                            <table className="w-full text-sm">
                                <thead className="bg-gray-50 dark:bg-gray-800/50">
                                    <tr>
                                        <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">Record</th>
                                        <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">Field</th>
                                        <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">Local Value</th>
                                        <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">Remote Value</th>
                                        <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">Status</th>
                                        <th className="px-4 py-3 text-right font-medium text-gray-500 dark:text-gray-400">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                                    {queue.map((item) => (
                                        <tr key={item.id} className="bg-white transition-colors hover:bg-gray-50 dark:bg-gray-900 dark:hover:bg-gray-800/50">
                                            <td className="px-4 py-3">
                                                <p className="font-medium text-gray-900 dark:text-white truncate max-w-[200px]">{item.entity_name || "—"}</p>
                                                <p className="text-xs text-gray-400 truncate max-w-[200px]">{item.canonical_url}</p>
                                            </td>
                                            <td className="px-4 py-3">
                                                <span className="inline-flex rounded bg-gray-100 px-1.5 py-0.5 text-xs font-mono text-gray-700 dark:bg-gray-800 dark:text-gray-300">{item.field}</span>
                                            </td>
                                            <td className="px-4 py-3 text-gray-600 dark:text-gray-400 max-w-[150px] truncate">{item.local_value || <span className="italic text-gray-400">empty</span>}</td>
                                            <td className="px-4 py-3 text-gray-900 dark:text-white font-medium max-w-[150px] truncate">{item.remote_value || <span className="italic text-gray-400">empty</span>}</td>
                                            <td className="px-4 py-3"><Badge variant={statusBadgeVariant(item.status)}>{item.status}</Badge></td>
                                            <td className="px-4 py-3 text-right">
                                                {item.status === "pending" && (
                                                    <div className="flex justify-end gap-1">
                                                        <button onClick={() => handleQueueAction(item.id, "approve")} className="rounded px-2 py-1 text-xs font-medium text-green-600 hover:bg-green-50 dark:hover:bg-green-500/10" title="Approve">✓</button>
                                                        <button onClick={() => handleQueueAction(item.id, "reject")} className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10" title="Reject">✗</button>
                                                    </div>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}

            {tab === "mappings" && (
                <div>
                    {mappings.length === 0 ? (
                        <div className="rounded-xl border border-dashed border-gray-300 py-12 text-center dark:border-gray-700">
                            <p className="text-gray-500 dark:text-gray-400">No record mappings yet</p>
                            <p className="mt-1 text-xs text-gray-400">Pull records from this adapter to create canonical URL mappings</p>
                        </div>
                    ) : (
                        <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800">
                            <table className="w-full text-sm">
                                <thead className="bg-gray-50 dark:bg-gray-800/50">
                                    <tr>
                                        <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">Remote Record</th>
                                        <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">Canonical URL</th>
                                        <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">SKU</th>
                                        <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">Price</th>
                                        <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">Stock</th>
                                        <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">Status</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                                    {mappings.map((m) => (
                                        <tr key={m.id} className="bg-white transition-colors hover:bg-gray-50 dark:bg-gray-900 dark:hover:bg-gray-800/50">
                                            <td className="px-4 py-3">
                                                <p className="font-medium text-gray-900 dark:text-white truncate max-w-[200px]">{m.remote_name || "—"}</p>
                                                <p className="text-xs text-gray-400">ID: {m.remote_entity_id}</p>
                                            </td>
                                            <td className="px-4 py-3">
                                                <a href={m.canonical_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline text-xs truncate block max-w-[200px] dark:text-blue-400">{m.canonical_url}</a>
                                            </td>
                                            <td className="px-4 py-3 text-gray-600 dark:text-gray-400 font-mono text-xs">{m.remote_sku || "—"}</td>
                                            <td className="px-4 py-3 text-gray-900 dark:text-white">{m.remote_price || "—"}</td>
                                            <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{m.remote_stock || "—"}</td>
                                            <td className="px-4 py-3"><Badge variant={statusBadgeVariant(m.sync_status)}>{m.sync_status}</Badge></td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}

            {tab === "logs" && (
                <div>
                    {logs.length === 0 ? (
                        <div className="rounded-xl border border-dashed border-gray-300 py-12 text-center dark:border-gray-700">
                            <p className="text-gray-500 dark:text-gray-400">No sync history yet</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {logs.map((l) => (
                                <div key={l.id} className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                                    <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm ${l.status === "success" ? "bg-green-50 text-green-600 dark:bg-green-500/10" :
                                            l.status === "error" ? "bg-red-50 text-red-600 dark:bg-red-500/10" :
                                                "bg-yellow-50 text-yellow-600 dark:bg-yellow-500/10"
                                        }`}>
                                        {l.action === "pull" ? "↓" : l.action === "push" ? "↑" : "⟲"}
                                    </div>
                                    <div className="flex-1">
                                        <p className="text-sm font-medium text-gray-900 dark:text-white capitalize">{l.action}</p>
                                        <p className="text-xs text-gray-500 dark:text-gray-400">{l.records_affected} records · {l.executed_at ? formatDateTime(l.executed_at) : ""}</p>
                                    </div>
                                    <Badge variant={statusBadgeVariant(l.status)}>{l.status}</Badge>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
