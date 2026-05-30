"use client";

import { useEffect, useState } from "react";
import { Badge, useToast } from "../components/ui";
import { apiFetch } from "@/lib/api";
import type { DomainAttribute, DomainSchema } from "../contexts/DomainContext";
import { useLanguage } from "../contexts/LanguageContext";

interface AuthorityGroup {
    main: string;
    variations: string[];
    count: number;
    has_rules: boolean;
    resolved_to: string | null;
}

interface AuthorityResponse {
    groups: AuthorityGroup[];
    total_groups: number;
    total_rules: number;
    pending_groups: number;
}

interface ApplyResult {
    rules_applied: number;
    records_updated: number;
}

interface GroupState {
    canonical: string;
    excluded: Set<string>;
    saved: boolean;
}

export default function DisambiguationTab({ activeDomain }: { activeDomain: DomainSchema | null }) {
    const { t } = useLanguage();
    const { toast } = useToast();
    const [field, setField] = useState("");
    const [data, setData] = useState<AuthorityResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [applying, setApplying] = useState(false);
    const [applyResult, setApplyResult] = useState<ApplyResult | null>(null);
    // State keyed by canonical group "main" so edits survive page navigation.
    const [groupStates, setGroupStates] = useState<Record<string, GroupState>>({});
    const [savingGroup, setSavingGroup] = useState<string | null>(null);
    const [page, setPage] = useState(0);
    const [limit, setLimit] = useState(20);
    const [analyzed, setAnalyzed] = useState(false);

    useEffect(() => {
        if (activeDomain && !field) {
            const firstStr = activeDomain.attributes.find((a: DomainAttribute) => a.type === "string");
            if (firstStr) setField(firstStr.name);
        }
    }, [activeDomain, field]);

    // Server-side pagination: refetch whenever the page or limit changes once analyzed.
    useEffect(() => {
        if (!analyzed || !field) return;
        void fetchPage(page, limit);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [page, limit, analyzed]);

    const visibleGroups = data ? data.groups : [];

    async function fetchPage(targetPage: number, pageLimit: number) {
        setLoading(true);
        try {
            const skip = targetPage * pageLimit;
            const res = await apiFetch(`/authority/${field}?skip=${skip}&limit=${pageLimit}`);
            if (!res.ok) throw new Error("Failed to fetch");
            const json: AuthorityResponse = await res.json();
            setData(json);
            setGroupStates(prev => {
                const states = { ...prev };
                json.groups.forEach(g => {
                    if (!states[g.main]) {
                        states[g.main] = { canonical: g.resolved_to || g.main, excluded: new Set<string>(), saved: g.has_rules };
                    }
                });
                return states;
            });
        } catch {
            toast("Error fetching authority data", "error");
        } finally {
            setLoading(false);
        }
    }

    async function analyze() {
        setData(null);
        setGroupStates({});
        setApplyResult(null);
        setPage(0);
        setAnalyzed(true);
        await fetchPage(0, limit);
    }

    function updateCanonical(main: string, value: string) {
        setGroupStates(prev => ({ ...prev, [main]: { ...prev[main], canonical: value, saved: false } }));
    }

    function toggleExclude(main: string, variation: string) {
        setGroupStates(prev => {
            const excluded = new Set(prev[main].excluded);
            if (excluded.has(variation)) excluded.delete(variation); else excluded.add(variation);
            return { ...prev, [main]: { ...prev[main], excluded, saved: false } };
        });
    }

    async function saveGroupRules(group: AuthorityGroup) {
        const state = groupStates[group.main];
        if (!state) return;
        const activeVariations = group.variations.filter(v => !state.excluded.has(v));
        setSavingGroup(group.main);
        try {
            const res = await apiFetch("/rules/bulk", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ field_name: field, canonical_value: state.canonical, variations: activeVariations }),
            });
            if (!res.ok) throw new Error("Failed to save rules");
            setGroupStates(prev => ({ ...prev, [group.main]: { ...prev[group.main], saved: true } }));
        } catch {
            toast("Error saving rules", "error");
        } finally {
            setSavingGroup(null);
        }
    }

    async function applyAllRules() {
        setApplying(true);
        setApplyResult(null);
        try {
            const res = await apiFetch(`/rules/apply?field_name=${field}`, { method: "POST" });
            if (!res.ok) throw new Error("Failed to apply rules");
            setApplyResult(await res.json());
        } catch {
            toast("Error applying rules", "error");
        } finally {
            setApplying(false);
        }
    }

    const savedCount = Object.values(groupStates).filter(s => s.saved).length;

    return (
        <div className="space-y-6">
            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <div className="flex flex-wrap items-end gap-4">
                    <div className="min-w-[200px] flex-1">
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {t("page.authority.disambig.field_label")}
                        </label>
                        <select
                            value={field}
                            onChange={e => setField(e.target.value)}
                            className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                        >
                            {activeDomain ? (
                                activeDomain.attributes
                                    .filter((a: DomainAttribute) => a.type === "string")
                                    .map((attr: DomainAttribute) => (
                                        <option key={attr.name} value={attr.name}>{attr.label}</option>
                                    ))
                            ) : (
                                <option value="">Loading attributes...</option>
                            )}
                        </select>
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
                                {t("page.authority.disambig.analyzing")}
                            </>
                        ) : (
                            <>
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                </svg>
                                {t("page.authority.disambig.analyze")}
                            </>
                        )}
                    </button>
                </div>
            </div>

            {data && (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <p className="text-sm text-gray-500 dark:text-gray-400">{t("page.authority.disambig.variation_groups")}</p>
                        <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{data.total_groups}</p>
                    </div>
                    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <p className="text-sm text-gray-500 dark:text-gray-400">{t("page.authority.disambig.existing_rules")}</p>
                        <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{data.total_rules}</p>
                    </div>
                    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <p className="text-sm text-gray-500 dark:text-gray-400">{t("page.authority.disambig.pending_review")}</p>
                        <p className="mt-1 text-2xl font-bold text-amber-600 dark:text-amber-400">{data.pending_groups}</p>
                    </div>
                </div>
            )}

            {data && (
                <div className="space-y-4">
                    {visibleGroups.map((group) => {
                        const state = groupStates[group.main];
                        if (!state) return null;
                        return (
                            <div key={group.main} className={`rounded-2xl border bg-white p-5 transition-shadow hover:shadow-md dark:bg-gray-900 ${state.saved ? "border-green-200 dark:border-green-800" : "border-gray-200 dark:border-gray-800"}`}>
                                <div className="mb-4 flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <Badge variant={state.saved ? "success" : "warning"} dot>
                                            {state.saved ? t("page.authority.disambig.resolved") : t("page.authority.disambig.pending")}
                                        </Badge>
                                        <span className="text-xs text-gray-400 dark:text-gray-500">{t("page.authority.disambig.n_variations", { count: group.count })}</span>
                                    </div>
                                    <button
                                        onClick={() => saveGroupRules(group)}
                                        disabled={savingGroup === group.main}
                                        className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                                    >
                                        {savingGroup === group.main ? t("page.authority.disambig.saving") : (
                                            <>
                                                <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                                </svg>
                                                {t("page.authority.disambig.save_rules")}
                                            </>
                                        )}
                                    </button>
                                </div>
                                <div className="mb-3">
                                    <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">{t("page.authority.disambig.canonical_value")}</label>
                                    <input
                                        type="text"
                                        value={state.canonical}
                                        onChange={e => updateCanonical(group.main, e.target.value)}
                                        className="h-9 w-full max-w-md rounded-lg border border-gray-200 bg-white px-3 text-sm font-semibold text-gray-900 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white"
                                    />
                                </div>
                                <div>
                                    <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400">{t("page.authority.disambig.variations_hint")}</label>
                                    <div className="flex flex-wrap gap-2">
                                        {group.variations.map((v, i) => {
                                            const isExcluded = state.excluded.has(v);
                                            const isCanonical = v === state.canonical;
                                            return (
                                                <button
                                                    key={i}
                                                    onClick={() => { if (!isCanonical) toggleExclude(group.main, v); }}
                                                    className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-sm transition-colors ${isCanonical
                                                        ? "border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-700 dark:bg-blue-500/10 dark:text-blue-400"
                                                        : isExcluded
                                                            ? "border-gray-200 bg-gray-50 text-gray-300 line-through dark:border-gray-800 dark:bg-gray-800/50 dark:text-gray-600"
                                                            : "border-gray-200 bg-gray-50 text-gray-700 hover:border-red-300 hover:bg-red-50 hover:text-red-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:border-red-700 dark:hover:bg-red-500/10 dark:hover:text-red-400"
                                                    }`}
                                                    title={isCanonical ? t("page.authority.disambig.tip_canonical") : isExcluded ? t("page.authority.disambig.tip_include") : t("page.authority.disambig.tip_exclude")}
                                                >
                                                    {v}
                                                    {isCanonical && <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>}
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>
                            </div>
                        );
                    })}

                    {data.total_groups > 0 && (
                        <div className="flex items-center justify-between border-t border-gray-200 pt-4 dark:border-gray-800">
                            <div className="flex items-center gap-2">
                                <span className="text-sm text-gray-500 dark:text-gray-400">{t("page.authority.disambig.rows_per_page")}</span>
                                <select
                                    value={limit}
                                    onChange={e => { setLimit(Number(e.target.value)); setPage(0); }}
                                    className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-sm text-gray-700 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
                                >
                                    {[10, 20, 50, 100].map(n => <option key={n} value={n}>{n}</option>)}
                                </select>
                            </div>
                            <div className="flex items-center gap-4">
                                <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3.5 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800">
                                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
                                    {t("page.authority.disambig.previous")}
                                </button>
                                <div className="flex items-center gap-2">
                                    <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm font-medium text-white">{page + 1}</span>
                                    <span className="text-sm text-gray-500">{t("page.authority.disambig.of_pages", { total: Math.ceil(data.total_groups / limit) })}</span>
                                </div>
                                <button onClick={() => setPage(p => p + 1)} disabled={(page + 1) * limit >= data.total_groups} className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3.5 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800">
                                    {t("page.authority.disambig.next")}
                                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                                </button>
                            </div>
                        </div>
                    )}

                    {data.total_groups === 0 && (
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 py-16 dark:border-gray-700">
                            <svg className="mb-3 h-12 w-12 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{t("page.authority.disambig.no_groups")}</p>
                            <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">{t("page.authority.disambig.no_groups_hint")}</p>
                        </div>
                    )}
                </div>
            )}

            {!data && !loading && (
                <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 py-16 dark:border-gray-700">
                    <svg className="mb-3 h-12 w-12 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                    </svg>
                    <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{t("page.authority.disambig.empty_title")}</p>
                    <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">{t("page.authority.disambig.empty_hint")}</p>
                </div>
            )}

            {data && data.total_groups > 0 && (
                <div className="sticky bottom-0 rounded-2xl border border-gray-200 bg-white p-4 shadow-lg dark:border-gray-800 dark:bg-gray-900">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-gray-900 dark:text-white">
                                {t("page.authority.disambig.groups_resolved", { saved: savedCount, total: data.total_groups })}
                            </p>
                            {applyResult && (
                                <p className="text-xs text-green-600 dark:text-green-400">
                                    {t("page.authority.disambig.apply_result", { rules: applyResult.rules_applied, records: applyResult.records_updated })}
                                </p>
                            )}
                        </div>
                        <button
                            onClick={applyAllRules}
                            disabled={applying || savedCount === 0}
                            className="inline-flex h-10 items-center gap-2 rounded-lg bg-green-600 px-5 text-sm font-medium text-white transition-colors hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {applying ? (
                                <>
                                    <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                    </svg>
                                    {t("page.authority.disambig.applying")}
                                </>
                            ) : (
                                <>
                                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                    </svg>
                                    {t("page.authority.disambig.apply_all")}
                                </>
                            )}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
