"use client";

import { useState } from "react";
import { useLanguage } from "../contexts/LanguageContext";
import type { EntityTableDomain } from "./EntityTable.types";
import MonteCarloChart from "./MonteCarloChart";
import { EnrichmentFailureDetails, parseEnrichmentFailure } from "./EnrichmentFailurePanel";
import { apiFetch } from "@/lib/api";
import type { Entity } from "./EntityTable.types";

export interface EntityTableDetailsModalProps {
    entity: Entity | null;
    activeDomain: EntityTableDomain;
    onClose: () => void;
}

function RetryEnrichmentButton({ entityId }: { entityId: number }) {
    const { t } = useLanguage();
    const [retrying, setRetrying] = useState(false);
    const [retried, setRetried] = useState(false);

    async function handleRetry() {
        setRetrying(true);
        try {
            const res = await apiFetch(`/enrich/row/${entityId}`, { method: "POST" });
            if (res.ok) setRetried(true);
        } finally {
            setRetrying(false);
        }
    }

    if (retried) {
        return <p className="mt-3 text-xs font-medium text-amber-600 dark:text-amber-400">{t("entities.filter.pending")}...</p>;
    }

    return (
        <button
            onClick={handleRetry}
            disabled={retrying}
            className="mt-3 rounded-lg bg-purple-100 px-3 py-1.5 text-xs font-bold text-purple-700 transition hover:bg-purple-200 disabled:opacity-50 dark:bg-purple-500/10 dark:text-purple-300 dark:hover:bg-purple-500/20"
        >
            {retrying ? "..." : t("page.entity_table.enrichment_retry")}
        </button>
    );
}

const CORE_FIELD_LABEL_KEYS: Record<string, string> = {
    primary_label: "entities.primary_label",
    secondary_label: "page.import.field.secondary_label",
    canonical_id: "page.import.field.canonical_id",
    entity_type: "page.import.field.entity_type",
    domain: "page.import.field.domain",
    validation_status: "page.import.field.validation_status",
};

const SYSTEM_FIELDS: Array<{ key: keyof Entity; labelKey: string }> = [
    { key: "enrichment_status", labelKey: "entities.enrichment_status" },
    { key: "source", labelKey: "page.exec_dashboard.source" },
    { key: "enrichment_citation_count", labelKey: "page.import.field.enrichment_citation_count" },
    { key: "quality_score", labelKey: "entities.quality" },
];

function parseJsonObject(raw: string | null): Record<string, unknown> {
    if (!raw) return {};
    try {
        return JSON.parse(raw) as Record<string, unknown>;
    } catch {
        return {};
    }
}

function titleCaseKey(key: string): string {
    return key
        .split("_")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
}

function formatValue(value: unknown, emptyLabel: string): string {
    if (value === null || value === undefined || value === "") return emptyLabel;
    if (Array.isArray(value)) return value.join(", ");
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
}

/**
 * Renders a list of authors paired with their ORCIDs (when available).
 * Each ORCID links to the official orcid.org profile.
 */
