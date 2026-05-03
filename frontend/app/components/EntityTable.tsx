"use client";

import { useRef, useState } from "react";
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
    const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

    const { shouldVirtualize, visibleEntities, paddingTop, paddingBottom, viewportHeight } = useEntityTableVirtualization({
        entities,
        editingId,
        scrollTop,
    });
    return (
        <div className="rounded-[28px] bg-slate-100/70 p-5 dark:bg-black/10">
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
                            viewMode={viewMode}
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
                            onViewModeChange={setViewMode}
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
                            viewMode={viewMode}
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
    );
}
