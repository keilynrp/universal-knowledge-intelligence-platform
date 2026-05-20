"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

interface Relationship {
    id: number;
    source_id: number;
    target_id: number;
    relation_type: string;
    weight: number;
    notes: string | null;
    created_at: string;
}

interface EntitySearchHit {
    id: number;
    primary_label: string | null;
    entity_type: string | null;
    domain: string | null;
}

interface RelationshipSuggestion {
    target_id: number;
    target_label: string;
    target_type: string | null;
    relation_type: string;
    weight: number;
    reason: string;
}

const RELATION_TYPES = ["related-to", "cites", "authored-by", "belongs-to", "published-in", "has-concept", "identified-by", "coauthor-with", "external-signal-for", "semantic-neighbor", "derived-keyword", "emerging-from"];

const TYPE_COLORS: Record<string, string> = {
    "cites":       "bg-indigo-100 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400",
    "authored-by": "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
    "belongs-to":  "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
    "published-in": "bg-cyan-100 text-cyan-700 dark:bg-cyan-500/10 dark:text-cyan-400",
    "has-concept": "bg-pink-100 text-pink-700 dark:bg-pink-500/10 dark:text-pink-400",
    "identified-by": "bg-slate-100 text-slate-700 dark:bg-slate-500/10 dark:text-slate-300",
    "coauthor-with": "bg-teal-100 text-teal-700 dark:bg-teal-500/10 dark:text-teal-400",
    "keyword-co-occurs-with": "bg-orange-100 text-orange-700 dark:bg-orange-500/10 dark:text-orange-400",
    "same-as": "bg-slate-200 text-slate-900 dark:bg-slate-400/20 dark:text-slate-100",
    "equivalent-to": "bg-purple-100 text-purple-700 dark:bg-purple-500/10 dark:text-purple-300",
    "external-signal-for": "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300",
    "semantic-neighbor": "bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300",
    "derived-keyword": "bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-500/10 dark:text-fuchsia-300",
    "emerging-from": "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300",
    "related-to":  "bg-violet-100 text-violet-700 dark:bg-violet-500/10 dark:text-violet-400",
};

