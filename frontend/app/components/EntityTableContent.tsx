"use client";

import type React from "react";
import { useState } from "react";
import Link from "next/link";
import { useLanguage } from "../contexts/LanguageContext";
import { Badge, ErrorBanner, QualityBadge } from "./ui";
import RecordResultCard from "./RecordResultCard";
import RecordListRow from "./RecordListRow";
import { EnrichmentFailureIcon, EnrichmentFailureDetails, parseEnrichmentFailure } from "./EnrichmentFailurePanel";
import type { EntityTableDomain, EditableFields, Entity } from "./EntityTable.types";
import { categoryFor } from "@/app/lib/workType";

function parseNormalizedJson(normalizedJson: string | null): Record<string, unknown> {
    if (!normalizedJson) return {};

    try {
        return JSON.parse(normalizedJson) as Record<string, unknown>;
    } catch {
        return {};
    }
}

function resolveAttributeValue(
    entity: Entity,
    parsedJson: Record<string, unknown>,
    attributeName: string,
    isCore: boolean,
): unknown {
    if (!isCore) {
        return parsedJson[attributeName] ?? "";
    }

    const directValue = entity[attributeName as keyof Entity];
    if (directValue !== undefined && directValue !== null && directValue !== "") {
        return directValue;
    }

    switch (attributeName) {
        case "title":
            return entity.primary_label ?? parsedJson.title ?? "";
        case "authors":
            return parsedJson.authors ?? entity.secondary_label ?? "";
        case "doi":
            return entity.canonical_id ?? parsedJson.doi ?? "";
        case "journal":
            return parsedJson.journal ?? parsedJson.venue ?? "";
        case "year":
            return parsedJson.year ?? "";
        case "citations":
            return entity.enrichment_citation_count ?? parsedJson.citation_count ?? "";
        default:
            return parsedJson[attributeName] ?? "";
    }
}

function renderDisplayValue(attributeName: string, value: unknown, emptyLabel: string) {
    if (value === null || value === "") {
        return <span className="text-gray-400">{emptyLabel}</span>;
    }

    if (attributeName === "canonical_id" || attributeName === "doi") {
        return (
            <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700 break-all dark:bg-gray-800 dark:text-gray-300">
                {String(value)}
            </code>
        );
    }

    return String(value);
}

function renderLocalizedValue(
    attributeName: string,
    value: unknown,
    emptyLabel: string,
    t: (key: string, params?: Record<string, string | number>) => string,
) {
    if (attributeName === "validation_status" && typeof value === "string" && value) {
        const statusKey = `page.entity_table.status_${value}`;
        const translated = t(statusKey);
        return translated === statusKey ? value : translated;
    }

    if (attributeName === "enrichment_status" && typeof value === "string" && value) {
        const enrichmentKeyMap: Record<string, string> = {
            completed: "entities.filter.enriched",
            pending: "entities.filter.pending",
            processing: "page.entity_table.status_processing",
            failed: "entities.filter.failed",
            none: "page.entity_table.status_not_started",
        };
        const translationKey = enrichmentKeyMap[value];
        if (!translationKey) return value;
        const translated = t(translationKey);
        return translated === translationKey ? value : translated;
    }

    return renderDisplayValue(attributeName, value, emptyLabel);
}

function EntityTitleLink({ entityId, title }: { entityId: number; title: string }) {
    return (
        <Link
            href={`/entities/${entityId}`}
            onClick={(event) => event.stopPropagation()}
            className="rounded-md px-0.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-slate-950 [@media(hover:hover)_and_(pointer:fine)]:hover:bg-violet-50 [@media(hover:hover)_and_(pointer:fine)]:hover:text-violet-700 dark:[@media(hover:hover)_and_(pointer:fine)]:hover:bg-violet-500/10 dark:[@media(hover:hover)_and_(pointer:fine)]:hover:text-violet-300"
        >
            {title}
        </Link>
    );
}

const CORE_ATTRIBUTE_LABEL_KEYS: Record<string, string> = {
    primary_label: "entities.primary_label",
    secondary_label: "page.import.field.secondary_label",
    canonical_id: "page.import.field.canonical_id",
    entity_type: "page.import.field.entity_type",
    domain: "page.import.field.domain",
    validation_status: "page.entity_table.review_status",
};

