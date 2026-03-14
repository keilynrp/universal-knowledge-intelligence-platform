"use client";

import { useState, useEffect, useCallback } from "react";
import { PageHeader, Badge, useToast } from "../../components/ui";
import { apiFetch } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

interface Entity {
    id: number;
    entity_name: string | null;
    brand_capitalized: string | null;
    status: string | null;
    classification: string | null;
    model: string | null;
    sku: string | null;
    [key: string]: unknown;
}

const EDITABLE_FIELDS = [
    { key: "entity_name",       label: "Name" },
    { key: "brand_capitalized", label: "Primary Label" },
    { key: "status",            label: "Status" },
    { key: "classification",    label: "Classification" },
    { key: "model",             label: "Secondary Label" },
    { key: "variant",           label: "Variant" },
    { key: "entity_type",       label: "Entity Type" },
];

const inputClass = "h-9 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none transition-colors focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:border-gray-700 dark:bg-gray-800 dark:text-white";

function Spinner({ className = "h-4 w-4" }: { className?: string }) {
    return (
        <svg className={`${className} animate-spin`} fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
    );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function BulkEditPage() {
    const { toast } = useToast();
    const [entities, setEntities] = useState<Entity[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const [search, setSearch] = useState("");
    const [selected, setSelected] = useState<Set<number>>(new Set());
    const pageSize = 50;

    // Bulk update form
    const [showBulkEdit, setShowBulkEdit] = useState(false);
    const [bulkField, setBulkField] = useState(EDITABLE_FIELDS[0].key);
    const [bulkValue, setBulkValue] = useState("");
    const [bulkSaving, setBulkSaving] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams({
                skip: String(page * pageSize),
                limit: String(pageSize),
            });
            if (search) params.set("search", search);
            const res = await apiFetch(`/entities?${params}`);
            if (res.ok) {
                const totalCount = res.headers.get("X-Total-Count");
                setTotal(totalCount ? parseInt(totalCount) : 0);
                setEntities(await res.json());
            }
        } finally {
            setLoading(false);
        }
    }, [page, search]);

    useEffect(() => { load(); }, [load]);

    const toggleSelect = (id: number) => {
        setSelected(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    };

    const selectAll = () => {
        if (selected.size === entities.length) {
            setSelected(new Set());
        } else {
            setSelected(new Set(entities.map(e => e.id)));
        }
    };

    const handleBulkUpdate = async () => {
        if (selected.size === 0) { toast("Select at least one entity", "warning"); return; }
        if (!bulkValue.trim()) { toast("Enter a value", "warning"); return; }
        setBulkSaving(true);
        try {
            const res = await apiFetch("/entities/bulk-update", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    ids: Array.from(selected),
                    updates: { [bulkField]: bulkValue.trim() },
                }),
            });
            if (res.ok) {
                const data = await res.json();
                toast(`Updated ${data.updated} entities`, "success");
                setSelected(new Set());
                setShowBulkEdit(false);
                setBulkValue("");
                load();
            } else {
                const err = await res.json();
                toast(err.detail || "Update failed", "error");
            }
        } finally {
            setBulkSaving(false);
        }
    };

    const handleBulkDelete = async () => {
        if (selected.size === 0) { toast("Select at least one entity", "warning"); return; }
        if (!confirm(`Delete ${selected.size} entities? This cannot be undone.`)) return;
        const res = await apiFetch("/entities/bulk", {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ids: Array.from(selected) }),
        });
        if (res.ok) {
            const data = await res.json();
            toast(`Deleted ${data.deleted} entities`, "success");
            setSelected(new Set());
            load();
        }
    };

    const totalPages = Math.ceil(total / pageSize);

    return (
        <div className="space-y-5">
            <PageHeader
                breadcrumbs={[
                    { label: "Home", href: "/" },
                    { label: "Knowledge Explorer", href: "/" },
                    { label: "Bulk Editor" },
                ]}
                title="Bulk Entity Editor"
                description="Select multiple entities for batch field updates or bulk deletion"
            />

            {/* Search + actions bar */}
            <div className="flex flex-wrap items-center gap-3">
                <div className="relative flex-1">
                    <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <input
                        type="text"
                        placeholder="Search entities…"
                        value={search}
                        onChange={e => { setSearch(e.target.value); setPage(0); }}
                        className="h-10 w-full rounded-xl border border-gray-200 bg-white pl-10 pr-4 text-sm text-gray-900 outline-none transition-colors focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:border-gray-700 dark:bg-gray-800 dark:text-white"
                    />
                </div>
                <span className="text-sm text-gray-400">{total} entities · {selected.size} selected</span>
            </div>

            {/* Bulk action toolbar — visible when items selected */}
            {selected.size > 0 && (
                <div className="flex items-center gap-3 rounded-2xl border border-indigo-200 bg-gradient-to-r from-indigo-50 to-white px-5 py-3 shadow-sm dark:border-indigo-500/20 dark:from-indigo-500/5 dark:to-gray-900">
                    <span className="text-sm font-semibold text-indigo-700 dark:text-indigo-400">
                        {selected.size} selected
                    </span>
                    <div className="mx-2 h-5 w-px bg-indigo-200 dark:bg-indigo-500/30" />
                    <button
                        onClick={() => setShowBulkEdit(s => !s)}
                        className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-700"
                    >
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                        Batch Edit
                    </button>
                    <button
                        onClick={handleBulkDelete}
                        className="flex items-center gap-1.5 rounded-lg bg-red-50 px-3 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-100 dark:bg-red-500/10 dark:text-red-400"
                    >
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>
                        Bulk Delete
                    </button>
                    <button
                        onClick={() => setSelected(new Set())}
                        className="ml-auto text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    >
                        Clear selection
                    </button>
                </div>
            )}

            {/* Batch edit form */}
            {showBulkEdit && selected.size > 0 && (
                <div className="rounded-2xl border border-indigo-200 bg-indigo-50/50 p-5 dark:border-indigo-500/20 dark:bg-indigo-500/5">
                    <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">
                        Batch update {selected.size} entities
                    </h3>
                    <div className="flex items-end gap-3">
                        <div className="flex-1">
                            <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Field</label>
                            <select
                                value={bulkField}
                                onChange={e => setBulkField(e.target.value)}
                                className={inputClass}
                            >
                                {EDITABLE_FIELDS.map(f => (
                                    <option key={f.key} value={f.key}>{f.label}</option>
                                ))}
                            </select>
                        </div>
                        <div className="flex-[2]">
                            <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">New Value</label>
                            <input
                                type="text"
                                value={bulkValue}
                                onChange={e => setBulkValue(e.target.value)}
                                placeholder={`Set ${EDITABLE_FIELDS.find(f => f.key === bulkField)?.label} to…`}
                                className={inputClass}
                            />
                        </div>
                        <button
                            onClick={handleBulkUpdate}
                            disabled={bulkSaving || !bulkValue.trim()}
                            className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                        >
                            {bulkSaving && <Spinner />}
                            {bulkSaving ? "Updating…" : "Apply"}
                        </button>
                    </div>
                </div>
            )}

            {/* Entity table */}
            <div className="overflow-x-auto rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
                {loading ? (
                    <div className="flex justify-center py-16">
                        <Spinner className="h-7 w-7 text-indigo-600" />
                    </div>
                ) : entities.length === 0 ? (
                    <div className="py-16 text-center text-sm text-gray-400 dark:text-gray-500">
                        {search ? "No entities match your search" : "No entities available"}
                    </div>
                ) : (
                    <table className="w-full min-w-[700px] text-sm">
                        <thead>
                            <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:border-gray-800 dark:text-gray-400">
                                <th className="px-4 py-3">
                                    <input
                                        type="checkbox"
                                        checked={selected.size === entities.length && entities.length > 0}
                                        onChange={selectAll}
                                        className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                                    />
                                </th>
                                <th className="px-4 py-3">ID</th>
                                <th className="px-4 py-3">Name</th>
                                <th className="px-4 py-3">Primary Label</th>
                                <th className="px-4 py-3">Status</th>
                                <th className="px-4 py-3">Classification</th>
                                <th className="px-4 py-3">Secondary Label</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                            {entities.map(entity => {
                                const isSelected = selected.has(entity.id);
                                return (
                                    <tr
                                        key={entity.id}
                                        onClick={() => toggleSelect(entity.id)}
                                        className={`cursor-pointer transition-colors ${
                                            isSelected
                                                ? "bg-indigo-50 dark:bg-indigo-500/5"
                                                : "hover:bg-gray-50 dark:hover:bg-gray-800/50"
                                        }`}
                                    >
                                        <td className="px-4 py-3">
                                            <input
                                                type="checkbox"
                                                checked={isSelected}
                                                onChange={() => toggleSelect(entity.id)}
                                                onClick={e => e.stopPropagation()}
                                                className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                                            />
                                        </td>
                                        <td className="px-4 py-3 font-mono text-xs text-gray-400">{entity.id}</td>
                                        <td className="max-w-[200px] truncate px-4 py-3 font-medium text-gray-900 dark:text-white">
                                            {entity.entity_name || "—"}
                                        </td>
                                        <td className="px-4 py-3 text-gray-600 dark:text-gray-300">
                                            {entity.brand_capitalized || "—"}
                                        </td>
                                        <td className="px-4 py-3">
                                            <Badge variant={entity.status === "active" ? "success" : "default"}>
                                                {entity.status || "—"}
                                            </Badge>
                                        </td>
                                        <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                                            {entity.classification || "—"}
                                        </td>
                                        <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                                            {entity.model || "—"}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2">
                    <button
                        disabled={page <= 0}
                        onClick={() => setPage(p => p - 1)}
                        className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-40 dark:border-gray-700 dark:text-gray-400"
                    >
                        ← Previous
                    </button>
                    <span className="text-xs text-gray-400">
                        Page {page + 1} of {totalPages}
                    </span>
                    <button
                        disabled={page >= totalPages - 1}
                        onClick={() => setPage(p => p + 1)}
                        className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-40 dark:border-gray-700 dark:text-gray-400"
                    >
                        Next →
                    </button>
                </div>
            )}
        </div>
    );
}
