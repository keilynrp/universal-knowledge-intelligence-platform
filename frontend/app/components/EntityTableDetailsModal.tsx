"use client";

import { useState } from "react";
import { useLanguage } from "../contexts/LanguageContext";
import type { EntityTableDomain } from "./EntityTable.types";
import MonteCarloChart from "./MonteCarloChart";
import { EnrichmentFailureDetails, parseEnrichmentFailure, FailureReasonBadge } from "./EnrichmentFailurePanel";
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
        const parsed = JSON.parse(raw) as unknown;
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
            ? parsed as Record<string, unknown>
            : {};
    } catch {
        return {};
    }
}

function titleCaseKey(key: string): string {
    if (SCIENCE_ATTRIBUTE_LABELS[key]) return SCIENCE_ATTRIBUTE_LABELS[key];
    return key
        .split("_")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
}

function formatObjectSummary(value: Record<string, unknown>): string {
    const keyword = value.keyword;
    const score = value.opportunity_score;
    const support = value.support_count;
    const external = value.external_support;
    if (typeof keyword === "string" && keyword.trim()) {
        const details = [
            typeof score === "number" ? `score ${Math.round(score)}` : null,
            typeof support === "number" ? `${support} registros` : null,
            typeof external === "number" && external > 0 ? `${external} externas` : null,
        ].filter(Boolean);
        return details.length > 0 ? `${keyword} (${details.join(" · ")})` : keyword;
    }
    return Object.entries(value)
        .slice(0, 4)
        .map(([key, entryValue]) => `${titleCaseKey(key)}: ${Array.isArray(entryValue) ? entryValue.join(", ") : String(entryValue)}`)
        .join(" · ");
}

function formatValue(value: unknown, emptyLabel: string): string {
    if (value === null || value === undefined || value === "") return emptyLabel;
    if (Array.isArray(value)) {
        if (value.length === 0) return emptyLabel;
        return value
            .map((item) => {
                if (item && typeof item === "object" && !Array.isArray(item)) {
                    return formatObjectSummary(item as Record<string, unknown>);
                }
                return String(item);
            })
            .join(", ");
    }
    if (typeof value === "object") return formatObjectSummary(value as Record<string, unknown>);
    return String(value);
}

const ABSTRACT_FIELD_KEYS = new Set([
    "abstract",
    "abstract_text",
    "summary",
    "resumen",
    "description",
    "raw_ab",
    "raw_abstract",
]);

interface AbstractMapping {
    key: string;
    label: string;
    source: string;
    text: string;
}

function stripInlineHtml(value: string): string {
    return value
        .replace(/<\s*br\s*\/?\s*>/gi, " ")
        .replace(/<\s*\/?\s*(sup|sub|i|em|b|strong|span)\b[^>]*>/gi, "")
        .replace(/<[^>]+>/g, "")
        .replace(/&nbsp;/g, " ")
        .replace(/&amp;/g, "&")
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/\s+/g, " ")
        .trim();
}

function resolveAbstractMapping(
    normalizedAttributes: Record<string, unknown>,
    sourceAttributes: Record<string, unknown>,
): AbstractMapping | null {
    const sources = [
        { source: "normalized_json", attrs: normalizedAttributes },
        { source: "attributes_json", attrs: sourceAttributes },
    ];

    for (const candidate of sources) {
        for (const key of ABSTRACT_FIELD_KEYS) {
            const value = candidate.attrs[key];
            if (typeof value === "string" && value.trim()) {
                return {
                    key,
                    label: titleCaseKey(key),
                    source: candidate.source,
                    text: stripInlineHtml(value),
                };
            }
        }

        const rawRecord = candidate.attrs.raw_record;
        if (rawRecord && typeof rawRecord === "object" && !Array.isArray(rawRecord)) {
            const rawAttrs = rawRecord as Record<string, unknown>;
            for (const key of ABSTRACT_FIELD_KEYS) {
                const value = rawAttrs[key];
                if (typeof value === "string" && value.trim()) {
                    return {
                        key: `raw_record.${key}`,
                        label: titleCaseKey(key),
                        source: `${candidate.source}.raw_record`,
                        text: stripInlineHtml(value),
                    };
                }
            }
        }
    }

    return null;
}