export default function RelationshipManager({
    entityId,
    onRefreshGraph,
}: {
    entityId: number;
    onRefreshGraph: () => void;
}) {
    const [relationships, setRelationships] = useState<Relationship[]>([]);
    const [loading, setLoading] = useState(true);
    const [suggestions, setSuggestions] = useState<RelationshipSuggestion[]>([]);
    const [loadingSuggestions, setLoadingSuggestions] = useState(true);

    // Add form state
    const [targetId, setTargetId] = useState("");
    const [targetQuery, setTargetQuery] = useState("");
    const [targetResults, setTargetResults] = useState<EntitySearchHit[]>([]);
    const [searchingTarget, setSearchingTarget] = useState(false);
    const [relType, setRelType] = useState("related-to");
    const [weight, setWeight] = useState("1.0");
    const [notes, setNotes] = useState("");
    const [adding, setAdding] = useState(false);
    const [addError, setAddError] = useState<string | null>(null);

    const [deletingId, setDeletingId] = useState<number | null>(null);

    useEffect(() => {
        fetchRelationships();
        fetchSuggestions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [entityId]);

    useEffect(() => {
        const trimmed = targetQuery.trim();
        if (trimmed.length < 2) {
            setTargetResults([]);
            return;
        }
        let active = true;
        const timer = window.setTimeout(async () => {
            setSearchingTarget(true);
            try {
                const res = await apiFetch(`/entities?search=${encodeURIComponent(trimmed)}&limit=6`);
                if (!active) return;
                const rows = res.ok ? await res.json() : [];
                setTargetResults((rows as EntitySearchHit[]).filter((row) => row.id !== entityId));
            } finally {
                if (active) setSearchingTarget(false);
            }
        }, 220);
        return () => {
            active = false;
            window.clearTimeout(timer);
        };
    }, [entityId, targetQuery]);

    async function fetchRelationships() {
        setLoading(true);
        try {
            const res = await apiFetch(`/entities/${entityId}/relationships`);
            if (res.ok) setRelationships(await res.json());
        } finally {
            setLoading(false);
        }
    }

    async function fetchSuggestions() {
        setLoadingSuggestions(true);
        try {
            const res = await apiFetch(`/entities/${entityId}/relationships/suggestions?limit=6`);
            if (res.ok) {
                const data = await res.json();
                setSuggestions(data.suggestions ?? []);
            }
        } finally {
            setLoadingSuggestions(false);
        }
    }

    async function createRelationship(target: number, type: string, relationshipWeight: number, relationshipNotes?: string | null) {
        const res = await apiFetch(`/entities/${entityId}/relationships`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                target_id: target,
                relation_type: type,
                weight: relationshipWeight,
                notes: relationshipNotes,
            }),
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail ?? "Failed to add relationship");
        }
        await fetchRelationships();
        await fetchSuggestions();
        onRefreshGraph();
    }

    async function handleAdd(e: React.FormEvent) {
        e.preventDefault();
        setAddError(null);
        const tid = parseInt(targetId);
        if (!tid || isNaN(tid)) { setAddError("Target entity ID must be a number"); return; }
        setAdding(true);
        try {
            await createRelationship(tid, relType, parseFloat(weight) || 1.0, notes.trim() || null);
            setTargetId("");
            setTargetQuery("");
            setTargetResults([]);
            setNotes("");
            setWeight("1.0");
        } catch (error) {
            setAddError(error instanceof Error ? error.message : "Failed to add relationship");
        } finally {
            setAdding(false);
        }
    }

    async function handleDelete(relId: number) {
        setDeletingId(relId);
        try {
            await apiFetch(`/relationships/${relId}`, { method: "DELETE" });
            setRelationships((prev) => prev.filter((r) => r.id !== relId));
            await fetchSuggestions();
            onRefreshGraph();
        } finally {
            setDeletingId(null);
        }
    }

    return (
        <div className="space-y-5">
            <div className="rounded-xl border border-indigo-100 bg-indigo-50/70 p-4 dark:border-indigo-500/20 dark:bg-indigo-500/10">
                <div className="mb-3 flex items-center justify-between gap-3">
                    <div>
                        <p className="text-xs font-bold uppercase tracking-wider text-indigo-700 dark:text-indigo-300">Relaciones sugeridas</p>
                        <p className="mt-1 text-xs text-indigo-700/70 dark:text-indigo-200/70">Conexiones inferidas desde batch, conceptos, autores y nodos derivados.</p>
                    </div>
                    {loadingSuggestions && <span className="text-xs font-semibold text-indigo-500">Analizando...</span>}
                </div>
                {!loadingSuggestions && suggestions.length === 0 ? (
                    <p className="text-xs text-indigo-700/70 dark:text-indigo-200/70">No hay sugerencias automáticas todavía. Genera relaciones desde el grafo o busca una entidad por nombre.</p>
                ) : (
                    <div className="grid gap-2 md:grid-cols-2">
                        {suggestions.map((suggestion) => (
                            <div key={`${suggestion.target_id}-${suggestion.relation_type}`} className="rounded-xl border border-white/70 bg-white p-3 shadow-sm dark:border-white/10 dark:bg-slate-950/40">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="min-w-0">
                                        <p className="truncate text-sm font-bold text-slate-900 dark:text-white">{suggestion.target_label}</p>
                                        <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">{suggestion.reason}</p>
                                    </div>
                                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${TYPE_COLORS[suggestion.relation_type] ?? TYPE_COLORS["related-to"]}`}>
                                        {suggestion.relation_type}
                                    </span>
                                </div>
                                <button
                                    onClick={() => void createRelationship(suggestion.target_id, suggestion.relation_type, suggestion.weight, suggestion.reason)}
                                    className="mt-3 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-bold text-white transition hover:bg-indigo-700"
                                >
                                    Aceptar relación
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Add form */}
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/50">
                <p className="mb-3 text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Add Relationship
                </p>
                <form onSubmit={handleAdd} className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <div className="relative col-span-2">
                        <label className="mb-1 block text-[10px] font-medium text-gray-500">Buscar entidad destino</label>
                        <input
                            type="text"
                            value={targetQuery}
                            onChange={(e) => setTargetQuery(e.target.value)}
                            placeholder="Nombre, DOI, concepto..."
                            className="h-8 w-full rounded-lg border border-gray-200 bg-white px-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                        />
                        {(targetResults.length > 0 || searchingTarget) && (
                            <div className="absolute left-0 right-0 top-full z-20 mt-1 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-900">
                                {searchingTarget && <p className="px-3 py-2 text-xs text-gray-400">Buscando...</p>}
                                {targetResults.map((result) => (
                                    <button
                                        type="button"
                                        key={result.id}
                                        onClick={() => {
                                            setTargetId(String(result.id));
                                            setTargetQuery(result.primary_label || `Entity #${result.id}`);
                                            setTargetResults([]);
                                        }}
                                        className="block w-full px-3 py-2 text-left hover:bg-indigo-50 dark:hover:bg-indigo-500/10"
                                    >
                                        <span className="block truncate text-xs font-bold text-gray-800 dark:text-white">{result.primary_label || `Entity #${result.id}`}</span>
                                        <span className="text-[10px] text-gray-400">#{result.id} · {result.entity_type || "entity"} · {result.domain || "domain"}</span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                    <div>
                        <label className="mb-1 block text-[10px] font-medium text-gray-500">Target ID</label>
                        <input
                            type="number"
                            min="1"
                            value={targetId}
                            onChange={(e) => setTargetId(e.target.value)}
                            placeholder="e.g. 42"
                            className="h-8 w-full rounded-lg border border-gray-200 bg-white px-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                            required
                        />
                    </div>
                    <div>
                        <label className="mb-1 block text-[10px] font-medium text-gray-500">Relation Type</label>
                        <select
                            value={relType}
                            onChange={(e) => setRelType(e.target.value)}
                            className="h-8 w-full rounded-lg border border-gray-200 bg-white px-2 text-sm outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                        >
                            {RELATION_TYPES.map((t) => (
                                <option key={t} value={t}>{t}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="mb-1 block text-[10px] font-medium text-gray-500">Weight (0–10)</label>
                        <input
                            type="number"
                            min="0"
                            max="10"
                            step="0.1"
                            value={weight}
                            onChange={(e) => setWeight(e.target.value)}
                            className="h-8 w-full rounded-lg border border-gray-200 bg-white px-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                        />
                    </div>
                    <div className="flex items-end">
                        <button
                            type="submit"
                            disabled={adding}
                            className="h-8 w-full rounded-lg bg-indigo-600 px-3 text-xs font-semibold text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
                        >
                            {adding ? "Adding\u2026" : "+ Add"}
                        </button>
                    </div>
                    <div className="col-span-2 sm:col-span-4">
                        <input
                            type="text"
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            placeholder="Optional notes\u2026"
                            maxLength={500}
                            className="h-8 w-full rounded-lg border border-gray-200 bg-white px-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                        />
                    </div>
                </form>
                {addError && (
                    <p className="mt-2 text-xs text-red-600 dark:text-red-400">{addError}</p>
                )}
            </div>

            {/* Relationship list */}
            {loading ? (
                <div className="flex h-20 items-center justify-center">
                    <svg className="h-5 w-5 animate-spin text-indigo-500" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                </div>
            ) : relationships.length === 0 ? (
                <p className="text-center text-sm text-gray-400 dark:text-gray-500">No relationships yet.</p>
            ) : (
                <div className="space-y-2">
                    {relationships.map((rel) => {
                        const isSource = rel.source_id === entityId;
                        const otherId = isSource ? rel.target_id : rel.source_id;
                        const direction = isSource ? "\u2192" : "\u2190";
                        const typeColor = TYPE_COLORS[rel.relation_type] ?? "bg-gray-100 text-gray-700";
                        return (
                            <div
                                key={rel.id}
                                className="flex items-center gap-3 rounded-lg border border-gray-100 bg-white px-3 py-2.5 shadow-sm dark:border-gray-800 dark:bg-gray-900"
                            >
                                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${typeColor}`}>
                                    {rel.relation_type}
                                </span>
                                <span className="text-xs text-gray-400">{direction}</span>
                                <Link
                                    href={`/entities/${otherId}`}
                                    className="text-sm font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                                >
                                    Entity #{otherId}
                                </Link>
                                {rel.weight !== 1.0 && (
                                    <span className="text-[10px] text-gray-400">w={rel.weight}</span>
                                )}
                                {rel.notes && (
                                    <span className="truncate text-xs text-gray-400 italic">{rel.notes}</span>
                                )}
                                <button
                                    onClick={() => handleDelete(rel.id)}
                                    disabled={deletingId === rel.id}
                                    className="ml-auto shrink-0 rounded p-1 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500 disabled:opacity-50 dark:hover:bg-red-500/10 dark:hover:text-red-400"
                                    title="Delete relationship"
                                >
                                    <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
