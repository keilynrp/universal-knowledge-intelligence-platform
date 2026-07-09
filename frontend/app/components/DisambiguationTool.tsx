"use client";

import { useState, useEffect } from "react";
import { useDomain } from "../contexts/DomainContext";
import { useAuth } from "../contexts/AuthContext";
import { apiFetch } from "@/lib/api";
import { EntityConcept, useToast } from "./ui";
import { useLanguage } from "../contexts/LanguageContext";
import DisambiguationGroupCard from "./DisambiguationGroupCard";

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

const ALGORITHM_KEYS = ["token_sort", "fingerprint", "ngram", "phonetic"] as const;
const ENTITY_TYPE_KEYS = ["general", "organization", "person", "institution", "concept"] as const;

export default function DisambiguationTool() {
    const { t } = useLanguage();
    const { activeDomain } = useDomain();
    const { user } = useAuth();
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
    const [hasSearched, setHasSearched] = useState(false);
    const [searchedField, setSearchedField] = useState("");

    // AI resolution state
    const [resolvingIdx, setResolvingIdx] = useState<number | null>(null);
    const [resolutions, setResolutions] = useState<Record<number, { canonical_value: string; reasoning: string }>>({});
    const [processingRule, setProcessingRule] = useState<number | null>(null);

    // Authority resolution state
    const [authorityLoading, setAuthorityLoading] = useState<Record<number, boolean>>({});
    const [authorityCandidates, setAuthorityCandidates] = useState<Record<number, AuthorityRecord[]>>({});
    const [authorityAction, setAuthorityAction] = useState<Record<number, number | null>>({});
    const canManageAuthority = ["super_admin", "admin", "editor"].includes(user?.role ?? "");

    async function readErrorMessage(res: Response, fallback: string) {
        try {
            const payload = await res.clone().json();
            if (typeof payload?.detail === "string" && payload.detail.trim()) {
                return payload.detail;
            }
            if (Array.isArray(payload?.detail) && payload.detail.length > 0) {
                return payload.detail
                    .map((item: { msg?: string; loc?: Array<string | number> }) => {
                        const path = Array.isArray(item?.loc) ? item.loc.join(" > ") : "";
                        return [path, item?.msg].filter(Boolean).join(": ");
                    })
                    .join(" | ");
            }
            if (typeof payload?.message === "string" && payload.message.trim()) {
                return payload.message;
            }
        } catch {
            // Fall back to text if the body is not JSON.
        }

        try {
            const text = (await res.text()).trim();
            return text || fallback;
        } catch {
            return fallback;
        }
    }

    async function analyze() {
        if (!field) return;
        setLoading(true);
        setHasSearched(false);
        try {
            const res = await apiFetch(`/disambiguate/${field}?threshold=${threshold}&algorithm=${algorithm}`);
            if (!res.ok) throw new Error("Failed to fetch analysis");
            const data: DisambiguationResponse = await res.json();
            setGroups(data.groups);
            setTotalGroups(data.total_groups);
            setAuthorityCandidates({});
            setSearchedField(fieldLabel);
            setHasSearched(true);
        } catch {
            toast(t('disambiguation.error_analyzing'), "error");
        } finally {
            setLoading(false);
        }
    }

    async function resolveWithAI(idx: number, variations: string[]) {
        if (!canManageAuthority) {
            toast(t('disambiguation.editor_required'), "warning");
            return;
        }
        setResolvingIdx(idx);
        try {
            const res = await apiFetch(`/disambiguate/ai-resolve`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ field_name: field, variations })
            });
            if (!res.ok) throw new Error(await readErrorMessage(res, "AI resolve failed"));
            const data = await res.json();
            setResolutions(prev => ({ ...prev, [idx]: data }));
        } catch (error) {
            toast(error instanceof Error ? error.message : "Error from AI resolution endpoint", "error");
        } finally {
            setResolvingIdx(null);
        }
    }

    async function acceptResolution(idx: number, canonical_value: string, variations: string[]) {
        if (!canManageAuthority) {
            toast(t('disambiguation.editor_required'), "warning");
            return;
        }
        setProcessingRule(idx);
        try {
            const res = await apiFetch(`/rules/bulk`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ field_name: field, canonical_value, variations })
            });
            if (!res.ok) throw new Error(await readErrorMessage(res, "Failed to save rules"));
            const applyRes = await apiFetch(`/rules/apply?field_name=${field}`, { method: "POST" });
            if (!applyRes.ok) throw new Error(await readErrorMessage(applyRes, "Failed to apply rules"));
            analyze();
        } catch (error) {
            toast(error instanceof Error ? error.message : "Error applying rules", "error");
        } finally {
            setProcessingRule(null);
        }
    }

    async function resolveWithAuthority(idx: number, mainValue: string) {
        if (!canManageAuthority) {
            toast(t('disambiguation.editor_required'), "warning");
            return;
        }
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
            if (!res.ok) throw new Error(await readErrorMessage(res, "Authority resolve failed"));
            const records: AuthorityRecord[] = await res.json();
            setAuthorityCandidates(prev => ({ ...prev, [idx]: records }));
        } catch (error) {
            toast(error instanceof Error ? error.message : "Error querying authority sources", "error");
        } finally {
            setAuthorityLoading(prev => ({ ...prev, [idx]: false }));
        }
    }

    async function confirmCandidate(groupIdx: number, recordId: number) {
        if (!canManageAuthority) {
            toast(t('disambiguation.editor_required'), "warning");
            return;
        }
        setAuthorityAction(prev => ({ ...prev, [groupIdx]: recordId }));
        try {
            const res = await apiFetch(`/authority/records/${recordId}/confirm`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ also_create_rule: true }),
            });
            if (!res.ok) throw new Error(await readErrorMessage(res, "Confirm failed"));
            const updated: AuthorityRecord = await res.json();
            setAuthorityCandidates(prev => ({
                ...prev,
                [groupIdx]: (prev[groupIdx] || []).map(r => r.id === recordId ? { ...r, status: updated.status } : r),
            }));
            toast(t('disambiguation.candidate_confirmed'), "success");
        } catch (error) {
            toast(error instanceof Error ? error.message : "Error confirming candidate", "error");
        } finally {
            setAuthorityAction(prev => ({ ...prev, [groupIdx]: null }));
        }
    }

    async function rejectCandidate(groupIdx: number, recordId: number) {
        if (!canManageAuthority) {
            toast(t('disambiguation.editor_required'), "warning");
            return;
        }
        setAuthorityAction(prev => ({ ...prev, [groupIdx]: recordId }));
        try {
            const res = await apiFetch(`/authority/records/${recordId}/reject`, {
                method: "POST",
            });
            if (!res.ok) throw new Error(await readErrorMessage(res, "Reject failed"));
            setAuthorityCandidates(prev => ({
                ...prev,
                [groupIdx]: (prev[groupIdx] || []).map(r => r.id === recordId ? { ...r, status: "rejected" } : r),
            }));
            toast(t('disambiguation.candidate_rejected'), "warning");
        } catch (error) {
            toast(error instanceof Error ? error.message : "Error rejecting candidate", "error");
        } finally {
            setAuthorityAction(prev => ({ ...prev, [groupIdx]: null }));
        }
    }

    const fieldLabel = activeDomain?.attributes.find(a => a.name === field)?.label || field;
    // fingerprint/phonetic cluster by an exact key and ignore the threshold, so
    // we visually disable the slider to avoid implying it has any effect.
    const thresholdApplies = algorithm === "token_sort" || algorithm === "ngram";

    return (
        <div className="space-y-6">
            {/* Controls card */}
            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <div className="flex flex-wrap items-end gap-4">
                    <div className="flex-1 min-w-[200px]">
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {t('disambiguation.attribute_label')}
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
                                <option value="">{t('disambiguation.loading_attributes')}</option>
                            )}
                        </select>
                    </div>
                    <div className="min-w-[180px]">
                        <div className="mb-1.5 flex items-center gap-1">
                            <label htmlFor="disambiguation-entity-type" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                {t('disambiguation.entity_type_label')}
                            </label>
                            <EntityConcept><span className="sr-only">{t('disambiguation.entity_type_label')}</span></EntityConcept>
                        </div>
                        <select
                            id="disambiguation-entity-type"
                            value={entityType}
                            onChange={(e) => setEntityType(e.target.value)}
                            className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                        >
                            {ENTITY_TYPE_KEYS.map(key => (
                                <option key={key} value={key}>{t(`disambiguation.entity_type.${key}`)}</option>
                            ))}
                        </select>
                    </div>
                    <div className={`min-w-[180px] ${thresholdApplies ? "" : "opacity-50"}`}>
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {t('disambiguation.threshold_label')}: {thresholdApplies ? `${threshold}%` : t('disambiguation.threshold_na')}
                        </label>
                        <input
                            type="range"
                            min={0}
                            max={100}
                            value={threshold}
                            disabled={!thresholdApplies}
                            onChange={(e) => setThreshold(Number(e.target.value))}
                            className="w-full accent-blue-600 disabled:cursor-not-allowed"
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
                                {t('disambiguation.parsing')}
                            </>
                        ) : (
                            <>
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                </svg>
                                {t('disambiguation.find_inconsistencies')}
                            </>
                        )}
                    </button>
                </div>
                {/* Algorithm selector */}
                <div className="mt-4 flex flex-col gap-1.5">
                    <label className="text-xs font-medium text-gray-700 dark:text-gray-300">{t('disambiguation.algorithm_label')}</label>
                    <div className="flex flex-wrap gap-2">
                        {ALGORITHM_KEYS.map((key) => (
                            <div key={key} className="relative group">
                                <button
                                    type="button"
                                    onClick={() => setAlgorithm(key)}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                                        algorithm === key
                                            ? "bg-indigo-600 text-white border-indigo-600"
                                            : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700 hover:border-indigo-400"
                                    }`}
                                >
                                    {t(`disambiguation.algo.${key}`)}
                                </button>
                                {/* Tooltip */}
                                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-52 rounded-lg bg-gray-900 dark:bg-gray-700 px-3 py-2 text-[11px] text-white shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
                                    {t(`disambiguation.algo.${key}_tip`)}
                                    <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900 dark:border-t-gray-700" />
                                </div>
                            </div>
                        ))}
                    </div>
                    {algorithm === "fingerprint" && (
                        <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">
                            {t('disambiguation.fingerprint_note')}
                        </p>
                    )}
                    {algorithm === "phonetic" && (
                        <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">
                            {t('disambiguation.phonetic_note')}
                        </p>
                    )}
                </div>
            </div>

            {/* Results summary */}
            {groups.length > 0 && (
                <div className="flex gap-4">
                    <div className="flex-1 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <p className="text-sm text-gray-500 dark:text-gray-400">{t('disambiguation.resolved_groups')}</p>
                        <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">{totalGroups}</p>
                    </div>
                    <div className="flex-1 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <p className="text-sm text-gray-500 dark:text-gray-400">{t('disambiguation.attribute')}</p>
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
                    <DisambiguationGroupCard
                        key={idx}
                        group={group}
                        idx={idx}
                        resolution={resolutions[idx]}
                        resolvingIdx={resolvingIdx}
                        processingRule={processingRule}
                        canManageAuthority={canManageAuthority}
                        authorityCandidates={authorityCandidates}
                        authorityLoading={authorityLoading}
                        authorityAction={authorityAction}
                        t={t}
                        onResolveWithAI={resolveWithAI}
                        onAcceptResolution={acceptResolution}
                        onResolveWithAuthority={resolveWithAuthority}
                        onConfirmCandidate={confirmCandidate}
                        onRejectCandidate={rejectCandidate}
                    />
                ))}
                {groups.length === 0 && !loading && (
                    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 py-16 dark:border-gray-700">
                        {hasSearched ? (
                            <>
                                <svg className="mb-3 h-12 w-12 text-emerald-300 dark:text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                                    {t('disambiguation.no_groups_found') || `No inconsistencies found for "${searchedField}"`}
                                </p>
                                <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                                    {t('disambiguation.no_groups_hint') || 'Try lowering the threshold or switching algorithm'}
                                </p>
                            </>
                        ) : (
                            <>
                                <svg className="mb-3 h-12 w-12 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                </svg>
                                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{t('disambiguation.ready_title')}</p>
                                <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">{t('disambiguation.ready_hint')}</p>
                            </>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}