function enrichmentBadgeMeta(
    status: string | null,
    t: (key: string, params?: Record<string, string | number>) => string,
): { label: string; variant: "success" | "warning" | "error" | "default"; pulse: boolean } {
    switch (status) {
        case "completed":
            return { label: t("entities.filter.enriched"), variant: "success", pulse: false };
        case "pending":
            return { label: t("entities.filter.pending"), variant: "warning", pulse: true };
        case "processing":
            return { label: t("page.entity_table.status_processing"), variant: "warning", pulse: true };
        case "failed":
            return { label: t("entities.filter.failed"), variant: "error", pulse: false };
        case "none":
        case null:
        default:
            return { label: t("page.entity_table.status_not_started"), variant: "default", pulse: false };
    }
}

function recordStatusTone(
    validationStatus: string | null,
    enrichmentStatus: string | null,
): "verified" | "review" | "rejected" | "pending" | "enriched" | "default" {
    if (validationStatus === "invalid") return "rejected";
    if (validationStatus === "valid") return "verified";
    if (enrichmentStatus === "completed") return "enriched";
    if (enrichmentStatus === "processing" || validationStatus === "pending") return "review";
    if (enrichmentStatus === "pending" || enrichmentStatus === "none") return "pending";
    return "default";
}

export interface EntityTableContentProps {
    activeDomain: EntityTableDomain;
    entities: Entity[];
    visibleEntities: Entity[];
    loading: boolean;
    limit: number;
    fetchError: string | null;
    shouldVirtualize: boolean;
    viewportHeight: number;
    paddingTop: number;
    paddingBottom: number;
    selectedIds: Set<number>;
    editingId: number | null;
    editData: EditableFields;
    saving: boolean;
    deletingId: number | null;
    enrichingId: number | null;
    portalByBatchId: Record<number, string>;
    viewMode?: "grid" | "list";
    sortBy: string;
    sortOrder: string;
    scrollContainerRef: React.RefObject<HTMLDivElement | null>;
    onScrollTopChange: (value: number) => void;
    onToggleSelectAll: () => void;
    onToggleSelect: (id: number) => void;
    onSortQuality: () => void;
    onRetry: () => void;
    onStartEdit: (entity: Entity) => void;
    onCancelEdit: () => void;
    onSaveEdit: () => void;
    onEditDataChange: (next: EditableFields) => void;
    onSelectEntity: (entity: Entity) => void;
    onDeleteEntity: (entity: Entity) => void;
    onEnrichEntity: (id: number) => void;
}

