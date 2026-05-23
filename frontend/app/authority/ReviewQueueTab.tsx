"use client";

import type { DomainSchema } from "../contexts/DomainContext";
import ReviewQueueControls from "./ReviewQueueControls";
import ReviewQueueRecordsTable from "./ReviewQueueRecordsTable";
import ReviewQueueSummaryPanels from "./ReviewQueueSummaryPanels";
import useReviewQueueController from "./useReviewQueueController";

export default function ReviewQueueTab({ activeDomain }: { activeDomain: DomainSchema | null }) {
    const controller = useReviewQueueController(activeDomain);

    return (
        <div className="space-y-6">
            <ReviewQueueControls
                activeDomain={activeDomain}
                queueMode={controller.queueMode}
                statusFilter={controller.statusFilter}
                fieldFilter={controller.fieldFilter}
                authorRouteFilter={controller.authorRouteFilter}
                authorReviewFilter={controller.authorReviewFilter}
                authorNilOnly={controller.authorNilOnly}
                batchField={controller.batchField}
                batchEntityType={controller.batchEntityType}
                batchLimit={controller.batchLimit}
                resolving={controller.resolving}
                resolveResult={controller.resolveResult}
                acting={controller.acting}
                selectedCount={controller.selected.size}
                summary={controller.summary}
                onQueueModeChange={controller.setQueueMode}
                onStatusFilterChange={controller.setStatusFilter}
                onFieldFilterChange={controller.setFieldFilter}
                onAuthorRouteFilterChange={controller.setAuthorRouteFilter}
                onAuthorReviewFilterChange={controller.setAuthorReviewFilter}
                onAuthorNilOnlyChange={controller.setAuthorNilOnly}
                onBatchFieldChange={controller.setBatchField}
                onBatchEntityTypeChange={controller.setBatchEntityType}
                onBatchLimitChange={controller.setBatchLimit}
                onBatchResolve={controller.batchResolve}
                onApplyInstitutionReconciliation={controller.applyInstitutionReconciliation}
                onBulkAction={controller.bulkAction}
            />

            <ReviewQueueSummaryPanels
                queueMode={controller.queueMode}
                summary={controller.summary}
                authorSummary={controller.authorSummary}
                authorMetrics={controller.authorMetrics}
            />

            <div className="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <ReviewQueueRecordsTable
                    queueMode={controller.queueMode}
                    statusFilter={controller.statusFilter}
                    loadingRecords={controller.loadingRecords}
                    records={controller.records}
                    selected={controller.selected}
                    rowActionId={controller.rowActionId}
                    expandedId={controller.expandedId}
                    loadingCompareId={controller.loadingCompareId}
                    linkActionId={controller.linkActionId}
                    compareMap={controller.compareMap}
                    affiliationMap={controller.affiliationMap}
                    onToggleSelectAll={controller.toggleSelectAll}
                    onToggleSelect={controller.toggleSelect}
                    onReviewRecord={controller.reviewRecord}
                    onReviewAuthorityLink={controller.reviewAuthorityLink}
                    onToggleExpanded={controller.toggleExpanded}
                />
            </div>
        </div>
    );
}
