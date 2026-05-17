"use client";

import { Badge } from "./ui";
import {
    type AuthorityRecord,
    type VariationGroup,
    SOURCE_STYLES,
} from "./disambiguationTypes";

interface ResolutionState {
    canonical_value: string;
    reasoning: string;
}

interface DisambiguationGroupCardProps {
    group: VariationGroup;
    idx: number;
    resolution: ResolutionState | undefined;
    resolvingIdx: number | null;
    processingRule: number | null;
    canManageAuthority: boolean;
    authorityCandidates: Record<number, AuthorityRecord[]>;
    authorityLoading: Record<number, boolean>;
    authorityAction: Record<number, number | null>;
    t: (key: string) => string;
    onResolveWithAI: (idx: number, variations: string[]) => void;
    onAcceptResolution: (idx: number, canonicalValue: string, variations: string[]) => void;
    onResolveWithAuthority: (idx: number, mainValue: string) => void;
    onConfirmCandidate: (groupIdx: number, recordId: number) => void;
    onRejectCandidate: (groupIdx: number, recordId: number) => void;
}

export default function DisambiguationGroupCard({
    group,
    idx,
    resolution,
    resolvingIdx,
    processingRule,
    canManageAuthority,
    authorityCandidates,
    authorityLoading,
    authorityAction,
    t,
    onResolveWithAI,
    onAcceptResolution,
    onResolveWithAuthority,
    onConfirmCandidate,
    onRejectCandidate,
}: DisambiguationGroupCardProps) {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md dark:border-gray-800 dark:bg-gray-900">
            <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                        {group.main}
                    </h3>
                    {group.algorithm_used && (
                        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-mono text-gray-500 dark:bg-gray-700 dark:text-gray-400">
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

            {resolution ? (
                <div className="relative mt-4 rounded-xl border border-indigo-200 bg-indigo-50/50 p-4 dark:border-indigo-500/30 dark:bg-indigo-500/10">
                    <div className="absolute right-4 top-4 text-indigo-400 dark:text-indigo-500">
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                    </div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">{t('disambiguation.ai_recommendation')}</p>
                    <div className="mt-2 flex items-end justify-between">
                        <div>
                            <div className="flex items-center gap-2">
                                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{t("disambiguation.canonical")}:</span>
                                <span className="inline-flex items-center rounded bg-indigo-100 px-2 py-0.5 font-mono text-lg font-bold text-indigo-800 dark:bg-indigo-500/20 dark:text-indigo-300">
                                    {resolution.canonical_value}
                                </span>
                            </div>
                            <p className="mt-2 max-w-xl text-xs text-slate-600 dark:text-slate-400">
                                <strong className="text-slate-700 dark:text-slate-300">{t('disambiguation.reasoning')}: </strong>
                                {resolution.reasoning}
                            </p>
                        </div>
                        <button
                        onClick={() => onAcceptResolution(idx, resolution.canonical_value, group.variations)}
                        disabled={processingRule === idx || !canManageAuthority}
                        title={!canManageAuthority ? t('disambiguation.editor_required') : undefined}
                        className="ml-4 inline-flex shrink-0 items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
                    >
                        {processingRule === idx ? t('disambiguation.applying') : t('disambiguation.approve_merge')}
                        </button>
                    </div>
                </div>
            ) : (
                <div className="mt-4 flex justify-end gap-2">
                    <button
                        onClick={() => onResolveWithAI(idx, group.variations)}
                        disabled={resolvingIdx === idx || !canManageAuthority}
                        title={!canManageAuthority ? t('disambiguation.editor_required') : undefined}
                        className="inline-flex items-center gap-2 rounded-lg border border-indigo-200 bg-white px-3 py-1.5 text-xs font-medium text-indigo-700 transition-colors hover:bg-indigo-50 disabled:opacity-50 dark:border-indigo-800 dark:bg-gray-900 dark:text-indigo-400 dark:hover:bg-indigo-900/30"
                    >
                        {resolvingIdx === idx ? (
                            <>
                                <svg className="h-3 w-3 animate-spin" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                                {t('disambiguation.analyzing')}
                            </>
                        ) : (
                            <>
                                <svg className="h-3.5 w-3.5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                </svg>
                                {t("disambiguation.resolve")}
                            </>
                        )}
                    </button>
                    <button
                        onClick={() => onResolveWithAuthority(idx, group.main)}
                        disabled={!!authorityLoading[idx] || !canManageAuthority}
                        title={!canManageAuthority ? t('disambiguation.editor_required') : undefined}
                        className="inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-white px-3 py-1.5 text-xs font-medium text-amber-700 transition-colors hover:bg-amber-50 disabled:opacity-50 dark:border-amber-800 dark:bg-gray-900 dark:text-amber-400 dark:hover:bg-amber-900/30"
                    >
                        {authorityLoading[idx] ? (
                            <>
                                <svg className="h-3 w-3 animate-spin" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                                {t('disambiguation.querying_sources')}
                            </>
                        ) : (
                            <>
                                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064" />
                                </svg>
                                {t('disambiguation.authority_resolve')}
                            </>
                        )}
                    </button>
                </div>
            )}

            {authorityCandidates[idx] && authorityCandidates[idx].length > 0 && (
                <div className="mt-4 space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                        {t('disambiguation.authority_candidates')} ({authorityCandidates[idx].length})
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
                                    <div className="min-w-0 flex-1">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <Badge variant={
                                                rec.authority_source === "wikidata" ? "warning" :
                                                    rec.authority_source === "viaf" ? "info" :
                                                        rec.authority_source === "orcid" ? "success" :
                                                            rec.authority_source === "dbpedia" ? "error" :
                                                                rec.authority_source === "openalex" ? "purple" : "default"
                                            }>{style.label}</Badge>
                                            <span className="truncate text-sm font-medium text-gray-900 dark:text-white">
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
                                            <p className="mt-0.5 line-clamp-1 text-xs text-gray-500 dark:text-gray-400">
                                                {rec.description}
                                            </p>
                                        )}
                                        <div className="mt-1.5 flex items-center gap-2">
                                            <div className="h-1.5 flex-1 rounded-full bg-gray-200 dark:bg-gray-700">
                                                <div
                                                    className="h-1.5 rounded-full bg-blue-500"
                                                    style={{ width: `${Math.round(rec.confidence * 100)}%` }}
                                                />
                                            </div>
                                            <span className="shrink-0 text-xs text-gray-500 dark:text-gray-400">
                                                {Math.round(rec.confidence * 100)}%
                                            </span>
                                        </div>
                                    </div>
                                    {rec.status === "pending" && (
                                        <div className="shrink-0 flex gap-1.5">
                                            <button
                                                onClick={() => onConfirmCandidate(idx, rec.id)}
                                                disabled={isActing || !canManageAuthority}
                                                title={!canManageAuthority ? t('disambiguation.editor_required') : undefined}
                                                className="inline-flex items-center gap-1 rounded-lg bg-green-600 px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-green-700 disabled:opacity-50"
                                            >
                                                {isActing ? "..." : t('disambiguation.confirm')}
                                            </button>
                                            <button
                                                onClick={() => onRejectCandidate(idx, rec.id)}
                                                disabled={isActing || !canManageAuthority}
                                                title={!canManageAuthority ? t('disambiguation.editor_required') : undefined}
                                                className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-100 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
                                            >
                                                {isActing ? "..." : t('disambiguation.reject')}
                                            </button>
                                        </div>
                                    )}
                                    {rec.status === "confirmed" && (
                                        <Badge variant="success">{t('disambiguation.confirmed_status')}</Badge>
                                    )}
                                    {rec.status === "rejected" && (
                                        <Badge variant="default">{t('disambiguation.rejected_status')}</Badge>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {authorityCandidates[idx] && authorityCandidates[idx].length === 0 && (
                <div className="mt-3 rounded-xl border border-dashed border-gray-200 p-3 text-center dark:border-gray-700">
                    <p className="text-xs text-gray-400 dark:text-gray-500">{t('disambiguation.no_candidates')} &quot;{group.main}&quot;</p>
                </div>
            )}
        </div>
    );
}
