"use client";

import { useLanguage } from "../contexts/LanguageContext";
import type { AuthorityRecord, AuthorAffiliationsResponse, AuthorCompareResponse } from "./reviewQueueTypes";
import { SOURCE_COLORS } from "./reviewQueueTypes";
import {
    getNilReasonLabel,
    getResolutionStatusLabel,
    getRouteLabel,
} from "./reviewQueueI18n";

export interface AuthorReviewExpandedPanelProps {
    record: AuthorityRecord;
    compare: AuthorCompareResponse | null;
    affiliations: AuthorAffiliationsResponse | null;
    loadingCompare: boolean;
    linkActionId: number | null;
    onReviewAuthorityLink: (linkId: number, action: "confirm" | "reject", authorRecordId: number) => void;
}

export default function AuthorReviewExpandedPanel({
    record,
    compare,
    affiliations,
    loadingCompare,
    linkActionId,
    onReviewAuthorityLink,
}: AuthorReviewExpandedPanelProps) {
    const { t } = useLanguage();

    return (
        <div className="space-y-4">
            {loadingCompare ? (
                <div className="rounded-xl border border-gray-200 bg-white p-4 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-900/60 dark:text-gray-400">
                    {t("page.authority.loading_candidate_comparison")}
                </div>
            ) : compare?.peer_count ? (
                <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900/60">
                    <div className="mb-3 flex items-center justify-between gap-3">
                        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                            {t("page.authority.winner_vs_runner_up")}
                        </p>
                        <span className="text-xs text-gray-400 dark:text-gray-500">
                            {compare.peer_count} {t("page.authority.alternate_candidates")}
                        </span>
                    </div>
                    <div className="space-y-3">
                        {compare.peers.map((peer) => (
                            <div
                                key={peer.id}
                                className="flex flex-col gap-2 rounded-lg border border-gray-200 p-3 dark:border-gray-700 sm:flex-row sm:items-center sm:justify-between"
                            >
                                <div className="space-y-1">
                                    <div className="flex items-center gap-2">
                                        <span className="font-medium text-gray-900 dark:text-white">{peer.canonical_label}</span>
                                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${SOURCE_COLORS[peer.authority_source] || "bg-gray-100 text-gray-600"}`}>
                                            {peer.authority_source}
                                        </span>
                                    </div>
                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                        {peer.authority_id} · {getResolutionStatusLabel(peer.resolution_status, t)}
                                    </p>
                                </div>
                                <div className="grid grid-cols-3 gap-4 text-xs text-gray-500 dark:text-gray-400">
                                    <div>
                                        <p className="uppercase tracking-wide">{t("page.authority.table_confidence")}</p>
                                        <p className="mt-1 font-mono text-gray-900 dark:text-white">{(peer.confidence * 100).toFixed(0)}%</p>
                                    </div>
                                    <div>
                                        <p className="uppercase tracking-wide">{t("page.authority.delta")}</p>
                                        <p className="mt-1 font-mono text-gray-900 dark:text-white">
                                            {((record.confidence - peer.confidence) * 100).toFixed(0)} {t("page.authority.points_suffix")}
                                        </p>
                                    </div>
                                    <div>
                                        <p className="uppercase tracking-wide">{t("page.authority.table_route")}</p>
                                        <p className="mt-1 font-mono text-gray-900 dark:text-white">{getRouteLabel(peer.resolution_route, t)}</p>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ) : null}

            {affiliations?.affiliations.length ? (
                <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900/60">
                    <div className="mb-3 flex items-center justify-between gap-3">
                        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                            {t("page.authority.affiliation_authority") || "Affiliation authority"}
                        </p>
                        <span className="text-xs text-gray-400 dark:text-gray-500">
                            {affiliations.affiliations.length}
                        </span>
                    </div>
                    <div className="space-y-3">
                        {affiliations.affiliations.map(({ link, institution_record }) => (
                            <div
                                key={link.id}
                                className="flex flex-col gap-3 rounded-lg border border-gray-200 p-3 dark:border-gray-700 lg:flex-row lg:items-center lg:justify-between"
                            >
                                <div className="min-w-0 space-y-1">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <span className="font-medium text-gray-900 dark:text-white">
                                            {institution_record?.canonical_label || t("page.authority.unavailable_record") || "Unavailable record"}
                                        </span>
                                        {institution_record && (
                                            <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${SOURCE_COLORS[institution_record.authority_source] || "bg-gray-100 text-gray-600"}`}>
                                                {institution_record.authority_source}
                                            </span>
                                        )}
                                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${link.status === "confirmed" ? "bg-green-100 text-green-700 dark:bg-green-500/10 dark:text-green-400" : link.status === "rejected" ? "bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400" : "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400"}`}>
                                            {link.status}
                                        </span>
                                    </div>
                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                        {link.link_type} · {(link.confidence * 100).toFixed(0)}%
                                        {institution_record?.authority_id ? ` · ${institution_record.authority_id}` : ""}
                                    </p>
                                    {link.evidence.length > 0 && (
                                        <div className="flex flex-wrap gap-1.5 pt-1">
                                            {link.evidence.slice(0, 4).map(item => (
                                                <span
                                                    key={item}
                                                    className="inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-600 dark:bg-gray-800 dark:text-gray-300"
                                                >
                                                    {item}
                                                </span>
                                            ))}
                                        </div>
                                    )}
                                </div>
                                <div className="flex shrink-0 items-center gap-2">
                                    <button
                                        onClick={() => onReviewAuthorityLink(link.id, "confirm", record.id)}
                                        disabled={linkActionId === link.id || link.status === "confirmed"}
                                        className="inline-flex h-7 items-center rounded-md bg-green-600 px-2.5 text-[11px] font-medium text-white transition-colors hover:bg-green-700 disabled:opacity-50"
                                    >
                                        {t("page.authority.confirm_button")}
                                    </button>
                                    <button
                                        onClick={() => onReviewAuthorityLink(link.id, "reject", record.id)}
                                        disabled={linkActionId === link.id || link.status === "rejected"}
                                        className="inline-flex h-7 items-center rounded-md bg-red-600 px-2.5 text-[11px] font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
                                    >
                                        {t("page.authority.reject_button")}
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ) : null}

            <div className="grid gap-4 lg:grid-cols-3">
                <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900/60">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                        {t("page.authority.resolution_decision")}
                    </p>
                    <dl className="mt-3 space-y-2 text-sm">
                        <div className="flex items-center justify-between gap-3">
                            <dt className="text-gray-500 dark:text-gray-400">{t("page.authority.table_route")}</dt>
                            <dd className="font-mono text-gray-900 dark:text-white">{getRouteLabel(record.resolution_route, t)}</dd>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                            <dt className="text-gray-500 dark:text-gray-400">{t("page.authority.complexity")}</dt>
                            <dd className="text-gray-900 dark:text-white">
                                {typeof record.complexity_score === "number" ? record.complexity_score.toFixed(2) : "--"}
                            </dd>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                            <dt className="text-gray-500 dark:text-gray-400">{t("page.authority.nil_score")}</dt>
                            <dd className="text-rose-600 dark:text-rose-400">
                                {typeof record.nil_score === "number" ? `${(record.nil_score * 100).toFixed(0)}%` : "--"}
                            </dd>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                            <dt className="text-gray-500 dark:text-gray-400">{t("page.authority.authority_id")}</dt>
                            <dd className="font-mono text-gray-900 dark:text-white">{record.authority_id}</dd>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                            <dt className="text-gray-500 dark:text-gray-400">{t("page.authority.resolution")}</dt>
                            <dd className="text-gray-900 dark:text-white">{getResolutionStatusLabel(record.resolution_status, t)}</dd>
                        </div>
                        {record.nil_reason && (
                            <div className="flex items-center justify-between gap-3">
                                <dt className="text-gray-500 dark:text-gray-400">{t("page.authority.nil_reason")}</dt>
                                <dd className="font-mono text-rose-600 dark:text-rose-400">{getNilReasonLabel(record.nil_reason, t)}</dd>
                            </div>
                        )}
                        {record.reformulation_trace?.attempted && (
                            <>
                                <div className="flex items-center justify-between gap-3">
                                    <dt className="text-gray-500 dark:text-gray-400">{t("page.authority.reformulation")}</dt>
                                    <dd className="text-blue-600 dark:text-blue-400">
                                        {record.reformulation_trace.applied ? t("page.authority.applied_state") : t("page.authority.attempted_state")}
                                    </dd>
                                </div>
                                <div className="flex items-center justify-between gap-3">
                                    <dt className="text-gray-500 dark:text-gray-400">{t("page.authority.retrieval_gain")}</dt>
                                    <dd className="text-gray-900 dark:text-white">{record.reformulation_gain ?? 0}</dd>
                                </div>
                            </>
                        )}
                    </dl>
                </div>

                <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900/60">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                        {t("page.authority.score_breakdown")}
                    </p>
                    <div className="mt-3 space-y-2">
                        {record.score_breakdown && Object.keys(record.score_breakdown).length > 0 ? (
                            Object.entries(record.score_breakdown).map(([key, value]) => (
                                <div key={key} className="flex items-center justify-between gap-3 text-sm">
                                    <span className="text-gray-500 dark:text-gray-400">{key.replaceAll("_", " ")}</span>
                                    <span className="font-mono text-gray-900 dark:text-white">
                                        {typeof value === "number" ? value.toFixed(2) : String(value)}
                                    </span>
                                </div>
                            ))
                        ) : (
                            <p className="text-sm text-gray-400 dark:text-gray-500">{t("page.authority.no_score_breakdown")}</p>
                        )}
                    </div>
                </div>

                <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900/60">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">{t("page.authority.evidence")}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                        {record.evidence && record.evidence.length > 0 ? (
                            record.evidence.map((item) => (
                                <span
                                    key={item}
                                    className="inline-flex rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300"
                                >
                                    {item}
                                </span>
                            ))
                        ) : (
                            <p className="text-sm text-gray-400 dark:text-gray-500">{t("page.authority.no_evidence")}</p>
                        )}
                    </div>
                    <div className="mt-4 space-y-3">
                        <div>
                            <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">{t("page.authority.merged_sources")}</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                                {record.merged_sources && record.merged_sources.length > 0 ? (
                                    record.merged_sources.map((source) => (
                                        <span
                                            key={source}
                                            className="inline-flex rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                                        >
                                            {source}
                                        </span>
                                    ))
                                ) : (
                                    <span className="text-xs text-gray-400 dark:text-gray-500">{t("common.none")}</span>
                                )}
                            </div>
                        </div>
                        <div>
                            <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">{t("page.authority.aliases")}</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                                {record.aliases && record.aliases.length > 0 ? (
                                    record.aliases.map((alias) => (
                                        <span
                                            key={alias}
                                            className="inline-flex rounded-full bg-emerald-50 px-2 py-1 text-xs text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300"
                                        >
                                            {alias}
                                        </span>
                                    ))
                                ) : (
                                    <span className="text-xs text-gray-400 dark:text-gray-500">{t("common.none")}</span>
                                )}
                            </div>
                        </div>
                        {record.reformulation_trace?.attempted && (
                            <div>
                                <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                                    {t("page.authority.reformulation_trace")}
                                </p>
                                <div className="mt-2 flex flex-wrap gap-2">
                                    {record.reformulation_trace.generated_queries && record.reformulation_trace.generated_queries.length > 0 ? (
                                        record.reformulation_trace.generated_queries.map((query) => (
                                            <span
                                                key={query}
                                                className="inline-flex rounded-full bg-sky-50 px-2 py-1 text-xs text-sky-700 dark:bg-sky-500/10 dark:text-sky-300"
                                            >
                                                {query}
                                            </span>
                                        ))
                                    ) : (
                                        <span className="text-xs text-gray-400 dark:text-gray-500">{t("page.authority.no_alternate_queries")}</span>
                                    )}
                                </div>
                                <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                                    {record.reformulation_trace.provider || t("page.authority.provider_unavailable")}
                                    {record.reformulation_trace.model ? ` · ${record.reformulation_trace.model}` : ""}
                                    {typeof record.reformulation_cost_estimate === "number" ? ` · est. $${record.reformulation_cost_estimate.toFixed(4)}` : ""}
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
