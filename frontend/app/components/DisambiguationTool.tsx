"use client";

import { useState, useEffect } from "react";
import { useDomain } from "../contexts/DomainContext";
import { apiFetch } from "@/lib/api";
import { Badge, useToast } from "./ui";
import { useLanguage } from "../contexts/LanguageContext";

interface VariationGroup {
    main: string;
    variations: string[];
    count: number;
    has_rules?: boolean;
    resolved_to?: string | null;
    algorithm_used?: string;
}

interface DisambiguationResponse {
    groups: VariationGroup[];
    total_groups: number;
    algorithm?: string;
}

interface AuthorityRecord {
    id: number;
    authority_source: string;
    authority_id: string;
    canonical_label: string;
    aliases: string[];
    description: string | null;
    confidence: number;
    uri: string | null;
    status: string;
}

const SOURCE_STYLES: Record<string, { label: string; bg: string; text: string }> = {
    wikidata:  { label: "Wikidata",  bg: "bg-amber-100 dark:bg-amber-500/20",  text: "text-amber-800 dark:text-amber-300" },
    viaf:      { label: "VIAF",      bg: "bg-blue-100 dark:bg-blue-500/20",    text: "text-blue-800 dark:text-blue-300" },
    orcid:     { label: "ORCID",     bg: "bg-green-100 dark:bg-green-500/20",  text: "text-green-800 dark:text-green-300" },
    dbpedia:   { label: "DBpedia",   bg: "bg-red-100 dark:bg-red-500/20",      text: "text-red-800 dark:text-red-300" },
    openalex:  { label: "OpenAlex",  bg: "bg-violet-100 dark:bg-violet-500/20", text: "text-violet-800 dark:text-violet-300" },
};

const ALGORITHMS = [
    {
        value: "token_sort",
        label: "Token Sort",
        tip: "Agrupa variantes por orden de palabras: 'Smith John' ≈ 'John Smith'. Ideal para nombres de personas y marcas.",
    },
    {
        value: "fingerprint",
        label: "Fingerprint",
        tip: "Normaliza puntuación y mayúsculas antes de comparar: 'Apple, Inc.' ≈ 'inc apple'. Ideal para datos inconsistentes.",
    },
    {
        value: "ngram",
        label: "N-gram",
        tip: "Similitud por bigramas de caracteres (Jaccard). Robusto ante errores tipográficos y OCR: 'colour' ≈ 'color'.",
    },
    {
        value: "phonetic",
        label: "Fonético",
        tip: "Agrupa por sonido (Cologne + Metaphone): 'Müller' ≈ 'Mueller'. Ideal para nombres europeos con grafías distintas.",
    },
];

const ENTITY_TYPES = [
    { value: "general",     label: "General" },
    { value: "organization", label: "Organization / Brand" },
    { value: "person",      label: "Person / Author" },
    { value: "institution", label: "Institution" },
    { value: "concept",     label: "Concept / Category" },
];

