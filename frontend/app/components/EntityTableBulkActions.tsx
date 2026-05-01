"use client";

import React from "react";
import { useLanguage } from "../contexts/LanguageContext";

export interface EntityTableBulkActionsProps {
    selectedCount: number;
    pageSelectionOnly?: boolean;
    bulkEnriching: boolean;
    bulkDeleting: boolean;
    onBulkEnrich: () => void;
    onBulkExport: () => void;
    onBulkDelete: () => void;
    onClearSelection: () => void;
}

export function EntityTableBulkActions({
    selectedCount,
    pageSelectionOnly = true,
    bulkEnriching,
    bulkDeleting,
    onBulkEnrich,
    onBulkExport,
    onBulkDelete,
    onClearSelection,
}: EntityTableBulkActionsProps) {
    const { t } = useLanguage();
    if (selectedCount === 0) return null;

    const selectedLabel = pageSelectionOnly
        ? t("page.entity_table.bulk_selected_page", { count: selectedCount })
        : t("page.entity_table.bulk_selected", { count: selectedCount });

    return (
        <div className="toast-enter fixed inset-x-0 bottom-4 z-[150] flex justify-center px-3 sm:bottom-6">
            <div className="w-full max-w-[calc(100vw-1.5rem)] rounded-3xl border border-slate-200 bg-white/95 p-3 shadow-2xl shadow-slate-900/15 backdrop-blur-xl dark:border-white/10 dark:bg-[var(--ukip-panel)] sm:max-w-xl lg:max-w-3xl xl:max-w-4xl">
                <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                    <div className="flex min-w-0 items-start gap-3">
                        <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-violet-600 text-sm font-black text-white shadow-[var(--ukip-glow-violet)]">
                            {selectedCount}
                        </span>
                        <div className="min-w-0">
                            <p className="truncate text-sm font-bold text-slate-800 dark:text-[var(--ukip-text-strong)]">
                                {selectedLabel}
                            </p>
                            {pageSelectionOnly && (
                                <p className="mt-0.5 text-xs leading-5 text-slate-500 dark:text-[var(--ukip-muted)]">
                                    {t("page.entity_table.bulk_page_scope_hint")}
                                </p>
                            )}
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-[repeat(4,auto)] sm:justify-end">
                        <button
                            onClick={onBulkEnrich}
                            disabled={bulkEnriching}
                            className="flex h-10 min-w-0 items-center justify-center gap-1.5 rounded-xl bg-purple-50 px-3 text-xs font-bold text-purple-700 transition-colors hover:bg-purple-100 disabled:opacity-60 dark:bg-purple-500/10 dark:text-purple-300 dark:hover:bg-purple-500/20"
                        >
                            {bulkEnriching ? (
                                <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                            ) : (
                                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                                </svg>
                            )}
                            <span className="truncate">{t("page.entity_table.bulk_enrich_action")}</span>
                        </button>
                        <button
                            onClick={onBulkExport}
                            className="flex h-10 min-w-0 items-center justify-center gap-1.5 rounded-xl bg-emerald-50 px-3 text-xs font-bold text-emerald-700 transition-colors hover:bg-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-300 dark:hover:bg-emerald-500/20"
                        >
                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                            </svg>
                            <span className="truncate">{t("page.entity_table.bulk_export_action")}</span>
                        </button>
                        <button
                            onClick={onBulkDelete}
                            disabled={bulkDeleting}
                            className="flex h-10 min-w-0 items-center justify-center gap-1.5 rounded-xl bg-red-50 px-3 text-xs font-bold text-red-700 transition-colors hover:bg-red-100 disabled:opacity-60 dark:bg-red-500/10 dark:text-red-300 dark:hover:bg-red-500/20"
                        >
                            {bulkDeleting ? (
                                <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                            ) : (
                                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                                </svg>
                            )}
                            <span className="truncate">{t("common.delete")}</span>
                        </button>
                        <button
                            onClick={onClearSelection}
                            className="flex h-10 items-center justify-center rounded-xl border border-slate-200 px-3 text-xs font-bold text-slate-500 transition hover:bg-slate-50 hover:text-slate-800 dark:border-white/10 dark:text-[var(--ukip-muted)] dark:hover:bg-white/10 dark:hover:text-[var(--ukip-text)]"
                            title={t("page.entity_table.clear_selection")}
                        >
                            <svg className="h-4 w-4 sm:mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                            <span className="hidden sm:inline">{t("page.entity_table.clear_selection")}</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default EntityTableBulkActions;
