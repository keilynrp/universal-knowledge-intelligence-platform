"use client";

import type { DomainAttribute, DomainSchema } from "../contexts/DomainContext";
import { useLanguage } from "../contexts/LanguageContext";
import type { QueueSummary } from "./reviewQueueTypes";
import { getEntityTypeLabel, getRouteLabel } from "./reviewQueueI18n";

interface ReviewQueueControlsProps {
    activeDomain: DomainSchema | null;
    queueMode: "generic" | "authors" | "institutions";
    statusFilter: string;
    fieldFilter: string;
    authorRouteFilter: string;
    authorReviewFilter: string;
    authorNilOnly: boolean;
    batchField: string;
    batchEntityType: string;
    batchLimit: number;
    resolving: boolean;
    resolveResult: string | null;
    acting: boolean;
    selectedCount: number;
    summary: QueueSummary | null;
    onQueueModeChange: (mode: "generic" | "authors" | "institutions") => void;
    onStatusFilterChange: (value: string) => void;
    onFieldFilterChange: (value: string) => void;
    onAuthorRouteFilterChange: (value: string) => void;
    onAuthorReviewFilterChange: (value: string) => void;
    onAuthorNilOnlyChange: (value: boolean) => void;
    onBatchFieldChange: (value: string) => void;
    onBatchEntityTypeChange: (value: string) => void;
    onBatchLimitChange: (value: number) => void;
    onBatchResolve: () => void;
    onApplyInstitutionReconciliation: () => void;
    onBulkAction: (action: "bulk-confirm" | "bulk-reject") => void;
}

