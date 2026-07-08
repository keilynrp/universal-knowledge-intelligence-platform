"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useLanguage } from "../contexts/LanguageContext";
import { useEnrichment } from "../contexts/EnrichmentContext";
import type { ActiveFacets } from "./FacetPanel";
import type { EditableFields, Entity } from "./EntityTable.types";
import type { ToastVariant } from "./ui";
import type { EnrichmentBatchState } from "./EnrichmentProgressToast";
import { apiFetch } from "@/lib/api";
import { qualityFilterParams } from "@/lib/qualityFilter";

interface UseEntityTableControllerOptions {
    toast: (message: string, variant?: ToastVariant) => void;
    activeDomainId?: string;
}

interface CatalogPortalSummary {
    slug: string;
    source_batch_id: number | null;
}

export function useEntityTableController({ toast, activeDomainId = "all" }: UseEntityTableControllerOptions) {
    const { t } = useLanguage();
    const { startPolling: startEnrichmentStatsPolling } = useEnrichment();
    const searchParams = useSearchParams();
    const readFacetParams = useCallback((): ActiveFacets => ({
        entity_type: searchParams.get("ft_entity_type"),
        work_type: searchParams.get("ft_work_type"),
        domain: searchParams.get("ft_domain"),
        validation_status: searchParams.get("ft_validation_status"),
        enrichment_status: searchParams.get("ft_enrichment_status"),
        source: searchParams.get("ft_source"),
        journal_metric_signal: searchParams.get("ft_journal_metric_signal"),
    }), [searchParams]);
    const [entities, setEntities] = useState<Entity[]>([]);
    const [totalCount, setTotalCount] = useState(0);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState(searchParams.get("q") ?? "");
    const [debouncedSearch, setDebouncedSearch] = useState(searchParams.get("q") ?? "");
    const [conceptFilter, setConceptFilter] = useState(searchParams.get("concept") ?? "");
    const [page, setPage] = useState(0);
    const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
    const [limit, setLimit] = useState(20);
    const [editingId, setEditingId] = useState<number | null>(null);
    const [editData, setEditData] = useState<EditableFields>({
        primary_label: "",
        secondary_label: "",
        canonical_id: "",
        entity_type: "",
        domain: "",
        validation_status: "",
    });
    const [saving, setSaving] = useState(false);
    const [enrichingId, setEnrichingId] = useState<number | null>(null);
    const [minQuality, setMinQuality] = useState<string>(searchParams.get("min_quality") ?? "");
    const [sortBy, setSortBy] = useState<string>("id");
    const [sortOrder, setSortOrder] = useState<string>("asc");
    const [deletingId, setDeletingId] = useState<number | null>(null);
    const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
    const [bulkDeleting, setBulkDeleting] = useState(false);
    const [bulkEnriching, setBulkEnriching] = useState(false);
    const [enrichmentBatch, setEnrichmentBatch] = useState<EnrichmentBatchState | null>(null);
    const [fetchError, setFetchError] = useState<string | null>(null);
    const [activeFacets, setActiveFacets] = useState<ActiveFacets>(readFacetParams);
    const [facetRefreshKey, setFacetRefreshKey] = useState(0);
    const [scrollTop, setScrollTop] = useState(0);
    const [portalByBatchId, setPortalByBatchId] = useState<Record<number, string>>({});
    const enrichmentPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const paramSignature = searchParams.toString();

    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedSearch(search);
            setPage(0);
        }, 500);

        return () => clearTimeout(handler);
    }, [search]);

    useEffect(() => {
        const nextSearch = searchParams.get("q") ?? "";
        const nextMinQuality = searchParams.get("min_quality") ?? "";
        const nextConcept = searchParams.get("concept") ?? "";
        setSearch(nextSearch);
        setDebouncedSearch(nextSearch);
        setMinQuality(nextMinQuality);
        setConceptFilter(nextConcept);
        setActiveFacets(readFacetParams());
        setPage(0);
    }, [paramSignature, readFacetParams, searchParams]);

    const fetchEntities = useCallback(async () => {
        setLoading(true);
        setSelectedIds(new Set());
        setFetchError(null);

        try {
            const queryParams = new URLSearchParams({
                skip: (page * limit).toString(),
                limit: limit.toString(),
                sort_by: sortBy,
                order: sortOrder,
            });

            if (debouncedSearch) queryParams.append("search", debouncedSearch);
            const qualityParams = qualityFilterParams(minQuality);
            if (qualityParams.min_quality) queryParams.append("min_quality", qualityParams.min_quality);
            if (qualityParams.max_quality) queryParams.append("max_quality", qualityParams.max_quality);
            if (conceptFilter) queryParams.append("concept", conceptFilter);
            if (activeFacets.entity_type) queryParams.append("ft_entity_type", activeFacets.entity_type);
            if (activeFacets.work_type) queryParams.append("ft_work_type", activeFacets.work_type);
            const effectiveDomain = activeFacets.domain || (activeDomainId !== "all" ? activeDomainId : null);
            if (effectiveDomain) queryParams.append("ft_domain", effectiveDomain);
            if (activeFacets.validation_status) queryParams.append("ft_validation_status", activeFacets.validation_status);
            if (activeFacets.enrichment_status) queryParams.append("ft_enrichment_status", activeFacets.enrichment_status);
            if (activeFacets.source) queryParams.append("ft_source", activeFacets.source);
            if (activeFacets.journal_metric_signal) queryParams.append("ft_journal_metric_signal", activeFacets.journal_metric_signal);

            const res = await apiFetch(`/entities?${queryParams}`);
            if (!res.ok) throw new Error(`Server responded with ${res.status}`);
            const headerTotal = Number(res.headers.get("X-Total-Count") ?? "0");
            setTotalCount(Number.isFinite(headerTotal) ? headerTotal : 0);
            setEntities(await res.json());
        } catch (error) {
            const message = error instanceof Error ? error.message : t("page.entity_table.unknown_error");
            setFetchError(message);
        } finally {
            setLoading(false);
        }
    }, [activeDomainId, activeFacets, conceptFilter, debouncedSearch, limit, minQuality, page, sortBy, sortOrder, t]);

    useEffect(() => {
        fetchEntities();
    }, [fetchEntities]);

    const fetchCatalogPortals = useCallback(async () => {
        try {
            const res = await apiFetch("/catalogs");
            if (!res.ok) throw new Error("Unable to load catalog portals");
            const portals = await res.json() as CatalogPortalSummary[];
            const nextMap: Record<number, string> = {};
            portals.forEach((portal) => {
                if (portal.source_batch_id && !nextMap[portal.source_batch_id]) {
                    nextMap[portal.source_batch_id] = portal.slug;
                }
            });
            setPortalByBatchId(nextMap);
        } catch {
            setPortalByBatchId({});
        }
    }, []);

    useEffect(() => {
        fetchCatalogPortals();
    }, [fetchCatalogPortals]);

    useEffect(() => {
        return () => {
            if (enrichmentPollRef.current) {
                clearInterval(enrichmentPollRef.current);
            }
        };
    }, []);

    function handleFacetChange(field: string, value: string | null) {
        setActiveFacets((prev) => ({ ...prev, [field]: value }));
        setPage(0);
    }

    function refreshFacets() {
        setFacetRefreshKey((current) => current + 1);
    }

    function startEdit(entity: Entity) {
        setEditingId(entity.id);
        setEditData({
            primary_label: entity.primary_label || "",
            secondary_label: entity.secondary_label || "",
            canonical_id: entity.canonical_id || "",
            entity_type: entity.entity_type || "",
            domain: entity.domain || "",
            validation_status: entity.validation_status || "pending",
        });
    }

    function cancelEdit() {
        setEditingId(null);
    }

    async function saveEdit() {
        if (!editingId) return;
        setSaving(true);

        try {
            const res = await apiFetch(`/entities/${editingId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(editData),
            });
            if (!res.ok) throw new Error(t("page.entity_table.update_failed"));
            const updated = await res.json();
            setEntities((prev) => prev.map((entity) => (entity.id === editingId ? updated : entity)));
            setEditingId(null);
            refreshFacets();
        } catch {
            toast(t("page.entity_table.update_error"), "error");
        } finally {
            setSaving(false);
        }
    }

    async function deleteEntity(id: number) {
        setDeletingId(id);
        try {
            const res = await apiFetch(`/entities/${id}`, { method: "DELETE" });
            if (!res.ok) throw new Error(t("page.entity_table.delete_failed"));
            setEntities((prev) => prev.filter((entity) => entity.id !== id));
            setTotalCount((prev) => Math.max(0, prev - 1));
            refreshFacets();
            toast(t("page.entity_table.delete_success"), "success");
        } catch {
            toast(t("page.entity_table.delete_error"), "error");
        } finally {
            setDeletingId(null);
        }
    }

    async function enrichEntity(id: number) {
        setEnrichingId(id);
        try {
            const res = await apiFetch(`/enrich/row/${id}`, { method: "POST" });
            if (!res.ok) throw new Error(t("page.entity_table.enrich_failed"));
            const enriched = await res.json();
            setEntities((prev) => prev.map((entity) => (entity.id === id ? { ...entity, ...enriched } : entity)));
            refreshFacets();
            toast(t("page.entity_table.enrich_success"), "success");
        } catch {
            toast(t("page.entity_table.enrich_error"), "error");
        } finally {
            setEnrichingId(null);
        }
    }

    function toggleSelect(id: number) {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    }

    function toggleSelectAll() {
        if (selectedIds.size === entities.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(entities.map((entity) => entity.id)));
        }
    }

    async function handleBulkDelete() {
        if (!confirm(t("page.entity_table.bulk_delete_confirm_page", { count: selectedIds.size }))) return;
        setBulkDeleting(true);
        try {
            const res = await apiFetch("/entities/bulk", {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ids: Array.from(selectedIds) }),
            });
            if (!res.ok) throw new Error(t("page.entity_table.bulk_delete_failed"));
            const data = await res.json();
            setEntities((prev) => prev.filter((entity) => !selectedIds.has(entity.id)));
            setTotalCount((prev) => Math.max(0, prev - data.deleted));
            setSelectedIds(new Set());
            refreshFacets();
            toast(t("page.entity_table.bulk_delete_success", { count: data.deleted }), "success");
        } catch {
            toast(t("page.entity_table.bulk_delete_failed"), "error");
        } finally {
            setBulkDeleting(false);
        }
    }

    function startRowPolling() {
        if (enrichmentPollRef.current) return; // already polling
        enrichmentPollRef.current = setInterval(async () => {
            await fetchEntities();
            // Stop row polling when no entity on the current page is still active
            setEntities((current) => {
                const stillActive = current.some(
                    (e) => e.enrichment_status === "pending" || e.enrichment_status === "processing",
                );
                if (!stillActive && enrichmentPollRef.current) {
                    clearInterval(enrichmentPollRef.current);
                    enrichmentPollRef.current = null;
                    refreshFacets();
                }
                return current;
            });
        }, 5000);
    }

    async function handleBulkEnrich() {
        setBulkEnriching(true);
        const batchIds = Array.from(selectedIds);
        try {
            const res = await apiFetch("/enrich/bulk-ids", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ids: batchIds }),
            });
            if (!res.ok) throw new Error(t("page.entity_table.bulk_enrich_failed"));
            const data = await res.json();
            setSelectedIds(new Set());
            if (data.queued > 0) {
                // Start progress tracking via EnrichmentProgressToast
                const queuedIds = batchIds.slice(0, data.queued + data.skipped);
                setEnrichmentBatch({ ids: queuedIds, skipped: data.skipped });
            } else if (data.skipped > 0) {
                toast(t("page.entity_table.enrichment_all_skipped", { count: data.skipped }), "info");
            }
            // Refresh entity rows immediately, then poll rows + global stats
            await fetchEntities();
            startRowPolling();
            startEnrichmentStatsPolling();
        } catch {
            toast(t("page.entity_table.bulk_enrich_failed"), "error");
        } finally {
            setBulkEnriching(false);
        }
    }

    function handleEnrichmentBatchComplete() {
        setEnrichmentBatch(null);
        fetchEntities();
    }

    function handleBulkExport() {
        const selected = entities.filter((entity) => selectedIds.has(entity.id));
        const headers: Array<
            "id" |
            "primary_label" |
            "secondary_label" |
            "canonical_id" |
            "entity_type" |
            "domain" |
            "validation_status" |
            "enrichment_status" |
            "source"
        > = [
            "id",
            "primary_label",
            "secondary_label",
            "canonical_id",
            "entity_type",
            "domain",
            "validation_status",
            "enrichment_status",
            "source",
        ];
        const rows = selected.map((entity) =>
            headers
                .map((header) => {
                    const value = entity[header];
                    return value == null ? "" : `"${String(value).replace(/"/g, '""')}"`;
                })
                .join(","),
        );
        const csv = [headers.join(","), ...rows].join("\n");
        const blob = new Blob([csv], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `entities_selection_${selected.length}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        toast(t("page.entity_table.bulk_export_success", { count: selected.length }), "success");
    }

    return {
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
        facetRefreshKey,
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
        enrichmentBatch,
        handleEnrichmentBatchComplete,
        scrollTop,
        setScrollTop,
        portalByBatchId,
    };
}