export default function DisambiguationTool() {
    const { t } = useLanguage();
    const { activeDomain } = useDomain();
    const { toast } = useToast();
    const [field, setField] = useState("");
    const [threshold, setThreshold] = useState<number>(80);
    const [entityType, setEntityType] = useState("general");
    const [algorithm, setAlgorithm] = useState<string>("token_sort");

    useEffect(() => {
        if (activeDomain && !field) {
            const firstString = activeDomain.attributes.find(a => a.type === "string");
            if (firstString) setField(firstString.name);
        }
    }, [activeDomain, field]);

    const [groups, setGroups] = useState<VariationGroup[]>([]);
    const [loading, setLoading] = useState(false);
    const [totalGroups, setTotalGroups] = useState(0);

    // AI resolution state
    const [resolvingIdx, setResolvingIdx] = useState<number | null>(null);
    const [resolutions, setResolutions] = useState<Record<number, { canonical_value: string; reasoning: string }>>({});
    const [processingRule, setProcessingRule] = useState<number | null>(null);

    // Authority resolution state
    const [authorityLoading, setAuthorityLoading] = useState<Record<number, boolean>>({});
    const [authorityCandidates, setAuthorityCandidates] = useState<Record<number, AuthorityRecord[]>>({});
    const [authorityAction, setAuthorityAction] = useState<Record<number, number | null>>({});

    async function analyze() {
        setLoading(true);
        try {
            const res = await apiFetch(`/disambiguate/${field}?threshold=${threshold}&algorithm=${algorithm}`);
            if (!res.ok) throw new Error("Failed to fetch analysis");
            const data: DisambiguationResponse = await res.json();
            setGroups(data.groups);
            setTotalGroups(data.total_groups);
            setAuthorityCandidates({});
        } catch (error) {
            toast("Error analyzing data", "error");
        } finally {
            setLoading(false);
        }
    }

    async function resolveWithAI(idx: number, variations: string[]) {
        setResolvingIdx(idx);
        try {
            const res = await apiFetch(`/disambiguate/ai-resolve`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ field_name: field, variations })
            });
            if (!res.ok) throw new Error("AI resolve failed");
            const data = await res.json();
            setResolutions(prev => ({ ...prev, [idx]: data }));
        } catch (error) {
            toast("Error from AI resolution endpoint", "error");
        } finally {
            setResolvingIdx(null);
        }
    }

    async function acceptResolution(idx: number, canonical_value: string, variations: string[]) {
        setProcessingRule(idx);
        try {
            const res = await apiFetch(`/rules/bulk`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ field_name: field, canonical_value, variations })
            });
            if (!res.ok) throw new Error("Failed to save rules");
            await apiFetch(`/rules/apply?field_name=${field}`, { method: "POST" });
            analyze();
        } catch (error) {
            toast("Error applying rules", "error");
        } finally {
            setProcessingRule(null);
        }
    }

    async function resolveWithAuthority(idx: number, mainValue: string) {
        setAuthorityLoading(prev => ({ ...prev, [idx]: true }));
        try {
            const res = await apiFetch(`/authority/resolve`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    field_name: field,
                    value: mainValue,
                    entity_type: entityType,
                }),
            });
            if (!res.ok) throw new Error("Authority resolve failed");
            const records: AuthorityRecord[] = await res.json();
            setAuthorityCandidates(prev => ({ ...prev, [idx]: records }));
        } catch (error) {
            toast("Error querying authority sources", "error");
        } finally {
            setAuthorityLoading(prev => ({ ...prev, [idx]: false }));
        }
    }

    async function confirmCandidate(groupIdx: number, recordId: number) {
        setAuthorityAction(prev => ({ ...prev, [groupIdx]: recordId }));
        try {
            const res = await apiFetch(`/authority/records/${recordId}/confirm`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ also_create_rule: true }),
            });
            if (!res.ok) throw new Error("Confirm failed");
            const updated: AuthorityRecord = await res.json();
            setAuthorityCandidates(prev => ({
                ...prev,
                [groupIdx]: (prev[groupIdx] || []).map(r => r.id === recordId ? { ...r, status: updated.status } : r),
            }));
            toast("Candidate confirmed", "success");
        } catch (error) {
            toast("Error confirming candidate", "error");
        } finally {
            setAuthorityAction(prev => ({ ...prev, [groupIdx]: null }));
        }
    }

    async function rejectCandidate(groupIdx: number, recordId: number) {
        setAuthorityAction(prev => ({ ...prev, [groupIdx]: recordId }));
        try {
            const res = await apiFetch(`/authority/records/${recordId}/reject`, {
                method: "POST",
            });
            if (!res.ok) throw new Error("Reject failed");
            setAuthorityCandidates(prev => ({
                ...prev,
                [groupIdx]: (prev[groupIdx] || []).map(r => r.id === recordId ? { ...r, status: "rejected" } : r),
            }));
            toast("Candidate rejected", "warning");
        } catch (error) {
            toast("Error rejecting candidate", "error");
        } finally {
            setAuthorityAction(prev => ({ ...prev, [groupIdx]: null }));
        }
    }

    const fieldLabel = activeDomain?.attributes.find(a => a.name === field)?.label || field;

    return (
        <div className="space-y-6">
            {/* Controls card */}
            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <div className="flex flex-wrap items-end gap-4">
                    <div className="flex-1 min-w-[200px]">
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Knowledge Attribute to Analyze
                        </label>
                        <select
                            value={field}
                            onChange={(e) => setField(e.target.value)}
                            className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                        >
                            {activeDomain ? (
                                activeDomain.attributes
                                    .filter(a => a.type === "string")
                                    .map(attr => (
                                        <option key={attr.name} value={attr.name}>{attr.label}</option>
                                    ))
                            ) : (
                                <option value="">Loading attributes...</option>
                            )}
                        </select>
                    </div>
                    <div className="min-w-[180px]">
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Entity Type (for Authority)
                        </label>
                        <select
                            value={entityType}
                            onChange={(e) => setEntityType(e.target.value)}
                            className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                        >
                            {ENTITY_TYPES.map(et => (
                                <option key={et.value} value={et.value}>{et.label}</option>
                            ))}
                        </select>
                    </div>
                    <div className="min-w-[180px]">
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Threshold: {threshold}%
                        </label>
                        <input
                            type="range"
                            min={0}
                            max={100}
                            value={threshold}
                            onChange={(e) => setThreshold(Number(e.target.value))}
                            className="w-full accent-blue-600"
                        />
                    </div>
                    <button
                        onClick={analyze}
                        disabled={loading}
                        className="inline-flex h-10 items-center gap-2 rounded-lg bg-blue-600 px-5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {loading ? (
                            <>
                                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                                Parsing context...
                            </>
                        ) : (
                            <>
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                </svg>
                                Find Inconsistencies
                            </>
                        )}
                    </button>
                </div>
                {/* Algorithm selector */}
                <div className="mt-4 flex flex-col gap-1.5">
                    <label className="text-xs font-medium text-gray-700 dark:text-gray-300">Algoritmo</label>
                    <div className="flex flex-wrap gap-2">
                        {ALGORITHMS.map((alg) => (
                            <div key={alg.value} className="relative group">
                                <button
                                    type="button"
                                    onClick={() => setAlgorithm(alg.value)}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                                        algorithm === alg.value
                                            ? "bg-indigo-600 text-white border-indigo-600"
                                            : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700 hover:border-indigo-400"
                                    }`}
                                >
                                    {alg.label}
                                </button>
                                {/* Tooltip */}
                                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-52 rounded-lg bg-gray-900 dark:bg-gray-700 px-3 py-2 text-[11px] text-white shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
                                    {alg.tip}
                                    <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900 dark:border-t-gray-700" />
                                </div>
                            </div>
                        ))}
                    </div>
                    {algorithm === "fingerprint" && (
                        <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">
                            Fingerprint usa coincidencia exacta — el slider de threshold no aplica.
                        </p>
                    )}
                    {algorithm === "phonetic" && (
                        <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">
                            Fonético usa código fonético exacto — el slider de threshold no aplica.
                        </p>
                    )}
                </div>
            </div>

            {/* Results summary */}
            {groups.length > 0 && (
                <div className="flex gap-4">
                    <div className="flex-1 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <p className="text-sm text-gray-500 dark:text-gray-400">Resolved Groups</p>
                        <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">{totalGroups}</p>
                    </div>
                    <div className="flex-1 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <p className="text-sm text-gray-500 dark:text-gray-400">Attribute</p>
                        <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">{fieldLabel}</p>
                    </div>
                    <div className="flex-1 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <p className="text-sm text-gray-500 dark:text-gray-400">{t('disambiguation.variants')}</p>
                        <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">
                            {groups.reduce((acc, g) => acc + g.count, 0)}
                        </p>
                    </div>
                </div>
            )}

            {/* Variation groups */}
            <div className="space-y-4">
                {groups.map((group, idx) => (
                    <div key={idx} className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md dark:border-gray-800 dark:bg-gray-900">
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                                <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                                    {group.main}
                                </h3>
                                {group.algorithm_used && (
                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 font-mono">
                                        {group.algorithm_used}
                                    </span>
                                )}
                            </div>
                            <Badge variant="info">{group.count} variants matched</Badge>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            {group.variations.map((v, i) => (
                                <span
                                    key={i}
                                    className="inline-flex items-center rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1 text-sm text-gray-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
                                >
                                    {v}
                                </span>
                            ))}
                        </div>

                        {/* AI Resolution block */}
                        {resolutions[idx] ? (
                            <div className="mt-4 rounded-xl relative border border-indigo-200 bg-indigo-50/50 p-4 dark:border-indigo-500/30 dark:bg-indigo-500/10">
                                <div className="absolute right-4 top-4 text-indigo-400 dark:text-indigo-500">
                                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                    </svg>
                                </div>
                                <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">Semantic AI Recommendation</p>
                                <div className="mt-2 flex items-end justify-between">
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('disambiguation.canonical')}:</span>
                                            <span className="inline-flex items-center rounded bg-indigo-100 px-2 py-0.5 font-mono text-lg font-bold text-indigo-800 dark:bg-indigo-500/20 dark:text-indigo-300">
                                                {resolutions[idx].canonical_value}
                                            </span>
                                        </div>
                                        <p className="mt-2 max-w-xl text-xs text-slate-600 dark:text-slate-400">
                                            <strong className="text-slate-700 dark:text-slate-300">Reasoning: </strong>
                                            {resolutions[idx].reasoning}
                                        </p>
                                    </div>
                                    <button
                                        onClick={() => acceptResolution(idx, resolutions[idx].canonical_value, group.variations)}
                                        disabled={processingRule === idx}
                                        className="ml-4 shrink-0 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
                                    >
                                        {processingRule === idx ? "Applying..." : "Approve & Merge"}
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div className="mt-4 flex justify-end gap-2">
                                <button
                                    onClick={() => resolveWithAI(idx, group.variations)}
                                    disabled={resolvingIdx === idx}
                                    className="inline-flex items-center gap-2 rounded-lg border border-indigo-200 bg-white px-3 py-1.5 text-xs font-medium text-indigo-700 transition-colors hover:bg-indigo-50 disabled:opacity-50 dark:border-indigo-800 dark:bg-gray-900 dark:text-indigo-400 dark:hover:bg-indigo-900/30"
                                >
                                    {resolvingIdx === idx ? (
                                        <>
                                            <svg className="h-3 w-3 animate-spin" fill="none" viewBox="0 0 24 24">
                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                            </svg>
                                            Analyzing...
                                        </>
                                    ) : (
                                        <>
                                            <svg className="h-3.5 w-3.5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                            </svg>
                                            {t('disambiguation.resolve')}
                                        </>
                                    )}
                                </button>
                                <button
                                    onClick={() => resolveWithAuthority(idx, group.main)}
                                    disabled={!!authorityLoading[idx]}
                                    className="inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-white px-3 py-1.5 text-xs font-medium text-amber-700 transition-colors hover:bg-amber-50 disabled:opacity-50 dark:border-amber-800 dark:bg-gray-900 dark:text-amber-400 dark:hover:bg-amber-900/30"
                                >
                                    {authorityLoading[idx] ? (
                                        <>
                                            <svg className="h-3 w-3 animate-spin" fill="none" viewBox="0 0 24 24">
                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                            </svg>
                                            Querying sources...
                                        </>
                                    ) : (
                                        <>
                                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064" />
                                            </svg>
                                            Resolve with Authority
                                        </>
                                    )}
                                </button>
                            </div>
                        )}

                        {/* Authority candidates panel */}
                        {authorityCandidates[idx] && authorityCandidates[idx].length > 0 && (
                            <div className="mt-4 space-y-2">
                                <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                                    Authority Candidates ({authorityCandidates[idx].length})
                                </p>
                                {authorityCandidates[idx].map((rec) => {
                                    const style = SOURCE_STYLES[rec.authority_source] ?? {
                                        label: rec.authority_source,
                                        bg: "bg-gray-100 dark:bg-gray-700",
                                        text: "text-gray-700 dark:text-gray-300",
                                    };
                                    const isActing = authorityAction[idx] === rec.id;
                                    return (
                                        <div
                                            key={rec.id}
                                            className={`rounded-xl border p-3 transition-opacity ${
                                                rec.status === "rejected"
                                                    ? "border-gray-200 opacity-40 dark:border-gray-700"
                                                    : rec.status === "confirmed"
                                                    ? "border-green-300 bg-green-50/40 dark:border-green-700 dark:bg-green-500/10"
                                                    : "border-gray-200 bg-gray-50/50 dark:border-gray-700 dark:bg-gray-800/50"
                                            }`}
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 flex-wrap">
                                                        <Badge variant={
                                                            rec.authority_source === "wikidata" ? "warning" :
                                                            rec.authority_source === "viaf" ? "info" :
                                                            rec.authority_source === "orcid" ? "success" :
                                                            rec.authority_source === "dbpedia" ? "error" :
                                                            rec.authority_source === "openalex" ? "purple" : "default"
                                                        }>{style.label}</Badge>
                                                        <span className="text-sm font-medium text-gray-900 truncate dark:text-white">
                                                            {rec.canonical_label}
                                                        </span>
                                                        {rec.uri && (
                                                            <a
                                                                href={rec.uri}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                className="text-gray-400 hover:text-blue-500 dark:text-gray-500 dark:hover:text-blue-400"
                                                            >
                                                                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                                                </svg>
                                                            </a>
                                                        )}
                                                    </div>
                                                    {rec.description && (
                                                        <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400 line-clamp-1">
                                                            {rec.description}
                                                        </p>
                                                    )}
                                                    {/* Confidence bar */}
                                                    <div className="mt-1.5 flex items-center gap-2">
                                                        <div className="h-1.5 flex-1 rounded-full bg-gray-200 dark:bg-gray-700">
                                                            <div
                                                                className="h-1.5 rounded-full bg-blue-500"
                                                                style={{ width: `${Math.round(rec.confidence * 100)}%` }}
                                                            />
                                                        </div>
                                                        <span className="text-xs text-gray-500 dark:text-gray-400 shrink-0">
                                                            {Math.round(rec.confidence * 100)}%
                                                        </span>
                                                    </div>
                                                </div>
                                                {rec.status === "pending" && (
                                                    <div className="flex gap-1.5 shrink-0">
                                                        <button
                                                            onClick={() => confirmCandidate(idx, rec.id)}
                                                            disabled={isActing}
                                                            className="inline-flex items-center gap-1 rounded-lg bg-green-600 px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-green-700 disabled:opacity-50"
                                                        >
                                                            {isActing ? "..." : "Confirm"}
                                                        </button>
                                                        <button
                                                            onClick={() => rejectCandidate(idx, rec.id)}
                                                            disabled={isActing}
                                                            className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-100 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
                                                        >
                                                            {isActing ? "..." : "Reject"}
                                                        </button>
                                                    </div>
                                                )}
                                                {rec.status === "confirmed" && (
                                                    <Badge variant="success">Confirmed</Badge>
                                                )}
                                                {rec.status === "rejected" && (
                                                    <Badge variant="default">Rejected</Badge>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}

                        {authorityCandidates[idx] && authorityCandidates[idx].length === 0 && (
                            <div className="mt-3 rounded-xl border border-dashed border-gray-200 p-3 text-center dark:border-gray-700">
                                <p className="text-xs text-gray-400 dark:text-gray-500">No authority candidates found for &quot;{group.main}&quot;</p>
                            </div>
                        )}
                    </div>
                ))}
                {groups.length === 0 && !loading && (
                    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 py-16 dark:border-gray-700">
                        <svg className="mb-3 h-12 w-12 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Ready for Ontological Analysis</p>
                        <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">Pick an entity attribute to find naming inconsistencies in the repository</p>
                    </div>
                )}
            </div>
        </div>
    );
}