export default function ReviewQueueControls({
    activeDomain,
    queueMode,
    statusFilter,
    fieldFilter,
    authorRouteFilter,
    authorReviewFilter,
    authorNilOnly,
    batchField,
    batchEntityType,
    batchLimit,
    resolving,
    resolveResult,
    acting,
    selectedCount,
    summary,
    onQueueModeChange,
    onStatusFilterChange,
    onFieldFilterChange,
    onAuthorRouteFilterChange,
    onAuthorReviewFilterChange,
    onAuthorNilOnlyChange,
    onBatchFieldChange,
    onBatchEntityTypeChange,
    onBatchLimitChange,
    onBatchResolve,
    onApplyInstitutionReconciliation,
    onBulkAction,
}: ReviewQueueControlsProps) {
    const { t } = useLanguage();

    return (
        <>
            <div className="inline-flex rounded-xl border border-gray-200 bg-white p-1 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <button
                    onClick={() => onQueueModeChange("generic")}
                    className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                        queueMode === "generic"
                            ? "bg-blue-600 text-white"
                            : "text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
                    }`}
                >
                    {t("page.authority.queue_generic")}
                </button>
                <button
                    onClick={() => onQueueModeChange("authors")}
                    className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                        queueMode === "authors"
                            ? "bg-blue-600 text-white"
                            : "text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
                    }`}
                >
                    {t("page.authority.queue_authors")}
                </button>
                <button
                    onClick={() => onQueueModeChange("institutions")}
                    className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                        queueMode === "institutions"
                            ? "bg-blue-600 text-white"
                            : "text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
                    }`}
                >
                    {t("page.authority.queue_institutions")}
                </button>
            </div>

            {queueMode === "generic" && (
                <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                    <h3 className="mb-3 text-sm font-medium text-gray-900 dark:text-white">{t("page.authority.batch_resolve")}</h3>
                    <div className="flex flex-wrap items-end gap-4">
                        <div className="min-w-[160px]">
                            <label className="mb-1 block text-xs text-gray-500 dark:text-gray-400">{t("page.authority.field")}</label>
                            <select
                                value={batchField}
                                onChange={e => onBatchFieldChange(e.target.value)}
                                className="h-9 w-full rounded-lg border border-gray-200 bg-white px-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                            >
                                {activeDomain ? (
                                    activeDomain.attributes
                                        .filter((a: DomainAttribute) => a.type === "string")
                                        .map((attr: DomainAttribute) => (
                                            <option key={attr.name} value={attr.name}>{attr.label}</option>
                                        ))
                                ) : (
                                    <option value="">{t("common.loading")}</option>
                                )}
                            </select>
                        </div>
                        <div className="min-w-[130px]">
                            <label className="mb-1 block text-xs text-gray-500 dark:text-gray-400">{t("page.authority.entity_type")}</label>
                            <select
                                value={batchEntityType}
                                onChange={e => onBatchEntityTypeChange(e.target.value)}
                                className="h-9 w-full rounded-lg border border-gray-200 bg-white px-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                            >
                                {["general", "person", "organization", "concept", "institution"].map(et => (
                                    <option key={et} value={et}>{getEntityTypeLabel(et, t)}</option>
                                ))}
                            </select>
                        </div>
                        <div className="w-20">
                            <label className="mb-1 block text-xs text-gray-500 dark:text-gray-400">{t("page.authority.limit")}</label>
                            <input
                                type="number"
                                min={1}
                                max={100}
                                value={batchLimit}
                                onChange={e => onBatchLimitChange(Number(e.target.value))}
                                className="h-9 w-full rounded-lg border border-gray-200 bg-white px-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                            />
                        </div>
                        <button
                            onClick={onBatchResolve}
                            disabled={resolving || !batchField}
                            className="inline-flex h-9 items-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                        >
                            {resolving ? (
                                <>
                                    <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                    </svg>
                                    {t("page.authority.resolving")}
                                </>
                            ) : t("page.authority.resolve_all")}
                        </button>
                    </div>
                    {resolveResult && (
                        <p className={`mt-3 text-sm ${resolveResult.startsWith("Error") ? "text-red-600" : "text-green-600 dark:text-green-400"}`}>
                            {resolveResult}
                        </p>
                    )}
                </div>
            )}

            {queueMode === "institutions" && (
                <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                    <h3 className="mb-3 text-sm font-medium text-gray-900 dark:text-white">{t("page.authority.institution_reconciliation")}</h3>
                    <div className="flex flex-wrap items-end gap-4">
                        <div className="w-24">
                            <label className="mb-1 block text-xs text-gray-500 dark:text-gray-400">{t("page.authority.limit")}</label>
                            <input
                                type="number"
                                min={1}
                                max={100}
                                value={batchLimit}
                                onChange={e => onBatchLimitChange(Number(e.target.value))}
                                className="h-9 w-full rounded-lg border border-gray-200 bg-white px-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                            />
                        </div>
                        <button
                            onClick={onApplyInstitutionReconciliation}
                            disabled={resolving}
                            className="inline-flex h-9 items-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                        >
                            {resolving ? t("page.authority.resolving") : t("page.authority.apply_institution_reconciliation")}
                        </button>
                    </div>
                    {resolveResult && (
                        <p className={`mt-3 text-sm ${resolveResult.startsWith("Error") ? "text-red-600" : "text-green-600 dark:text-green-400"}`}>
                            {resolveResult}
                        </p>
                    )}
                </div>
            )}

            <div className="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 px-5 py-3 dark:border-gray-800">
                    <div className="flex items-center gap-3">
                        <select
                            value={statusFilter}
                            onChange={e => onStatusFilterChange(e.target.value)}
                            className="h-8 rounded-lg border border-gray-200 bg-white px-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                        >
                            <option value="pending">{t("page.authority.filter_pending")}</option>
                            <option value="confirmed">{t("page.authority.filter_confirmed")}</option>
                            <option value="rejected">{t("page.authority.filter_rejected")}</option>
                        </select>
                        {queueMode === "generic" ? (
                            <select
                                value={fieldFilter}
                                onChange={e => onFieldFilterChange(e.target.value)}
                                className="h-8 rounded-lg border border-gray-200 bg-white px-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                            >
                                <option value="">{t("page.authority.all_fields")}</option>
                                {summary?.by_field.map(f => (
                                    <option key={f.field_name} value={f.field_name}>{f.field_name}</option>
                                ))}
                            </select>
                        ) : queueMode === "authors" ? (
                            <>
                                <select
                                    value={authorRouteFilter}
                                    onChange={e => onAuthorRouteFilterChange(e.target.value)}
                                    className="h-8 rounded-lg border border-gray-200 bg-white px-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                                >
                                    <option value="">{t("page.authority.all_routes")}</option>
                                    <option value="fast_path">{getRouteLabel("fast_path", t)}</option>
                                    <option value="hybrid_path">{getRouteLabel("hybrid_path", t)}</option>
                                    <option value="llm_path">{getRouteLabel("llm_path", t)}</option>
                                    <option value="manual_review">{getRouteLabel("manual_review", t)}</option>
                                </select>
                                <select
                                    value={authorReviewFilter}
                                    onChange={e => onAuthorReviewFilterChange(e.target.value)}
                                    className="h-8 rounded-lg border border-gray-200 bg-white px-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                                >
                                    <option value="required">{t("page.authority.needs_review")}</option>
                                    <option value="all">{t("page.authority.all_review_states")}</option>
                                    <option value="not_required">{t("page.authority.no_review_needed")}</option>
                                </select>
                                <label className="inline-flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                                    <input
                                        type="checkbox"
                                        checked={authorNilOnly}
                                        onChange={e => onAuthorNilOnlyChange(e.target.checked)}
                                        className="rounded border-gray-300"
                                    />
                                    {t("page.authority.nil_only")}
                                </label>
                            </>
                        ) : (
                            <span className="text-xs text-gray-500 dark:text-gray-400">{t("page.authority.ror_review_queue")}</span>
                        )}
                    </div>
                    {statusFilter === "pending" && (
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => onBulkAction("bulk-confirm")}
                                disabled={acting || selectedCount === 0}
                                className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-green-600 px-3 text-xs font-medium text-white transition-colors hover:bg-green-700 disabled:opacity-50"
                            >
                                {t("page.authority.confirm_button")} ({selectedCount})
                            </button>
                            <button
                                onClick={() => onBulkAction("bulk-reject")}
                                disabled={acting || selectedCount === 0}
                                className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-red-600 px-3 text-xs font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
                            >
                                {t("page.authority.reject_button")} ({selectedCount})
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}