export default function EntityTableContent({
    activeDomain,
    entities,
    visibleEntities,
    loading,
    limit,
    fetchError,
    shouldVirtualize,
    viewportHeight,
    paddingTop,
    paddingBottom,
    selectedIds,
    editingId,
    editData,
    saving,
    portalByBatchId,
    viewMode = "grid",
    scrollContainerRef,
    onScrollTopChange,
    onToggleSelect,
    onRetry,
    onStartEdit,
    onCancelEdit,
    onSaveEdit,
    onEditDataChange,
    onSelectEntity,
    onDeleteEntity,
    onEnrichEntity,
}: EntityTableContentProps) {
    const { t } = useLanguage();
    const [expandedFailureId, setExpandedFailureId] = useState<number | null>(null);
    const inputClass =
        "h-10 w-full rounded-xl border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white";
    const activeAttributes = activeDomain?.attributes ?? [];
    const sourceLabel = (() => {
        const translated = t("page.exec_dashboard.source");
        return translated === "page.exec_dashboard.source" ? "Source" : translated;
    })();

    return (
        <div className="overflow-hidden rounded-2xl bg-transparent">
            <div
                ref={scrollContainerRef}
                className="space-y-4"
                style={shouldVirtualize ? { maxHeight: viewportHeight, overflowY: "auto" } : undefined}
                onScroll={shouldVirtualize ? (event) => onScrollTopChange(event.currentTarget.scrollTop) : undefined}
            >
                {fetchError ? (
                    <div className="p-4">
                        <ErrorBanner variant="row" message={t("page.entity_table.failed_load")} detail={fetchError} onRetry={onRetry} />
                    </div>
                ) : loading ? (
                    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                        {Array.from({ length: limit }).map((_, index) => (
                            <div key={index} className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-950">
                                <div className="flex animate-pulse gap-4">
                                    <div className="h-16 w-16 rounded-2xl bg-gray-100 dark:bg-gray-800" />
                                    <div className="flex-1 space-y-3">
                                        <div className="h-4 w-2/3 rounded bg-gray-100 dark:bg-gray-800" />
                                        <div className="h-3 w-1/2 rounded bg-gray-100 dark:bg-gray-800" />
                                        <div className="grid gap-2 sm:grid-cols-3">
                                            <div className="h-10 rounded-xl bg-gray-100 dark:bg-gray-800" />
                                            <div className="h-10 rounded-xl bg-gray-100 dark:bg-gray-800" />
                                            <div className="h-10 rounded-xl bg-gray-100 dark:bg-gray-800" />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : entities.length === 0 ? (
                    <div className="px-5 py-12 text-center">
                        <div className="flex flex-col items-center gap-2">
                            <svg className="h-10 w-10 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                            </svg>
                            <span className="text-sm text-gray-500 dark:text-gray-400">{t("entities.empty")}</span>
                        </div>
                    </div>
                ) : (
                    <>
                        {paddingTop > 0 && <div style={{ height: paddingTop }} />}
                        <div className={viewMode === "list" ? "space-y-2" : "grid grid-cols-1 gap-4 xl:grid-cols-2"}>
                            {visibleEntities.map((entity) => {
                                const isEditing = editingId === entity.id;
                                const parsedJson = parseNormalizedJson(entity.normalized_json);
                                const titleValue = String(resolveAttributeValue(entity, parsedJson, "title", true) || entity.primary_label || t("page.entity_table.unnamed_entity"));
                                const secondaryValue = resolveAttributeValue(entity, parsedJson, "authors", true) || resolveAttributeValue(entity, parsedJson, "secondary_label", true);
                                const identifierValue = resolveAttributeValue(entity, parsedJson, "doi", true) || resolveAttributeValue(entity, parsedJson, "canonical_id", true);
                                // Prefer the authoritative journal name resolved from enrichment_issn_l;
                                // fall back to the journal/venue stored in attributes.
                                const journalValue = entity.journal_display_name || resolveAttributeValue(entity, parsedJson, "journal", true);
                                const yearValue = resolveAttributeValue(entity, parsedJson, "year", true);
                                const citationsValue = resolveAttributeValue(entity, parsedJson, "citations", true);
                                const statusMeta = enrichmentBadgeMeta(entity.enrichment_status, t);
                                const portalSlug = entity.import_batch_id ? portalByBatchId[entity.import_batch_id] : undefined;
                                const statusTone = recordStatusTone(entity.validation_status, entity.enrichment_status);

                                if (isEditing) {
                                    return (
                                        <div key={entity.id} className="bg-blue-50/50 p-4 dark:bg-blue-500/5">
                                            <div className="rounded-2xl border border-blue-200 bg-white p-4 shadow-sm dark:border-blue-900/40 dark:bg-gray-950">
                                                <div className="flex flex-wrap items-center justify-between gap-3">
                                                    <div>
                                                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-700 dark:text-blue-300">{t("common.edit")}</p>
                                                        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">#{entity.id}</p>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <QualityBadge score={entity.quality_score} />
                                                        <select
                                                            className={inputClass}
                                                            value={editData.validation_status ?? ""}
                                                            onChange={(event) => onEditDataChange({ ...editData, validation_status: event.target.value })}
                                                        >
                                                            <option value="pending">{t("page.entity_table.status_pending")}</option>
                                                            <option value="valid">{t("page.entity_table.status_valid")}</option>
                                                            <option value="invalid">{t("page.entity_table.status_invalid")}</option>
                                                        </select>
                                                    </div>
                                                </div>

                                                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                                                    {(activeAttributes.length > 0 ? activeAttributes : [{ name: "primary_label", label: t("entities.primary_label"), is_core: true }]).map((attribute) => {
                                                        const value = resolveAttributeValue(entity, parsedJson, attribute.name, attribute.is_core);
                                                        const isEditableCoreField = attribute.is_core && attribute.name in editData;
                                                        return (
                                                            <label key={attribute.name} className="space-y-2">
                                                                <span className="text-xs font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">
                                                                    {CORE_ATTRIBUTE_LABEL_KEYS[attribute.name] ? t(CORE_ATTRIBUTE_LABEL_KEYS[attribute.name]) : attribute.label}
                                                                </span>
                                                                <input
                                                                    className={inputClass}
                                                                    value={String(value ?? "")}
                                                                    onChange={(event) => {
                                                                        if (isEditableCoreField) {
                                                                            onEditDataChange({ ...editData, [attribute.name]: event.target.value });
                                                                        }
                                                                    }}
                                                                    disabled={!isEditableCoreField}
                                                                    title={!isEditableCoreField ? t("page.entity_table.extended_attributes_readonly") : ""}
                                                                />
                                                            </label>
                                                        );
                                                    })}
                                                </div>

                                                <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
                                                    <button onClick={onCancelEdit} className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800">
                                                        {t("common.cancel")}
                                                    </button>
                                                    <button onClick={onSaveEdit} disabled={saving} className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-70">
                                                        {saving ? `${t("common.save")}...` : t("common.save")}
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                }

                                if (viewMode === "list") {
                                    return (
                                        <RecordListRow
                                            key={entity.id}
                                            selected={selectedIds.has(entity.id)}
                                            selectable
                                            tone={statusTone}
                                            onSelect={() => onToggleSelect(entity.id)}
                                            onClick={() => onSelectEntity(entity)}
                                            title={<EntityTitleLink entityId={entity.id} title={titleValue} />}
                                            metaLine={
                                                <>
                                                    {identifierValue ? String(identifierValue) : `#${entity.id}`}
                                                    {entity.entity_type ? ` · ${entity.entity_type}` : ""}
                                                    {entity.domain ? ` · ${entity.domain}` : ""}
                                                    {journalValue ? ` · ${String(journalValue)}` : ""}
                                                </>
                                            }
                                            authorityScore={entity.quality_score !== null && entity.quality_score !== undefined ? entity.quality_score.toFixed(2) : "—"}
                                            qualityScore={entity.quality_score !== null && entity.quality_score !== undefined ? entity.quality_score.toFixed(2) : "—"}
                                            statusBadge={<Badge variant={statusMeta.variant} dot={statusMeta.pulse} dotPulse={statusMeta.pulse}>{statusMeta.label}</Badge>}
                                            owner={secondaryValue ? String(secondaryValue) : sourceLabel}
                                        />
                                    );
                                }

                                return (
                                    <div key={entity.id} className={`${selectedIds.has(entity.id) ? "rounded-2xl bg-violet-50/70 dark:bg-violet-500/5" : ""}`}>
                                        <RecordResultCard
                                            leadingSlot={
                                                <div className="flex flex-col items-start gap-3">
                                                    <input
                                                        type="checkbox"
                                                        className="ukip-selection-control"
                                                        checked={selectedIds.has(entity.id)}
                                                        onChange={() => onToggleSelect(entity.id)}
                                                        aria-label={`${t("page.entity_table.select_entity")} ${entity.id}`}
                                                    />
                                                </div>
                                            }
                                            statusTone={statusTone}
                                            title={<EntityTitleLink entityId={entity.id} title={titleValue} />}
                                            secondaryLine={
                                                <>
                                                    {secondaryValue ? <span>{String(secondaryValue)}</span> : null}
                                                    {secondaryValue && (journalValue || yearValue) ? <span>·</span> : null}
                                                    {journalValue ? <span>{String(journalValue)}</span> : null}
                                                    {journalValue && yearValue ? <span>·</span> : null}
                                                    {yearValue ? <span>{String(yearValue)}</span> : null}
                                                </>
                                            }
                                            statusRow={
                                                <>
                                                    <Badge variant={statusMeta.variant} dot={statusMeta.pulse} dotPulse={statusMeta.pulse}>{statusMeta.label}</Badge>
                                                    {entity.enrichment_status === "failed" && (
                                                        <EnrichmentFailureIcon
                                                            failure={parseEnrichmentFailure(entity.attributes_json)}
                                                            expanded={expandedFailureId === entity.id}
                                                            onToggle={() => setExpandedFailureId(expandedFailureId === entity.id ? null : entity.id)}
                                                        />
                                                    )}
                                                    <QualityBadge score={entity.quality_score} />
                                                    {entity.entity_type ? <Badge variant="default">{entity.entity_type}</Badge> : null}
                                                    {entity.enrichment_work_type ? <Badge variant="info">{t(`page.work_type.${categoryFor(entity.enrichment_work_type)}`)}</Badge> : null}
                                                </>
                                            }
                                            primaryMeta={[
                                                {
                                                    label: "ID canónico",
                                                    value: renderDisplayValue("canonical_id", identifierValue, t("page.entity_table.empty_value")),
                                                    minWidthClassName: "sm:min-w-[12rem]",
                                                },
                                                {
                                                    label: "Revisión",
                                                    value: renderLocalizedValue("validation_status", entity.validation_status, t("page.entity_table.empty_value"), t),
                                                },
                                                {
                                                    label: "Citas",
                                                    value: citationsValue !== null && citationsValue !== "" ? String(citationsValue) : "0",
                                                },
                                                {
                                                    label: "Dominio",
                                                    value: entity.domain || sourceLabel,
                                                },
                                            ]}
                                            actions={
                                                <>
                                                    <Link
                                                        href={`/entities/${entity.id}`}
                                                        className="rounded-lg px-2 py-1 text-xs font-bold text-violet-600 transition hover:bg-violet-50 hover:text-violet-800 dark:text-violet-300 dark:hover:bg-violet-500/10"
                                                    >
                                                        Ver
                                                    </Link>
                                                    <button
                                                        onClick={() => onStartEdit(entity)}
                                                        className="rounded-lg px-2 py-1 text-xs font-bold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950 dark:text-[var(--ukip-muted)] dark:hover:bg-white/10 dark:hover:text-[var(--ukip-text)]"
                                                    >
                                                        Editar
                                                    </button>
                                                    <button
                                                        onClick={() => onEnrichEntity(entity.id)}
                                                        className="rounded-lg px-2 py-1 text-xs font-bold text-purple-600 transition hover:bg-purple-50 hover:text-purple-800 dark:text-purple-300 dark:hover:bg-purple-500/10"
                                                    >
                                                        Enriquecer
                                                    </button>
                                                    {portalSlug ? (
                                                        <Link href={`/catalogs/${portalSlug}`} className="rounded-lg px-2 py-1 text-xs font-bold text-emerald-600 transition hover:bg-emerald-50 hover:text-emerald-800 dark:text-emerald-300 dark:hover:bg-emerald-500/10">
                                                            Portal
                                                        </Link>
                                                    ) : null}
                                                    <button
                                                        onClick={() => onSelectEntity(entity)}
                                                        className="rounded-lg px-2 py-1 text-xs font-bold text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:text-[var(--ukip-muted)] dark:hover:bg-white/10 dark:hover:text-[var(--ukip-text)]"
                                                    >
                                                        Vista rápida
                                                    </button>
                                                    <button
                                                        onClick={() => onDeleteEntity(entity)}
                                                        className="rounded-lg px-2 py-1 text-xs font-bold text-red-600 transition hover:bg-red-50 hover:text-red-800 dark:text-red-300 dark:hover:bg-red-500/10"
                                                    >
                                                        Eliminar
                                                    </button>
                                                </>
                                            }
                                        />
                                        {expandedFailureId === entity.id && entity.enrichment_status === "failed" && (() => {
                                            const failure = parseEnrichmentFailure(entity.attributes_json);
                                            return failure ? <EnrichmentFailureDetails failure={failure} /> : null;
                                        })()}
                                    </div>
                                );
                            })}
                        </div>
                        {paddingBottom > 0 && <div style={{ height: paddingBottom }} />}
                    </>
                )}
            </div>
        </div>
    );
}
