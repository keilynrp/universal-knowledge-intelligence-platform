"use client";

import { Fragment } from "react";
import { Badge } from "../components/ui";
import AnnotationThread from "../components/AnnotationThread";
import ScoreBreakdown from "../components/ScoreBreakdown";
import { useLanguage } from "../contexts/LanguageContext";
import AuthorReviewExpandedPanel from "./AuthorReviewExpandedPanel";
import {
    type AuthorAffiliationsResponse,
    type AuthorCompareResponse,
    type AuthorityRecord,
    SOURCE_COLORS,
} from "./reviewQueueTypes";
import {
    getNilReasonLabel,
    getRouteLabel,
    getStatusLabel,
} from "./reviewQueueI18n";

interface ReviewQueueRecordsTableProps {
    queueMode: "generic" | "authors" | "institutions";
    statusFilter: string;
    loadingRecords: boolean;
    records: AuthorityRecord[];
    selected: Set<number>;
    rowActionId: number | null;
    expandedId: number | null;
    loadingCompareId: number | null;
    linkActionId: number | null;
    compareMap: Record<number, AuthorCompareResponse>;
    affiliationMap: Record<number, AuthorAffiliationsResponse>;
    onToggleSelectAll: () => void;
    onToggleSelect: (id: number) => void;
    onReviewRecord: (record: AuthorityRecord, action: "confirm" | "reject") => void;
    onReviewAuthorityLink: (linkId: number, action: "confirm" | "reject", authorRecordId: number) => void;
    onToggleExpanded: (record: AuthorityRecord) => void;
}