function wordCount(text: string): number {
    return text.split(/\s+/).filter(Boolean).length;
}

const SYSTEM_ATTRIBUTE_KEYS = new Set([
    "validation_status",
    "enrichment_status",
    "enrichment_source",
    "enrichment_doi",
    "enrichment_citation_count",
    "enrichment_concepts",
    "enrichment_authors",
    "enrichment_author_orcids",
    "enrichment_failure",
    "import_batch_id",
    "quality_score",
    "attention_score",
]);

const PRIMARY_ATTRIBUTE_KEYS = new Set([
    "primary_label",
    "secondary_label",
    "canonical_id",
    "entity_type",
    "domain",
]);

function comparableValue(value: unknown): string | null {
    if (value === null || value === undefined || value === "") return null;
    if (Array.isArray(value)) {
        const normalizedItems = value
            .map((item) => comparableValue(item))
            .filter((item): item is string => Boolean(item));
        return normalizedItems.length ? normalizedItems.join("|") : null;
    }
    if (typeof value === "object") return null;
    return stripInlineHtml(String(value)).trim().toLocaleLowerCase();
}

function fieldGroup(key: string): string {
    const normalizedKey = key.toLocaleLowerCase();
    if (["title", "name", "primary_label"].includes(normalizedKey)) return "title";
    if (["authors", "author", "full_authors", "secondary_label"].includes(normalizedKey)) return "authors";
    if (["doi", "raw_di", "enrichment_doi", "canonical_id", "provider_record_id"].includes(normalizedKey)) return "identifier";
    if (["entity_type", "type", "document_type", "publication_type", "subtype", "subtypedescription", "raw_dt", "_entry_type", "_ris_type", "_plaintext_type"].includes(normalizedKey)) return "entity_type";
    if (["affiliation", "affiliations", "institution", "institutions", "organization"].includes(normalizedKey)) return "affiliation";
    if (["citation_count", "citations", "enrichment_citation_count", "raw_ct"].includes(normalizedKey)) return "citations";
    if (["source", "source_name", "_source_name", "enrichment_source"].includes(normalizedKey)) return "source";
    return normalizedKey;
}

function hasDisplayedEquivalent(key: string, value: unknown, displayedValuesByGroup: Record<string, unknown[]>): boolean {
    const group = fieldGroup(key);
    const comparable = comparableValue(value);
    if (!comparable) return false;
    return (displayedValuesByGroup[group] ?? []).some((displayedValue) => comparableValue(displayedValue) === comparable);
}

function getNestedString(source: Record<string, unknown>, path: string[]): string | null {
    let current: unknown = source;
    for (const key of path) {
        if (!current || typeof current !== "object" || Array.isArray(current)) return null;
        current = (current as Record<string, unknown>)[key];
    }
    if (typeof current === "string" && current.trim()) return current.trim();
    if (typeof current === "number" && Number.isFinite(current)) return String(current);
    if (Array.isArray(current)) {
        const text = current
            .map((item) => {
                if (typeof item === "string") return item.trim();
                if (typeof item === "number" && Number.isFinite(item)) return String(item);
                if (item && typeof item === "object" && !Array.isArray(item)) {
                    return getNestedString(item as Record<string, unknown>, ["name"]) ||
                        getNestedString(item as Record<string, unknown>, ["display_name"]) ||
                        getNestedString(item as Record<string, unknown>, ["value"]);
                }
                return "";
            })
            .filter(Boolean)
            .join("; ");
        return text || null;
    }
    if (current && typeof current === "object") {
        return getNestedString(current as Record<string, unknown>, ["name"]) ||
            getNestedString(current as Record<string, unknown>, ["display_name"]) ||
            getNestedString(current as Record<string, unknown>, ["value"]);
    }
    return null;
}

