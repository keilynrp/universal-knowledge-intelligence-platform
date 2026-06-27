"use client";

import { useState } from "react";
import { useLanguage } from "../contexts/LanguageContext";
import type { EntityTableDomain } from "./EntityTable.types";
import MonteCarloChart from "./MonteCarloChart";
import { EnrichmentFailureDetails, parseEnrichmentFailure, FailureReasonBadge } from "./EnrichmentFailurePanel";
import { apiFetch } from "@/lib/api";
import type { Entity } from "./EntityTable.types";
import { Badge, EntityConcept } from "./ui";
import { JournalMetricsSection } from "./JournalMetricsSection";
import { categoryFor } from "@/app/lib/workType";

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

function isPlainRecord(value: unknown): value is Record<string, unknown> {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function valueString(value: unknown): string {
    if (value === null || value === undefined || value === "") return "";
    if (typeof value === "string") return stripInlineHtml(value);
    if (typeof value === "number" || typeof value === "boolean") return String(value);
    return "";
}

function firstRecordValue(record: Record<string, unknown>, keys: string[]): string | null {
    for (const key of keys) {
        const direct = valueString(record[key]);
        if (direct) return direct;
    }
    return null;
}

function normalizedOrcidHref(orcid: string): string {
    const normalized = orcid
        .trim()
        .replace(/^https?:\/\/orcid\.org\//i, "")
        .replace(/^orcid:\s*/i, "");
    return `https://orcid.org/${normalized}`;
}

function FieldValueLink({ value }: { value: string }) {
    if (!/^https?:\/\//i.test(value)) return <>{value}</>;
    return (
        <a
            href={value}
            target="_blank"
            rel="noreferrer"
            className="break-all text-blue-700 underline decoration-blue-300 underline-offset-2 hover:text-blue-900 dark:text-blue-300 dark:decoration-blue-500"
        >
            {value}
        </a>
    );
}

function SoftIcon({ type }: { type: "author" | "institution" | "keyword" | "openalex" | "ror" | "orcid" | "funding" | "external" | "info" }) {
    const common = {
        className: "h-5 w-5",
        fill: "none",
        stroke: "currentColor",
        strokeWidth: 1.9,
        strokeLinecap: "round" as const,
        strokeLinejoin: "round" as const,
        viewBox: "0 0 24 24",
    };
    if (type === "author") {
        return (
            <svg {...common}>
                <path d="M9 11a4 4 0 100-8 4 4 0 000 8z" />
                <path d="M2.5 21a6.5 6.5 0 0113 0" />
                <path d="M17 8.5a3 3 0 110 6" />
                <path d="M18.5 17a5 5 0 013 4" />
            </svg>
        );
    }
    if (type === "institution") {
        return (
            <svg {...common}>
                <path d="M4 10h16" />
                <path d="M6 10v8" />
                <path d="M10 10v8" />
                <path d="M14 10v8" />
                <path d="M18 10v8" />
                <path d="M3 18h18" />
                <path d="M12 3l8 5H4l8-5z" />
            </svg>
        );
    }
    if (type === "keyword") {
        return (
            <svg {...common}>
                <path d="M20 12l-8 8-8-8V4h8l8 8z" />
                <path d="M7.5 7.5h.01" />
            </svg>
        );
    }
    if (type === "funding") {
        return (
            <svg {...common}>
                <path d="M12 4v10" />
                <path d="M8.5 7.5A3.5 3.5 0 0112 4a3.5 3.5 0 013.5 3.5c0 2-1.6 2.8-3.5 2.8s-3.5.8-3.5 2.7A3.5 3.5 0 0012 16.5a3.5 3.5 0 003.5-3.5" />
                <path d="M4 16.5c2.4 2.8 5 4 8 4s5.6-1.2 8-4" />
            </svg>
        );
    }
    if (type === "external") {
        return (
            <svg {...common}>
                <path d="M14 4h6v6" />
                <path d="M20 4l-9 9" />
                <path d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4" />
            </svg>
        );
    }
    if (type === "info") {
        return (
            <svg {...common}>
                <circle cx="12" cy="12" r="9" />
                <path d="M12 10v6" />
                <path d="M12 7h.01" />
            </svg>
        );
    }
    if (type === "orcid") {
        return <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-lime-500 text-[10px] font-black leading-none text-white">iD</span>;
    }
    if (type === "ror") {
        return <span className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-gray-400 text-[8px] font-black text-gray-600 dark:border-gray-500 dark:text-gray-300">ROR</span>;
    }
    return (
        <svg {...common}>
            <path d="M12 3l7 4v10l-7 4-7-4V7l7-4z" />
            <path d="M12 8l4 2.25v4.5L12 17l-4-2.25v-4.5L12 8z" />
            <path d="M19 7l-7 4-7-4" />
        </svg>
    );
}

function countryFlag(country: string): string | null {
    const code = country.trim().toUpperCase();
    if (code === "CN") return "🇨🇳";
    if (code === "US" || code === "USA") return "🇺🇸";
    if (code === "GB" || code === "UK") return "🇬🇧";
    if (code === "MX") return "🇲🇽";
    if (code === "ES") return "🇪🇸";
    if (code === "DE") return "🇩🇪";
    if (code === "FR") return "🇫🇷";
    if (code === "BR") return "🇧🇷";
    return null;
}

function countryName(country: string): string {
    const code = country.trim().toUpperCase();
    if (code === "CN") return "China";
    if (code === "US" || code === "USA") return "United States";
    if (code === "GB" || code === "UK") return "United Kingdom";
    if (code === "MX") return "Mexico";
    if (code === "ES") return "Spain";
    if (code === "DE") return "Germany";
    if (code === "FR") return "France";
    if (code === "BR") return "Brazil";
    return country;
}

function compactIdentifier(value: string, prefixes: string[]): string {
    let compact = value.trim();
    for (const prefix of prefixes) {
        compact = compact.replace(new RegExp(`^https?://${prefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`, "i"), "");
    }
    return compact.replace(/^\/+/, "");
}

function isAuthorRecord(record: Record<string, unknown>): boolean {
    return Boolean(
        firstRecordValue(record, ["author_name", "authorName", "name", "display_name", "displayName"]) ||
        firstRecordValue(record, ["author_orcid", "authorOrcid", "orcid", "orcid_id", "orcidId"]) ||
        firstRecordValue(record, ["author_openalex_id", "authorOpenalexId", "openalex_id", "openalexId"])
    );
}

function authorPositionLabel(position: string | null): { label: string; className: string; prefix: string } {
    const normalized = position?.toLowerCase();
    if (normalized === "first") return { label: "Primero", prefix: "★", className: "bg-amber-100 text-amber-800 dark:bg-amber-400/15 dark:text-amber-200" };
    if (normalized === "last") return { label: "Último", prefix: "★", className: "bg-purple-100 text-purple-800 dark:bg-purple-400/15 dark:text-purple-200" };
    return { label: "Medio", prefix: "•••", className: "bg-blue-50 text-blue-700 dark:bg-blue-400/10 dark:text-blue-200" };
}

function AuthorAffiliationsTable({ records }: { records: Record<string, unknown>[] }) {
    return (
        <div className="overflow-x-auto rounded-2xl border border-gray-100 bg-white/80 shadow-sm dark:border-gray-800 dark:bg-gray-800/40">
            <div className="min-w-[54rem]">
                <div className="grid grid-cols-[10rem_minmax(12rem,1fr)_minmax(13rem,1.1fr)_minmax(15rem,1.2fr)] border-b border-gray-100 bg-gray-50/80 text-sm font-bold text-gray-600 dark:border-gray-800 dark:bg-gray-900/30 dark:text-gray-300">
                    <div className="px-4 py-4">Posición</div>
                    <div className="px-4 py-4">Autor</div>
                    <div className="flex items-center gap-2 px-4 py-4">ORCID <SoftIcon type="orcid" /></div>
                    <div className="flex items-center gap-2 px-4 py-4">OpenAlex ID <SoftIcon type="openalex" /></div>
                </div>
                <div className="divide-y divide-gray-100 dark:divide-gray-800">
                    {records.map((record, index) => {
                        const name = firstRecordValue(record, ["author_name", "authorName", "name", "display_name", "displayName"]) ?? `Autor ${index + 1}`;
                        const orcid = firstRecordValue(record, ["author_orcid", "authorOrcid", "orcid", "orcid_id", "orcidId"]);
                        const openAlex = firstRecordValue(record, ["author_openalex_id", "authorOpenalexId", "openalex_id", "openalexId"]);
                        const position = authorPositionLabel(firstRecordValue(record, ["author_position", "authorPosition", "position"]));
                        return (
                            <div key={`${index}-${name}`} className="grid grid-cols-[10rem_minmax(12rem,1fr)_minmax(13rem,1.1fr)_minmax(15rem,1.2fr)] items-center text-sm font-bold text-gray-900 dark:text-white">
                                <div className="px-4 py-4">
                                    <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-bold ${position.className}`}>
                                        <span>{position.prefix}</span>
                                        {position.label}
                                    </span>
                                </div>
                                <div className="min-w-0 px-4 py-4">{name}</div>
                                <div className="min-w-0 px-4 py-4">
                                    {orcid ? <a href={normalizedOrcidHref(orcid)} target="_blank" rel="noreferrer" className="inline-flex min-w-0 items-center gap-2 text-blue-600 dark:text-blue-300"><SoftIcon type="orcid" /><span className="break-all">{orcid}</span></a> : <span className="text-gray-300">—</span>}
                                </div>
                                <div className="min-w-0 px-4 py-4">
                                    {openAlex ? <span className="inline-flex min-w-0 items-center gap-3"><span className="text-gray-500"><SoftIcon type="openalex" /></span><FieldValueLink value={openAlex} /></span> : <span className="text-gray-300">—</span>}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}

function isAffiliationRecord(record: Record<string, unknown>): boolean {
    return Boolean(
        firstRecordValue(record, ["institution", "institution_name", "organization", "organization_name", "affiliation"]) ||
        firstRecordValue(record, ["ror", "ror_id", "rorId"]) ||
        firstRecordValue(record, ["institution_openalex_id", "institutionOpenalexId"]) ||
        (firstRecordValue(record, ["country", "country_code", "countryCode"]) && firstRecordValue(record, ["name", "display_name", "openalex_id", "openalexId"]))
    );
}

function AffiliationCards({ records }: { records: Record<string, unknown>[] }) {
    return (
        <div className="overflow-hidden rounded-2xl border border-gray-100 bg-white/80 shadow-sm dark:border-gray-800 dark:bg-gray-800/40">
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
                {records.map((record, index) => {
                    const institution = firstRecordValue(record, ["institution", "institution_name", "organization", "organization_name", "affiliation", "name", "display_name"]) ?? `Institución ${index + 1}`;
                    const ror = firstRecordValue(record, ["ror", "ror_id", "rorId"]);
                    const openAlex = firstRecordValue(record, ["openalex_id", "openalexId", "institution_openalex_id", "institutionOpenalexId"]);
                    const country = firstRecordValue(record, ["country", "country_code", "countryCode"]);
                    const flag = country ? countryFlag(country) : null;
                    return (
                        <div key={`${index}-${institution}`} className="grid gap-4 p-5 md:grid-cols-[auto_1fr_auto] md:items-center">
                            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 dark:bg-blue-400/10 dark:text-blue-200"><SoftIcon type="institution" /></span>
                            <div className="min-w-0">
                                <p className="break-words text-lg font-black text-gray-900 dark:text-white">{institution}</p>
                                <div className="mt-3 flex flex-wrap items-center gap-4 text-sm font-bold text-blue-600 dark:text-blue-300">
                                    {ror ? <span className="inline-flex min-w-0 items-center gap-2"><SoftIcon type="ror" />ROR: {compactIdentifier(ror, ["ror.org"])}</span> : null}
                                    {openAlex ? <span className="inline-flex min-w-0 items-center gap-2"><span className="text-gray-500"><SoftIcon type="openalex" /></span>OpenAlex ID: {compactIdentifier(openAlex, ["openalex.org/"])}</span> : null}
                                </div>
                            </div>
                            {country ? <span className="inline-flex w-fit items-center gap-3 rounded-xl bg-gray-50 px-4 py-2 text-sm font-black text-gray-800 ring-1 ring-gray-200 dark:bg-white/10 dark:text-gray-100 dark:ring-white/10">{flag ? <span>{flag}</span> : null}{countryName(country)}</span> : null}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function NormalizedAffiliationsTable({ records }: { records: Record<string, unknown>[] }) {
    return (
        <div className="overflow-x-auto rounded-2xl border border-gray-100 bg-white/80 shadow-sm dark:border-gray-800 dark:bg-gray-800/40">
            <div className="min-w-[58rem]">
                <div className="grid grid-cols-[minmax(16rem,1.5fr)_minmax(12rem,1fr)_minmax(15rem,1.2fr)_8rem] border-b border-gray-100 bg-gray-50/80 text-sm font-bold text-gray-600 dark:border-gray-800 dark:bg-gray-900/30 dark:text-gray-300">
                    <div className="px-4 py-4">Institución / Organización</div>
                    <div className="flex items-center gap-2 px-4 py-4">ROR <SoftIcon type="ror" /></div>
                    <div className="flex items-center gap-2 px-4 py-4">OpenAlex ID <SoftIcon type="openalex" /></div>
                    <div className="px-4 py-4">País</div>
                </div>
                <div className="divide-y divide-gray-100 dark:divide-gray-800">
                    {records.map((record, index) => {
                        const institution = firstRecordValue(record, ["institution", "institution_name", "organization", "organization_name", "affiliation", "name", "display_name"]) ?? `Institución ${index + 1}`;
                        const ror = firstRecordValue(record, ["ror", "ror_id", "rorId"]);
                        const openAlex = firstRecordValue(record, ["openalex_id", "openalexId", "institution_openalex_id", "institutionOpenalexId"]);
                        const country = firstRecordValue(record, ["country", "country_code", "countryCode"]);
                        const flag = country ? countryFlag(country) : null;
                        return (
                            <div key={`${index}-${institution}`} className="grid grid-cols-[minmax(16rem,1.5fr)_minmax(12rem,1fr)_minmax(15rem,1.2fr)_8rem] items-center text-sm font-bold text-gray-900 dark:text-white">
                                <div className="flex min-w-0 items-center gap-4 px-4 py-4"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-400/10 dark:text-blue-200"><SoftIcon type="institution" /></span><span className="break-words">{institution}</span></div>
                                <div className="min-w-0 px-4 py-4">{ror ? <span className="inline-flex min-w-0 items-center gap-3"><SoftIcon type="ror" /><FieldValueLink value={ror} /></span> : <span className="text-gray-300">—</span>}</div>
                                <div className="min-w-0 px-4 py-4">{openAlex ? <span className="inline-flex min-w-0 items-center gap-3"><span className="text-gray-500"><SoftIcon type="openalex" /></span><FieldValueLink value={openAlex} /></span> : <span className="text-gray-300">—</span>}</div>
                                <div className="px-4 py-4">{country ? <span className="inline-flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-1 text-xs font-black text-gray-700 ring-1 ring-gray-200 dark:bg-white/10 dark:text-gray-200 dark:ring-white/10">{flag ? <span>{flag}</span> : null}{country.toUpperCase()}</span> : <span className="text-gray-300">—</span>}</div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}

function isFundingRecord(record: Record<string, unknown>): boolean {
    return Boolean(
        firstRecordValue(record, ["funder", "funder_name", "funderName", "funding", "funding_agency", "agency", "name", "display_name"]) ||
        firstRecordValue(record, ["award", "award_id", "grant", "grant_id"])
    );
}

function FundingTable({ records }: { records: Record<string, unknown>[] }) {
    return (
        <div className="rounded-[1.35rem] border border-gray-100 bg-white/90 p-6 shadow-sm dark:border-gray-800 dark:bg-gray-800/40">
            <div className="mb-8 flex items-center gap-6">
                <span className="flex h-20 w-20 shrink-0 items-center justify-center rounded-[1.35rem] bg-blue-50 text-blue-600 dark:bg-blue-400/10 dark:text-blue-200">
                    <SoftIcon type="funding" />
                </span>
                <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-3 text-4xl font-black tracking-tight text-gray-950 dark:text-white">
                        Financiamiento
                        <span className="text-blue-600 dark:text-blue-300"><SoftIcon type="info" /></span>
                    </p>
                    <p className="mt-3 text-xl font-semibold text-gray-500 dark:text-gray-400">
                        Información de financiamiento o ayuda económica.
                    </p>
                </div>
            </div>
            <div className="overflow-x-auto rounded-[1.35rem] border border-gray-100 bg-white/80 dark:border-gray-800 dark:bg-gray-900/30">
                <div className="min-w-[48rem]">
                    <div className="grid grid-cols-[minmax(18rem,1fr)_minmax(16rem,0.5fr)] border-b border-gray-100 bg-gray-50/70 text-xl font-black text-gray-900 dark:border-gray-800 dark:bg-white/[0.04] dark:text-white">
                        <div className="px-8 py-7">Entidad financiadora</div>
                        <div className="px-8 py-7">Tipo</div>
                    </div>
                    <div className="divide-y divide-gray-100 dark:divide-gray-800">
                        {records.map((record, index) => {
                            const name = firstRecordValue(record, ["funder", "funder_name", "funderName", "funding", "funding_agency", "agency", "name", "display_name"]) ?? `Entidad ${index + 1}`;
                            const type = firstRecordValue(record, ["type", "role", "entity_type", "relationship"]) ?? "Entidad financiadora";
                            return (
                                <div key={`${index}-${name}`} className="grid grid-cols-[minmax(18rem,1fr)_minmax(16rem,0.5fr)] items-center text-gray-900 dark:text-white">
                                    <div className="flex min-w-0 items-center gap-8 px-8 py-7">
                                        <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 dark:bg-blue-400/10 dark:text-blue-200">
                                            <SoftIcon type="institution" />
                                        </span>
                                        <span className="break-words text-2xl font-black">{name}</span>
                                    </div>
                                    <div className="px-8 py-7">
                                        <span className="inline-flex items-center gap-3 rounded-2xl bg-lime-50 px-6 py-3 text-lg font-black text-lime-800 dark:bg-lime-400/15 dark:text-lime-100">
                                            <SoftIcon type="openalex" />
                                            {type}
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                    <div className="flex items-center gap-4 border-t border-gray-100 px-8 py-7 text-xl font-semibold text-gray-500 dark:border-gray-800 dark:text-gray-400">
                        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-50 text-blue-600 dark:bg-blue-400/10 dark:text-blue-200">
                            <SoftIcon type="info" />
                        </span>
                        {records.length} entidades financiadoras
                    </div>
                </div>
            </div>
        </div>
    );
}

function isKeywordSignalRecord(record: Record<string, unknown>): boolean {
    return Boolean(firstRecordValue(record, ["keyword", "label", "name", "concept"]) && (
        valueString(record.opportunity_score) ||
        valueString(record.score) ||
        valueString(record.support_count) ||
        valueString(record.records)
    ));
}

function KeywordSignalGrid({ records }: { records: Record<string, unknown>[] }) {
    return (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {records.map((record, index) => {
                const keyword = firstRecordValue(record, ["keyword", "label", "name", "concept"]) ?? `Keyword ${index + 1}`;
                const score = firstRecordValue(record, ["opportunity_score", "score"]) ?? "—";
                const support = firstRecordValue(record, ["support_count", "records", "support"]) ?? "0";
                return (
                    <div key={`${index}-${keyword}`} className="rounded-2xl border border-gray-100 bg-white/80 p-5 shadow-sm dark:border-gray-800 dark:bg-gray-800/40">
                        <div className="flex items-center gap-4">
                            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-400/10 dark:text-blue-200"><SoftIcon type="keyword" /></span>
                            <p className="min-w-0 break-words text-base font-black text-gray-900 dark:text-white">{keyword}</p>
                        </div>
                        <div className="mt-5 flex flex-wrap items-center gap-3 text-sm font-bold text-gray-700 dark:text-gray-200">
                            <span>Score</span>
                            <span className="rounded-full bg-lime-100 px-3 py-0.5 text-xs font-black text-lime-800 dark:bg-lime-400/20 dark:text-lime-100">{score}</span>
                            <span className="text-gray-400">•</span>
                            <span className="text-blue-600 dark:text-blue-300">{support} registros</span>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

function isExternalIdList(value: unknown): value is string[] {
    return Array.isArray(value) && value.length > 0 && value.every((item) => typeof item === "string" && /^https?:\/\//i.test(item));
}

function ExternalIdList({ values }: { values: string[] }) {
    return (
        <div className="overflow-hidden rounded-2xl border border-gray-100 bg-white/80 shadow-sm dark:border-gray-800 dark:bg-gray-800/40">
            <div className="flex items-center justify-between gap-4 border-b border-gray-100 bg-gray-50/80 px-5 py-4 dark:border-gray-800 dark:bg-gray-900/30">
                <div className="flex items-center gap-3 text-sm font-black text-gray-800 dark:text-gray-100"><span className="text-blue-600 dark:text-blue-300"><SoftIcon type="keyword" /></span>Enrichment Concept Ids</div>
                <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-black text-blue-600 dark:bg-blue-400/10 dark:text-blue-200">{values.length} conceptos</span>
            </div>
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
                {values.map((value, index) => (
                    <div key={`${index}-${value}`} className="grid grid-cols-[3.5rem_1fr_auto] items-center gap-4 px-5 py-4 text-sm font-bold">
                        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-50 text-blue-700 dark:bg-blue-400/10 dark:text-blue-200">{index + 1}</span>
                        <FieldValueLink value={value} />
                        <a href={value} target="_blank" rel="noreferrer" className="text-blue-600 hover:text-blue-800 dark:text-blue-300" aria-label="Abrir identificador externo"><SoftIcon type="external" /></a>
                    </div>
                ))}
            </div>
        </div>
    );
}

function isRichStructuredValue(value: unknown): boolean {
    if (isExternalIdList(value)) return true;
    if (!Array.isArray(value) || value.length === 0 || !value.every(isPlainRecord)) return false;
    const records = value as Record<string, unknown>[];
    return records.some(isAuthorRecord) || records.some(isAffiliationRecord) || records.some(isKeywordSignalRecord) || records.some(isFundingRecord);
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

function StructuredFieldValue({ value, emptyLabel, fieldKey }: { value: unknown; emptyLabel: string; fieldKey?: string }) {
    if (value === null || value === undefined || value === "") return <span>{emptyLabel}</span>;
    if (isExternalIdList(value)) return <ExternalIdList values={value} />;
    if (Array.isArray(value)) {
        if (value.length === 0) return <span>{emptyLabel}</span>;
        if (value.every(isPlainRecord)) {
            const records = value as Record<string, unknown>[];
            const authorLike = records.some(isAuthorRecord);
            const affiliationLike = records.some(isAffiliationRecord);
            const keywordLike = records.some(isKeywordSignalRecord);
            const fundingLike = records.some(isFundingRecord);
            if (authorLike) return <AuthorAffiliationsTable records={records} />;
            if (keywordLike) return <KeywordSignalGrid records={records} />;
            if (fundingLike) return <FundingTable records={records} />;
            if (affiliationLike && ["affiliation", "affiliations"].includes((fieldKey ?? "").toLowerCase())) return <AffiliationCards records={records} />;
            if (affiliationLike) return <NormalizedAffiliationsTable records={records} />;
            return (
                <div className="grid max-h-[24rem] gap-3 overflow-y-auto pr-1 sm:grid-cols-2">
                    {records.map((record, index) => (
                        <div key={index} className="rounded-xl border border-gray-100 bg-gray-50/70 p-3 text-xs font-medium text-gray-600 dark:border-gray-800 dark:bg-gray-800/40 dark:text-gray-300">
                            <div className="grid gap-2">
                                {Object.entries(record).map(([key, entryValue]) => (
                                    <div key={key} className="min-w-0">
                                        <span className="mr-1 text-gray-400">{titleCaseKey(key)}:</span>
                                        <span className="break-words">{formatValue(entryValue, emptyLabel)}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            );
        }
    }
    if (isPlainRecord(value)) {
        return (
            <div className="rounded-xl border border-gray-100 bg-gray-50/70 p-3 text-xs font-medium text-gray-600 dark:border-gray-800 dark:bg-gray-800/40 dark:text-gray-300">
                <div className="grid gap-2">
                    {Object.entries(value).map(([key, entryValue]) => (
                        <div key={key} className="min-w-0">
                            <span className="mr-1 text-gray-400">{titleCaseKey(key)}:</span>
                            <span className="break-words">{formatValue(entryValue, emptyLabel)}</span>
                        </div>
                    ))}
                </div>
            </div>
        );
    }
    return <span>{formatValue(value, emptyLabel)}</span>;
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
    const issnL = typeof sourceAttributes.issn_l === "string" && sourceAttributes.issn_l.trim()
        ? sourceAttributes.issn_l.trim()
        : null;
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
            key: attribute.name,
            label: CORE_FIELD_LABEL_KEYS[attribute.name] ? t(CORE_FIELD_LABEL_KEYS[attribute.name]) : attribute.label,
            value: attribute.name === "entity_type"
                ? resolvedEntityType
                : resolveDomainAttributeValue(entity, mergedExtendedAttributes, attribute.name),
          }))
        : [
            { key: "primary_label", label: t("entities.primary_label"), value: entity.primary_label },
            { key: "secondary_label", label: t("page.import.field.secondary_label"), value: entity.secondary_label },
            { key: "canonical_id", label: t("page.import.field.canonical_id"), value: entity.canonical_id },
            { key: "entity_type", label: t("page.import.field.entity_type"), value: resolvedEntityType },
            { key: "domain", label: t("page.import.field.domain"), value: entity.domain },
        ];

    const coreFieldsWithType = entity.enrichment_work_type
        ? [
            ...coreFields,
            {
                key: "work_type",
                label: t("page.import.field.work_type"),
                value: t(`page.work_type.${categoryFor(entity.enrichment_work_type)}`),
            },
          ]
        : coreFields;

    const systemFields = SYSTEM_FIELDS.map((field) => ({
        label: t(field.labelKey),
        value: entity[field.key],
    }));
    // `displayedValuesByGroup` represents values already rendered at primary
    // positions in the modal (header card, core fields, system fields). It is
    // consumed by `hasDisplayedEquivalent` to suppress duplicate rows when an
    // extended attribute happens to mirror a value already shown.
    //
    // The `affiliation` group has NO dedicated primary slot in this modal —
    // affiliation always renders as an extended attribute. Previously this
    // entry pointed at [journal, venue, source_title, publisher, raw_so,
    // _source_name] which are publication-source fields, not affiliations,
    // and caused false positives: a real affiliation value that coincidentally
    // matched a journal name (notably for legacy entities affected by the
    // cbe3255 → 19e97ff backend bug) would be hidden. Leave this group empty
    // so genuine affiliations always render.
    const displayedValuesByGroup: Record<string, unknown[]> = {
        title: [entity.primary_label, mergedExtendedAttributes.title, mergedExtendedAttributes.name],
        authors: [entity.secondary_label],
        identifier: [entity.canonical_id, mergedExtendedAttributes.enrichment_doi],
        entity_type: [resolvedEntityType],
        affiliation: [],
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
                        <div className="mt-1 flex items-center gap-2">
                            <p className="text-sm text-gray-500">{t("page.entity_table.full_details")}</p>
                            {entity.enrichment_work_type ? (
                                <Badge variant="info">
                                    {t(`page.work_type.${categoryFor(entity.enrichment_work_type)}`)}
                                </Badge>
                            ) : null}
                        </div>
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
                                {coreFieldsWithType.map((field) => (
                                    <div key={field.key} className="flex flex-col gap-1 border-b border-gray-50 pb-2 dark:border-gray-800/50">
                                        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                                            {field.key === "entity_type" ? <EntityConcept>{field.label}</EntityConcept> : field.label}
                                        </span>
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
                                        const richStructured = isRichStructuredValue(field.value);
                                        return (
                                            <div key={field.label} className={`flex flex-col gap-1 border-b border-gray-50 pb-2 dark:border-gray-800/50${hasOrcids || richStructured ? " md:col-span-2" : ""}`}>
                                                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{field.label}</span>
                                                {hasOrcids ? (
                                                    <AuthorsWithOrcids authors={authorsList} orcids={enrichmentOrcids} />
                                                ) : (
                                                    <div className="min-w-0 text-sm font-medium text-gray-700 dark:text-gray-300">
                                                        <StructuredFieldValue value={field.value} emptyLabel={t("common.no_data")} fieldKey={field.key} />
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            </section>
                        )}
                    </div>
                    {issnL && (
                        <section>
                            <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">Journal</h3>
                            <JournalMetricsSection issnL={issnL} />
                        </section>
                    )}
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
