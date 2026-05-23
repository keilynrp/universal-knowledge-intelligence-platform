"use client";

import { useLanguage } from "../contexts/LanguageContext";
import type {
    AuthorMetrics,
    AuthorQueueSummary,
    QueueSummary,
} from "./reviewQueueTypes";
import { getNilReasonLabel, getRouteLabel } from "./reviewQueueI18n";

interface ReviewQueueSummaryPanelsProps {
    queueMode: "generic" | "authors" | "institutions";
    summary: QueueSummary | null;
    authorSummary: AuthorQueueSummary | null;
    authorMetrics: AuthorMetrics | null;
}

export default function ReviewQueueSummaryPanels({
    queueMode,
    summary,
    authorSummary,
    authorMetrics,
}: ReviewQueueSummaryPanelsProps) {
    const { t } = useLanguage();

    return (
        <>
            {queueMode === "generic" && summary && (
                <>
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                            <p className="text-sm text-gray-500 dark:text-gray-400">{t("page.authority.pending_review")}</p>
                            <p className="mt-1 text-2xl font-bold text-amber-600 dark:text-amber-400">{summary.total_pending}</p>
                        </div>
                        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                            <p className="text-sm text-gray-500 dark:text-gray-400">{t("page.authority.filter_confirmed")}</p>
                            <p className="mt-1 text-2xl font-bold text-green-600 dark:text-green-400">{summary.total_confirmed}</p>
                        </div>
                        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                            <p className="text-sm text-gray-500 dark:text-gray-400">{t("page.authority.filter_rejected")}</p>
                            <p className="mt-1 text-2xl font-bold text-red-600 dark:text-red-400">{summary.total_rejected}</p>
                        </div>
                    </div>

                    {summary.by_field.length > 0 && (
                        <div className="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
                            <div className="border-b border-gray-200 px-5 py-3 dark:border-gray-800">
                                <h3 className="text-sm font-medium text-gray-900 dark:text-white">{t("page.authority.by_field")}</h3>
                            </div>
                            <div className="divide-y divide-gray-100 dark:divide-gray-800">
                                {summary.by_field.map(f => (
                                    <div key={f.field_name} className="flex items-center justify-between px-5 py-3">
                                        <span className="text-sm font-mono text-gray-700 dark:text-gray-300">{f.field_name}</span>
                                        <div className="flex items-center gap-4 text-xs">
                                            <span className="text-amber-600">{f.pending} {t("page.authority.filter_pending").toLowerCase()}</span>
                                            <span className="text-green-600">{f.confirmed} {t("page.authority.filter_confirmed").toLowerCase()}</span>
                                            <span className="text-red-600">{f.rejected} {t("page.authority.filter_rejected").toLowerCase()}</span>
                                            <span className="text-gray-400">{t("page.authority.average_short")} {(f.avg_confidence * 100).toFixed(0)}%</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </>
            )}

            {queueMode === "authors" && authorSummary && (
                <>
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                            <p className="text-sm text-gray-500 dark:text-gray-400">{t("page.authority.author_records")}</p>
                            <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{authorSummary.total_records}</p>
                        </div>
                        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                            <p className="text-sm text-gray-500 dark:text-gray-400">{t("page.authority.needs_review")}</p>
                            <p className="mt-1 text-2xl font-bold text-amber-600 dark:text-amber-400">{authorSummary.pending_review}</p>
                        </div>
                        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                            <p className="text-sm text-gray-500 dark:text-gray-400">{t("page.authority.nil_cases")}</p>
                            <p className="mt-1 text-2xl font-bold text-rose-600 dark:text-rose-400">{authorSummary.nil_cases}</p>
                        </div>
                    </div>

                    {authorMetrics && (
                        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                            <div className="mb-4 flex items-center justify-between gap-3">
                                <h3 className="text-sm font-medium text-gray-900 dark:text-white">{t("page.authority.engine_metrics")}</h3>
                                <span className="text-xs text-gray-400 dark:text-gray-500">{t("page.authority.author_only_runtime")}</span>
                            </div>
                            <div className="grid grid-cols-2 gap-4 lg:grid-cols-5 xl:grid-cols-10">
                                <div>
                                    <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{t("page.authority.avg_confidence")}</p>
                                    <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">
                                        {(authorMetrics.avg_confidence * 100).toFixed(0)}%
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{t("page.authority.avg_complexity")}</p>
                                    <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">
                                        {authorMetrics.avg_complexity.toFixed(2)}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{t("page.authority.avg_nil_score")}</p>
                                    <p className="mt-1 text-lg font-semibold text-rose-600 dark:text-rose-400">
                                        {(authorMetrics.avg_nil_score * 100).toFixed(0)}%
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{t("page.authority.review_rate")}</p>
                                    <p className="mt-1 text-lg font-semibold text-amber-600 dark:text-amber-400">
                                        {(authorMetrics.review_rate * 100).toFixed(0)}%
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{t("page.authority.confirm_rate")}</p>
                                    <p className="mt-1 text-lg font-semibold text-green-600 dark:text-green-400">
                                        {(authorMetrics.confirm_rate * 100).toFixed(0)}%
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{t("page.authority.nil_rate")}</p>
                                    <p className="mt-1 text-lg font-semibold text-rose-600 dark:text-rose-400">
                                        {(authorMetrics.nil_rate * 100).toFixed(0)}%
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{t("page.authority.reformulations")}</p>
                                    <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">
                                        {authorMetrics.reformulation_attempts}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{t("page.authority.applied")}</p>
                                    <p className="mt-1 text-lg font-semibold text-blue-600 dark:text-blue-400">
                                        {authorMetrics.reformulation_applied}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{t("page.authority.apply_rate")}</p>
                                    <p className="mt-1 text-lg font-semibold text-blue-600 dark:text-blue-400">
                                        {(authorMetrics.reformulation_apply_rate * 100).toFixed(0)}%
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{t("page.authority.avg_gain")}</p>
                                    <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">
                                        {authorMetrics.avg_reformulation_gain.toFixed(2)}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{t("page.authority.estimated_cost")}</p>
                                    <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">
                                        ${authorMetrics.total_reformulation_cost.toFixed(4)}
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}

                    {authorMetrics && Object.keys(authorMetrics.by_nil_reason).length > 0 && (
                        <div className="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
                            <div className="border-b border-gray-200 px-5 py-3 dark:border-gray-800">
                                <h3 className="text-sm font-medium text-gray-900 dark:text-white">{t("page.authority.nil_reasons")}</h3>
                            </div>
                            <div className="divide-y divide-gray-100 dark:divide-gray-800">
                                {Object.entries(authorMetrics.by_nil_reason).map(([reason, count]) => (
                                    <div key={reason} className="flex items-center justify-between px-5 py-3">
                                        <span className="text-sm font-mono text-gray-700 dark:text-gray-300">{getNilReasonLabel(reason, t)}</span>
                                        <span className="text-xs text-gray-500 dark:text-gray-400">{count} {t("page.authority.records_label")}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {Object.keys(authorSummary.by_route).length > 0 && (
                        <div className="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
                            <div className="border-b border-gray-200 px-5 py-3 dark:border-gray-800">
                                <h3 className="text-sm font-medium text-gray-900 dark:text-white">{t("page.authority.by_route")}</h3>
                            </div>
                            <div className="divide-y divide-gray-100 dark:divide-gray-800">
                                {Object.entries(authorSummary.by_route).map(([routeKey, count]) => (
                                    <div key={routeKey} className="flex items-center justify-between px-5 py-3">
                                        <span className="text-sm font-mono text-gray-700 dark:text-gray-300">{getRouteLabel(routeKey, t)}</span>
                                        <span className="text-xs text-gray-500 dark:text-gray-400">{count} {t("page.authority.records_label")}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </>
            )}
        </>
    );
}
