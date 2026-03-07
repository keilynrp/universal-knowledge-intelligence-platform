"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import MonteCarloChart from "./MonteCarloChart";
import { useDomain } from "../contexts/DomainContext";
import { apiFetch } from "@/lib/api";
import { Badge, useToast } from "./ui";

interface Entity {
    id: number;
    entity_name: string;
    brand_capitalized: string | null; // Changed to string | null
    model: string | null; // Changed to string | null
    sku: string | null; // Changed to string | null
    classification: string | null; // Changed to string | null
    entity_type: string | null; // Changed to string | null
    variant: string | null; // Changed to string | null
    gtin: string | null; // Changed to string | null
    barcode: string;
    status: string | null; // Changed to string | null
    validation_status: string;
    enrichment_status?: string;
    normalized_json: string | null; // Added normalized_json
}

type EditableFields = Pick<Entity, "entity_name" | "brand_capitalized" | "model" | "sku" | "classification" | "entity_type" | "validation_status" | "gtin" | "variant" | "status">;

export default function EntityTable() {
    const { activeDomain, activeDomainId } = useDomain();
    const { toast } = useToast();
    const [entities, setEntities] = useState<Entity[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");
    const [page, setPage] = useState(0);
    const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
    const [limit, setLimit] = useState(20);

    // Edit state
    const [editingId, setEditingId] = useState<number | null>(null);
    const [editData, setEditData] = useState<EditableFields>({
        entity_name: "",
        brand_capitalized: "",
        model: "",
        sku: "",
        classification: "",
        entity_type: "",
        validation_status: "",
        gtin: "",
        variant: "",
        status: "",
    });
    const [saving, setSaving] = useState(false);

    const [enrichingId, setEnrichingId] = useState<number | null>(null);

    // Delete state
    const [deletingId, setDeletingId] = useState<number | null>(null);

    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedSearch(search);
            setPage(0);
        }, 500);
        return () => clearTimeout(handler);
    }, [search]);

    const fetchEntities = useCallback(async () => {
        setLoading(true);
        try {
            const queryParams = new URLSearchParams({
                skip: (page * limit).toString(),
                limit: limit.toString(),
            });
            if (debouncedSearch) queryParams.append("search", debouncedSearch);

            const res = await apiFetch(`/entities?${queryParams}`);
            if (!res.ok) throw new Error("Failed to fetch entities");
            setEntities(await res.json());
        } catch (error) {
            console.error("Error fetching entities:", error);
        } finally {
            setLoading(false);
        }
    }, [debouncedSearch, page, limit, activeDomainId]);

    useEffect(() => { fetchEntities(); }, [fetchEntities]);

    function startEdit(entity: Entity) {
        setEditingId(entity.id);
        setEditData({
            entity_name: entity.entity_name || "",
            brand_capitalized: entity.brand_capitalized || "",
            model: entity.model || "",
            sku: entity.sku || "",
            classification: entity.classification || "",
            entity_type: entity.entity_type || "",
            validation_status: entity.validation_status || "pending",
            gtin: entity.gtin || "",
            variant: entity.variant || "",
            status: entity.status || "",
        });
    }

    function cancelEdit() {
        setEditingId(null);
    }

    async function saveEdit() {
        if (!editingId) return;
        setSaving(true);
        try {
            const res = await apiFetch(`/entities/${editingId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(editData),
            });
            if (!res.ok) throw new Error("Failed to update");
            const updated = await res.json();
            setEntities((prev) => prev.map((e) => (e.id === editingId ? updated : e)));
            setEditingId(null);
        } catch (error) {
            console.error(error);
            toast("Error updating entity", "error");
        } finally {
            setSaving(false);
        }
    }

    async function deleteEntity(id: number) {
        setDeletingId(id);
        try {
            const res = await apiFetch(`/entities/${id}`, { method: "DELETE" });
            if (!res.ok) throw new Error("Failed to delete");
            setEntities((prev) => prev.filter((e) => e.id !== id));
            toast("Entity deleted", "success");
        } catch (error) {
            console.error(error);
            toast("Error deleting entity", "error");
        } finally {
            setDeletingId(null);
        }
    }

    async function enrichEntity(id: number) {
        setEnrichingId(id);
        try {
            const res = await apiFetch(`/enrich/row/${id}`, { method: "POST" });
            if (!res.ok) throw new Error("Failed to enrich");
            const enriched = await res.json();
            setEntities((prev) => prev.map((e) => (e.id === id ? { ...e, ...enriched } : e)));
            toast("Enrichment complete", "success");
        } catch (error) {
            console.error(error);
            toast("Error enriching entity", "error");
        } finally {
            setEnrichingId(null);
        }
    }

    const thClass = "px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400";
    const inputClass = "h-8 w-full rounded border border-gray-200 bg-white px-2 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white";

    return (
        <div className="space-y-6">
            {/* Search bar */}
            <div className="flex items-center justify-between">
                <div className="relative">
                    <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <input
                        type="text"
                        placeholder="Search entities..."
                        className="h-10 w-80 rounded-lg border border-gray-200 bg-white pl-10 pr-4 text-sm text-gray-700 placeholder-gray-400 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:placeholder-gray-500 dark:focus:border-blue-500"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                    Page {page + 1}
                </span>
            </div>

            {/* Table card */}
            <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <div className="table-container">
                    <table className="w-full min-w-[1200px] text-left text-sm">
                        <thead>
                            <tr className="border-b border-gray-200 dark:border-gray-800">
                                <th className={`${thClass} no-wrap w-16`}>ID</th>
                                {activeDomain ? (
                                    activeDomain.attributes.map(attr => (
                                        <th key={attr.name} className={`${thClass} no-wrap`}>{attr.label}</th>
                                    ))
                                ) : (
                                    <th className={`${thClass} no-wrap`}>Entity Name</th>
                                )}
                                <th className={`${thClass} no-wrap`}>System Status</th>
                                <th className={`${thClass} no-wrap text-right`}>Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                            {loading ? (
                                <tr>
                                    <td colSpan={11} className="px-5 py-12 text-center">
                                        <div className="flex flex-col items-center gap-2">
                                            <svg className="h-6 w-6 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                            </svg>
                                            <span className="text-sm text-gray-500 dark:text-gray-400">Loading entities...</span>
                                        </div>
                                    </td>
                                </tr>
                            ) : entities.length === 0 ? (
                                <tr>
                                    <td colSpan={11} className="px-5 py-12 text-center">
                                        <div className="flex flex-col items-center gap-2">
                                            <svg className="h-10 w-10 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                                            </svg>
                                            <span className="text-sm text-gray-500 dark:text-gray-400">No entities found</span>
                                        </div>
                                    </td>
                                </tr>
                            ) : (
                                entities.map((entity) => {
                                    const isEditing = editingId === entity.id;

                                    let parsedJson: Record<string, any> = {};
                                    if (entity.normalized_json) {
                                        try { parsedJson = JSON.parse(entity.normalized_json); } catch (e) { }
                                    }

                                    if (isEditing) {
                                        return (
                                            <tr key={entity.id} className="bg-blue-50/50 dark:bg-blue-500/5">
                                                <td className="px-5 py-2.5 text-gray-500 dark:text-gray-400">{entity.id}</td>
                                                {activeDomain ? (
                                                    activeDomain.attributes.map(attr => {
                                                        const val = attr.is_core ? editData[attr.name as keyof typeof editData] : (parsedJson[attr.name] || "");
                                                        // Fallback safe value rendering
                                                        return (
                                                            <td key={attr.name} className="px-5 py-2.5">
                                                                <input
                                                                    className={inputClass}
                                                                    value={String(val || "")}
                                                                    onChange={(e) => {
                                                                        if (attr.is_core) setEditData({ ...editData, [attr.name]: e.target.value });
                                                                    }}
                                                                    disabled={!attr.is_core} // Just core editing supported for now
                                                                    title={!attr.is_core ? "Extended attributes cannot be edited natively yet" : ""}
                                                                />
                                                            </td>
                                                        );
                                                    })
                                                ) : (
                                                    <td className="px-5 py-2.5">
                                                        <input className={inputClass} value={editData.entity_name} onChange={(e) => setEditData({ ...editData, entity_name: e.target.value })} />
                                                    </td>
                                                )}
                                                <td className="px-5 py-2.5">
                                                    <select
                                                        className={inputClass}
                                                        value={editData.validation_status}
                                                        onChange={(e) => setEditData({ ...editData, validation_status: e.target.value })}
                                                    >
                                                        <option value="pending">pending</option>
                                                        <option value="valid">valid</option>
                                                        <option value="invalid">invalid</option>
                                                    </select>
                                                </td>
                                                <td className="px-5 py-2.5">
                                                    <div className="flex items-center justify-end gap-1">
                                                        <button
                                                            onClick={saveEdit}
                                                            disabled={saving}
                                                            className="rounded-lg p-1.5 text-green-600 hover:bg-green-100 disabled:opacity-50 dark:text-green-400 dark:hover:bg-green-500/10"
                                                            title="Save"
                                                        >
                                                            {saving ? (
                                                                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                                                </svg>
                                                            ) : (
                                                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                                                </svg>
                                                            )}
                                                        </button>
                                                        <button
                                                            onClick={cancelEdit}
                                                            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                                                            title="Cancel"
                                                        >
                                                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                                            </svg>
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        );
                                    }

                                    return (
                                        <tr key={entity.id} className="group transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50">
                                            <td className="px-5 py-3.5 text-gray-500 dark:text-gray-400">{entity.id}</td>
                                            {activeDomain ? (
                                                activeDomain.attributes.map(attr => {
                                                    let val = attr.is_core ? (entity as any)[attr.name] : (parsedJson[attr.name] || "");
                                                    return (
                                                        <td key={attr.name} className="px-5 py-3.5 text-gray-600 dark:text-gray-300">
                                                            {val !== null && val !== "" ? (
                                                                attr.name === "gtin" || attr.name === "sku" || attr.name === "doi" ? (
                                                                    <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                                                                        {val}
                                                                    </code>
                                                                ) : String(val)
                                                            ) : (
                                                                <span className="text-gray-400">—</span>
                                                            )}
                                                        </td>
                                                    );
                                                })
                                            ) : (
                                                <td className="px-5 py-3.5 font-medium text-gray-900 dark:text-white">
                                                    {entity.entity_name}
                                                </td>
                                            )}
                                            <td className="px-5 py-3.5">
                                                <Badge variant={
                                                    entity.validation_status === "valid" || entity.validation_status === "active" ? "success" :
                                                    entity.validation_status === "invalid" ? "error" :
                                                    entity.validation_status === "inactive" ? "default" : "warning"
                                                }>{entity.validation_status}</Badge>
                                            </td>
                                            <td className="px-5 py-3.5">
                                                <div className="flex items-center justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                                                    <button
                                                        onClick={() => setSelectedEntity(entity)}
                                                        className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800"
                                                        title="Quick view"
                                                    >
                                                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                                        </svg>
                                                    </button>
                                                    <Link
                                                        href={`/entities/${entity.id}`}
                                                        className="rounded-lg p-1.5 text-gray-400 hover:bg-blue-100 hover:text-blue-600 dark:hover:bg-blue-500/10 dark:hover:text-blue-400"
                                                        title="View full details"
                                                    >
                                                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                                                        </svg>
                                                    </Link>
                                                    <button
                                                        onClick={() => startEdit(entity)}
                                                        className="rounded-lg p-1.5 text-gray-400 hover:bg-blue-100 hover:text-blue-600 dark:hover:bg-blue-500/10 dark:hover:text-blue-400"
                                                        title="Edit"
                                                    >
                                                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                                                        </svg>
                                                    </button>
                                                    <button
                                                        onClick={() => {
                                                            if (confirm(`Delete entity #${entity.id} "${entity.entity_name}"?`)) {
                                                                deleteEntity(entity.id);
                                                            }
                                                        }}
                                                        disabled={deletingId === entity.id}
                                                        className="rounded-lg p-1.5 text-gray-400 hover:bg-red-100 hover:text-red-600 disabled:opacity-50 dark:hover:bg-red-500/10 dark:hover:text-red-400"
                                                        title="Delete"
                                                    >
                                                        {deletingId === entity.id ? (
                                                            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                                            </svg>
                                                        ) : (
                                                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                                                            </svg>
                                                        )}
                                                    </button>
                                                    <button
                                                        onClick={() => enrichEntity(entity.id)}
                                                        disabled={enrichingId === entity.id}
                                                        className="rounded-lg p-1.5 text-gray-400 hover:bg-purple-100 hover:text-purple-600 disabled:opacity-50 dark:hover:bg-purple-500/10 dark:hover:text-purple-400"
                                                        title="Enrich entity"
                                                    >
                                                        {enrichingId === entity.id ? (
                                                            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                                            </svg>
                                                        ) : (
                                                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                                                            </svg>
                                                        )}
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Details Modal */}
                {selectedEntity && (
                    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
                        <div className="flex h-[90vh] w-full max-w-4xl flex-col rounded-2xl bg-white shadow-2xl dark:bg-gray-900">
                            <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4 dark:border-gray-800">
                                <div>
                                    <h2 className="text-xl font-bold text-gray-900 dark:text-white">{selectedEntity.entity_name}</h2>
                                    <p className="text-sm text-gray-500">Full details and attributes</p>
                                </div>
                                <button onClick={() => setSelectedEntity(null)} className="rounded-lg p-2 hover:bg-gray-100 dark:hover:bg-gray-800">
                                    <svg className="h-6 w-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                            <div className="flex-1 overflow-y-auto p-6">
                                <div className="grid grid-cols-1 gap-x-8 gap-y-6 md:grid-cols-2">
                                    {Object.entries(selectedEntity).map(([key, value]) => {
                                        if (key === "id" || key === "normalized_json") return null;
                                        // Format key to Header Case
                                        const label = key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
                                        return (
                                            <div key={key} className="flex flex-col gap-1 border-b border-gray-50 pb-2 dark:border-gray-800/50">
                                                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{label}</span>
                                                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                                                    {value !== null && value !== "" ? String(value) : <span className="text-gray-300 italic">No data</span>}
                                                </span>
                                            </div>
                                        );
                                    })}
                                </div>
                                {selectedEntity.enrichment_status === "completed" && (
                                    <div className="mt-8 rounded-xl border border-purple-100 bg-white p-5 shadow-sm dark:border-purple-500/10 dark:bg-gray-800/50">
                                        <MonteCarloChart productId={selectedEntity.id} />
                                    </div>
                                )}
                            </div>
                            <div className="border-t border-gray-100 px-6 py-4 dark:border-gray-800">
                                <button
                                    onClick={() => setSelectedEntity(null)}
                                    className="w-full rounded-xl bg-gray-100 py-2.5 text-sm font-semibold text-gray-900 transition-colors hover:bg-gray-200 dark:bg-gray-800 dark:text-white dark:hover:bg-gray-700"
                                >
                                    Close Details
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Pagination */}
                <div className="flex items-center justify-between border-t border-gray-200 px-5 py-3.5 dark:border-gray-800">
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-500 dark:text-gray-400">Rows per page:</span>
                        <select
                            value={limit}
                            onChange={(e) => {
                                setLimit(Number(e.target.value));
                                setPage(0);
                            }}
                            className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-sm text-gray-700 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
                        >
                            <option value={10}>10</option>
                            <option value={20}>20</option>
                            <option value={50}>50</option>
                            <option value={100}>100</option>
                        </select>
                    </div>

                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => setPage(p => Math.max(0, p - 1))}
                            disabled={page === 0 || loading}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3.5 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                        >
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                            </svg>
                            Previous
                        </button>
                        <div className="flex items-center gap-2">
                            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm font-medium text-white">
                                {page + 1}
                            </span>
                        </div>
                        <button
                            onClick={() => setPage(p => p + 1)}
                            disabled={entities.length < limit || loading}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3.5 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                        >
                            Next
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