function firstStringFromAttributes(
    sources: Record<string, unknown>[],
    paths: string[][],
): string | null {
    for (const source of sources) {
        for (const path of paths) {
            const value = getNestedString(source, path);
            if (value) return value;
        }
    }
    return null;
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

function _resolveAuthorsList(attrs: Record<string, unknown>): string[] {
    // Prefer enrichment_authors (individual names from enrichment source, aligned with ORCIDs)
    const enrichmentAuthors = attrs.enrichment_authors;
    if (Array.isArray(enrichmentAuthors) && enrichmentAuthors.length > 0) {
        return enrichmentAuthors.map(String);
    }
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
    affiliation: "Afiliación",
    affiliations: "Afiliaciones",
    authors: "Autores",
    canonical_affiliations: "Afiliaciones normalizadas",
    canonical_authors: "Autores normalizados",
    canonical_identifiers: "Identificadores normalizados",
    citation_count: "Citas",
    document_type: "Tipo de documento",
    doi: "DOI",
    full_authors: "Autores completos",
    institution: "Institución",
    journal: "Revista",
    publication_type: "Tipo de publicación",
    publisher: "Editorial",
    source_title: "Fuente",
    venue: "Revista o conferencia",
    year: "Año",
    corresponding_author: "Autor de correspondencia",
    researcher_ids: "Researcher IDs",
    orcids: "ORCIDs",
    funding: "Financiamiento",
    reference_count: "Referencias",
    references_count: "Referencias",
    open_access: "Acceso abierto",
    retrieved_at: "Fecha de recuperación",
    eissn: "EISSN",
    pubmed_id: "PubMed ID",
    month: "Mes de publicación",
    provider: "Proveedor",
    provider_record_id: "ID del proveedor",
    mapping_version: "Versión de mapeo",
    mesh_terms: "Términos MeSH",
    license: "Licencia",
    raw_fn: "Encabezado de archivo original",
    raw_vr: "Versión de formato original",
    raw_pt: "Tipo de publicación original",
    raw_au: "Autores originales",
    raw_af: "Autores completos originales",
    raw_ti: "Título original",
    raw_so: "Fuente original",
    raw_la: "Idioma original",
    raw_dt: "Tipo de documento original",
    raw_c1: "Afiliaciones de autores originales",
    raw_c3: "Instituciones originales",
    raw_rp: "Autor de correspondencia original",
    raw_ri: "Researcher IDs originales",
    raw_oi: "ORCIDs originales",
    raw_fu: "Financiamiento original",
    raw_ct: "Citas originales",
    raw_nr: "Referencias originales",
    raw_pu: "Editorial original",
    raw_sn: "ISSN original",
    raw_ei: "EISSN original",
    raw_pd: "Mes de publicación original",
    raw_py: "Año de publicación original",
    raw_vl: "Volumen original",
    raw_is: "Número original",
    raw_bp: "Página inicial original",
    raw_ep: "Página final original",
    raw_di: "DOI original",
    raw_pg: "Páginas originales",
    raw_pm: "PubMed ID original",
    raw_oa: "Acceso abierto original",
    raw_da: "Fecha de recuperación original",
    _entry_type: "Tipo de entrada",
    _plaintext_type: "Tipo de texto plano",
    _ris_type: "Tipo RIS",
    _source_name: "Nombre de fuente",
    _source_version: "Versión de fuente",
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
    const abstractMapping = resolveAbstractMapping(normalizedAttributes, sourceAttributes);
    const attributeSources = [mergedExtendedAttributes, sourceAttributes, normalizedAttributes];
    const resolvedEntityType = entity.entity_type || firstStringFromAttributes(attributeSources, [
        ["entity_type"],
        ["publication_type"],
        ["document_type"],
        ["type"],
        ["subtypeDescription"],
        ["subtype"],
        ["raw_dt"],
        ["_entry_type"],
        ["_ris_type"],
        ["_plaintext_type"],
        ["raw_record", "entity_type"],
        ["raw_record", "publication_type"],
        ["raw_record", "document_type"],
        ["raw_record", "type"],
        ["raw_record", "subtypeDescription"],
        ["raw_record", "subtype"],
        ["raw_record", "DT"],
        ["raw_record", "raw_dt"],
    ]);

    const coreFields = activeDomain
        ? activeDomain.attributes.filter((attribute) => attribute.is_core).map((attribute) => ({
            label: CORE_FIELD_LABEL_KEYS[attribute.name] ? t(CORE_FIELD_LABEL_KEYS[attribute.name]) : attribute.label,
            value: attribute.name === "entity_type"
                ? resolvedEntityType
                : resolveDomainAttributeValue(entity, mergedExtendedAttributes, attribute.name),
          }))
        : [
            { label: t("entities.primary_label"), value: entity.primary_label },
            { label: t("page.import.field.secondary_label"), value: entity.secondary_label },
            { label: t("page.import.field.canonical_id"), value: entity.canonical_id },
            { label: t("page.import.field.entity_type"), value: resolvedEntityType },
            { label: t("page.import.field.domain"), value: entity.domain },
        ];

    const systemFields = SYSTEM_FIELDS.map((field) => ({
        label: t(field.labelKey),
        value: entity[field.key],
    }));
    const displayedValuesByGroup: Record<string, unknown[]> = {
        title: [entity.primary_label, mergedExtendedAttributes.title, mergedExtendedAttributes.name],
        authors: [entity.secondary_label],
        identifier: [entity.canonical_id, mergedExtendedAttributes.enrichment_doi],
        entity_type: [resolvedEntityType],
        affiliation: [
            mergedExtendedAttributes.journal,
            mergedExtendedAttributes.venue,
            mergedExtendedAttributes.source_title,
            mergedExtendedAttributes.publisher,
            mergedExtendedAttributes.raw_so,
            mergedExtendedAttributes._source_name,
        ],
        citations: [entity.enrichment_citation_count],
        source: [entity.source, mergedExtendedAttributes.enrichment_source, mergedExtendedAttributes.source_name, mergedExtendedAttributes.source],
    };

    // Pair authors with ORCIDs for rich rendering
    const enrichmentOrcids = (sourceAttributes.enrichment_author_orcids ?? []) as (string | null)[];
    const authorsList = _resolveAuthorsList(sourceAttributes);

    const extendedFields = sortExtendedFields(
        activeDomain?.id,
        Object.entries(mergedExtendedAttributes)
        .filter(([key, value]) =>
            value !== null &&
            value !== undefined &&
            value !== "" &&
            !PRIMARY_ATTRIBUTE_KEYS.has(key) &&
            !SYSTEM_ATTRIBUTE_KEYS.has(key) &&
            !ABSTRACT_FIELD_KEYS.has(key) &&
            !hasDisplayedEquivalent(key, value, displayedValuesByGroup)
        )
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

                        {abstractMapping && (
                            <section>
                                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{t("page.entity_table.section_abstract")}</h3>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-bold text-blue-700 dark:bg-blue-500/10 dark:text-blue-300">
                                            {t("page.entity_table.abstract_source")}: {abstractMapping.source}
                                        </span>
                                        <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[11px] font-bold text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                                            {t("page.entity_table.abstract_word_count", { count: wordCount(abstractMapping.text) })}
                                        </span>
                                        <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-bold text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
                                            {t("page.entity_table.abstract_pattern_ready")}
                                        </span>
                                    </div>
                                </div>
                                <div className="rounded-xl border border-gray-100 bg-gray-50/70 p-4 dark:border-gray-800 dark:bg-gray-800/40">
                                    <span className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-gray-400">{abstractMapping.label}</span>
                                    <p className="max-h-56 overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-gray-700 dark:text-gray-300">
                                        {abstractMapping.text}
                                    </p>
                                </div>
                            </section>
                        )}

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
                        return (
                            <div className="mt-6">
                                <div className="flex items-center gap-2 mb-2">
                                    <h3 className="text-sm font-semibold text-red-700 dark:text-red-400">{t("page.entity_table.enrichment_failure_title")}</h3>
                                    <FailureReasonBadge reason={entity.enrichment_failure_reason} />
                                </div>
                                {failure && <EnrichmentFailureDetails failure={failure} />}
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
