"use client";

import { useRef } from "react";
import { useDomain } from "../contexts/DomainContext";
import { useLanguage } from "../contexts/LanguageContext";
import { useToast } from "./ui";
import FacetPanel from "./FacetPanel";
import EntityTablePagination from "./EntityTablePagination";
import EntityTableBulkActions from "./EntityTableBulkActions";
import EntityTableToolbar from "./EntityTableToolbar";
import EntityTableContent from "./EntityTableContent";
import EntityTableDetailsModal from "./EntityTableDetailsModal";
import { useEntityTableController } from "./useEntityTableController";
import { useEntityTableVirtualization } from "./useEntityTableVirtualization";

export default function EntityTable() {
    const { activeDomain } = useDomain();
    const { t } = useLanguage();
    const { toast } = useToast();
    const {
        entities,
        totalCount,
        loading,
        search,
        setSearch,
        page,
        setPage,
        selectedEntity,
        setSelectedEntity,
        limit,
        setLimit,
        editingId,
        editData,
        setEditData,
        saving,
        enrichingId,
        minQuality,
        setMinQuality,
        sortBy,
        setSortBy,
        sortOrder,
        setSortOrder,
        deletingId,
        selectedIds,
        setSelectedIds,
        bulkDeleting,
        bulkEnriching,
        fetchError,
        activeFacets,
        portalByBatchId,
        handleFacetChange,
        fetchEntities,
        startEdit,
        cancelEdit,
        saveEdit,
        deleteEntity,
        enrichEntity,
        toggleSelect,
        toggleSelectAll,
        handleBulkDelete,
        handleBulkEnrich,
        handleBulkExport,
        scrollTop,
        setScrollTop,
    } = useEntityTableController({ toast });
    const scrollContainerRef = useRef<HTMLDivElement>(null);

    const { shouldVirtualize, visibleEntities, paddingTop, paddingBottom, viewportHeight } = useEntityTableVirtualization({
        entities,
        editingId,
        scrollTop,
    });
    const enrichedCount = entities.filter((entity) => entity.enrichment_status === "completed").length;
    const verifiedCount = entities.filter((entity) => entity.validation_status === "valid").length;
    const avgQuality = entities.length
        ? entities.reduce((sum, entity) => sum + (entity.quality_score ?? 0), 0) / entities.length
        : 0;
    const verifiedPercent = entities.length ? Math.round((verifiedCount / entities.length) * 100) : 0;
    const pipelineStages = [
        { label: "Ingesta", group: "Knowledge", active: true },
        { label: "Autoridad", group: "Knowledge", active: verifiedCount > 0 },
        { label: "Enriquecimiento", group: "Knowledge", active: enrichedCount > 0 },
        { label: "Grafo", group: "Intelligence", active: enrichedCount > 0 },
        { label: "Analisis", group: "Intelligence", active: avgQuality > 0.3 },
        { label: "Respuestas", group: "Intelligence", active: avgQuality > 0.5 },
        { label: "Entrega", group: "Delivery", active: verifiedPercent > 25 },
    ];

    return (
        <div className="rounded-[28px] bg-slate-100/70 p-5 dark:bg-black/10">
            <div className="space-y-6">
                <section className="border-b border-slate-200 pb-6 dark:border-white/10">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                        <div>
                            <div className="flex flex-wrap items-center gap-2">
                                <span className="rounded-full bg-violet-50 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-violet-700 dark:bg-violet-500/10 dark:text-violet-200">
                                    In Knowledge
                                </span>
                                <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">/ Ingesta</span>
                            </div>
                            <h2 className="mt-4 text-3xl font-bold tracking-[-0.05em] text-slate-950 dark:text-[var(--ukip-text-strong)]">
                                Catálogo de Entidades
                            </h2>
                            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600 dark:text-[var(--ukip-muted)]">
                                Browse universal con facetas dinamicas y cards densos. Esquema: primary_label, canonical_id, entity_type, domain, authority_tier.
                            </p>
                            <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-[var(--ukip-muted)]">
                                <span className="rounded-full bg-white px-3 py-1 shadow-sm dark:bg-white/10">Etapa 01 / 07</span>
                                <span className="rounded-full bg-white px-3 py-1 shadow-sm dark:bg-white/10">Entidades {totalCount.toLocaleString()}</span>
                                <span className="rounded-full bg-white px-3 py-1 shadow-sm dark:bg-white/10">Ultima importacion hace 2h</span>
                            </div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <button className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-white/10 dark:bg-[var(--ukip-panel)] dark:text-[var(--ukip-text)]">
                                Sembrar demo
                            </button>
                            <a href="/import-export" className="rounded-xl bg-violet-600 px-4 py-2 text-sm font-bold text-white shadow-sm shadow-violet-500/20 transition hover:bg-violet-700">
                                Nuevo wizard
                            </a>
                        </div>
                    </div>
                </section>

                <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
                    <div className="flex items-center justify-between gap-3">
                        <p className="ukip-kicker">Pipeline UKIP</p>
                        <span className="text-xs text-slate-500 dark:text-[var(--ukip-muted)]">raw → answer</span>
                    </div>
                    <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
                        {pipelineStages.map((stage, index) => (
                            <div key={stage.label} className="rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-white/10 dark:bg-white/5">
                                <div className="flex items-center justify-between text-[11px] font-bold text-slate-500 dark:text-[var(--ukip-muted)]">
                                    <span className="flex items-center gap-2">
                                        <span className={`h-2 w-2 rounded-full ${stage.active ? "bg-violet-500" : "bg-slate-300"}`} />
                                        {String(index + 1).padStart(2, "0")}
                                    </span>
                                    <span>◎</span>
                                </div>
                                <p className="mt-3 text-sm font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">{stage.label}</p>
                                <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500 dark:text-[var(--ukip-muted)]">{stage.group}</p>
                            </div>
                        ))}
                    </div>
                </section>

                <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    {[
                        { label: "Total entidades", value: totalCount.toLocaleString(), delta: "+12 todas las fuentes", tone: "violet" },
                        { label: "Tasa de duplicados", value: "3.4%", delta: "-0.8pp fuzzy matching", tone: "amber" },
                        { label: "Authority media", value: avgQuality ? avgQuality.toFixed(2) : "0.00", delta: "+0.03 score 0-1.0", tone: "emerald" },
                        { label: "Verificadas", value: `${verifiedPercent}%`, delta: "+6pp ratio sobre total", tone: "sky" },
                    ].map((metric) => (
                        <div key={metric.label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
                            <div className="flex items-start justify-between">
                                <p className="text-sm font-semibold text-slate-500 dark:text-[var(--ukip-muted)]">{metric.label}</p>
                                <span className={`h-8 w-8 rounded-full ${metric.tone === "violet" ? "bg-violet-100 text-violet-700" : metric.tone === "amber" ? "bg-amber-100 text-amber-700" : metric.tone === "emerald" ? "bg-emerald-100 text-emerald-700" : "bg-sky-100 text-sky-700"} flex items-center justify-center text-xs font-bold`}>
                                    ●
                                </span>
                            </div>
                            <p className="mt-4 font-mono text-4xl font-bold tracking-[-0.06em] text-slate-950 dark:text-[var(--ukip-text-strong)]">{metric.value}</p>
                            <p className="mt-2 text-xs font-semibold text-emerald-600">{metric.delta}</p>
                        </div>
                    ))}
                </section>

                <div className="grid items-start gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
                    <FacetPanel
                        activeFacets={activeFacets}
                        onFacetChange={handleFacetChange}
                        search={search}
                        minQuality={minQuality}
                        totalCount={totalCount}
                        visibleCount={entities.length}
                    />
                    <div className="min-w-0 space-y-4">
                        <EntityTableToolbar
                            activeFacets={activeFacets}
                            search={search}
                            minQuality={minQuality}
                            page={page}
                            totalCount={totalCount}
                            visibleCount={entities.length}
                            selectedCount={selectedIds.size}
                            selectableCount={entities.length}
                            isAllSelected={entities.length > 0 && selectedIds.size === entities.length}
                            isPartiallySelected={selectedIds.size > 0 && selectedIds.size < entities.length}
                            sortLabel={`${t("entities.quality")} ${sortBy === "quality_score" ? (sortOrder === "desc" ? "↓" : "↑") : "↕"}`}
                            onToggleSelectAll={toggleSelectAll}
                            onSortQuality={() => {
                                if (sortBy === "quality_score") {
                                    setSortOrder((currentOrder) => (currentOrder === "asc" ? "desc" : "asc"));
                                } else {
                                    setSortBy("quality_score");
                                    setSortOrder("desc");
                                }
                                setPage(0);
                            }}
                            onSearchChange={setSearch}
                            onMinQualityChange={(value) => {
                                setMinQuality(value);
                                setPage(0);
                            }}
                            onClearFacet={(field) => handleFacetChange(field, null)}
                        />

                        <EntityTableContent
                            activeDomain={activeDomain}
                            entities={entities}
                            visibleEntities={visibleEntities}
                            loading={loading}
                            limit={limit}
                            fetchError={fetchError}
                            shouldVirtualize={shouldVirtualize}
                            viewportHeight={viewportHeight}
                            paddingTop={paddingTop}
                            paddingBottom={paddingBottom}
                            selectedIds={selectedIds}
                            editingId={editingId}
                            editData={editData}
                            saving={saving}
                            deletingId={deletingId}
                            enrichingId={enrichingId}
                            portalByBatchId={portalByBatchId}
                            sortBy={sortBy}
                            sortOrder={sortOrder}
                            scrollContainerRef={scrollContainerRef}
                            onScrollTopChange={setScrollTop}
                            onToggleSelectAll={toggleSelectAll}
                            onToggleSelect={toggleSelect}
                            onSortQuality={() => {
                                if (sortBy === "quality_score") {
                                    setSortOrder((currentOrder) => (currentOrder === "asc" ? "desc" : "asc"));
                                } else {
                                    setSortBy("quality_score");
                                    setSortOrder("desc");
                                }
                                setPage(0);
                            }}
                            onRetry={fetchEntities}
                            onStartEdit={startEdit}
                            onCancelEdit={cancelEdit}
                            onSaveEdit={saveEdit}
                            onEditDataChange={setEditData}
                            onSelectEntity={setSelectedEntity}
                            onDeleteEntity={(entity) => {
                                if (confirm(t("page.entity_table.delete_single_confirm", {
                                    id: entity.id,
                                    label: entity.primary_label ?? t("page.entity_table.unnamed_entity"),
                                }))) {
                                    deleteEntity(entity.id);
                                }
                            }}
                            onEnrichEntity={enrichEntity}
                        />
                    </div>

                    <div className="lg:col-start-2">
                        <EntityTablePagination
                            totalCount={totalCount}
                            limit={limit}
                            page={page}
                            loading={loading}
                            onLimitChange={setLimit}
                            onPageChange={setPage}
                        />
                    </div>

                    <div className="lg:col-start-2">
                        <EntityTableBulkActions
                            selectedCount={selectedIds.size}
                            pageSelectionOnly
                            bulkEnriching={bulkEnriching}
                            bulkDeleting={bulkDeleting}
                            onBulkEnrich={handleBulkEnrich}
                            onBulkExport={handleBulkExport}
                            onBulkDelete={handleBulkDelete}
                            onClearSelection={() => setSelectedIds(new Set())}
                        />
                    </div>
                </div>

                <EntityTableDetailsModal
                    entity={selectedEntity}
                    activeDomain={activeDomain}
                    onClose={() => setSelectedEntity(null)}
                />
            </div>
        </div>
    );
}
