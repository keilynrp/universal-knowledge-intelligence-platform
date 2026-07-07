"use client";

import { useCallback, useEffect, useState } from "react";
import { useToast } from "../components/ui";
import { apiFetch } from "@/lib/api";
import type { DomainAttribute, DomainSchema } from "../contexts/DomainContext";
import type {
    AuthorAffiliationsResponse,
    AuthorCompareResponse,
    AutoConfirmResponse,
    GroupedRecord,
    GroupedRecordsResponse,
    InstitutionApplyResponse,
    InstitutionQueueResponse,
    AuthorMetrics,
    AuthorQueueResponse,
    AuthorQueueSummary,
    AuthorityRecord,
    QueueSummary,
} from "./reviewQueueTypes";

export default function useReviewQueueController(activeDomain: DomainSchema | null) {
    const { toast } = useToast();
    const [summary, setSummary] = useState<QueueSummary | null>(null);
    const [authorSummary, setAuthorSummary] = useState<AuthorQueueSummary | null>(null);
    const [authorMetrics, setAuthorMetrics] = useState<AuthorMetrics | null>(null);
    const [records, setRecords] = useState<AuthorityRecord[]>([]);
    const [loadingRecords, setLoadingRecords] = useState(false);
    const [selected, setSelected] = useState<Set<number>>(new Set());
    const [acting, setActing] = useState(false);
    const [rowActionId, setRowActionId] = useState<number | null>(null);
    const [queueMode, setQueueMode] = useState<"generic" | "authors" | "institutions">("generic");
    const [statusFilter, setStatusFilter] = useState("pending");
    const [fieldFilter, setFieldFilter] = useState("");
    const [authorRouteFilter, setAuthorRouteFilter] = useState("");
    const [authorReviewFilter, setAuthorReviewFilter] = useState("required");
    const [authorNilOnly, setAuthorNilOnly] = useState(false);
    const [batchField, setBatchField] = useState("");
    const [batchEntityType, setBatchEntityType] = useState("general");
    const [batchLimit, setBatchLimit] = useState(20);
    const [resolving, setResolving] = useState(false);
    const [resolveResult, setResolveResult] = useState<string | null>(null);
    const [expandedId, setExpandedId] = useState<number | null>(null);
    const [compareMap, setCompareMap] = useState<Record<number, AuthorCompareResponse>>({});
    const [affiliationMap, setAffiliationMap] = useState<Record<number, AuthorAffiliationsResponse>>({});
    const [loadingCompareId, setLoadingCompareId] = useState<number | null>(null);
    const [linkActionId, setLinkActionId] = useState<number | null>(null);
    // Review-at-scale (generic queue): grouped view + auto-confirm.
    const [groupedView, setGroupedView] = useState(false);
    const [groupedRecords, setGroupedRecords] = useState<GroupedRecord[]>([]);
    const [autoConfirmMinConfidence, setAutoConfirmMinConfidence] = useState(0.95);

    useEffect(() => {
        if (activeDomain && !batchField) {
            const firstStr = activeDomain.attributes.find((a: DomainAttribute) => a.type === "string");
            if (firstStr) setBatchField(firstStr.name);
        }
    }, [activeDomain, batchField]);

    const fetchSummary = useCallback(async () => {
        try {
            if (queueMode === "authors") {
                const [queueRes, metricsRes] = await Promise.all([
                    apiFetch("/authority/authors/review-queue"),
                    apiFetch("/authority/authors/metrics"),
                ]);
                if (queueRes.ok) {
                    const payload: AuthorQueueResponse = await queueRes.json();
                    setAuthorSummary(payload.summary);
                    setSummary(null);
                }
                if (metricsRes.ok) {
                    setAuthorMetrics(await metricsRes.json());
                }
            } else if (queueMode === "institutions") {
                setSummary(null);
                setAuthorSummary(null);
                setAuthorMetrics(null);
            } else {
                const res = await apiFetch("/authority/queue/summary");
                if (res.ok) {
                    setSummary(await res.json());
                    setAuthorSummary(null);
                    setAuthorMetrics(null);
                }
            }
        } catch {}
    }, [queueMode]);

    const fetchRecords = useCallback(async () => {
        setLoadingRecords(true);
        try {
            if (queueMode === "authors") {
                const params = new URLSearchParams({ status: statusFilter, limit: "100" });
                if (authorRouteFilter) params.set("route", authorRouteFilter);
                if (authorReviewFilter === "required") params.set("review_required", "true");
                if (authorReviewFilter === "not_required") params.set("review_required", "false");
                if (authorNilOnly) params.set("nil_only", "true");

                const res = await apiFetch(`/authority/authors/review-queue?${params.toString()}`);
                if (res.ok) {
                    const data: AuthorQueueResponse = await res.json();
                    setRecords(data.records ?? []);
                    setAuthorSummary(data.summary);
                    setSelected(new Set());
                }
            } else if (queueMode === "institutions") {
                const params = new URLSearchParams({ status: statusFilter, limit: "100" });
                const res = await apiFetch(`/authority/institutions/review-queue?${params.toString()}`);
                if (res.ok) {
                    const data: InstitutionQueueResponse = await res.json();
                    setRecords(data.records ?? []);
                    setSelected(new Set());
                }
            } else {
                const params = new URLSearchParams({ status: statusFilter, limit: "100" });
                if (fieldFilter) params.set("field_name", fieldFilter);
                const res = await apiFetch(`/authority/records?${params.toString()}`);
                if (res.ok) {
                    const data = await res.json();
                    setRecords(data.records ?? []);
                    setSelected(new Set());
                }
            }
        } catch {
        } finally {
            setLoadingRecords(false);
        }
    }, [statusFilter, fieldFilter, queueMode, authorRouteFilter, authorReviewFilter, authorNilOnly]);

    useEffect(() => {
        fetchSummary();
    }, [fetchSummary]);

    const fetchGrouped = useCallback(async () => {
        if (queueMode !== "generic" || !groupedView) return;
        setLoadingRecords(true);
        try {
            const params = new URLSearchParams({ status: statusFilter, limit: "200" });
            if (fieldFilter) params.set("field_name", fieldFilter);
            const res = await apiFetch(`/authority/records/grouped?${params.toString()}`);
            if (res.ok) {
                const data: GroupedRecordsResponse = await res.json();
                setGroupedRecords(data.groups ?? []);
            }
        } catch {
        } finally {
            setLoadingRecords(false);
        }
    }, [queueMode, groupedView, statusFilter, fieldFilter]);

    useEffect(() => {
        fetchRecords();
    }, [fetchRecords]);

    useEffect(() => {
        fetchGrouped();
    }, [fetchGrouped]);

    async function autoConfirm() {
        setActing(true);
        try {
            const params = new URLSearchParams({ min_confidence: String(autoConfirmMinConfidence) });
            if (fieldFilter) params.set("field_name", fieldFilter);
            const res = await apiFetch(`/authority/records/auto-confirm?${params.toString()}`, {
                method: "POST",
            });
            if (res.ok) {
                const data: AutoConfirmResponse = await res.json();
                toast(`Auto-confirmed ${data.confirmed}, rejected ${data.rejected}`, "success");
                await fetchSummary();
                await fetchRecords();
                await fetchGrouped();
            } else {
                const err = await res.json().catch(() => ({}));
                toast(`Auto-confirm failed: ${err.detail || res.statusText}`, "error");
            }
        } catch {
            toast("Auto-confirm failed", "error");
        } finally {
            setActing(false);
        }
    }

    function toggleSelect(id: number) {
        setSelected(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    }

    function toggleSelectAll() {
        if (selected.size === records.length) {
            setSelected(new Set());
        } else {
            setSelected(new Set(records.map(r => r.id)));
        }
    }

    async function bulkAction(action: "bulk-confirm" | "bulk-reject") {
        if (selected.size === 0) return;
        setActing(true);
        try {
            const path = queueMode === "institutions"
                ? action === "bulk-confirm"
                    ? "/authority/records/bulk-confirm"
                    : "/authority/records/bulk-reject"
                : `/authority/records/${action}`;
            const res = await apiFetch(path, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ids: Array.from(selected), also_create_rules: true }),
            });
            if (res.ok) {
                await fetchSummary();
                await fetchRecords();
            }
        } catch {
        } finally {
            setActing(false);
        }
    }

    async function batchResolve() {
        if (!batchField) return;
        setResolving(true);
        setResolveResult(null);
        try {
            const res = await apiFetch("/authority/resolve/batch", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    field_name: batchField,
                    entity_type: batchEntityType,
                    limit: batchLimit,
                }),
            });
            if (res.ok) {
                const data = await res.json();
                setResolveResult(
                    `Resolved ${data.resolved_count} values, created ${data.records_created} records` +
                    (data.already_existed_count ? `, ${data.already_existed_count} already existed` : "")
                );
                await fetchSummary();
                await fetchRecords();
            } else {
                const err = await res.json().catch(() => ({}));
                setResolveResult(`Error: ${err.detail || res.statusText}`);
            }
        } catch {
            setResolveResult("Network error");
        } finally {
            setResolving(false);
        }
    }

    async function reviewRecord(rec: AuthorityRecord, action: "confirm" | "reject") {
        setRowActionId(rec.id);
        try {
            const path = queueMode === "institutions"
                ? `/authority/institutions/review-queue/${rec.id}/${action === "confirm" ? "accept" : "reject"}`
                : `/authority/records/${rec.id}/${action}`;
            const res = await apiFetch(path, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: action === "confirm"
                    ? JSON.stringify({ also_create_rule: !rec.nil_reason })
                    : undefined,
            });
            if (!res.ok) {
                toast(`Failed to ${action} record`, "error");
                return;
            }
            toast(
                action === "confirm"
                    ? (queueMode === "institutions" ? "Institution confirmed" : rec.nil_reason ? "NIL case accepted" : "Author candidate confirmed")
                    : (queueMode === "institutions" ? "Institution rejected" : "Author candidate rejected"),
                "success"
            );
            await fetchSummary();
            await fetchRecords();
        } catch {
            toast(`Failed to ${action} record`, "error");
        } finally {
            setRowActionId(null);
        }
    }

    async function toggleExpanded(rec: AuthorityRecord) {
        const nextExpanded = expandedId === rec.id ? null : rec.id;
        setExpandedId(nextExpanded);
        if (queueMode !== "authors" || nextExpanded === null) {
            return;
        }

        if (compareMap[rec.id] && affiliationMap[rec.id]) {
            return;
        }

        setLoadingCompareId(rec.id);
        try {
            const [compareRes, affiliationsRes] = await Promise.all([
                compareMap[rec.id] ? null : apiFetch(`/authority/authors/review-queue/${rec.id}/compare`),
                affiliationMap[rec.id] ? null : apiFetch(`/authority/authors/review-queue/${rec.id}/affiliations`),
            ]);
            if (compareRes?.ok) {
                const payload: AuthorCompareResponse = await compareRes.json();
                setCompareMap(prev => ({ ...prev, [rec.id]: payload }));
            }
            if (affiliationsRes?.ok) {
                const payload: AuthorAffiliationsResponse = await affiliationsRes.json();
                setAffiliationMap(prev => ({ ...prev, [rec.id]: payload }));
            }
        } catch {
        } finally {
            setLoadingCompareId(current => (current === rec.id ? null : current));
        }
    }

    async function reviewAuthorityLink(linkId: number, action: "confirm" | "reject", authorRecordId: number) {
        setLinkActionId(linkId);
        try {
            const res = await apiFetch(`/authority/links/${linkId}/${action}`, { method: "POST" });
            if (!res.ok) {
                toast(`Failed to ${action} affiliation link`, "error");
                return;
            }
            const updated = await res.json();
            setAffiliationMap(prev => {
                const current = prev[authorRecordId];
                if (!current) return prev;
                return {
                    ...prev,
                    [authorRecordId]: {
                        ...current,
                        affiliations: current.affiliations.map(item =>
                            item.link.id === linkId ? { ...item, link: updated } : item
                        ),
                    },
                };
            });
            toast(action === "confirm" ? "Affiliation link confirmed" : "Affiliation link rejected", "success");
        } catch {
            toast(`Failed to ${action} affiliation link`, "error");
        } finally {
            setLinkActionId(null);
        }
    }

    async function applyInstitutionReconciliation() {
        setResolving(true);
        setResolveResult(null);
        try {
            const res = await apiFetch("/authority/institutions/reconcile/apply", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    domain_id: activeDomain?.id ?? undefined,
                    limit: batchLimit,
                    live_lookup: true,
                }),
            });
            if (res.ok) {
                const data: InstitutionApplyResponse = await res.json();
                setResolveResult(
                    `Reviewed ${data.preview_count} affiliations, created ${data.created}, reused ${data.reused}, linked ${data.links_created}`
                );
                await fetchSummary();
                await fetchRecords();
            } else {
                const err = await res.json().catch(() => ({}));
                setResolveResult(`Error: ${err.detail || res.statusText}`);
            }
        } catch {
            setResolveResult("Network error");
        } finally {
            setResolving(false);
        }
    }

    return {
        summary,
        authorSummary,
        authorMetrics,
        records,
        loadingRecords,
        selected,
        acting,
        rowActionId,
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
        expandedId,
        compareMap,
        affiliationMap,
        loadingCompareId,
        linkActionId,
        groupedView,
        groupedRecords,
        autoConfirmMinConfidence,
        setGroupedView,
        setAutoConfirmMinConfidence,
        autoConfirm,
        setQueueMode,
        setStatusFilter,
        setFieldFilter,
        setAuthorRouteFilter,
        setAuthorReviewFilter,
        setAuthorNilOnly,
        setBatchField,
        setBatchEntityType,
        setBatchLimit,
        toggleSelect,
        toggleSelectAll,
        bulkAction,
        batchResolve,
        applyInstitutionReconciliation,
        reviewRecord,
        toggleExpanded,
        reviewAuthorityLink,
    };
}