export default function ReviewQueueRecordsTable({
    queueMode,
    statusFilter,
    loadingRecords,
    records,
    selected,
    rowActionId,
    expandedId,
    loadingCompareId,
    linkActionId,
    compareMap,
    affiliationMap,
    onToggleSelectAll,
    onToggleSelect,
    onReviewRecord,
    onReviewAuthorityLink,
    onToggleExpanded,
}: ReviewQueueRecordsTableProps) {
    const { t } = useLanguage();

    if (loadingRecords) {
        return (
            <div className="flex items-center justify-center py-12">
                <svg className="h-6 w-6 animate-spin text-gray-400" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
            </div>
        );
    }

    if (records.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-12">
                <p className="text-sm text-gray-400 dark:text-gray-500">
                    {t("page.authority.no_records")}
                </p>
            </div>
        );
    }

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-sm">
                <thead>
                    <tr className="border-b border-gray-100 text-left text-xs font-medium text-gray-500 dark:border-gray-800 dark:text-gray-400">
                        {statusFilter === "pending" && (
                            <th className="w-10 px-4 py-2">
                                <input
                                    type="checkbox"
                                    checked={selected.size === records.length && records.length > 0}
                                    onChange={onToggleSelectAll}
                                    className="rounded border-gray-300"
                                />
                            </th>
                        )}
                        <th className="px-4 py-2">{t("page.authority.original_value")}</th>
                        <th className="px-4 py-2">{queueMode === "authors" ? t("page.authority.candidate") : t("page.authority.canonical_label")}</th>
                        <th className="px-4 py-2">{t("page.authority.table_source")}</th>
                        <th className="px-4 py-2">{t("page.authority.table_confidence")}</th>
                        <th className="px-4 py-2">{queueMode === "authors" ? t("page.authority.table_route") : queueMode === "institutions" ? t("page.authority.resolution") : t("page.authority.field")}</th>
                        <th className="px-4 py-2">{t("common.status")}</th>
                        <th className="px-4 py-2">{queueMode === "authors" || queueMode === "institutions" ? t("common.actions") : ""}</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                    {records.map(rec => (
                        <Fragment key={rec.id}>
                            <tr className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                                {statusFilter === "pending" && (
                                    <td className="px-4 py-2.5">
                                        <input
                                            type="checkbox"
                                            checked={selected.has(rec.id)}
                                            onChange={() => onToggleSelect(rec.id)}
                                            className="rounded border-gray-300"
                                        />
                                    </td>
                                )}
                                <td className="px-4 py-2.5 font-medium text-gray-900 dark:text-white">
                                    {rec.original_value}
                                </td>
                                <td className="px-4 py-2.5 text-gray-700 dark:text-gray-300">
                                    <div className="flex items-center gap-2">
                                        {rec.canonical_label}
                                        {rec.resolution_status === "partial_ancestor_match" && (
                                            <Badge variant="info">{t("page.authority.ancestor_match")}</Badge>
                                        )}
                                        {queueMode === "authors" && rec.nil_reason && (
                                            <Badge variant="error">NIL</Badge>
                                        )}
                                        {rec.uri && (
                                            <a
                                                href={rec.uri}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-blue-500 hover:text-blue-600"
                                                title={t("page.authority.view_in_authority_source")}
                                            >
                                                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                                </svg>
                                            </a>
                                        )}
                                    </div>
                                    {rec.description && (
                                        <p className="mt-0.5 max-w-xs truncate text-xs text-gray-400 dark:text-gray-500">
                                            {rec.description}
                                        </p>
                                    )}
                                    {queueMode === "authors" && rec.nil_reason && (
                                        <p className="mt-0.5 text-xs text-rose-500 dark:text-rose-400">
                                            {getNilReasonLabel(rec.nil_reason, t)}
                                        </p>
                                    )}
                                    {queueMode !== "authors" && rec.resolution_status === "partial_ancestor_match" && typeof rec.hierarchy_distance === "number" && (
                                        <p className="mt-0.5 text-xs text-indigo-600 dark:text-indigo-400">
                                            {t("page.authority.ancestor_distance")} {rec.hierarchy_distance}
                                        </p>
                                    )}
                                </td>
                                <td className="px-4 py-2.5">
                                    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${SOURCE_COLORS[rec.authority_source] || "bg-gray-100 text-gray-600"}`}>
                                        {rec.authority_source}
                                    </span>
                                </td>
                                <td className="px-4 py-2.5">
                                    <div className="flex items-center gap-2">
                                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                                            <div
                                                className={`h-full rounded-full ${rec.confidence >= 0.8 ? "bg-green-500" : rec.confidence >= 0.5 ? "bg-amber-500" : "bg-red-500"}`}
                                                style={{ width: `${rec.confidence * 100}%` }}
                                            />
                                        </div>
                                        <span className="text-xs text-gray-500">{(rec.confidence * 100).toFixed(0)}%</span>
                                    </div>
                                </td>
                                <td className="px-4 py-2.5 font-mono text-xs text-gray-500">
                                    {queueMode === "authors" ? (
                                        <div className="space-y-1">
                                            <div>{getRouteLabel(rec.resolution_route, t)}</div>
                                            <div className="text-[11px] text-gray-400">
                                                {t("page.authority.complexity")} {typeof rec.complexity_score === "number" ? rec.complexity_score.toFixed(2) : "--"}
                                            </div>
                                            <div className="text-[11px] text-rose-500 dark:text-rose-400">
                                                {t("page.authority.nil_short")} {typeof rec.nil_score === "number" ? `${(rec.nil_score * 100).toFixed(0)}%` : "--"}
                                            </div>
                                        </div>
                                    ) : queueMode === "institutions" ? (
                                        <div className="space-y-1">
                                            <div>{rec.resolution_status}</div>
                                            {rec.score_breakdown && Object.keys(rec.score_breakdown).length > 0 && (
                                                <div className="text-[11px] text-gray-400">
                                                    {Object.entries(rec.score_breakdown).slice(0, 2).map(([key, value]) => `${key}:${value.toFixed(2)}`).join(" ")}
                                                </div>
                                            )}
                                        </div>
                                    ) : rec.field_name}
                                    {queueMode === "generic" && rec.resolution_status === "partial_ancestor_match" && typeof rec.hierarchy_distance === "number" && (
                                        <div className="mt-1 text-[11px] text-indigo-500 dark:text-indigo-400">
                                            {t("page.authority.ancestor_short")} +{rec.hierarchy_distance}
                                        </div>
                                    )}
                                </td>
                                <td className="px-4 py-2.5">
                                    <div className="flex flex-col items-start gap-1">
                                        <Badge variant={rec.status === "confirmed" ? "success" : rec.status === "rejected" ? "error" : "warning"}>
                                            {getStatusLabel(rec.status, t)}
                                        </Badge>
                                        {(queueMode === "authors" || queueMode === "institutions") && rec.review_required && (
                                            <span className="text-[11px] text-amber-600 dark:text-amber-400">{t("page.authority.needs_review")}</span>
                                        )}
                                    </div>
                                </td>
                                <td className="px-4 py-2.5">
                                    <div className="flex items-center justify-end gap-2">
                                        {(queueMode === "authors" || queueMode === "institutions") && statusFilter === "pending" && (
                                            <>
                                                <button
                                                    onClick={() => onReviewRecord(rec, "confirm")}
                                                    disabled={rowActionId === rec.id}
                                                    className="inline-flex h-7 items-center rounded-md bg-green-600 px-2.5 text-[11px] font-medium text-white transition-colors hover:bg-green-700 disabled:opacity-50"
                                                >
                                                    {rowActionId === rec.id ? t("page.authority.saving") : queueMode === "institutions" ? t("page.authority.confirm_button") : rec.nil_reason ? t("page.authority.accept_nil") : t("page.authority.confirm_button")}
                                                </button>
                                                <button
                                                    onClick={() => onReviewRecord(rec, "reject")}
                                                    disabled={rowActionId === rec.id}
                                                    className="inline-flex h-7 items-center rounded-md bg-red-600 px-2.5 text-[11px] font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
                                                >
                                                    {t("page.authority.reject_button")}
                                                </button>
                                            </>
                                        )}
                                        <button
                                            onClick={() => onToggleExpanded(rec)}
                                            className={`rounded p-1 transition-colors ${expandedId === rec.id ? "text-indigo-600 dark:text-indigo-400" : "text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400"}`}
                                            title={t("page.authority.toggle_comments")}
                                        >
                                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                            </svg>
                                        </button>
                                    </div>
                                </td>
                            </tr>
                            {expandedId === rec.id && (
                                <tr>
                                    <td colSpan={statusFilter === "pending" ? 8 : 7} className="border-t border-gray-100 bg-gray-50 px-6 py-4 dark:border-gray-800 dark:bg-gray-800/30">
                                        <div className="space-y-4">
                                            {queueMode === "authors" && (
                                                <AuthorReviewExpandedPanel
                                                    record={rec}
                                                    compare={compareMap[rec.id] ?? null}
                                                    affiliations={affiliationMap[rec.id] ?? null}
                                                    loadingCompare={loadingCompareId === rec.id}
                                                    linkActionId={linkActionId}
                                                    onReviewAuthorityLink={onReviewAuthorityLink}
                                                />
                                            )}

                                            {queueMode !== "authors" &&
                                                (rec.score_breakdown || (rec.evidence && rec.evidence.length > 0)) && (
                                                <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900/40">
                                                    <h4 className="mb-2 text-xs font-semibold text-gray-700 dark:text-gray-300">
                                                        {t("page.authority.score_breakdown") || "Desglose de puntuación"}
                                                    </h4>
                                                    <ScoreBreakdown
                                                        breakdown={rec.score_breakdown}
                                                        evidence={rec.evidence}
                                                    />
                                                </div>
                                            )}

                                            {queueMode !== "authors" && statusFilter === "pending" && (
                                                <div className="flex items-center gap-2">
                                                    <button
                                                        onClick={() => onReviewRecord(rec, "confirm")}
                                                        disabled={rowActionId === rec.id}
                                                        className="inline-flex h-7 items-center rounded-md bg-green-600 px-3 text-xs font-medium text-white transition-colors hover:bg-green-700 disabled:opacity-50"
                                                    >
                                                        {rowActionId === rec.id ? t("page.authority.saving") : t("page.authority.confirm_button")}
                                                    </button>
                                                    <button
                                                        onClick={() => onReviewRecord(rec, "reject")}
                                                        disabled={rowActionId === rec.id}
                                                        className="inline-flex h-7 items-center rounded-md bg-red-600 px-3 text-xs font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
                                                    >
                                                        {t("page.authority.reject_button")}
                                                    </button>
                                                </div>
                                            )}

                                            <AnnotationThread authorityId={rec.id} />
                                        </div>
                                    </td>
                                </tr>
                            )}
                        </Fragment>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
