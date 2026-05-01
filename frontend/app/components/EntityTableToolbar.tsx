"use client";

import { useLanguage } from "../contexts/LanguageContext";
import type { ActiveFacets } from "./FacetPanel";

const FIELD_LABELS: Record<string, string> = {
    entity_type: "page.import.field.entity_type",
    domain: "page.import.field.domain",
    validation_status: "page.entity_table.review_status",
    enrichment_status: "page.entity_table.system_status",
    source: "page.exec_dashboard.source",
};

export interface EntityTableToolbarProps {
    activeFacets: ActiveFacets;
    search: string;
    minQuality: string;
    page: number;
    totalCount?: number;
    visibleCount?: number;
    selectedCount?: number;
    selectableCount?: number;
    isAllSelected?: boolean;
    isPartiallySelected?: boolean;
    sortLabel?: string;
    viewMode?: "grid" | "list";
    onToggleSelectAll?: () => void;
    onSortQuality?: () => void;
    onViewModeChange?: (mode: "grid" | "list") => void;
    onSearchChange: (value: string) => void;
    onMinQualityChange: (value: string) => void;
    onClearFacet: (field: string) => void;
}

export default function EntityTableToolbar({
    activeFacets,
    search,
    minQuality,
    page,
    totalCount,
    visibleCount,
    selectedCount,
    selectableCount,
    isAllSelected,
    isPartiallySelected,
    sortLabel,
    viewMode = "grid",
    onToggleSelectAll,
    onSortQuality,
    onViewModeChange,
    onSearchChange,
    onMinQualityChange,
    onClearFacet,
}: EntityTableToolbarProps) {
    const { t } = useLanguage();
    const hasActiveFacets = Object.entries(activeFacets).some(([, value]) => value);
    const hasToolbarFilters = hasActiveFacets || Boolean(search) || Boolean(minQuality);
    const formatFacetField = (field: string) => {
        const key = FIELD_LABELS[field];
        if (!key) return field.replace(/_/g, " ");
        const translated = t(key);
        return translated === key ? field.replace(/_/g, " ") : translated;
    };
    const formatFacetValue = (field: string, value: string | null) => {
        if (!value) return t("page.entity_table.empty_value");
        if (field === "entity_type") {
            const translated = t(`page.authority.entity_type_${value}`);
            return translated === `page.authority.entity_type_${value}` ? value : translated;
        }
        if (field === "validation_status") {
            const translated = t(`page.entity_table.status_${value}`);
            return translated === `page.entity_table.status_${value}` ? value : translated;
        }
        if (field === "enrichment_status") {
            const enrichmentKeyMap: Record<string, string> = {
                completed: "entities.filter.enriched",
                pending: "entities.filter.pending",
                processing: "page.entity_table.status_processing",
                failed: "entities.filter.failed",
                none: "page.entity_table.status_not_started",
            };
            const key = enrichmentKeyMap[value] ?? `entities.filter.${value}`;
            const translated = t(key);
            return translated === key ? value : translated;
        }
        return value;
    };

    return (
        <>
            {hasToolbarFilters && (
                <div className="mb-3 flex flex-wrap gap-1.5 px-1">
                    {search && (
                        <span className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs text-sky-800 dark:border-sky-500/20 dark:bg-sky-500/10 dark:text-sky-200">
                            <span className="font-medium">{t("common.search")}:</span> {search}
                            <button
                                onClick={() => onSearchChange("")}
                                className="ml-0.5 font-bold leading-none hover:text-sky-600"
                            >
                                x
                            </button>
                        </span>
                    )}
                    {minQuality && (
                        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs text-emerald-800 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-200">
                            <span className="font-medium">{t("page.entity_table.min_quality")}:</span>
                            {minQuality === "0.7" ? "70%+" : minQuality === "0.3" ? "30%+" : t("page.entity_table.under_30")}
                            <button
                                onClick={() => onMinQualityChange("")}
                                className="ml-0.5 font-bold leading-none hover:text-emerald-600"
                            >
                                x
                            </button>
                        </span>
                    )}
                    {Object.entries(activeFacets)
                        .filter(([, value]) => value)
                        .map(([field, value]) => (
                            <span
                                key={field}
                                className="inline-flex items-center gap-1 rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-xs text-violet-800 dark:border-violet-500/20 dark:bg-violet-500/10 dark:text-violet-200"
                            >
                                <span className="font-medium">{formatFacetField(field)}:</span> {formatFacetValue(field, value)}
                                <button
                                    onClick={() => onClearFacet(field)}
                                    className="ml-0.5 font-bold leading-none hover:text-indigo-600"
                                >
                                    x
                                </button>
                            </span>
                        ))}
                </div>
            )}

            <div className="min-w-0 rounded-[22px] border border-slate-200 bg-white p-2 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
                <div className="grid min-w-0 grid-cols-1 gap-2">
                    <div className="relative w-full">
                        <svg
                            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                            />
                        </svg>
                        <input
                            type="text"
                            placeholder="Buscar por título, canonical_id u owner..."
                            className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50/80 pl-10 pr-4 text-sm text-slate-700 outline-none transition-colors placeholder:text-slate-400 focus:border-violet-300 focus:bg-white focus:ring-2 focus:ring-violet-100 dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-text)] dark:focus:ring-violet-500/20"
                            value={search}
                            onChange={(event) => onSearchChange(event.target.value)}
                        />
                    </div>
                    <div className="grid min-w-0 grid-cols-2 gap-2 sm:grid-cols-[auto_minmax(4.5rem,auto)_minmax(8rem,1fr)_auto_auto]">
                        {onToggleSelectAll ? (
                            <label className="flex h-11 min-w-0 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm font-semibold text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-text)]">
                                <input
                                    type="checkbox"
                                    className="ukip-selection-control"
                                    checked={Boolean(isAllSelected)}
                                    ref={(element) => {
                                        if (element) {
                                            element.indeterminate = Boolean(isPartiallySelected);
                                        }
                                    }}
                                    onChange={onToggleSelectAll}
                                    aria-label={t("page.entity_table.select_all")}
                                />
                                <span className="truncate">{selectedCount ? `${selectedCount} sel.` : `${(selectableCount ?? visibleCount ?? 0).toLocaleString()}`}</span>
                            </label>
                        ) : null}
                        <div className="flex h-11 min-w-0 items-center justify-center gap-2 rounded-xl px-2 font-mono text-xs font-semibold text-slate-500 dark:text-[var(--ukip-muted)]">
                            <span>{(visibleCount ?? 0).toLocaleString()}</span>
                            <span>/</span>
                            <span>{(totalCount ?? 0).toLocaleString()}</span>
                        </div>
                        <button
                            type="button"
                            onClick={onSortQuality}
                            className="col-span-2 h-11 min-w-0 rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm font-semibold text-slate-700 outline-none transition hover:bg-white focus:border-violet-300 focus:ring-2 focus:ring-violet-100 dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-text)] sm:col-span-1"
                        >
                            <span className="block truncate">{sortLabel ?? "↕ Recientes"}</span>
                        </button>
                        <select
                            value={minQuality}
                            onChange={(event) => onMinQualityChange(event.target.value)}
                            className="h-11 min-w-0 rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm text-slate-700 outline-none focus:border-violet-300 focus:ring-2 focus:ring-violet-100 dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-text)]"
                            title={t("page.entity_table.min_quality")}
                        >
                            <option value="">{t("common.all")}</option>
                            <option value="0.7">70%+</option>
                            <option value="0.3">30%+</option>
                            <option value="0.0">{t("page.entity_table.under_30")}</option>
                        </select>
                        <div className="flex h-11 min-w-[5.75rem] overflow-hidden rounded-xl border border-slate-200 bg-slate-50 p-1 dark:border-white/10 dark:bg-white/5">
                            <button
                                type="button"
                                onClick={() => onViewModeChange?.("grid")}
                                className={`flex h-full w-10 items-center justify-center rounded-lg transition ${viewMode === "grid" ? "bg-white text-violet-600 shadow-sm dark:bg-white/10 dark:text-violet-200" : "text-slate-500 hover:text-violet-600 dark:text-[var(--ukip-muted)]"}`}
                                aria-label="Grid view"
                                aria-pressed={viewMode === "grid"}
                            >
                                ⊞
                            </button>
                            <button
                                type="button"
                                onClick={() => onViewModeChange?.("list")}
                                className={`flex h-full w-10 items-center justify-center rounded-lg transition ${viewMode === "list" ? "bg-white text-violet-600 shadow-sm dark:bg-white/10 dark:text-violet-200" : "text-slate-500 hover:text-violet-600 dark:text-[var(--ukip-muted)]"}`}
                                aria-label="List view"
                                aria-pressed={viewMode === "list"}
                            >
                                ☰
                            </button>
                        </div>
                        <span className="sr-only">{t("common.page")} {page + 1}</span>
                    </div>
                </div>
            </div>
        </>
    );
}