function AuthorsWithOrcids({ authors, orcids }: { authors: string[]; orcids: (string | null)[] }) {
    return (
        <ul className="space-y-1">
            {authors.map((name, i) => {
                const orcid = orcids[i] ?? null;
                return (
                    <li key={`${name}-${i}`} className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                        <span className="font-medium">{name}</span>
                        {orcid && (
                            <a
                                href={`https://orcid.org/${orcid}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 rounded bg-green-50 px-1.5 py-0.5 text-[11px] font-semibold text-green-700 transition hover:bg-green-100 dark:bg-green-500/10 dark:text-green-400 dark:hover:bg-green-500/20"
                                title={`ORCID: ${orcid}`}
                            >
                                <svg className="h-3 w-3" viewBox="0 0 256 256" fill="currentColor">
                                    <path d="M128 0C57.3 0 0 57.3 0 128s57.3 128 128 128 128-57.3 128-128S198.7 0 128 0zM86.3 186.2H70.9V79.1h15.4v107.1zM78.6 66.4c-5.7 0-10.3-4.6-10.3-10.3 0-5.7 4.6-10.3 10.3-10.3 5.7 0 10.3 4.6 10.3 10.3C88.9 61.8 84.3 66.4 78.6 66.4zM196.5 186.2h-15.4v-64.2c0-17.2-6.5-25.9-19.4-25.9-14.8 0-22.2 10-22.2 29.5v60.6h-15.4V79.1h15.4v14.4c0 0 0 0 0 0 6.6-11.2 17.5-17.2 31.2-17.2 22.7 0 25.8 18.5 25.8 37.7V186.2z" />
                                </svg>
                                {orcid}
                            </a>
                        )}
                    </li>
                );
            })}
        </ul>
    );
}

function _resolveAuthorsList(attrs: Record<string, unknown>, entity: Entity): string[] {
    const raw = attrs.authors ?? attrs.full_authors ?? entity.secondary_label;
    if (!raw) return [];
    if (Array.isArray(raw)) return raw.map(String);
    if (typeof raw === "string") return raw.split(/;\s*|,\s*/).filter(Boolean);
    return [];
}

function resolveDomainAttributeValue(
    entity: Entity,
    mergedAttributes: Record<string, unknown>,
    attributeName: string,
): unknown {
    const direct = entity[attributeName as keyof Entity];
    if (direct !== undefined && direct !== null && direct !== "") {
        return direct;
    }

    switch (attributeName) {
        case "title":
            return entity.primary_label ?? mergedAttributes.title ?? "";
        case "authors":
            return mergedAttributes.authors ?? entity.secondary_label ?? "";
        case "doi":
            return entity.canonical_id ?? mergedAttributes.doi ?? "";
        case "journal":
            return mergedAttributes.journal ?? "";
        case "year":
            return mergedAttributes.year ?? "";
        case "citations":
            return entity.enrichment_citation_count ?? mergedAttributes.citation_count ?? "";
        default:
            return mergedAttributes[attributeName] ?? "";
    }
}

const SCIENCE_ATTRIBUTE_LABELS: Record<string, string> = {
    full_authors: "Full Authors",
    document_type: "Document Type",
    corresponding_author: "Corresponding Author",
    researcher_ids: "Researcher IDs",
    orcids: "ORCIDs",
    funding: "Funding",
    reference_count: "Reference Count",
    open_access: "Open Access",
    retrieved_at: "Retrieved At",
    eissn: "EISSN",
    pubmed_id: "PubMed ID",
    month: "Publication Month",
    raw_fn: "Source File Header",
    raw_vr: "Source Format Version",
    raw_pt: "Raw Publication Type",
    raw_au: "Raw Authors",
    raw_af: "Raw Full Authors",
    raw_ti: "Raw Title",
    raw_so: "Raw Source Title",
    raw_la: "Raw Language",
    raw_dt: "Raw Document Type",
    raw_c1: "Raw Author Affiliations",
    raw_c3: "Raw Institutions",
    raw_rp: "Raw Corresponding Author",
    raw_ri: "Raw Researcher IDs",
    raw_oi: "Raw ORCIDs",
    raw_fu: "Raw Funding",
    raw_ct: "Raw Citation Count",
    raw_nr: "Raw Reference Count",
    raw_pu: "Raw Publisher",
    raw_sn: "Raw ISSN",
    raw_ei: "Raw EISSN",
    raw_pd: "Raw Publication Month",
    raw_py: "Raw Publication Year",
    raw_vl: "Raw Volume",
    raw_is: "Raw Issue",
    raw_bp: "Raw Begin Page",
    raw_ep: "Raw End Page",
    raw_di: "Raw DOI",
    raw_pg: "Raw Page Count",
    raw_pm: "Raw PubMed ID",
    raw_oa: "Raw Open Access",
    raw_da: "Raw Retrieved At",
};

const SCIENCE_FIELD_ORDER = [
    "authors",
    "full_authors",
    "journal",
    "year",
    "document_type",
    "publisher",
    "volume",
    "issue",
    "start_page",
    "end_page",
    "pages",
    "issn",
    "eissn",
    "language",
    "institution",
    "corresponding_author",
    "researcher_ids",
    "orcids",
    "funding",
    "citation_count",
    "reference_count",
    "open_access",
    "retrieved_at",
    "_source_name",
    "_source_version",
    "_plaintext_type",
    "raw_c1",
    "raw_c3",
    "raw_rp",
    "raw_ri",
    "raw_oi",
    "raw_fu",
];

function sortExtendedFields(activeDomainId: string | null | undefined, fields: Array<{ key: string; label: string; value: unknown }>) {
    if (activeDomainId !== "science") return fields;
    return [...fields].sort((left, right) => {
        const leftIndex = SCIENCE_FIELD_ORDER.indexOf(left.key);
        const rightIndex = SCIENCE_FIELD_ORDER.indexOf(right.key);
        const normalizedLeft = leftIndex === -1 ? Number.MAX_SAFE_INTEGER : leftIndex;
        const normalizedRight = rightIndex === -1 ? Number.MAX_SAFE_INTEGER : rightIndex;
        if (normalizedLeft !== normalizedRight) return normalizedLeft - normalizedRight;
        return left.label.localeCompare(right.label);
    });
}

export default function EntityTableDetailsModal({ entity, activeDomain, onClose }: EntityTableDetailsModalProps) {
    const { t } = useLanguage();
    if (!entity) return null;

    const normalizedAttributes = parseJsonObject(entity.normalized_json);
    const sourceAttributes = parseJsonObject(entity.attributes_json);
    const mergedExtendedAttributes = { ...sourceAttributes, ...normalizedAttributes };

    const coreFields = activeDomain
        ? activeDomain.attributes.filter((attribute) => attribute.is_core).map((attribute) => ({
            label: CORE_FIELD_LABEL_KEYS[attribute.name] ? t(CORE_FIELD_LABEL_KEYS[attribute.name]) : attribute.label,
            value: resolveDomainAttributeValue(entity, mergedExtendedAttributes, attribute.name),
          }))
        : [
            { label: t("entities.primary_label"), value: entity.primary_label },
            { label: t("page.import.field.secondary_label"), value: entity.secondary_label },
            { label: t("page.import.field.canonical_id"), value: entity.canonical_id },
            { label: t("page.import.field.entity_type"), value: entity.entity_type },
            { label: t("page.import.field.domain"), value: entity.domain },
        ];

    const systemFields = SYSTEM_FIELDS.map((field) => ({
        label: t(field.labelKey),
        value: entity[field.key],
    }));

    // Pair authors with ORCIDs for rich rendering
    const enrichmentOrcids = (sourceAttributes.enrichment_author_orcids ?? []) as (string | null)[];
    const authorsList = _resolveAuthorsList(mergedExtendedAttributes, entity);

    const extendedFields = sortExtendedFields(
        activeDomain?.id,
        Object.entries(mergedExtendedAttributes)
        .filter(([key, value]) => value !== null && value !== undefined && value !== "" && key !== "enrichment_author_orcids")
        .map(([key, value]) => ({
            key,
            label: activeDomain?.attributes.find((attribute) => attribute.name === key)?.label ?? titleCaseKey(key),
            value,
        }))
    ).map((field) => ({
            ...field,
            label: SCIENCE_ATTRIBUTE_LABELS[field.key] ?? field.label,
        }));

    return (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
            <div className="flex h-[90vh] w-full max-w-4xl flex-col rounded-2xl bg-white shadow-2xl dark:bg-gray-900">
                <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4 dark:border-gray-800">
                    <div>
                        <h2 className="text-xl font-bold text-gray-900 dark:text-white">{entity.primary_label}</h2>
                        <p className="text-sm text-gray-500">{t("page.entity_table.full_details")}</p>
                    </div>
                    <button onClick={onClose} className="rounded-lg p-2 hover:bg-gray-100 dark:hover:bg-gray-800">
                        <svg className="h-6 w-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
                <div className="flex-1 overflow-y-auto p-6">
                    <div className="space-y-8">
                        <section>
                            <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">{t("page.entity_table.section_core")}</h3>
                            <div className="grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
                                {coreFields.map((field) => (
                                    <div key={field.label} className="flex flex-col gap-1 border-b border-gray-50 pb-2 dark:border-gray-800/50">
                                        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{field.label}</span>
                                        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                                            {formatValue(field.value, t("common.no_data"))}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </section>

                        <section>
                            <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">{t("page.entity_table.section_system")}</h3>
                            <div className="grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
                                {systemFields.map((field) => (
                                    <div key={field.label} className="flex flex-col gap-1 border-b border-gray-50 pb-2 dark:border-gray-800/50">
                                        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{field.label}</span>
                                        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                                            {formatValue(field.value, t("common.no_data"))}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </section>

                        {extendedFields.length > 0 && (
                            <section>
                                <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">{t("page.entity_table.section_extended")}</h3>
                                <div className="grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
                                    {extendedFields.map((field) => {
                                        const isAuthorsField = field.key === "authors" || field.key === "full_authors";
                                        const hasOrcids = isAuthorsField && enrichmentOrcids.length > 0 && authorsList.length > 0;
                                        return (
                                            <div key={field.label} className={`flex flex-col gap-1 border-b border-gray-50 pb-2 dark:border-gray-800/50${hasOrcids ? " md:col-span-2" : ""}`}>
                                                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{field.label}</span>
                                                {hasOrcids ? (
                                                    <AuthorsWithOrcids authors={authorsList} orcids={enrichmentOrcids} />
                                                ) : (
                                                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                                                        {formatValue(field.value, t("common.no_data"))}
                                                    </span>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            </section>
                        )}
                    </div>
                    {entity.enrichment_status === "failed" && (() => {
                        const failure = parseEnrichmentFailure(entity.attributes_json);
                        if (!failure) return null;
                        return (
                            <div className="mt-6">
                                <h3 className="mb-2 text-sm font-semibold text-red-700 dark:text-red-400">{t("page.entity_table.enrichment_failure_title")}</h3>
                                <EnrichmentFailureDetails failure={failure} />
                                <RetryEnrichmentButton entityId={entity.id} />
                            </div>
                        );
                    })()}
                    {entity.enrichment_status === "completed" && (
                        <div className="mt-8 rounded-xl border border-purple-100 bg-white p-5 shadow-sm dark:border-purple-500/10 dark:bg-gray-800/50">
                            <MonteCarloChart productId={entity.id} />
                        </div>
                    )}
                </div>
                <div className="border-t border-gray-100 px-6 py-4 dark:border-gray-800">
                    <button
                        onClick={onClose}
                        className="w-full rounded-xl bg-gray-100 py-2.5 text-sm font-semibold text-gray-900 transition-colors hover:bg-gray-200 dark:bg-gray-800 dark:text-white dark:hover:bg-gray-700"
                    >
                        {t("page.entity_table.close_details")}
                    </button>
                </div>
            </div>
        </div>
    );
}
