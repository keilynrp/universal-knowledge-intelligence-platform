"use client";

import React from "react";
import { useLanguage } from "../contexts/LanguageContext";

export interface EntityTablePaginationProps {
    totalCount: number;
    limit: number;
    page: number;
    loading: boolean;
    onLimitChange: (limit: number) => void;
    onPageChange: (updater: number | ((prev: number) => number)) => void;
}

export function EntityTablePagination({
    totalCount,
    limit,
    page,
    loading,
    onLimitChange,
    onPageChange
}: EntityTablePaginationProps) {
    const { t } = useLanguage();
    const pageStart = totalCount === 0 ? 0 : page * limit + 1;
    const pageEnd = Math.min((page + 1) * limit, totalCount);
    const totalPages = totalCount > 0 ? Math.ceil(totalCount / limit) : 1;
    const hasNextPage = pageEnd < totalCount;

    return (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-200 px-5 py-3.5 dark:border-gray-800">
            <div className="flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-500 dark:text-gray-400">{t("common.rows_per_page")}:</span>
                    <select
                        value={limit}
                        onChange={(e) => {
                            onLimitChange(Number(e.target.value));
                            onPageChange(0);
                        }}
                        className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-sm text-gray-700 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
                    >
                        <option value={10}>10</option>
                        <option value={20}>20</option>
                        <option value={50}>50</option>
                        <option value={100}>100</option>
                        <option value={200}>200</option>
                    </select>
                </div>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                    {t("page.entity_table.pagination_summary", {
                        start: pageStart,
                        end: pageEnd,
                        total: totalCount,
                    })}
                </span>
            </div>

            <div className="flex items-center gap-4">
                <button
                    onClick={() => onPageChange(p => Math.max(0, p - 1))}
                    disabled={page === 0 || loading}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3.5 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                    </svg>
                    {t("page.entity_table.previous_page")}
                </button>
                <div className="flex items-center gap-2">
                    <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm font-medium text-white">
                        {page + 1}
                    </span>
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                        {t("page.entity_table.page_of_total", { page: page + 1, total: totalPages })}
                    </span>
                </div>
                <button
                    onClick={() => onPageChange(p => p + 1)}
                    disabled={!hasNextPage || loading}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3.5 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                    {t("common.next")}
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                </button>
            </div>
        </div>
    );
}

export default EntityTablePagination;
