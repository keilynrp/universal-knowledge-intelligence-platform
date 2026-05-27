"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { Badge, useToast } from "../../components/ui";
import MonteCarloChart from "../../components/MonteCarloChart";
import AnnotationThread from "../../components/AnnotationThread";
import EntityGraph from "../../components/EntityGraph";
import RelationshipManager from "../../components/RelationshipManager";
import PresenceAvatars from "../../components/PresenceAvatars";
import { useWebSocket } from "@/lib/useWebSocket";
import { useAssistantContextRegistration, type AssistantContext } from "../../contexts/AssistantContext";
import { useLanguage } from "../../contexts/LanguageContext";

type EntityValue =
    | string
    | number
    | boolean
    | null
    | undefined
    | string[]
    | number[]
    | Record<string, unknown>;

type EnrichmentPhase = "idle" | "running" | "syncing" | "complete" | "error";

interface QualityBreakdownDimension {
    weight?: number;
    contribution?: number;
    raw?: number;
    score?: number;
    label?: string;
    explanation?: string;
}

interface EntityQualityData {
    score: number;
    stored_score: number | null;
    breakdown: Record<string, QualityBreakdownDimension>;
}

interface EntityAttentionData {
    summary: {
        attention_score: number;
        category: "none" | "low" | "moderate" | "high" | "very_high";
        total_mentions: number;
        active_sources: number;
        last_seen_at: string | null;
    };
    source_counts: Record<string, number>;
    source_breakdown: Array<{
        source_type: string;
        mentions: number;
        weighted_contribution: number;
        share: number;
        weight: number;
    }>;
    timeline: Array<{
        period: string;
        mentions: number;
        score_delta: number;
        weighted_score: number;
        top_source_type: string | null;
        spike: boolean;
        spike_reason: string | null;
    }>;
    explanations: Array<{
        type: string;
        label: string;
        evidence: string;
        priority: number;
    }>;
    alerts: Array<{
        type: string;
        severity: "low" | "medium" | "high";
        confidence: "low" | "medium" | "high";
        label: string;
        evidence: string;
        period: string | null;
        priority: number;
    }>;
}

interface EnrichmentFailureDetails {
    code?: string;
    evidence?: string;
    recommendations?: string[];
    provider_attempts?: string[];
    exception_type?: string | null;
    failed_at?: string;
}

interface Entity {
    id: number;
    import_batch_id: number | null;
    primary_label: string | null;
    secondary_label: string | null;
    canonical_id: string | null;
    entity_type: string | null;
    domain: string | null;
    validation_status: string | null;
    enrichment_status: string | null;
    enrichment_doi: string | null;
    enrichment_citation_count: number | null;
    enrichment_concepts: string | null;
    enrichment_source: string | null;
    quality_score: number | null;
    source: string | null;
    attributes_json: string | null;
    normalized_json: string | null;
    [key: string]: EntityValue;
}

interface AuthorityRecord {
    id: number;
    field_name: string;
    original_value: string;
    authority_source: string;
    authority_id: string;
    canonical_label: string;
    aliases: string[];
    description: string | null;
    confidence: number;
    uri: string | null;
    status: string;
    resolution_status: string;
}

type Tab = "overview" | "enrichment" | "authority" | "graph" | "comments";

const CORE_FIELDS: (keyof Entity)[] = [
    "primary_label",
    "secondary_label",
    "canonical_id",
    "entity_type",
    "domain",
];

function sourceVariant(source: string) {
    return source === "wikidata" ? "warning" as const :
           source === "viaf" ? "info" as const :
           source === "orcid" ? "success" as const :
           source === "dbpedia" ? "error" as const :
           source === "openalex" ? "purple" as const : "default" as const;
}

function validationVariant(status: string | null) {
    return status === "valid" ? "success" as const :
           status === "invalid" ? "error" as const : "warning" as const;
}

function enrichmentVariant(status: string | null) {
    return status === "completed" ? "success" as const :
           status === "pending" ? "warning" as const :
           status === "failed" ? "error" as const : "default" as const;
}

function enrichmentHealth(percent: number) {
    const safePercent = Math.round(Math.max(0, Math.min(100, percent)));
    if (safePercent <= 20) {
        return {
            panelClass: "bg-gradient-to-br from-red-600 to-rose-600 shadow-[0_18px_50px_rgba(239,68,68,0.24)]",
            barClass: "bg-white",
        };
    }
    if (safePercent < 80) {
        return {
            panelClass: "bg-gradient-to-br from-amber-500 to-orange-500 shadow-[0_18px_50px_rgba(245,158,11,0.22)]",
            barClass: "bg-white",
        };
    }
    return {
        panelClass: "bg-gradient-to-br from-emerald-600 to-teal-600 shadow-[0_18px_50px_rgba(16,185,129,0.22)]",
        barClass: "bg-white",
    };
}

function enrichmentStatusLabel(
    status: string | null,
    tr: (key: string, fallback: string) => string,
) {
    const normalized = status || "none";
    const labels: Record<string, string> = {
        completed: tr("entities.detail.enrichment.status_completed", "Enriquecido"),
        pending: tr("entities.detail.enrichment.status_pending", "Pendiente"),
        processing: tr("entities.detail.enrichment.status_processing", "Procesando"),
        failed: tr("entities.detail.enrichment.status_failed", "Fallido"),
        none: tr("entities.detail.enrichment.status_none", "Sin iniciar"),
    };
    return labels[normalized] || normalized;
}

function attentionLabel(category: EntityAttentionData["summary"]["category"]) {
    return category === "very_high" ? "Muy alta" :
           category === "high" ? "Alta" :
           category === "moderate" ? "Media" :
           category === "low" ? "Baja" : "Sin señal";
}

function attentionClass(category: EntityAttentionData["summary"]["category"]) {
    return category === "very_high" ? "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700 dark:border-fuchsia-400/20 dark:bg-fuchsia-400/10 dark:text-fuchsia-200" :
           category === "high" ? "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-400/20 dark:bg-violet-400/10 dark:text-violet-200" :
           category === "moderate" ? "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-200" :
           category === "low" ? "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-200" :
           "border-slate-200 bg-slate-50 text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-300";
}

function attentionSourceLabel(sourceType: string) {
    return sourceType === "policy" ? "Policy" :
           sourceType === "news" ? "Noticias" :
           sourceType === "wikipedia" ? "Wikipedia" :
           sourceType === "repository" ? "Repositorios" :
           sourceType === "blog" ? "Blogs" :
           sourceType === "scholarly_web" ? "Web académica" :
           sourceType === "social_web" ? "Social/web" : "Otras";
}

function QualityIndexTooltip({
    ariaLabel,
    title,
    body,
}: {
    ariaLabel: string;
    title: string;
    body: string;
}) {
    return (
        <span className="group relative inline-flex">
            <button
                type="button"
                className="flex h-6 w-6 items-center justify-center rounded-full border border-slate-900 bg-slate-950 text-xs font-black text-white shadow-sm transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2 dark:border-white dark:bg-white dark:text-slate-950 dark:hover:bg-slate-200 dark:focus:ring-offset-slate-950"
                aria-label={ariaLabel}
            >
                i
            </button>
            <span
                role="tooltip"
                className="pointer-events-none absolute left-1/2 top-8 z-30 w-80 -translate-x-1/2 rounded-2xl border border-slate-200 bg-slate-950 p-4 text-left text-xs font-medium leading-5 text-white opacity-0 shadow-2xl transition group-hover:opacity-100 group-focus-within:opacity-100 dark:border-white/10 dark:bg-white dark:text-slate-900"
            >
                <span className="block text-[11px] font-black uppercase tracking-[0.14em] text-violet-300 dark:text-violet-600">
                    {title}
                </span>
                <span className="mt-2 block">
                    {body}
                </span>
            </span>
        </span>
    );
}

function FieldHint({ title, body, ariaLabel }: { title: string; body: string; ariaLabel: string }) {
    return (
        <span className="group relative inline-flex">
            <button
                type="button"
                className="flex h-4 w-4 items-center justify-center rounded-full border border-slate-300 bg-white text-[10px] font-black text-slate-500 transition hover:border-violet-400 hover:text-violet-600 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-1 dark:border-white/20 dark:bg-white/10 dark:text-slate-300 dark:hover:border-violet-300 dark:hover:text-violet-200 dark:focus:ring-offset-slate-950"
                aria-label={ariaLabel}
            >
                i
            </button>
            <span
                role="tooltip"
                className="pointer-events-none absolute left-0 top-6 z-30 w-72 -translate-x-2 rounded-2xl border border-slate-200 bg-slate-950 p-3.5 text-left text-xs font-medium leading-5 text-white opacity-0 shadow-2xl transition group-hover:opacity-100 group-focus-within:opacity-100 dark:border-white/10 dark:bg-white dark:text-slate-900"
            >
                <span className="block text-[10px] font-black uppercase tracking-[0.14em] text-violet-300 dark:text-violet-600">
                    {title}
                </span>
                <span className="mt-1.5 block normal-case tracking-normal">{body}</span>
            </span>
        </span>
    );
}

function alertClass(severity: "low" | "medium" | "high") {
    return severity === "high" ? "border-red-200 bg-red-50 text-red-700 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200" :
           severity === "medium" ? "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-200" :
           "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-200";
}

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

function parseEnrichmentFailure(value: unknown): EnrichmentFailureDetails | null {
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    const payload = value as Record<string, unknown>;
    return {
        code: typeof payload.code === "string" ? payload.code : undefined,
        evidence: typeof payload.evidence === "string" ? payload.evidence : undefined,
        recommendations: Array.isArray(payload.recommendations)
            ? payload.recommendations.filter((item): item is string => typeof item === "string")
            : [],
        provider_attempts: Array.isArray(payload.provider_attempts)
            ? payload.provider_attempts.filter((item): item is string => typeof item === "string")
            : [],
        exception_type: typeof payload.exception_type === "string" ? payload.exception_type : null,
        failed_at: typeof payload.failed_at === "string" ? payload.failed_at : undefined,
    };
}

function fallbackEnrichmentFailure(
    entity: Entity,
    tr: (key: string, fallback: string) => string,
): EnrichmentFailureDetails {
    if (!entity.primary_label) {
        return {
            code: "missing_title",
            evidence: tr("entities.detail.enrichment.failure_missing_title_evidence", "El registro está en estado fallido y no tiene una etiqueta principal suficiente para buscar coincidencias externas."),
            recommendations: [
                tr("entities.detail.enrichment.failure_missing_title_rec_title", "Complete el título o etiqueta principal antes de reintentar."),
                tr("entities.detail.enrichment.failure_missing_title_rec_identifier", "Agregue un DOI o identificador estable si está disponible."),
            ],
            provider_attempts: entity.enrichment_source && entity.enrichment_source !== "None"
                ? [entity.enrichment_source]
                : [],
        };
    }
    return {
        code: "legacy_failed",
        evidence: tr("entities.detail.enrichment.failure_legacy_evidence", "El registro ya estaba marcado como fallido, pero no conserva una evidencia técnica detallada del intento anterior."),
        recommendations: [
            tr("entities.detail.enrichment.failure_legacy_rec_title", "Revise que el título no tenga abreviaturas, HTML residual o errores tipográficos."),
            tr("entities.detail.enrichment.failure_legacy_rec_doi", "Agregue o corrija el DOI para aumentar la probabilidad de coincidencia."),
            tr("entities.detail.enrichment.failure_legacy_rec_retry", "Reintente el enriquecimiento para generar una nueva evidencia diagnóstica."),
        ],
        provider_attempts: entity.enrichment_source && entity.enrichment_source !== "None"
            ? [entity.enrichment_source]
            : [],
    };
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
                    label: fieldLabel(key),
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
                        label: fieldLabel(key),
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

function isUrlValue(value: string): boolean {
    return /^https?:\/\//i.test(value);
}

function FieldValueLink({ value }: { value: string }) {
    if (!isUrlValue(value)) return <>{value}</>;
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
        return <span className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-slate-400 text-[8px] font-black text-slate-600 dark:border-slate-500 dark:text-slate-300">ROR</span>;
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
    if (normalized === "first") return { label: "Primero", prefix: "★", className: "bg-amber-100 text-amber-800 ring-amber-200 dark:bg-amber-400/15 dark:text-amber-200 dark:ring-amber-400/20" };
    if (normalized === "last") return { label: "Último", prefix: "★", className: "bg-purple-100 text-purple-800 ring-purple-200 dark:bg-purple-400/15 dark:text-purple-200 dark:ring-purple-400/20" };
    return { label: "Medio", prefix: "•••", className: "bg-blue-50 text-blue-700 ring-blue-100 dark:bg-blue-400/10 dark:text-blue-200 dark:ring-blue-400/20" };
}

function AuthorAffiliationsTable({ records }: { records: Record<string, unknown>[] }) {
    return (
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white/80 shadow-sm dark:border-white/10 dark:bg-white/[0.04]">
            <div className="min-w-[54rem]">
            <div className="grid grid-cols-[10rem_minmax(12rem,1fr)_minmax(13rem,1.1fr)_minmax(15rem,1.2fr)] border-b border-slate-200 bg-slate-50/80 text-sm font-black text-slate-600 dark:border-white/10 dark:bg-white/[0.03] dark:text-slate-300">
                <div className="px-4 py-4">Posición</div>
                <div className="px-4 py-4">Autor</div>
                <div className="flex items-center gap-2 px-4 py-4">ORCID <SoftIcon type="orcid" /></div>
                <div className="flex items-center gap-2 px-4 py-4">OpenAlex ID <SoftIcon type="openalex" /></div>
            </div>
            <div className="divide-y divide-slate-200 dark:divide-white/10">
                {records.map((record, index) => {
                    const name = firstRecordValue(record, ["author_name", "authorName", "name", "display_name", "displayName"]) ?? `Autor ${index + 1}`;
                    const orcid = firstRecordValue(record, ["author_orcid", "authorOrcid", "orcid", "orcid_id", "orcidId"]);
                    const openAlex = firstRecordValue(record, ["author_openalex_id", "authorOpenalexId", "openalex_id", "openalexId"]);
                    const position = authorPositionLabel(firstRecordValue(record, ["author_position", "authorPosition", "position"]));
                    return (
                        <div key={`${index}-${name}`} className="grid grid-cols-[10rem_minmax(12rem,1fr)_minmax(13rem,1.1fr)_minmax(15rem,1.2fr)] items-center text-sm font-bold text-slate-800 dark:text-slate-100">
                            <div className="px-4 py-4">
                                <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-black ring-1 ${position.className}`}>
                                    <span>{position.prefix}</span>
                                    {position.label}
                                </span>
                            </div>
                            <div className="min-w-0 px-4 py-4">
                                <span className="break-words">{name}</span>
                            </div>
                            <div className="min-w-0 px-4 py-4">
                                {orcid ? (
                                    <a href={normalizedOrcidHref(orcid)} target="_blank" rel="noreferrer" className="inline-flex min-w-0 items-center gap-2 text-blue-600 hover:text-blue-800 dark:text-blue-300">
                                        <SoftIcon type="orcid" />
                                        <span className="break-all">{orcid}</span>
                                    </a>
                                ) : <span className="text-slate-300">—</span>}
                            </div>
                            <div className="min-w-0 px-4 py-4">
                                {openAlex ? (
                                    <span className="inline-flex min-w-0 items-center gap-3">
                                        <span className="text-slate-500 dark:text-slate-400"><SoftIcon type="openalex" /></span>
                                        <FieldValueLink value={openAlex} />
                                    </span>
                                ) : <span className="text-slate-300">—</span>}
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
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white/80 shadow-sm dark:border-white/10 dark:bg-white/[0.04]">
            <div className="divide-y divide-slate-200 dark:divide-white/10">
                {records.map((record, index) => {
                    const institution = firstRecordValue(record, ["institution", "institution_name", "organization", "organization_name", "affiliation", "name", "display_name"]) ?? `Institución ${index + 1}`;
                    const ror = firstRecordValue(record, ["ror", "ror_id", "rorId"]);
                    const openAlex = firstRecordValue(record, ["openalex_id", "openalexId", "institution_openalex_id", "institutionOpenalexId"]);
                    const country = firstRecordValue(record, ["country", "country_code", "countryCode"]);
                    const flag = country ? countryFlag(country) : null;
                    return (
                        <div key={`${index}-${institution}`} className="grid gap-4 p-5 md:grid-cols-[auto_1fr_auto] md:items-center">
                            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 dark:bg-blue-400/10 dark:text-blue-200">
                                <SoftIcon type="institution" />
                            </span>
                            <div className="min-w-0">
                                <p className="break-words text-lg font-black text-slate-900 dark:text-white">{institution}</p>
                                <div className="mt-3 flex flex-wrap items-center gap-4 text-sm font-bold text-blue-600 dark:text-blue-300">
                                    {ror ? (
                                        <span className="inline-flex min-w-0 items-center gap-2">
                                            <SoftIcon type="ror" />
                                            <FieldValueLink value={`ROR: ${compactIdentifier(ror, ["ror.org"])}`} />
                                        </span>
                                    ) : null}
                                    {openAlex ? (
                                        <span className="inline-flex min-w-0 items-center gap-2">
                                            <span className="text-slate-500 dark:text-slate-400"><SoftIcon type="openalex" /></span>
                                            <FieldValueLink value={`OpenAlex ID: ${compactIdentifier(openAlex, ["openalex.org/"])}`} />
                                        </span>
                                    ) : null}
                                </div>
                            </div>
                            {country ? (
                                <span className="inline-flex w-fit items-center gap-3 rounded-xl bg-slate-50 px-4 py-2 text-sm font-black text-slate-800 ring-1 ring-slate-200 dark:bg-white/10 dark:text-slate-100 dark:ring-white/10">
                                    {flag ? <span>{flag}</span> : null}
                                    {countryName(country)}
                                </span>
                            ) : null}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function NormalizedAffiliationsTable({ records }: { records: Record<string, unknown>[] }) {
    return (
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white/80 shadow-sm dark:border-white/10 dark:bg-white/[0.04]">
            <div className="min-w-[58rem]">
            <div className="grid grid-cols-[minmax(16rem,1.5fr)_minmax(12rem,1fr)_minmax(15rem,1.2fr)_8rem] border-b border-slate-200 bg-slate-50/80 text-sm font-black text-slate-600 dark:border-white/10 dark:bg-white/[0.03] dark:text-slate-300">
                <div className="px-4 py-4">Institución / Organización</div>
                <div className="flex items-center gap-2 px-4 py-4">ROR <SoftIcon type="ror" /></div>
                <div className="flex items-center gap-2 px-4 py-4">OpenAlex ID <SoftIcon type="openalex" /></div>
                <div className="px-4 py-4">País</div>
            </div>
            <div className="divide-y divide-slate-200 dark:divide-white/10">
                {records.map((record, index) => {
                    const institution = firstRecordValue(record, ["institution", "institution_name", "organization", "organization_name", "affiliation", "name", "display_name"]) ?? `Institución ${index + 1}`;
                    const ror = firstRecordValue(record, ["ror", "ror_id", "rorId"]);
                    const openAlex = firstRecordValue(record, ["openalex_id", "openalexId", "institution_openalex_id", "institutionOpenalexId"]);
                    const country = firstRecordValue(record, ["country", "country_code", "countryCode"]);
                    const flag = country ? countryFlag(country) : null;
                    return (
                        <div key={`${index}-${institution}`} className="grid grid-cols-[minmax(16rem,1.5fr)_minmax(12rem,1fr)_minmax(15rem,1.2fr)_8rem] items-center text-sm font-bold text-slate-800 dark:text-slate-100">
                            <div className="flex min-w-0 items-center gap-4 px-4 py-4">
                                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-400/10 dark:text-blue-200">
                                    <SoftIcon type="institution" />
                                </span>
                                <span className="break-words">{institution}</span>
                            </div>
                            <div className="min-w-0 px-4 py-4">
                                {ror ? (
                                    <span className="inline-flex min-w-0 items-center gap-3">
                                        <SoftIcon type="ror" />
                                        <FieldValueLink value={ror} />
                                    </span>
                                ) : <span className="text-slate-300">—</span>}
                            </div>
                            <div className="min-w-0 px-4 py-4">
                                {openAlex ? (
                                    <span className="inline-flex min-w-0 items-center gap-3">
                                        <span className="text-slate-500 dark:text-slate-400"><SoftIcon type="openalex" /></span>
                                        <FieldValueLink value={openAlex} />
                                    </span>
                                ) : <span className="text-slate-300">—</span>}
                            </div>
                            <div className="px-4 py-4">
                                {country ? (
                                    <span className="inline-flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-1 text-xs font-black text-slate-700 ring-1 ring-slate-200 dark:bg-white/10 dark:text-slate-200 dark:ring-white/10">
                                        {flag ? <span>{flag}</span> : null}
                                        {country.toUpperCase()}
                                    </span>
                                ) : <span className="text-slate-300">—</span>}
                            </div>
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
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white/80 shadow-sm dark:border-white/10 dark:bg-white/[0.04]">
            <div className="grid grid-cols-[minmax(16rem,1fr)_minmax(12rem,0.5fr)] border-b border-slate-200 bg-slate-50/80 text-base font-black text-slate-700 dark:border-white/10 dark:bg-white/[0.03] dark:text-slate-200">
                <div className="px-5 py-5">Entidad financiadora</div>
                <div className="px-5 py-5">Tipo</div>
            </div>
            <div className="divide-y divide-slate-200 dark:divide-white/10">
                {records.map((record, index) => {
                    const name = firstRecordValue(record, ["funder", "funder_name", "funderName", "funding", "funding_agency", "agency", "name", "display_name"]) ?? `Entidad ${index + 1}`;
                    const type = firstRecordValue(record, ["type", "role", "entity_type", "relationship"]) ?? "Entidad financiadora";
                    return (
                        <div key={`${index}-${name}`} className="grid grid-cols-[minmax(16rem,1fr)_minmax(12rem,0.5fr)] items-center text-sm font-bold text-slate-900 dark:text-white">
                            <div className="flex min-w-0 items-center gap-5 px-5 py-5">
                                <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 dark:bg-blue-400/10 dark:text-blue-200">
                                    <SoftIcon type="institution" />
                                </span>
                                <span className="break-words text-lg font-black">{name}</span>
                            </div>
                            <div className="px-5 py-5">
                                <span className="inline-flex items-center gap-2 rounded-xl bg-lime-50 px-4 py-2 text-sm font-black text-lime-800 dark:bg-lime-400/15 dark:text-lime-100">
                                    <SoftIcon type="openalex" />
                                    {type}
                                </span>
                            </div>
                        </div>
                    );
                })}
            </div>
            <div className="flex items-center gap-3 px-5 py-5 text-sm font-bold text-slate-500 dark:text-slate-400">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-50 text-blue-600 dark:bg-blue-400/10 dark:text-blue-200">
                    <SoftIcon type="info" />
                </span>
                {records.length} entidades financiadoras
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
                    <div key={`${index}-${keyword}`} className="rounded-2xl border border-slate-200 bg-white/80 p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.04]">
                        <div className="flex items-center gap-4">
                            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-400/10 dark:text-blue-200">
                                <SoftIcon type="keyword" />
                            </span>
                            <p className="min-w-0 break-words text-base font-black text-slate-900 dark:text-white">{keyword}</p>
                        </div>
                        <div className="mt-5 flex flex-wrap items-center gap-3 text-sm font-bold text-slate-700 dark:text-slate-200">
                            <span>Score</span>
                            <span className="rounded-full bg-lime-100 px-3 py-0.5 text-xs font-black text-lime-800 dark:bg-lime-400/20 dark:text-lime-100">
                                {score}
                            </span>
                            <span className="text-slate-400">•</span>
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
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white/80 shadow-sm dark:border-white/10 dark:bg-white/[0.04]">
            <div className="flex items-center justify-between gap-4 border-b border-slate-200 bg-slate-50/80 px-5 py-4 dark:border-white/10 dark:bg-white/[0.03]">
                <div className="flex items-center gap-3 text-sm font-black text-slate-800 dark:text-slate-100">
                    <span className="text-blue-600 dark:text-blue-300"><SoftIcon type="keyword" /></span>
                    Enrichment Concept Ids
                </div>
                <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-black text-blue-600 dark:bg-blue-400/10 dark:text-blue-200">
                    {values.length} conceptos
                </span>
            </div>
            <div className="divide-y divide-slate-200 dark:divide-white/10">
                {values.map((value, index) => (
                    <div key={`${index}-${value}`} className="grid grid-cols-[3.5rem_1fr_auto] items-center gap-4 px-5 py-4 text-sm font-bold">
                        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-50 text-blue-700 dark:bg-blue-400/10 dark:text-blue-200">
                            {index + 1}
                        </span>
                        <FieldValueLink value={value} />
                        <a href={value} target="_blank" rel="noreferrer" className="text-blue-600 hover:text-blue-800 dark:text-blue-300" aria-label="Abrir identificador externo">
                            <SoftIcon type="external" />
                        </a>
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
        .map(([key, entryValue]) => `${fieldLabel(key)}: ${Array.isArray(entryValue) ? entryValue.join(", ") : String(entryValue)}`)
        .join(" · ");
}

function formatValue(value: unknown): React.ReactNode {
    if (value === null || value === undefined || value === "") {
        return <span className="italic text-gray-300 dark:text-gray-600">—</span>;
    }
    if (Array.isArray(value)) {
        if (value.length === 0) return <span className="italic text-gray-300 dark:text-gray-600">—</span>;
        return value
            .map((item) => {
                if (item && typeof item === "object" && !Array.isArray(item)) {
                    return formatObjectSummary(item as Record<string, unknown>);
                }
                return stripInlineHtml(String(item));
            })
            .join(", ");
    }
    if (typeof value === "object") {
        return formatObjectSummary(value as Record<string, unknown>);
    }
    return stripInlineHtml(String(value));
}

function StructuredFieldValue({ value, fieldKey }: { value: unknown; fieldKey?: string }) {
    if (value === null || value === undefined || value === "") {
        return <span className="italic text-gray-300 dark:text-gray-600">—</span>;
    }
    if (isExternalIdList(value)) {
        return <ExternalIdList values={value} />;
    }
    if (Array.isArray(value)) {
        if (value.length === 0) return <span className="italic text-gray-300 dark:text-gray-600">—</span>;
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
                <div className="grid max-h-[28rem] gap-3 overflow-y-auto pr-1 sm:grid-cols-2">
                    {records.map((record, index) => (
                        <div key={index} className="rounded-xl border border-slate-200 bg-white/80 p-3 text-xs font-semibold text-slate-600 shadow-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300">
                            <div className="grid gap-2">
                                {Object.entries(record).map(([key, entryValue]) => (
                                    <div key={key} className="min-w-0">
                                        <span className="mr-1 text-slate-400">{fieldLabel(key)}:</span>
                                        <span className="break-words">{formatValue(entryValue)}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            );
        }
        return (
            <div className="flex flex-wrap gap-2">
                {value.map((item, index) => (
                    <span key={index} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600 dark:bg-white/10 dark:text-slate-200">
                        {formatValue(item)}
                    </span>
                ))}
            </div>
        );
    }
    if (isPlainRecord(value)) {
        return (
            <div className="rounded-xl border border-slate-200 bg-white/80 p-3 text-xs font-semibold text-slate-600 shadow-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300">
                <div className="grid gap-2">
                    {Object.entries(value).map(([key, entryValue]) => (
                        <div key={key} className="min-w-0">
                            <span className="mr-1 text-slate-400">{fieldLabel(key)}:</span>
                            <span className="break-words">{formatValue(entryValue)}</span>
                        </div>
                    ))}
                </div>
            </div>
        );
    }
    return <>{formatValue(value)}</>;
}

const Spinner = () => (
    <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
);

const DETAIL_TABS: { id: Tab; labelKey: string }[] = [
    { id: "overview", labelKey: "entities.detail.tab.overview" },
    { id: "enrichment", labelKey: "entities.detail.tab.enrichment" },
    { id: "authority", labelKey: "entities.detail.tab.authority" },
    { id: "graph", labelKey: "entities.detail.tab.graph" },
    { id: "comments", labelKey: "entities.detail.tab.comments" },
];

const DETAIL_CARD =
    "rounded-[1.35rem] border border-slate-200/80 bg-white/90 shadow-[0_18px_55px_rgba(79,70,229,0.08)] backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/80 dark:shadow-[0_18px_55px_rgba(15,23,42,0.35)]";

const DETAIL_ROW =
    "grid gap-1 border-b border-slate-100 pb-4 last:border-b-0 dark:border-white/10";

function enrichmentPhaseLabel(
    phase: EnrichmentPhase,
    tr: (key: string, fallback: string) => string,
): string {
    if (phase === "running") return tr("entities.detail.enrichment.phase_running", "Enriqueciendo registro");
    if (phase === "syncing") return tr("entities.detail.enrichment.phase_syncing", "Sincronizando resultados");
    if (phase === "complete") return tr("entities.detail.enrichment.phase_complete", "Enriquecimiento actualizado");
    if (phase === "error") return tr("entities.detail.enrichment.phase_error", "No se pudo completar el enriquecimiento");
    return "";
}

function enrichmentPhaseDescription(
    phase: EnrichmentPhase,
    tr: (key: string, fallback: string) => string,
): string {
    if (phase === "running") return tr("entities.detail.enrichment.phase_running_help", "La vista se mantiene estable mientras se consultan las fuentes externas.");
    if (phase === "syncing") return tr("entities.detail.enrichment.phase_syncing_help", "Estamos aplicando los nuevos metadatos sin desmontar los cards actuales.");
    if (phase === "complete") return tr("entities.detail.enrichment.phase_complete_help", "Los datos enriquecidos ya están reflejados en esta vista.");
    if (phase === "error") return tr("entities.detail.enrichment.phase_error_help", "Conservamos los datos previos para que puedas revisar o reintentar.");
    return "";
}

const QUALITY_FALLBACK_DIMENSIONS = [
    { key: "primary_label", label: "Etiqueta principal", weight: 0.15, icon: "type" },
    { key: "secondary_label", label: "Etiqueta secundaria", weight: 0.10, icon: "tag" },
    { key: "canonical_id", label: "ID canónico", weight: 0.10, icon: "link" },
    { key: "entity_type", label: "Tipo de entidad", weight: 0.05, icon: "cube" },
    { key: "enrichment_status", label: "Estado de enriquecimiento", weight: 0.25, icon: "spark" },
    { key: "enrichment_doi", label: "DOI de enriquecimiento", weight: 0.05, icon: "file" },
    { key: "authority_confirmed", label: "Autoridad confirmada", weight: 0.20, icon: "shield" },
    { key: "relationships", label: "Relaciones", weight: 0.10, icon: "nodes" },
];

const DETAIL_FIELD_LABELS: Record<string, string> = {
    abstract: "Resumen",
    abstract_text: "Resumen",
    affiliation: "Afiliación",
    affiliations: "Afiliaciones",
    authors: "Autores",
    canonical_affiliations: "Afiliaciones normalizadas",
    canonical_authors: "Autores normalizados",
    canonical_id: "ID canónico",
    canonical_identifiers: "Identificadores normalizados",
    citation_count: "Citas",
    document_type: "Tipo de documento",
    doi: "DOI",
    entity_type: "Tipo de entidad",
    eissn: "EISSN",
    funding: "Financiamiento",
    full_authors: "Autores completos",
    institution: "Institución",
    institutions: "Instituciones",
    issue: "Número",
    journal: "Revista",
    language: "Idioma",
    license: "Licencia",
    mapping_version: "Versión de mapeo",
    mesh_terms: "Términos MeSH",
    month: "Mes de publicación",
    open_access: "Acceso abierto",
    organization: "Organización",
    primary_label: "Etiqueta principal",
    provider: "Proveedor",
    provider_record_id: "ID del proveedor",
    publication_type: "Tipo de publicación",
    publisher: "Editorial",
    raw_af: "Autores completos originales",
    raw_au: "Autores originales",
    raw_bp: "Página inicial original",
    raw_c1: "Afiliaciones de autores originales",
    raw_c3: "Instituciones originales",
    raw_ct: "Citas originales",
    raw_da: "Fecha de recuperación original",
    raw_di: "DOI original",
    raw_dt: "Tipo de documento original",
    raw_ei: "EISSN original",
    raw_ep: "Página final original",
    raw_fn: "Encabezado de archivo original",
    raw_fu: "Financiamiento original",
    raw_is: "Número original",
    raw_la: "Idioma original",
    raw_nr: "Referencias originales",
    raw_oa: "Acceso abierto original",
    raw_oi: "ORCID originales",
    raw_pd: "Mes de publicación original",
    raw_pg: "Páginas originales",
    raw_pm: "PubMed ID original",
    raw_pu: "Editorial original",
    raw_py: "Año de publicación original",
    raw_record: "Registro original",
    raw_ri: "Researcher IDs originales",
    raw_rp: "Autor de correspondencia original",
    raw_sn: "ISSN original",
    raw_so: "Fuente original",
    raw_ti: "Título original",
    raw_vl: "Volumen original",
    raw_vr: "Versión de formato original",
    reference_count: "Referencias",
    references_count: "Referencias",
    researcher_ids: "Researcher IDs",
    retrieved_at: "Fecha de recuperación",
    secondary_label: "Etiqueta secundaria",
    source_title: "Fuente",
    start_page: "Página inicial",
    subtype: "Subtipo",
    subtypeDescription: "Descripción del subtipo",
    summary: "Resumen",
    title: "Título",
    type: "Tipo",
    venue: "Revista o conferencia",
    volume: "Volumen",
    year: "Año",
    _entry_type: "Tipo de entrada",
    _plaintext_type: "Tipo de texto plano",
    _ris_type: "Tipo RIS",
    _source_name: "Nombre de fuente",
    _source_version: "Versión de fuente",
};

function normalizePercent(value: number | null | undefined): number {
    if (value === null || value === undefined || Number.isNaN(value)) return 0;
    return Math.max(0, Math.min(100, value > 1 ? value : value * 100));
}

function labelize(value: string): string {
    return value
        .replace(/[_-]/g, " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function fieldLabel(key: string, fallback?: string): string {
    return fallback || DETAIL_FIELD_LABELS[key] || labelize(key);
}

const FIELD_HINTS: Record<string, string> = {
    title: "Título oficial de la publicación o del recurso.",
    name: "Nombre del recurso, persona u organización.",
    authors: "Lista de autores reportada por la fuente. Puede combinarse con ORCID, afiliación y orden.",
    full_authors: "Listado completo y expandido de autores (no abreviado).",
    author: "Autor principal del registro.",
    author_orcids: "Identificadores ORCID asociados a los autores.",
    enrichment_authors: "Autores reportados por el proveedor académico durante el enriquecimiento.",
    enrichment_author_orcids: "ORCID de autores devueltos por el proveedor académico.",
    affiliation: "Institución u organización a la que pertenece el autor / registro.",
    affiliations: "Lista de instituciones u organizaciones asociadas.",
    institution: "Institución académica o de investigación.",
    institutions: "Conjunto de instituciones vinculadas al registro.",
    organization: "Organización responsable o vinculada.",
    journal: "Revista o publicación donde apareció el registro.",
    venue: "Lugar de publicación: revista, conferencia, evento o repositorio.",
    publisher: "Editorial o entidad responsable de la publicación.",
    source_title: "Título de la fuente declarada en los metadatos originales.",
    year: "Año de publicación o referencia temporal del registro.",
    publication_year: "Año en que se publicó el registro.",
    publication_date: "Fecha completa de publicación.",
    date: "Fecha asociada al registro.",
    retrieved_at: "Fecha en la que se recuperó este registro desde la fuente.",
    doi: "Digital Object Identifier — clave para deduplicar y referenciar.",
    isbn: "International Standard Book Number.",
    issn: "International Standard Serial Number.",
    pmid: "PubMed ID.",
    url: "URL canónica del registro.",
    abstract: "Resumen o sinopsis del contenido.",
    summary: "Resumen breve del registro.",
    keywords: "Palabras clave declaradas por la fuente.",
    concepts: "Conceptos temáticos inferidos o declarados por el proveedor académico.",
    enrichment_concepts: "Conceptos temáticos detectados por el proveedor académico (OpenAlex, Scholar…).",
    citation_count: "Número de citas reportadas para este registro.",
    citations: "Citas detectadas.",
    enrichment_citation_count: "Citas reportadas por el proveedor académico tras el enriquecimiento.",
    reference_count: "Cantidad de referencias citadas dentro del registro.",
    references_count: "Cantidad de referencias citadas dentro del registro.",
    language: "Idioma principal del registro.",
    volume: "Volumen de la publicación.",
    issue: "Número o ejemplar dentro del volumen.",
    page: "Páginas que ocupa el registro.",
    pages: "Rango de páginas.",
    start_page: "Primera página del registro.",
    end_page: "Última página del registro.",
    open_access: "Indica si el registro está disponible en acceso abierto.",
    license: "Licencia de uso o redistribución declarada.",
    type: "Tipo / clasificación del registro reportada por la fuente.",
    document_type: "Tipo de documento (artículo, libro, capítulo, dataset…).",
    publication_type: "Tipo de publicación reportado.",
    subtype: "Subtipo dentro de la categoría declarada.",
    funding: "Información de financiamiento o ayuda económica.",
    source: "Fuente declarada de los datos.",
    source_name: "Nombre legible de la fuente.",
    _source_name: "Nombre del adaptador o canal que ingestó el registro.",
    _source_version: "Versión del adaptador / esquema en el momento de la ingesta.",
    raw_record: "Estructura completa tal como llegó del proveedor original (snapshot).",
};

function fieldHintFor(key: string): string | null {
    if (FIELD_HINTS[key]) return FIELD_HINTS[key];
    const normalized = key.toLocaleLowerCase();
    if (normalized.startsWith("raw_")) {
        return "Campo original tal como llegó de la fuente, sin normalizar. Útil para auditoría.";
    }
    if (normalized.includes("orcid")) return "Identificador ORCID asociado al autor o autora.";
    if (normalized.includes("doi")) return "Digital Object Identifier — clave de referencia única.";
    if (normalized.includes("issn") || normalized.includes("isbn")) {
        return "Identificador estándar internacional (ISSN para revistas, ISBN para libros).";
    }
    if (normalized.includes("citation") || normalized.includes("cited_by")) {
        return "Conteo de citas reportadas para este registro.";
    }
    if (normalized.includes("year")) return "Año asociado al registro.";
    if (normalized.includes("date")) return "Fecha asociada al registro.";
    if (normalized.includes("author")) return "Información de autor o autores del registro.";
    if (normalized.includes("affiliation") || normalized.includes("institution")) {
        return "Institución u organización vinculada al registro.";
    }
    if (normalized.includes("language")) return "Idioma del registro.";
    if (normalized.includes("publisher")) return "Editorial responsable de la publicación.";
    if (normalized.includes("url") || normalized.includes("link")) return "Enlace asociado al registro.";
    return null;
}

function hasMeaningfulValue(value: unknown): boolean {
    if (value === null || value === undefined || value === "") return false;
    if (Array.isArray(value)) return value.length > 0;
    return true;
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

function normalizeIdentifier(value: string | null | undefined): string {
    return String(value || "")
        .trim()
        .replace(/^https?:\/\/(dx\.)?doi\.org\//i, "")
        .replace(/^doi:\s*/i, "")
        .toLocaleLowerCase();
}

function IconGlyph({ name, className = "h-5 w-5" }: { name: string; className?: string }) {
    const common = {
        className,
        fill: "none",
        stroke: "currentColor",
        strokeWidth: 1.8,
        strokeLinecap: "round" as const,
        strokeLinejoin: "round" as const,
        viewBox: "0 0 24 24",
    };

    if (name === "bookmark") {
        return (
            <svg {...common}>
                <path d="M6 4.75A2.25 2.25 0 018.25 2.5h7.5A2.25 2.25 0 0118 4.75v16l-6-3.75L6 20.75v-16z" />
            </svg>
        );
    }
    if (name === "edit") {
        return (
            <svg {...common}>
                <path d="M4 20h4.5L19 9.5a2.8 2.8 0 00-4-4L4.5 16 4 20z" />
                <path d="M13.5 7L17 10.5" />
            </svg>
        );
    }
    if (name === "spark" || name === "quality") {
        return (
            <svg {...common}>
                <path d="M13 2l-1.6 5.2L6 9l5.4 1.8L13 16l1.6-5.2L20 9l-5.4-1.8L13 2z" />
                <path d="M5 15l-.8 2.4L2 18.2l2.2.8L5 21.5l.8-2.5 2.2-.8-2.2-.8L5 15z" />
            </svg>
        );
    }
    if (name === "type") {
        return (
            <svg {...common}>
                <path d="M4 6h16" />
                <path d="M12 6v12" />
                <path d="M9 18h6" />
            </svg>
        );
    }
    if (name === "tag") {
        return (
            <svg {...common}>
                <path d="M20 12l-8 8-8-8V4h8l8 8z" />
                <path d="M7.5 7.5h.01" />
            </svg>
        );
    }
    if (name === "link") {
        return (
            <svg {...common}>
                <path d="M10 13a5 5 0 007.1 0l1.4-1.4a5 5 0 00-7.1-7.1L10.5 5.4" />
                <path d="M14 11a5 5 0 00-7.1 0l-1.4 1.4a5 5 0 007.1 7.1l.9-.9" />
            </svg>
        );
    }
    if (name === "cube") {
        return (
            <svg {...common}>
                <path d="M12 2.75l8 4.5v9.5l-8 4.5-8-4.5v-9.5l8-4.5z" />
                <path d="M4.5 7.5L12 12l7.5-4.5" />
                <path d="M12 21v-9" />
            </svg>
        );
    }
    if (name === "file") {
        return (
            <svg {...common}>
                <path d="M7 3.5h6l4 4v13H7a2 2 0 01-2-2v-13a2 2 0 012-2z" />
                <path d="M13 3.5v4h4" />
            </svg>
        );
    }
    if (name === "shield") {
        return (
            <svg {...common}>
                <path d="M12 21s7-3.5 7-10V5.5L12 3 5 5.5V11c0 6.5 7 10 7 10z" />
                <path d="M9 12l2 2 4-5" />
            </svg>
        );
    }
    if (name === "nodes") {
        return (
            <svg {...common}>
                <circle cx="6" cy="7" r="2.25" />
                <circle cx="18" cy="7" r="2.25" />
                <circle cx="12" cy="18" r="2.25" />
                <path d="M8 8l3 7" />
                <path d="M16 8l-3 7" />
            </svg>
        );
    }
    if (name === "user") {
        return (
            <svg {...common}>
                <path d="M12 12a4 4 0 100-8 4 4 0 000 8z" />
                <path d="M4.5 20a7.5 7.5 0 0115 0" />
            </svg>
        );
    }
    if (name === "database") {
        return (
            <svg {...common}>
                <ellipse cx="12" cy="5" rx="7" ry="3" />
                <path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5" />
                <path d="M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
            </svg>
        );
    }
    if (name === "star") {
        return (
            <svg {...common}>
                <path d="M12 3l2.6 5.3 5.9.9-4.2 4.1 1 5.8L12 16.3 6.7 19.1l1-5.8-4.2-4.1 5.9-.9L12 3z" />
            </svg>
        );
    }
    if (name === "quote") {
        return (
            <svg {...common}>
                <path d="M8 11H5.5A3.5 3.5 0 009 7.5V6a5 5 0 00-5 5v5h4v-5z" />
                <path d="M19 11h-2.5A3.5 3.5 0 0020 7.5V6a5 5 0 00-5 5v5h4v-5z" />
            </svg>
        );
    }
    if (name === "globe") {
        return (
            <svg {...common}>
                <circle cx="12" cy="12" r="9" />
                <path d="M3 12h18" />
                <path d="M12 3c2.2 2.4 3.3 5.4 3.3 9S14.2 18.6 12 21c-2.2-2.4-3.3-5.4-3.3-9S9.8 5.4 12 3z" />
            </svg>
        );
    }
    if (name === "calendar") {
        return (
            <svg {...common}>
                <path d="M7 3v3" />
                <path d="M17 3v3" />
                <rect x="4" y="5" width="16" height="16" rx="2" />
                <path d="M4 10h16" />
            </svg>
        );
    }
    if (name === "institution") {
        return (
            <svg {...common}>
                <path d="M3 9l9-5 9 5" />
                <path d="M5 10h14" />
                <path d="M6 10v8" />
                <path d="M10 10v8" />
                <path d="M14 10v8" />
                <path d="M18 10v8" />
                <path d="M4 18h16" />
            </svg>
        );
    }
    if (name === "chart") {
        return (
            <svg {...common}>
                <path d="M4 19h16" />
                <path d="M7 16l4-4 3 2 5-7" />
                <path d="M7 16v3" />
                <path d="M14 14v5" />
                <path d="M19 7v12" />
            </svg>
        );
    }

    return (
        <svg {...common}>
            <circle cx="12" cy="12" r="9" />
            <path d="M12 8v4l2.5 2.5" />
        </svg>
    );
}

function qualityHealth(percent: number) {
    const safePercent = Math.round(Math.max(0, Math.min(100, percent)));
    if (safePercent <= 20) {
        return {
            key: "critical" as const,
            ring: "#ef4444",
            track: "#fee2e2",
            textClass: "text-red-600 dark:text-red-300",
            shadow: "shadow-[inset_0_0_0_1px_rgba(239,68,68,0.22)]",
            barClass: "bg-red-500",
        };
    }
    if (safePercent < 80) {
        return {
            key: "warning" as const,
            ring: "#f59e0b",
            track: "#fef3c7",
            textClass: "text-amber-600 dark:text-amber-300",
            shadow: "shadow-[inset_0_0_0_1px_rgba(245,158,11,0.24)]",
            barClass: "bg-amber-500",
        };
    }
    return {
        key: "healthy" as const,
        ring: "#10b981",
        track: "#d1fae5",
        textClass: "text-emerald-600 dark:text-emerald-300",
        shadow: "shadow-[inset_0_0_0_1px_rgba(16,185,129,0.22)]",
        barClass: "bg-emerald-500",
    };
}

function QualityRing({ percent, label }: { percent: number; label: string }) {
    const safePercent = Math.round(Math.max(0, Math.min(100, percent)));
    const health = qualityHealth(safePercent);
    return (
        <div
            className={`relative flex h-36 w-36 shrink-0 items-center justify-center rounded-full ${health.shadow}`}
            style={{
                background: `conic-gradient(${health.ring} ${safePercent * 3.6}deg, ${health.track} ${safePercent * 3.6}deg)`,
            }}
            aria-label={`${label} ${safePercent}%`}
        >
            <div className="absolute inset-4 rounded-full bg-white dark:bg-slate-950" />
            <span className={`relative text-4xl font-black tracking-tight ${health.textClass}`}>
                {safePercent}%
            </span>
        </div>
    );
}

export default function EntityDetailPage() {
    const params = useParams();
    const entityId = params.id as string;
    const { toast } = useToast();
    const { t } = useLanguage();

    // Real-time presence (Sprint 91)
    const { presence, isConnected, send: wsSend } = useWebSocket(
        entityId ? `entity-${entityId}` : null
    );

    const [entity, setEntity] = useState<Entity | null>(null);
    const [loading, setLoading] = useState(true);
    const [tab, setTab] = useState<Tab>("overview");

    // Edit mode
    const [isEditing, setIsEditing] = useState(false);
    const [editData, setEditData] = useState<Partial<Entity>>({});
    const [saving, setSaving] = useState(false);

    // Enrichment
    const [enriching, setEnriching] = useState(false);
    const [enrichmentPhase, setEnrichmentPhase] = useState<EnrichmentPhase>("idle");
    const enrichmentResetRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Authority tab
    const [authorityRecords, setAuthorityRecords] = useState<AuthorityRecord[]>([]);
    const [authorityLoading, setAuthorityLoading] = useState(false);
    const [authorityAction, setAuthorityAction] = useState<number | null>(null);

    // Comments tab
    const [commentCount, setCommentCount] = useState<number>(0);

    // Graph tab
    const [graphKey, setGraphKey] = useState(0);

    // Quality score
    const [qualityData, setQualityData] = useState<EntityQualityData | null>(null);
    const [attentionData, setAttentionData] = useState<EntityAttentionData | null>(null);

    useEffect(() => {
        return () => {
            if (enrichmentResetRef.current) clearTimeout(enrichmentResetRef.current);
        };
    }, []);

    const fetchEntity = useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiFetch(`/entities/${entityId}`);
            if (!res.ok) throw new Error("Not found");
            setEntity(await res.json());
        } catch {
            setEntity(null);
        } finally {
            setLoading(false);
        }
    }, [entityId]);

    useEffect(() => { fetchEntity(); }, [fetchEntity]);

    useEffect(() => {
        if (!entity) return;
        apiFetch(`/annotations?entity_id=${entity.id}&limit=200`)
            .then((r) => r.ok ? r.json() : [])
            .then((data: unknown[]) => setCommentCount(Array.isArray(data) ? data.length : 0))
            .catch(() => {});
    }, [entity]);

    const fetchAuthority = useCallback(async () => {
        if (!entity) return;
        setAuthorityLoading(true);
        try {
            const res = await apiFetch(`/authority/records?field_name=entity_name&limit=200`);
            if (res.ok) {
                const data = await res.json();
                const records: AuthorityRecord[] = data.records ?? data;
                const name = (entity.primary_label ?? "").toLowerCase();
                setAuthorityRecords(
                    records.filter((r: AuthorityRecord) =>
                        r.original_value.toLowerCase().includes(name) ||
                        name.includes(r.original_value.toLowerCase())
                    )
                );
            }
        } finally {
            setAuthorityLoading(false);
        }
    }, [entity]);

    useEffect(() => {
        if (tab === "authority" && entity) {
            fetchAuthority();
        }
    }, [tab, entity, fetchAuthority]);

    useEffect(() => {
        if (tab === "overview" && entity && !qualityData) {
            apiFetch(`/entities/${entity.id}/quality`)
                .then((r) => r.ok ? r.json() : null)
                .then((data: EntityQualityData | null) => { if (data) setQualityData(data); })
                .catch(() => {});
        }
        if (tab === "overview" && entity && !attentionData) {
            apiFetch(`/entities/${entity.id}/attention`)
                .then((r) => r.ok ? r.json() : null)
                .then((data: EntityAttentionData | null) => { if (data) setAttentionData(data); })
                .catch(() => {});
        }
    }, [tab, entity, qualityData, attentionData]);
    const entityAssistantContext = useMemo<Partial<AssistantContext>>(() => ({
        route: `/entities/${entityId}`,
        domainId: entity?.domain || "all",
        moduleLabel: "Detalle de entidad",
        totalEntities: entity ? 1 : null,
        enrichedCount: entity?.enrichment_status === "completed" ? 1 : 0,
        enrichmentPct: entity?.enrichment_status === "completed" ? 100 : entity?.enrichment_status === "processing" ? 65 : entity?.enrichment_status === "pending" ? 45 : entity?.enrichment_status === "failed" ? 12 : 0,
        qualityPct: qualityData?.score != null
            ? normalizePercent(qualityData.score)
            : entity?.quality_score != null
                ? normalizePercent(entity.quality_score)
                : null,
        activeSources: attentionData?.summary.active_sources ?? (entity?.source || entity?.enrichment_source ? 1 : 0),
        leadingGap: entity?.enrichment_status === "failed"
            ? "El enriquecimiento fallo para este registro"
            : !entity?.canonical_id
                ? "Falta ID canonico estable"
                : !entity?.entity_type
                    ? "Falta tipo de entidad normalizado"
                    : null,
        recommendedActions: [
            entity?.primary_label ? `Registro: ${entity.primary_label}` : `Registro #${entityId}`,
            entity?.canonical_id ? `ID canonico: ${entity.canonical_id}` : "Validar ID canonico",
            entity?.entity_type ? `Tipo: ${entity.entity_type}` : "Mapear tipo de entidad",
            entity?.enrichment_status ? `Enrichment: ${entity.enrichment_status}` : "Ejecutar enriquecimiento",
        ],
        actionLinks: [
            {
                id: "entity-run-enrichment",
                label: "Enriquecer registro actual",
                href: `/entities/${entityId}#enrichment`,
                kind: "mutation",
                apiPath: `/enrich/row/${entityId}`,
                method: "POST",
                requiresConfirmation: true,
                confirmationLabel: "Se ejecutara el enriquecimiento para este registro y se actualizaran metadatos, DOI, citas, conceptos y fuente si hay coincidencias confiables. Requiere permisos editor/admin.",
                successLabel: "Enriquecimiento del registro completado.",
            },
            { id: "entity-enrichment", label: "Ver enriquecimiento", href: `/entities/${entityId}#enrichment`, kind: "preview" },
            { id: "entity-authority", label: "Revisar autoridad", href: `/entities/${entityId}#authority`, kind: "preview" },
            { id: "entity-graph", label: "Abrir relaciones", href: `/entities/${entityId}#graph`, kind: "navigate" },
            { id: "entity-rag", label: "Preguntar en RAG", href: "/rag", kind: "navigate" },
        ],
    }), [attentionData, entity, entityId, qualityData]);
    useAssistantContextRegistration(entityAssistantContext);

    async function refreshAnalysisData(targetEntityId: number) {
        const [qualityResult, attentionResult] = await Promise.allSettled([
            apiFetch(`/entities/${targetEntityId}/quality`).then((r) => r.ok ? r.json() as Promise<EntityQualityData> : null),
            apiFetch(`/entities/${targetEntityId}/attention`).then((r) => r.ok ? r.json() as Promise<EntityAttentionData> : null),
        ]);

        if (qualityResult.status === "fulfilled" && qualityResult.value) {
            setQualityData(qualityResult.value);
        }
        if (attentionResult.status === "fulfilled" && attentionResult.value) {
            setAttentionData(attentionResult.value);
        }
    }

    function startEdit() {
        if (!entity) return;
        const data: Partial<Entity> = {};
        CORE_FIELDS.forEach((f) => { data[f] = entity[f]; });
        data.validation_status = entity.validation_status;
        setEditData(data);
        setIsEditing(true);
        wsSend("entity.editing", { entity_id: Number(entityId), editing: true });
    }

    function cancelEdit() {
        setIsEditing(false);
        setEditData({});
        wsSend("entity.editing", { entity_id: Number(entityId), editing: false });
    }

    async function handleSave() {
        setSaving(true);
        try {
            const res = await apiFetch(`/entities/${entityId}`, {
                method: "PUT",
                body: JSON.stringify(editData),
            });
            if (!res.ok) throw new Error("Save failed");
            setEntity(await res.json());
            setIsEditing(false);
            setEditData({});
            toast("Entity saved", "success");
            wsSend("entity.saved", { entity_id: Number(entityId) });
        } catch {
            toast("Error saving entity", "error");
        } finally {
            setSaving(false);
        }
    }

    async function handleEnrich() {
        if (!entity) return;
        if (enrichmentResetRef.current) clearTimeout(enrichmentResetRef.current);
        setEnriching(true);
        setEnrichmentPhase("running");
        setEntity((current) => current ? { ...current, enrichment_status: "processing" } : current);
        try {
            const res = await apiFetch(`/enrich/row/${entityId}`, { method: "POST" });
            if (!res.ok) throw new Error("Enrichment failed");
            setEnrichmentPhase("syncing");
            const enrichedEntity = await res.json() as Entity;
            setEntity((current) => current ? { ...current, ...enrichedEntity } : enrichedEntity);
            await refreshAnalysisData(enrichedEntity.id);
            setEnrichmentPhase("complete");
            toast(tr("entities.detail.enrichment.phase_complete", "Enriquecimiento actualizado"), "success");
            enrichmentResetRef.current = setTimeout(() => setEnrichmentPhase("idle"), 2800);
        } catch {
            setEnrichmentPhase("error");
            setEntity((current) => current ? { ...current, enrichment_status: entity.enrichment_status } : current);
            toast(tr("entities.detail.enrichment.phase_error", "No se pudo completar el enriquecimiento"), "error");
            enrichmentResetRef.current = setTimeout(() => setEnrichmentPhase("idle"), 4200);
        } finally {
            setEnriching(false);
        }
    }

    async function confirmAuthority(recordId: number) {
        setAuthorityAction(recordId);
        try {
            await apiFetch(`/authority/records/${recordId}/confirm`, {
                method: "POST",
                body: JSON.stringify({ also_create_rule: true }),
            });
            setAuthorityRecords(prev =>
                prev.map(r => r.id === recordId ? { ...r, status: "confirmed" } : r)
            );
        } finally {
            setAuthorityAction(null);
        }
    }

    async function rejectAuthority(recordId: number) {
        setAuthorityAction(recordId);
        try {
            await apiFetch(`/authority/records/${recordId}/reject`, { method: "POST" });
            setAuthorityRecords(prev =>
                prev.map(r => r.id === recordId ? { ...r, status: "rejected" } : r)
            );
        } finally {
            setAuthorityAction(null);
        }
    }

    if (loading) {
        return (
            <div className="flex h-64 items-center justify-center">
                <svg className="h-8 w-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
            </div>
        );
    }

    if (!entity) {
        return (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 py-20 dark:border-gray-700">
                <p className="text-lg font-semibold text-gray-500 dark:text-gray-400">{t("entities.detail.not_found")}</p>
                <Link href="/" className="mt-3 text-sm text-blue-600 hover:underline dark:text-blue-400">
                    {t("entities.detail.back")}
                </Link>
            </div>
        );
    }

    const sourceAttributes = parseJsonObject(entity.attributes_json);
    const normalizedAttributes = parseJsonObject(entity.normalized_json);
    const mergedAttributes: Record<string, unknown> = {
        ...sourceAttributes,
        ...normalizedAttributes,
    };
    const abstractMapping = resolveAbstractMapping(normalizedAttributes, sourceAttributes);
    const displayTitle = entity.primary_label || String(mergedAttributes.title || mergedAttributes.name || `Registro #${entityId}`);
    const description = [
        entity.secondary_label,
        mergedAttributes.journal || mergedAttributes.venue,
        mergedAttributes.year || mergedAttributes.publication_year,
    ].filter(Boolean).map(String).join(" · ");
    const tr = (key: string, fallback: string) => {
        const value = t(key);
        return value === key ? fallback : value;
    };
    const enrichmentFeedbackActive = enrichmentPhase !== "idle";
    const enrichmentFeedbackLabel = enrichmentPhaseLabel(enrichmentPhase, tr);
    const enrichmentFeedbackDescription = enrichmentPhaseDescription(enrichmentPhase, tr);
    const qualityPercent = normalizePercent(qualityData?.score ?? entity.quality_score);
    const qualityHealthState = qualityHealth(qualityPercent);
    const qualityRows = qualityData
        ? Object.entries(qualityData.breakdown).map(([key, dim]) => ({
            key,
            label: dim.label || fieldLabel(key),
            weight: normalizePercent(dim.weight),
            contribution: normalizePercent(dim.contribution),
            icon: QUALITY_FALLBACK_DIMENSIONS.find((item) => item.key === key)?.icon || "quality",
        }))
        : QUALITY_FALLBACK_DIMENSIONS.map((item) => {
            const value =
                item.key === "authority_confirmed"
                    ? entity.validation_status === "valid"
                    : item.key === "relationships"
                    ? false
                    : entity[item.key];
            const contribution = hasMeaningfulValue(value) ? item.weight : 0;
            return {
                key: item.key,
                label: item.label,
                weight: item.weight * 100,
                contribution: contribution * 100,
                icon: item.icon,
            };
        });
    const attributeSources = [mergedAttributes, sourceAttributes, normalizedAttributes];
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
    const resolvedDoi = entity.enrichment_doi || firstStringFromAttributes(attributeSources, [
        ["doi"],
        ["raw_di"],
        ["raw_record", "doi"],
        ["raw_record", "DI"],
        ["raw_record", "prism:doi"],
    ]);
    const canonicalDuplicatesDoi = Boolean(
        entity.canonical_id &&
        resolvedDoi &&
        normalizeIdentifier(entity.canonical_id) === normalizeIdentifier(resolvedDoi)
    );
    const canonicalDisplayValue = canonicalDuplicatesDoi ? null : entity.canonical_id;
    const primaryFields: Array<{
        key: string;
        label: string;
        value: unknown;
        icon: string;
        copyable?: boolean;
        hint?: { title: string; body: string };
    }> = [
        {
            key: "primary_label",
            label: tr("entities.detail.fields.primary_label", "Etiqueta principal"),
            value: entity.primary_label,
            icon: "type",
            hint: {
                title: tr("entities.detail.fields.primary_label", "Etiqueta principal"),
                body: tr(
                    "entities.detail.fields.primary_label_hint",
                    "Nombre principal del registro: título de la publicación, nombre del autor, denominación de la institución u otra etiqueta canónica."
                ),
            },
        },
        {
            key: "secondary_label",
            label: tr("entities.detail.fields.secondary_label_short", "Etiqueta secundaria"),
            value: entity.secondary_label,
            icon: "tag",
            hint: {
                title: tr("entities.detail.fields.secondary_label_short", "Etiqueta secundaria"),
                body: tr(
                    "entities.detail.fields.secondary_label_hint",
                    "Contexto del registro: autor, institución, fuente, revista, afiliación u otra etiqueta de soporte."
                ),
            },
        },
        {
            key: "canonical_id",
            label: tr("entities.detail.fields.canonical_id_short", "ID canónico"),
            value: canonicalDisplayValue,
            icon: "link",
            copyable: true,
            hint: {
                title: tr("entities.detail.fields.canonical_id_short", "ID canónico"),
                body: tr(
                    "entities.detail.fields.canonical_id_hint",
                    "Identificador único del registro: DOI, ORCID, ROR, ISBN, ID local u otro identificador estable."
                ),
            },
        },
        {
            key: "entity_type",
            label: tr("entities.detail.fields.entity_type", "Tipo de entidad"),
            value: resolvedEntityType,
            icon: "cube",
            hint: {
                title: tr("entities.detail.fields.entity_type", "Tipo de entidad"),
                body: tr(
                    "entities.detail.fields.entity_type_hint",
                    "Clasificación del registro: artículo, libro, persona, organización, concepto, conjunto de datos, etc. Se infiere de los metadatos de origen."
                ),
            },
        },
        {
            key: "domain",
            label: tr("entities.detail.fields.domain", "Dominio"),
            value: entity.domain,
            icon: "globe",
            hint: {
                title: tr("entities.detail.fields.domain", "Dominio"),
                body: tr(
                    "entities.detail.fields.domain_hint",
                    "Dominio temático al que pertenece el registro (ciencia, salud, default…). Define el esquema y las reglas aplicables."
                ),
            },
        },
    ];
    const systemFields: Array<{
        key: string;
        label: string;
        value: unknown;
        icon: string;
        badge?: string;
        copyable?: boolean;
        hint?: { title: string; body: string };
    }> = [
        {
            key: "validation_status",
            label: tr("entities.detail.fields.validation_status", "Validación"),
            value: entity.validation_status,
            badge: "validation",
            icon: "quality",
            hint: {
                title: tr("entities.detail.fields.validation_status", "Validación"),
                body: tr(
                    "entities.detail.fields.validation_status_hint",
                    "Estado de validación del registro: pendiente, válido o requiere revisión. Lo determinan las reglas de calidad y la autoridad confirmada."
                ),
            },
        },
        {
            key: "enrichment_status",
            label: tr("entities.enrichment_status", "Estado de enriquecimiento"),
            value: entity.enrichment_status,
            badge: "enrichment",
            icon: "shield",
            hint: {
                title: tr("entities.enrichment_status", "Estado de enriquecimiento"),
                body: tr(
                    "entities.detail.fields.enrichment_status_hint",
                    "Estado del enriquecimiento académico: ninguno, pendiente, en proceso, completado o fallido. Se calcula tras consultar proveedores como OpenAlex, Scholar o WoS."
                ),
            },
        },
        {
            key: "source",
            label: tr("entities.detail.fields.source", "Fuente"),
            value: entity.source,
            icon: "user",
            hint: {
                title: tr("entities.detail.fields.source", "Fuente"),
                body: tr(
                    "entities.detail.fields.source_hint",
                    "Origen del registro: carga manual del usuario, dataset demo o un adaptador externo (tienda conectada, API)."
                ),
            },
        },
        {
            key: "import_batch_id",
            label: tr("entities.detail.fields.import_batch_id", "Lote de importación"),
            value: entity.import_batch_id,
            icon: "database",
            hint: {
                title: tr("entities.detail.fields.import_batch_id", "Lote de importación"),
                body: tr(
                    "entities.detail.fields.import_batch_id_hint",
                    "Identificador del batch de ingesta al que pertenece el registro. Permite trazar de qué archivo / sincronización vino."
                ),
            },
        },
        {
            key: "quality_score",
            label: tr("entities.detail.fields.quality_score", "Puntuación de calidad"),
            value: qualityPercent > 0 ? `${Math.round(qualityPercent)}%` : null,
            icon: "star",
            hint: {
                title: tr("entities.detail.fields.quality_score", "Puntuación de calidad"),
                body: tr(
                    "entities.detail.fields.quality_score_hint",
                    "Índice de calidad global del registro (0-100%). Combina completitud, identificadores, enriquecimiento, validación y autoridad."
                ),
            },
        },
        {
            key: "attention_score",
            label: tr("entities.detail.attention.badge_label", "Atención externa"),
            value: attentionData
                ? `${attentionData.summary.attention_score}/100 · ${attentionData.summary.total_mentions} menciones · ${attentionData.summary.active_sources} fuentes`
                : null,
            badge: "attention",
            icon: "spark",
            hint: {
                title: tr("entities.detail.attention.badge_label", "Atención externa"),
                body: tr(
                    "entities.detail.fields.attention_score_hint",
                    "Señal de atención fuera del catálogo: menciones en noticias, políticas, repositorios, redes y web académica. No mide calidad académica."
                ),
            },
        },
        {
            key: "enrichment_citation_count",
            label: tr("entities.detail.fields.enrichment_citation_count", "Citas"),
            value: entity.enrichment_citation_count ?? 0,
            icon: "quote",
            hint: {
                title: tr("entities.detail.fields.enrichment_citation_count", "Citas"),
                body: tr(
                    "entities.detail.fields.enrichment_citation_count_hint",
                    "Número de citas detectadas por el proveedor académico para este registro (OpenAlex, Scholar, WoS)."
                ),
            },
        },
        {
            key: "enrichment_source",
            label: tr("entities.detail.enrichment.source", "Fuente académica"),
            value: entity.enrichment_source === "None" ? tr("common.none", "Ninguno") : entity.enrichment_source,
            icon: "cube",
            hint: {
                title: tr("entities.detail.enrichment.source", "Fuente académica"),
                body: tr(
                    "entities.detail.fields.enrichment_source_hint",
                    "Proveedor académico que entregó las señales enriquecidas: OpenAlex, Google Scholar, Web of Science, Crossref u otro."
                ),
            },
        },
        {
            key: "enrichment_doi",
            label: tr("entities.detail.fields.enrichment_doi", "DOI"),
            value: resolvedDoi,
            icon: "link",
            copyable: true,
            hint: {
                title: tr("entities.detail.fields.enrichment_doi", "DOI"),
                body: tr(
                    "entities.detail.fields.enrichment_doi_hint",
                    "Digital Object Identifier confirmado o inferido durante el enriquecimiento. Es la clave principal para deduplicación y referencia externa."
                ),
            },
        },
    ];
    const enrichmentPercent =
        entity.enrichment_status === "completed" ? 100 :
        entity.enrichment_status === "processing" ? 65 :
        entity.enrichment_status === "pending" ? 45 :
        entity.enrichment_status === "failed" ? 12 :
        0;
    const enrichmentHealthState = enrichmentHealth(enrichmentPercent);
    const enrichmentLabel = enrichmentStatusLabel(entity.enrichment_status, tr);
    const enrichmentFailure: EnrichmentFailureDetails | null = entity.enrichment_status === "failed"
        ? parseEnrichmentFailure(sourceAttributes.enrichment_failure) || fallbackEnrichmentFailure(entity, tr)
        : null;
    const enrichmentConcepts = entity.enrichment_concepts
        ? entity.enrichment_concepts.split(",").map((concept) => concept.trim()).filter(Boolean)
        : [];
    const sanitizedEnrichmentSource = entity.enrichment_source && entity.enrichment_source !== "None" ? entity.enrichment_source : "";
    const shortSource = sanitizedEnrichmentSource || entity.source || String(mergedAttributes.source_name || mergedAttributes.source || "");
    const attentionTimelineMax = attentionData?.timeline.length
        ? Math.max(...attentionData.timeline.map((item) => item.weighted_score), 1)
        : 1;
    const enrichmentSignals = [
        { label: tr("entities.detail.enrichment.status", "Estado"), value: enrichmentLabel, badge: "enrichment", icon: "shield" },
        { label: tr("entities.detail.enrichment.citations_detected", "Citas detectadas"), value: entity.enrichment_citation_count ?? 0, icon: "quote" },
        { label: tr("entities.detail.enrichment.academic_source", "Fuente académica"), value: entity.enrichment_source || shortSource || "—", icon: "database" },
        { label: tr("entities.detail.enrichment.normalized_doi", "DOI normalizado"), value: resolvedDoi, icon: "link", href: resolvedDoi ? `https://doi.org/${resolvedDoi}` : undefined },
    ];
    const displayedValuesByGroup: Record<string, unknown[]> = {
        title: [displayTitle, entity.primary_label],
        authors: [entity.secondary_label],
        identifier: [entity.canonical_id, resolvedDoi],
        entity_type: [resolvedEntityType],
        affiliation: [
            mergedAttributes.journal,
            mergedAttributes.venue,
            mergedAttributes.source_title,
            mergedAttributes.publisher,
            mergedAttributes.raw_so,
            mergedAttributes._source_name,
        ],
        citations: [entity.enrichment_citation_count],
        source: [entity.source, entity.enrichment_source, shortSource],
    };
    const extendedEntries = Object.entries(mergedAttributes).filter(
        ([key, value]) =>
            hasMeaningfulValue(value) &&
            !PRIMARY_ATTRIBUTE_KEYS.has(key) &&
            !SYSTEM_ATTRIBUTE_KEYS.has(key) &&
            !ABSTRACT_FIELD_KEYS.has(key) &&
            !hasDisplayedEquivalent(key, value, displayedValuesByGroup)
    );

    // Provenance split: distinguish ingested data, normalized data, and enrichment signals
    type ProvenanceEntry = {
        key: string;
        value: unknown;
        normalizedValue?: unknown; // present when source value was rewritten by normalization
    };
    const ingestionEntries: ProvenanceEntry[] = [];
    const normalizationEntries: ProvenanceEntry[] = [];
    const enrichmentExtraEntries: ProvenanceEntry[] = [];

    for (const [key, value] of extendedEntries) {
        const isEnrichmentField = key.startsWith("enrichment_") || key === "concepts";
        if (isEnrichmentField) {
            enrichmentExtraEntries.push({ key, value });
            continue;
        }
        const inSource = Object.prototype.hasOwnProperty.call(sourceAttributes, key);
        const inNormalized = Object.prototype.hasOwnProperty.call(normalizedAttributes, key);
        if (inNormalized && !inSource) {
            normalizationEntries.push({ key, value });
        } else if (inSource && inNormalized) {
            const srcVal = sourceAttributes[key];
            const normVal = normalizedAttributes[key];
            const same = comparableValue(srcVal) === comparableValue(normVal);
            if (same) {
                ingestionEntries.push({ key, value: srcVal });
            } else {
                ingestionEntries.push({ key, value: srcVal, normalizedValue: normVal });
            }
        } else {
            ingestionEntries.push({ key, value });
        }
    }

    const ingestionSourceLabel = entity.source
        ? (entity.source === "user" ? "Carga manual" : entity.source === "demo" ? "Datos demo" : entity.source)
        : "—";
    const academicEnrichmentSource = sanitizedEnrichmentSource || null;

    async function copyValue(value: unknown) {
        if (!value) return;
        await navigator.clipboard.writeText(String(value));
        toast("Copiado al portapapeles", "success");
    }

    return (
        <div className="-m-4 min-h-screen space-y-6 bg-[radial-gradient(circle_at_8%_0%,rgba(124,58,237,0.13),transparent_30%),radial-gradient(circle_at_100%_18%,rgba(59,130,246,0.10),transparent_28%),linear-gradient(180deg,#fbfcff_0%,#f7f8fc_100%)] p-4 text-slate-950 dark:bg-[radial-gradient(circle_at_8%_0%,rgba(124,58,237,0.20),transparent_30%),radial-gradient(circle_at_100%_18%,rgba(59,130,246,0.14),transparent_28%),linear-gradient(180deg,#020617_0%,#0f172a_100%)] dark:text-white sm:-m-6 sm:p-6 lg:-m-8 lg:p-8">
            <div className="mx-auto max-w-7xl space-y-6">
                <header className="space-y-6">
                    <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-500 dark:text-slate-400">
                        <Link href="/" className="transition-colors hover:text-violet-600 dark:hover:text-violet-300">
                            {tr("entities.detail.breadcrumb.home", "Inicio")}
                        </Link>
                        <span>/</span>
                        <Link href="/" className="transition-colors hover:text-violet-600 dark:hover:text-violet-300">
                            {tr("entities.detail.breadcrumb.explorer", "Explorador de Conocimiento")}
                        </Link>
                        <span>/</span>
                        <span className="font-semibold text-slate-700 dark:text-slate-200">{displayTitle}</span>
                    </div>

                    <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0 space-y-2">
                            <div className="flex flex-wrap items-center gap-3">
                                <h1 className="text-3xl font-black tracking-tight text-slate-950 dark:text-white md:text-4xl">
                                    {displayTitle}
                                </h1>
                                {attentionData ? (
                                    <span
                                        className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-bold ${attentionClass(attentionData.summary.category)}`}
                                        title={tr("entities.detail.attention.badge_tooltip", "Señal contextual: mide atención externa, no calidad académica.")}
                                    >
                                        <IconGlyph name="spark" className="h-3.5 w-3.5" />
                                        {tr("entities.detail.attention.badge_label", "Atención externa")}: {attentionLabel(attentionData.summary.category)}
                                        <span className="font-black">{attentionData.summary.attention_score}</span>
                                    </span>
                                ) : null}
                                <button
                                    type="button"
                                    className="rounded-xl p-2 text-slate-400 transition-colors hover:bg-violet-50 hover:text-violet-600 dark:hover:bg-white/10 dark:hover:text-violet-200"
                                    aria-label="Guardar registro"
                                >
                                    <IconGlyph name="bookmark" className="h-5 w-5" />
                                </button>
                            </div>
                            {description ? (
                                <p className="text-base font-medium text-slate-500 dark:text-slate-400">{description}</p>
                            ) : null}
                        </div>

                        <div className="flex flex-wrap items-center gap-3">
                            <div className="flex items-center gap-2 rounded-full bg-white/80 px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm ring-1 ring-slate-200 dark:bg-white/10 dark:text-slate-200 dark:ring-white/10">
                                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                                <PresenceAvatars presence={presence} isConnected={isConnected} />
                            </div>
                            {isEditing ? (
                                <>
                                    <button
                                        onClick={handleSave}
                                        disabled={saving}
                                        className="flex items-center gap-2 rounded-xl bg-violet-600 px-5 py-3 text-sm font-bold text-white shadow-[0_14px_35px_rgba(124,58,237,0.28)] transition hover:bg-violet-700 disabled:opacity-50"
                                    >
                                        {saving ? <Spinner /> : null}
                                        {tr("entities.detail.btn.save", "Guardar")}
                                    </button>
                                    <button
                                        onClick={cancelEdit}
                                        className="rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm font-bold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-white/10 dark:bg-white/10 dark:text-slate-200 dark:hover:bg-white/15"
                                    >
                                        {tr("entities.detail.btn.cancel", "Cancelar")}
                                    </button>
                                </>
                            ) : (
                                <button
                                    onClick={startEdit}
                                    className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm font-bold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-white/10 dark:bg-white/10 dark:text-slate-200 dark:hover:bg-white/15"
                                >
                                    <IconGlyph name="edit" className="h-4 w-4" />
                                    {tr("entities.detail.btn.edit", "Editar")}
                                </button>
                            )}
                            <button
                                onClick={handleEnrich}
                                disabled={enriching}
                                aria-busy={enriching}
                                className="flex min-w-[10.5rem] items-center justify-center gap-2 rounded-xl bg-violet-600 px-5 py-3 text-sm font-bold text-white shadow-[0_14px_35px_rgba(124,58,237,0.28)] transition hover:bg-violet-700 disabled:opacity-80"
                            >
                                {enriching ? <Spinner /> : <IconGlyph name="spark" className="h-4 w-4" />}
                                {enrichmentFeedbackActive && enrichmentPhase !== "complete"
                                    ? enrichmentFeedbackLabel
                                    : tr("entities.detail.btn.enrich", "Enriquecer")}
                            </button>
                        </div>
                    </div>

                    <nav className="flex gap-7 overflow-x-auto border-b border-slate-200 dark:border-white/10">
                        {DETAIL_TABS.map((item) => (
                            <button
                                key={item.id}
                                onClick={() => setTab(item.id)}
                                className={`relative whitespace-nowrap pb-4 text-sm font-bold transition-colors ${
                                    tab === item.id
                                        ? "text-violet-600 dark:text-violet-300"
                                        : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                                }`}
                            >
                                {tr(item.labelKey, labelize(item.id))}
                                {item.id === "comments" && commentCount > 0 ? (
                                    <span className="ml-2 rounded-full bg-violet-100 px-2 py-0.5 text-xs text-violet-700 dark:bg-violet-500/20 dark:text-violet-200">
                                        {commentCount}
                                    </span>
                                ) : null}
                                {tab === item.id ? (
                                    <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-violet-600 dark:bg-violet-300" />
                                ) : null}
                            </button>
                        ))}
                    </nav>

                    {enrichmentFeedbackActive ? (
                        <div
                            role={enrichmentPhase === "error" ? "alert" : "status"}
                            aria-live="polite"
                            className={`rounded-2xl border p-4 shadow-sm ${
                                enrichmentPhase === "error"
                                    ? "border-red-200 bg-red-50 text-red-800 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-100"
                                    : enrichmentPhase === "complete"
                                    ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-100"
                                    : "border-violet-200 bg-violet-50 text-violet-800 dark:border-violet-400/20 dark:bg-violet-400/10 dark:text-violet-100"
                            }`}
                        >
                            <div className="flex items-start gap-3">
                                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-white/80 text-violet-600 shadow-sm dark:bg-white/10 dark:text-violet-200">
                                    {enriching ? <Spinner /> : <IconGlyph name={enrichmentPhase === "error" ? "shield" : "spark"} className="h-4 w-4" />}
                                </span>
                                <div className="min-w-0">
                                    <p className="text-sm font-black">{enrichmentFeedbackLabel}</p>
                                    <p className="mt-1 text-xs font-semibold opacity-80">{enrichmentFeedbackDescription}</p>
                                </div>
                            </div>
                        </div>
                    ) : null}
                </header>

            {/* ── Overview ── */}
            {tab === "overview" && (
                <div className="space-y-6">
                    <section className={`${DETAIL_CARD} overflow-hidden p-6 md:p-8`}>
                        <div className="grid gap-8 lg:grid-cols-[0.95fr_1.25fr] lg:divide-x lg:divide-slate-200 dark:lg:divide-white/10">
                            <div className="space-y-8 lg:pr-8">
                                <div className="flex items-center gap-4">
                                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-600 dark:bg-violet-500/20 dark:text-violet-200">
                                        <IconGlyph name="quality" className="h-6 w-6" />
                                    </div>
                                    <h2 className="text-sm font-black uppercase tracking-[0.18em] text-violet-700 dark:text-violet-300">
                                        {tr("entities.detail.section.quality", "Puntuación de calidad")}
                                    </h2>
                                </div>
                                <div className="flex flex-col gap-8 sm:flex-row sm:items-center">
                                    <QualityRing
                                        percent={qualityPercent}
                                        label={tr("entities.detail.quality.ring_aria", "Índice de calidad global")}
                                    />
                                    <div className="min-w-0 flex-1 space-y-3">
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm font-bold text-slate-700 dark:text-slate-200">
                                                {tr("entities.detail.quality.overall", "Índice de Calidad Global")}
                                            </span>
                                            <QualityIndexTooltip
                                                ariaLabel={tr("entities.detail.quality.tooltip_aria", "Qué significa el Índice de Calidad Global")}
                                                title={tr("entities.detail.quality.tooltip_title", "Índice de Calidad Global")}
                                                body={tr("entities.detail.quality.tooltip_body", "Mide qué tan listo está este registro para el análisis ejecutivo dentro de UKIP. Combina completitud de metadatos, identificadores, enriquecimiento, validación, relaciones y señales de autoridad. No es una métrica de impacto académico ni de atención externa.")}
                                            />
                                        </div>
                                        <div className="h-3 max-w-xs rounded-full bg-slate-100 dark:bg-white/10">
                                            <div
                                                className={`h-3 rounded-full ${qualityHealthState.barClass}`}
                                                style={{ width: `${qualityPercent}%` }}
                                            />
                                        </div>
                                        {qualityData?.stored_score != null ? (
                                            <p className="text-xs font-medium text-slate-400">
                                                Puntuación almacenada {Math.round(normalizePercent(qualityData.stored_score))}%
                                            </p>
                                        ) : null}
                                    </div>
                                </div>
                            </div>
                            <div className="overflow-x-auto lg:pl-8">
                                <table className="w-full min-w-[560px] text-sm">
                                    <thead>
                                        <tr className="border-b border-slate-200 text-xs font-black uppercase tracking-[0.13em] text-slate-400 dark:border-white/10">
                                            <th className="pb-4 text-left">Dimension</th>
                                            <th className="pb-4 text-right">Peso</th>
                                            <th className="pb-4 text-right">Contribucion</th>
                                            <th className="pb-4 pl-8 text-left">Progreso</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-100 dark:divide-white/10">
                                        {qualityRows.map((row) => {
                                            const progress = row.weight > 0 ? Math.min(100, (row.contribution / row.weight) * 100) : 0;
                                            return (
                                                <tr key={row.key}>
                                                    <td className="py-3.5">
                                                        <div className="flex items-center gap-3">
                                                            <span className="text-violet-600 dark:text-violet-300">
                                                                <IconGlyph name={row.icon} className="h-5 w-5" />
                                                            </span>
                                                            <span className="font-bold text-slate-700 dark:text-slate-200">{row.label}</span>
                                                        </div>
                                                    </td>
                                                    <td className="py-3.5 text-right font-semibold text-slate-500 dark:text-slate-400">{Math.round(row.weight)}%</td>
                                                    <td className="py-3.5 text-right font-black text-violet-600 dark:text-violet-300">+{Math.round(row.contribution)}%</td>
                                                    <td className="py-3.5 pl-8">
                                                        <div className="h-2 w-36 rounded-full bg-slate-100 dark:bg-white/10">
                                                            <div className="h-2 rounded-full bg-violet-500" style={{ width: `${progress}%` }} />
                                                        </div>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </section>

                    <div className="grid gap-6 lg:grid-cols-2">
                        <section className={`${DETAIL_CARD} p-6 md:p-8`}>
                            <div className="mb-7 flex items-center gap-4">
                                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-600 dark:bg-violet-500/20 dark:text-violet-200">
                                    <IconGlyph name="file" className="h-6 w-6" />
                                </div>
                                <h2 className="text-sm font-black uppercase tracking-[0.18em] text-violet-700 dark:text-violet-300">
                                    Campos principales
                                </h2>
                            </div>
                            <div className="grid grid-cols-1 gap-x-8 gap-y-5 md:grid-cols-2">
                                {primaryFields.map((field) => {
                                    const value = isEditing && CORE_FIELDS.includes(field.key as keyof Entity)
                                        ? editData[field.key as keyof Entity]
                                        : field.value;

                                return (
                                    <div key={field.key} className={DETAIL_ROW}>
                                        <div className="flex items-center gap-3 text-violet-600 dark:text-violet-300">
                                            <IconGlyph name={field.icon} className="h-5 w-5" />
                                            <span className="flex items-center gap-1.5 text-[11px] font-black uppercase tracking-[0.15em] text-slate-400">
                                                {field.label}
                                                {field.hint ? (
                                                    <FieldHint
                                                        title={field.hint.title}
                                                        body={field.hint.body}
                                                        ariaLabel={tr("entities.detail.fields.hint_aria", "Más información sobre este campo")}
                                                    />
                                                ) : null}
                                            </span>
                                        </div>
                                        {isEditing ? (
                                            <input
                                                value={(value as string) ?? ""}
                                                onChange={(e) => setEditData({ ...editData, [field.key]: e.target.value })}
                                                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold outline-none transition focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 dark:border-white/10 dark:bg-white/10 dark:text-white"
                                            />
                                        ) : (
                                            <div className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-slate-200">
                                                <span className="break-words">{formatValue(value)}</span>
                                                {field.copyable && hasMeaningfulValue(value) ? (
                                                    <button
                                                        onClick={() => copyValue(value)}
                                                        className="rounded-lg p-1 text-slate-400 transition hover:bg-violet-50 hover:text-violet-600 dark:hover:bg-white/10"
                                                        aria-label={`Copiar ${field.label}`}
                                                    >
                                                        <IconGlyph name="link" className="h-4 w-4" />
                                                    </button>
                                                ) : null}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                            </div>
                        </section>

                        <section className={`${DETAIL_CARD} p-6 md:p-8`}>
                            <div className="mb-7 flex items-center gap-4">
                                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-600 dark:bg-violet-500/20 dark:text-violet-200">
                                    <IconGlyph name="spark" className="h-6 w-6" />
                                </div>
                                <h2 className="text-sm font-black uppercase tracking-[0.18em] text-violet-700 dark:text-violet-300">
                                    Senales del sistema
                                </h2>
                            </div>
                            <div className="grid grid-cols-1 gap-x-8 gap-y-5 md:grid-cols-2">
                                {systemFields.map((field) => (
                                    <div key={field.key} className={DETAIL_ROW}>
                                        <div className="flex items-center gap-3 text-violet-600 dark:text-violet-300">
                                            <IconGlyph name={field.icon} className="h-5 w-5" />
                                            <span className="flex items-center gap-1.5 text-[11px] font-black uppercase tracking-[0.15em] text-slate-400">
                                                {field.label}
                                                {field.hint ? (
                                                    <FieldHint
                                                        title={field.hint.title}
                                                        body={field.hint.body}
                                                        ariaLabel={tr("entities.detail.fields.hint_aria", "Más información sobre este campo")}
                                                    />
                                                ) : null}
                                            </span>
                                        </div>
                                        {field.badge === "validation" && entity.validation_status ? (
                                            <Badge variant={validationVariant(entity.validation_status)}>
                                                {entity.validation_status}
                                            </Badge>
                                        ) : field.badge === "enrichment" && entity.enrichment_status ? (
                                            <Badge variant={enrichmentVariant(entity.enrichment_status)}>
                                                {enrichmentLabel}
                                            </Badge>
                                        ) : field.badge === "attention" && attentionData ? (
                                            <span className={`inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1 text-xs font-bold ${attentionClass(attentionData.summary.category)}`}>
                                                {attentionLabel(attentionData.summary.category)}
                                                <span className="font-black">{attentionData.summary.attention_score}</span>
                                            </span>
                                        ) : (
                                            <div className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-slate-200">
                                                <span className="break-words">{formatValue(field.value)}</span>
                                                {field.copyable && hasMeaningfulValue(field.value) ? (
                                                    <button
                                                        onClick={() => copyValue(field.value)}
                                                        className="rounded-lg p-1 text-slate-400 transition hover:bg-violet-50 hover:text-violet-600 dark:hover:bg-white/10"
                                                        aria-label={`Copiar ${field.label}`}
                                                    >
                                                        <IconGlyph name="link" className="h-4 w-4" />
                                                    </button>
                                                ) : null}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                            {attentionData && attentionData.source_breakdown.length > 0 ? (
                                <div className="mt-7 rounded-2xl border border-slate-100 bg-slate-50/70 p-4 dark:border-white/10 dark:bg-white/5">
                                    <div className="mb-4 flex items-center justify-between gap-3">
                                        <div>
                                            <p className="text-[11px] font-black uppercase tracking-[0.15em] text-slate-400">
                                                {tr("entities.detail.attention.composition_title", "Composición de atención")}
                                            </p>
                                            <p className="mt-1 text-xs font-semibold text-slate-500 dark:text-slate-400">
                                                {tr("entities.detail.attention.composition_help", "Contribución por fuente; no representa calidad académica.")}
                                            </p>
                                        </div>
                                        <span className="rounded-full bg-white px-3 py-1 text-xs font-black text-violet-600 shadow-sm dark:bg-white/10 dark:text-violet-200">
                                            {attentionData.summary.active_sources} fuentes
                                        </span>
                                    </div>
                                    <div className="space-y-3">
                                        {attentionData.source_breakdown.slice(0, 4).map((source) => (
                                            <div key={source.source_type} className="grid gap-2">
                                                <div className="flex items-center justify-between gap-3 text-xs font-bold">
                                                    <span className="text-slate-600 dark:text-slate-300">
                                                        {attentionSourceLabel(source.source_type)}
                                                    </span>
                                                    <span className="text-slate-400">
                                                        {source.mentions} menciones · {Math.round(source.share * 100)}%
                                                    </span>
                                                </div>
                                                <div className="h-2 rounded-full bg-white dark:bg-white/10">
                                                    <div
                                                        className="h-2 rounded-full bg-violet-500"
                                                        style={{ width: `${Math.max(3, Math.round(source.share * 100))}%` }}
                                                    />
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ) : null}
                            {attentionData && attentionData.timeline.length > 0 ? (
                                <div className="mt-4 rounded-2xl border border-slate-100 bg-white/70 p-4 dark:border-white/10 dark:bg-white/5">
                                    <div className="mb-4 flex items-center justify-between gap-3">
                                        <div>
                                            <p className="text-[11px] font-black uppercase tracking-[0.15em] text-slate-400">
                                                Timeline de atencion
                                            </p>
                                            <p className="mt-1 text-xs font-semibold text-slate-500 dark:text-slate-400">
                                                Evolucion mensual desde observaciones externas.
                                            </p>
                                        </div>
                                        {attentionData.timeline.some((bucket) => bucket.spike) ? (
                                            <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-black text-amber-700 ring-1 ring-amber-200 dark:bg-amber-400/10 dark:text-amber-200 dark:ring-amber-400/20">
                                                Spike
                                            </span>
                                        ) : null}
                                    </div>
                                    <div className="flex items-end gap-2 overflow-x-auto pb-1">
                                        {attentionData.timeline.slice(-8).map((bucket) => {
                                            const height = Math.max(12, Math.round((bucket.weighted_score / attentionTimelineMax) * 64));
                                            return (
                                                <div key={bucket.period} className="flex min-w-12 flex-col items-center gap-2">
                                                    <div
                                                        className={`w-8 rounded-t-xl ${bucket.spike ? "bg-amber-400" : "bg-violet-500"}`}
                                                        style={{ height }}
                                                        title={`${bucket.period}: ${bucket.mentions} menciones`}
                                                    />
                                                    <span className="text-[10px] font-bold text-slate-400">
                                                        {bucket.period.slice(5)}
                                                    </span>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            ) : null}
                            {attentionData && attentionData.explanations.length > 0 ? (
                                <div className="mt-4 rounded-2xl border border-slate-100 bg-slate-50/70 p-4 dark:border-white/10 dark:bg-white/5">
                                    <div className="mb-4">
                                        <p className="text-[11px] font-black uppercase tracking-[0.15em] text-slate-400">
                                            Explicaciones
                                        </p>
                                        <p className="mt-1 text-xs font-semibold text-slate-500 dark:text-slate-400">
                                            Evidencia compacta que explica por que cambia la atencion.
                                        </p>
                                    </div>
                                    <div className="space-y-3">
                                        {attentionData.explanations.slice(0, 3).map((explanation) => (
                                            <div key={`${explanation.type}-${explanation.label}`} className="rounded-xl bg-white p-3 shadow-sm ring-1 ring-slate-100 dark:bg-white/5 dark:ring-white/10">
                                                <div className="flex items-start gap-3">
                                                    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-violet-50 text-violet-600 dark:bg-violet-400/10 dark:text-violet-200">
                                                        <IconGlyph name={explanation.type === "attention_spike" ? "chart" : "spark"} className="h-4 w-4" />
                                                    </span>
                                                    <div className="min-w-0">
                                                        <p className="text-sm font-bold text-slate-700 dark:text-slate-200">
                                                            {explanation.label}
                                                        </p>
                                                        <p className="mt-1 text-xs font-medium leading-5 text-slate-500 dark:text-slate-400">
                                                            {explanation.evidence}
                                                        </p>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ) : null}
                            {attentionData && attentionData.alerts.length > 0 ? (
                                <div className="mt-4 rounded-2xl border border-slate-100 bg-white/70 p-4 dark:border-white/10 dark:bg-white/5">
                                    <div className="mb-4 flex items-center justify-between gap-3">
                                        <div>
                                            <p className="text-[11px] font-black uppercase tracking-[0.15em] text-slate-400">
                                                Alertas de atencion
                                            </p>
                                            <p className="mt-1 text-xs font-semibold text-slate-500 dark:text-slate-400">
                                                Reglas accionables sobre cambios y fuentes externas.
                                            </p>
                                        </div>
                                        <span className="rounded-full bg-slate-50 px-3 py-1 text-xs font-black text-slate-500 ring-1 ring-slate-200 dark:bg-white/10 dark:text-slate-300 dark:ring-white/10">
                                            {attentionData.alerts.length}
                                        </span>
                                    </div>
                                    <div className="space-y-2">
                                        {attentionData.alerts.slice(0, 3).map((alert) => (
                                            <div key={`${alert.type}-${alert.period ?? "current"}`} className={`rounded-xl border p-3 ${alertClass(alert.severity)}`}>
                                                <div className="flex items-start justify-between gap-3">
                                                    <div className="min-w-0">
                                                        <p className="text-sm font-bold">{alert.label}</p>
                                                        <p className="mt-1 text-xs font-medium leading-5 opacity-80">{alert.evidence}</p>
                                                    </div>
                                                    <span className="shrink-0 rounded-full bg-white/70 px-2 py-0.5 text-[10px] font-black uppercase tracking-wide dark:bg-white/10">
                                                        {alert.confidence}
                                                    </span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ) : null}
                        </section>
                    </div>

                    {abstractMapping && (
                        <section className={`${DETAIL_CARD} p-6 md:p-8`}>
                            <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
                                <div className="flex items-center gap-4">
                                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-100 text-blue-600 dark:bg-blue-500/20 dark:text-blue-200">
                                        <IconGlyph name="file" className="h-6 w-6" />
                                    </div>
                                    <div>
                                        <h2 className="text-sm font-black uppercase tracking-[0.18em] text-blue-700 dark:text-blue-300">
                                            {tr("page.entity_table.section_abstract", "Abstract / resumen")}
                                        </h2>
                                        <p className="mt-1 text-xs font-semibold text-slate-400">
                                            {tr("page.entity_table.abstract_source", "Fuente mapeada")}: {abstractMapping.source}
                                        </p>
                                    </div>
                                </div>
                                <div className="flex flex-wrap items-center gap-2">
                                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-500 dark:bg-white/10 dark:text-slate-300">
                                        {t("page.entity_table.abstract_word_count", { count: wordCount(abstractMapping.text) })}
                                    </span>
                                    <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700 ring-1 ring-emerald-100 dark:bg-emerald-400/10 dark:text-emerald-200 dark:ring-emerald-400/20">
                                        {tr("page.entity_table.abstract_pattern_ready", "Listo para análisis de patrones")}
                                    </span>
                                </div>
                            </div>
                            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-5 dark:border-white/10 dark:bg-white/5">
                                <span className="mb-3 block text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">
                                    {abstractMapping.label}
                                </span>
                                <p className="whitespace-pre-wrap text-sm font-medium leading-7 text-slate-700 dark:text-slate-200">
                                    {abstractMapping.text}
                                </p>
                            </div>
                        </section>
                    )}

                    {(() => {
                        const iconFor = (key: string) =>
                            key.includes("author") || key.includes("orcid") ? "user" :
                            key.includes("year") || key.includes("date") || key.includes("retrieved") ? "calendar" :
                            key.includes("institution") || key.includes("affiliation") ? "institution" :
                            key.includes("citation") || key.includes("count") ? "chart" :
                            key.includes("doi") || key.includes("id") || key.includes("url") ? "link" :
                            key.includes("source") ? "database" : "file";

                        const renderRow = (entry: ProvenanceEntry, accent: string) => {
                            const hintBody = fieldHintFor(entry.key);
                            const fieldName = fieldLabel(entry.key);
                            const richStructured = isRichStructuredValue(entry.value);
                            return (
                            <div key={entry.key} className={`grid grid-cols-[1.5rem_1fr] gap-x-4 border-b border-slate-100 pb-5 dark:border-white/10 ${richStructured ? "lg:col-span-2" : ""}`}>
                                <span className={`mt-1 ${accent}`}>
                                    <IconGlyph name={iconFor(entry.key)} className="h-5 w-5" />
                                </span>
                                <div className="min-w-0 space-y-1">
                                    <span className="flex items-center gap-1.5 text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">
                                        {fieldName}
                                        {hintBody ? (
                                            <FieldHint
                                                title={fieldName}
                                                body={hintBody}
                                                ariaLabel={tr("entities.detail.fields.hint_aria", "Más información sobre este campo")}
                                            />
                                        ) : null}
                                    </span>
                                    <div className="block min-w-0 break-words text-sm font-bold leading-6 text-slate-700 dark:text-slate-200">
                                        <StructuredFieldValue value={entry.value} fieldKey={entry.key} />
                                    </div>
                                    {entry.normalizedValue !== undefined ? (
                                        <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-blue-700 ring-1 ring-blue-100 dark:bg-blue-400/10 dark:text-blue-200 dark:ring-blue-400/20">
                                            Normalizado: {formatValue(entry.normalizedValue)}
                                        </span>
                                    ) : null}
                                </div>
                            </div>
                            );
                        };

                        return (
                            <>
                                {ingestionEntries.length > 0 && (
                                    <section className={`${DETAIL_CARD} p-6 md:p-8`}>
                                        <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
                                            <div className="flex items-center gap-4">
                                                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-700 dark:bg-white/10 dark:text-slate-200">
                                                    <IconGlyph name="database" className="h-6 w-6" />
                                                </div>
                                                <div>
                                                    <h2 className="text-sm font-black uppercase tracking-[0.18em] text-slate-700 dark:text-slate-200">
                                                        {tr("entities.detail.section.ingested", "Datos de la fuente original")}
                                                    </h2>
                                                    <p className="mt-1 text-xs font-semibold text-slate-400">
                                                        {tr("entities.detail.section.ingested_subtitle", "Tal como llegaron desde la ingesta")}: <span className="font-bold text-slate-600 dark:text-slate-300">{ingestionSourceLabel}</span>
                                                    </p>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-bold uppercase tracking-wide text-white dark:bg-white/15">
                                                    {ingestionSourceLabel}
                                                </span>
                                                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-500 dark:bg-white/10 dark:text-slate-300">
                                                    {ingestionEntries.length} {tr("entities.detail.section.fields_suffix", "campos")}
                                                </span>
                                            </div>
                                        </div>
                                        <div className="grid grid-cols-1 gap-x-10 gap-y-5 lg:grid-cols-2">
                                            {ingestionEntries.map((entry) => renderRow(entry, "text-slate-500 dark:text-slate-300"))}
                                        </div>
                                    </section>
                                )}

                                {normalizationEntries.length > 0 && (
                                    <section className={`${DETAIL_CARD} p-6 md:p-8`}>
                                        <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
                                            <div className="flex items-center gap-4">
                                                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-200">
                                                    <IconGlyph name="shield" className="h-6 w-6" />
                                                </div>
                                                <div>
                                                    <h2 className="text-sm font-black uppercase tracking-[0.18em] text-blue-700 dark:text-blue-300">
                                                        {tr("entities.detail.section.normalized", "Campos normalizados")}
                                                    </h2>
                                                    <p className="mt-1 text-xs font-semibold text-slate-400">
                                                        {tr("entities.detail.section.normalized_subtitle", "Generados o reescritos por harmonización / reglas")}
                                                    </p>
                                                </div>
                                            </div>
                                            <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700 ring-1 ring-blue-100 dark:bg-blue-400/10 dark:text-blue-200 dark:ring-blue-400/20">
                                                {normalizationEntries.length} {tr("entities.detail.section.fields_suffix", "campos")}
                                            </span>
                                        </div>
                                        <div className="grid grid-cols-1 gap-x-10 gap-y-5 lg:grid-cols-2">
                                            {normalizationEntries.map((entry) => renderRow(entry, "text-blue-600 dark:text-blue-300"))}
                                        </div>
                                    </section>
                                )}

                                {(enrichmentExtraEntries.length > 0 || academicEnrichmentSource) && (
                                    <section className={`${DETAIL_CARD} p-6 md:p-8`}>
                                        <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
                                            <div className="flex items-center gap-4">
                                                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-700 dark:bg-violet-500/20 dark:text-violet-200">
                                                    <IconGlyph name="spark" className="h-6 w-6" />
                                                </div>
                                                <div>
                                                    <h2 className="text-sm font-black uppercase tracking-[0.18em] text-violet-700 dark:text-violet-300">
                                                        {tr("entities.detail.section.enrichment_provider", "Señales enriquecidas")}
                                                    </h2>
                                                    <p className="mt-1 text-xs font-semibold text-slate-400">
                                                        {academicEnrichmentSource
                                                            ? `${tr("entities.detail.section.enrichment_subtitle", "Proveedor académico")}: ${academicEnrichmentSource}`
                                                            : tr("entities.detail.section.enrichment_subtitle_empty", "Sin proveedor académico todavía")}
                                                    </p>
                                                </div>
                                            </div>
                                            {academicEnrichmentSource ? (
                                                <Badge variant={sourceVariant(academicEnrichmentSource.toLowerCase())}>
                                                    {academicEnrichmentSource.toUpperCase()}
                                                </Badge>
                                            ) : null}
                                        </div>
                                        {enrichmentExtraEntries.length > 0 ? (
                                            <div className="grid grid-cols-1 gap-x-10 gap-y-5 lg:grid-cols-2">
                                                {enrichmentExtraEntries.map((entry) => renderRow(entry, "text-violet-600 dark:text-violet-300"))}
                                            </div>
                                        ) : (
                                            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                                                {tr("entities.detail.section.enrichment_only_columns", "Revisa la pestaña 'Enriquecimiento' para ver el detalle del proveedor.")}
                                            </p>
                                        )}
                                    </section>
                                )}
                            </>
                        );
                    })()}
                </div>
            )}

            {/* ── Enrichment ── */}
            {tab === "enrichment" && (
                <div className="space-y-6">
                    <section className={`${DETAIL_CARD} overflow-hidden p-6 md:p-8`}>
                        <div className="grid gap-8 lg:grid-cols-[0.85fr_1.15fr] lg:divide-x lg:divide-slate-200 dark:lg:divide-white/10">
                            <div className="space-y-7 lg:pr-8">
                                <div className="flex items-center gap-4">
                                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-600 dark:bg-violet-500/20 dark:text-violet-200">
                                        <IconGlyph name="spark" className="h-6 w-6" />
                                    </div>
                                    <div>
                                        <p className="text-xs font-black uppercase tracking-[0.18em] text-violet-700 dark:text-violet-300">
                                            {tr("entities.detail.tab.enrichment", "Enriquecimiento")}
                                        </p>
                                        <h2 className="mt-1 text-2xl font-black tracking-tight text-slate-950 dark:text-white">
                                            {tr("entities.detail.enrichment.coverage_title", "Cobertura académica del registro")}
                                        </h2>
                                    </div>
                                </div>
                                <div className={`rounded-[1.25rem] p-5 text-white ${enrichmentHealthState.panelClass}`}>
                                    <div className="flex items-end justify-between gap-4">
                                        <div>
                                            <p className="text-xs font-bold uppercase tracking-[0.18em] text-white/70">
                                                {tr("entities.detail.quality.progress", "Progreso")}
                                            </p>
                                            <p className="mt-2 text-5xl font-black tracking-tight">{enrichmentPercent}%</p>
                                        </div>
                                        <Badge variant={enrichmentVariant(entity.enrichment_status)}>
                                            {enrichmentLabel}
                                        </Badge>
                                    </div>
                                    <div className="mt-5 h-3 rounded-full bg-white/20">
                                        <div className={`h-3 rounded-full ${enrichmentHealthState.barClass}`} style={{ width: `${enrichmentPercent}%` }} />
                                    </div>
                                    <p className="mt-4 text-sm font-medium leading-6 text-white/82">
                                        {entity.enrichment_status === "completed"
                                            ? tr("entities.detail.enrichment.summary_completed", "El registro ya tiene señales enriquecidas listas para análisis, impacto y brief.")
                                            : entity.enrichment_status === "processing"
                                            ? tr("entities.detail.enrichment.summary_processing", "El enriquecimiento está procesando el registro. Espera a que termine antes de reintentar.")
                                            : entity.enrichment_status === "pending"
                                            ? tr("entities.detail.enrichment.summary_pending", "El enriquecimiento está en proceso. La lectura ejecutiva debe esperar a que termine la normalización.")
                                            : entity.enrichment_status === "failed"
                                            ? tr("entities.detail.enrichment.summary_failed", "El intento de enriquecimiento falló. Conviene reintentar o revisar DOI, fuente y metadatos base.")
                                            : tr("entities.detail.enrichment.summary_idle", "Ejecuta el enriquecimiento para conectar el registro con citas, DOI, conceptos y fuentes académicas.")}
                                    </p>
                                </div>
                                {enrichmentFailure ? (
                                    <div className="rounded-2xl border border-rose-200 bg-rose-50/80 p-4 text-rose-950 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-100">
                                        <p className="text-[11px] font-black uppercase tracking-[0.16em] text-rose-600 dark:text-rose-200">
                                            {tr("entities.detail.enrichment.failure_title", "Evidencia del fallo")}
                                        </p>
                                        <p className="mt-2 text-sm font-semibold leading-6">
                                            {enrichmentFailure.evidence || tr("entities.detail.enrichment.failure_generic", "No se obtuvo una coincidencia confiable con las fuentes de enriquecimiento disponibles.")}
                                        </p>
                                        {enrichmentFailure.provider_attempts && enrichmentFailure.provider_attempts.length > 0 ? (
                                            <p className="mt-3 text-xs font-bold text-rose-700 dark:text-rose-200">
                                                {tr("entities.detail.enrichment.failure_sources", "Fuentes consultadas")}: {enrichmentFailure.provider_attempts.join(", ")}
                                            </p>
                                        ) : null}
                                        {enrichmentFailure.recommendations && enrichmentFailure.recommendations.length > 0 ? (
                                            <div className="mt-4">
                                                <p className="text-[11px] font-black uppercase tracking-[0.16em] text-rose-600 dark:text-rose-200">
                                                    {tr("entities.detail.enrichment.failure_recommendations", "Recomendaciones")}
                                                </p>
                                                <ul className="mt-2 space-y-2 text-sm font-medium leading-5">
                                                    {enrichmentFailure.recommendations.map((recommendation) => (
                                                        <li key={recommendation} className="flex gap-2">
                                                            <span aria-hidden="true">-</span>
                                                            <span>{recommendation}</span>
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        ) : null}
                                    </div>
                                ) : null}
                            </div>

                            <div className="grid gap-5 sm:grid-cols-2 lg:pl-8">
                                {enrichmentSignals.map((signal) => (
                                    <div key={signal.label} className="grid grid-cols-[2.5rem_1fr] gap-4 rounded-2xl border border-slate-100 bg-slate-50/80 p-4 dark:border-white/10 dark:bg-white/5">
                                        <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white text-violet-600 shadow-sm dark:bg-white/10 dark:text-violet-200">
                                            <IconGlyph name={signal.icon} className="h-5 w-5" />
                                        </span>
                                        <div className="min-w-0 space-y-1">
                                            <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">{signal.label}</p>
                                            {signal.badge === "enrichment" && entity.enrichment_status ? (
                                                <Badge variant={enrichmentVariant(entity.enrichment_status)}>
                                                    {enrichmentLabel}
                                                </Badge>
                                            ) : signal.href ? (
                                                <a href={signal.href} target="_blank" rel="noopener noreferrer" className="block truncate text-sm font-black text-violet-600 hover:underline dark:text-violet-300">
                                                    {formatValue(signal.value)}
                                                </a>
                                            ) : (
                                                <p className="break-words text-sm font-black text-slate-700 dark:text-slate-200">
                                                    {formatValue(signal.value)}
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </section>

                    <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
                        <section className={`${DETAIL_CARD} p-6 md:p-8 lg:col-span-2`}>
                            <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
                                <div className="flex items-center gap-4">
                                    <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 dark:bg-blue-400/10 dark:text-blue-200">
                                        <SoftIcon type="keyword" />
                                    </div>
                                    <div>
                                        <p className="flex items-center gap-3 text-3xl font-black tracking-tight text-slate-950 dark:text-white">
                                            {tr("entities.detail.section.enrichment_provider", "Señales enriquecidas")}
                                            <span className="text-blue-600 dark:text-blue-300"><SoftIcon type="info" /></span>
                                        </p>
                                        <p className="mt-2 text-base font-semibold text-slate-500 dark:text-slate-400">
                                            {tr("entities.detail.section.enrichment_subtitle", "Información enriquecida proveniente de proveedores académicos.")}
                                        </p>
                                    </div>
                                </div>
                                {academicEnrichmentSource ? (
                                    <Badge variant={sourceVariant(academicEnrichmentSource.toLowerCase())}>
                                        {academicEnrichmentSource.toUpperCase()}
                                    </Badge>
                                ) : null}
                            </div>
                            {academicEnrichmentSource ? (
                                <div className="mb-6 flex flex-wrap items-center gap-5 rounded-2xl border border-blue-100 bg-blue-50/50 px-5 py-4 text-base font-bold text-slate-600 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-slate-200">
                                    <span className="text-slate-900 dark:text-white"><SoftIcon type="openalex" /></span>
                                    <span className="text-blue-600 dark:text-blue-300">{academicEnrichmentSource.toUpperCase()}</span>
                                    <span className="hidden h-8 w-px bg-slate-200 dark:bg-white/10 sm:block" />
                                    <span className="flex items-center gap-3">
                                        <SoftIcon type="institution" />
                                        {tr("entities.detail.section.enrichment_subtitle", "Proveedor académico")}: <span className="text-blue-600 dark:text-blue-300">{academicEnrichmentSource}</span>
                                    </span>
                                </div>
                            ) : null}
                            {enrichmentConcepts.length > 0 ? (
                                <ExternalIdList values={enrichmentConcepts} />
                            ) : (
                                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 p-6 text-sm font-semibold text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-400">
                                    {tr("entities.detail.enrichment.concepts_empty", "Aún no hay conceptos enriquecidos. Ejecuta el enriquecimiento para activar esta capa semántica.")}
                                </div>
                            )}
                            <div className="mt-5 flex items-center gap-3 text-sm font-bold text-slate-500 dark:text-slate-400">
                                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-50 text-blue-600 dark:bg-blue-400/10 dark:text-blue-200">
                                    <SoftIcon type="info" />
                                </span>
                                Datos proporcionados por {academicEnrichmentSource ?? "proveedor académico"}.
                            </div>
                        </section>

                        <section className={`${DETAIL_CARD} p-6 md:p-8`}>
                            <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
                                <div className="flex items-center gap-4">
                                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-600 dark:bg-violet-500/20 dark:text-violet-200">
                                        <IconGlyph name="chart" className="h-6 w-6" />
                                    </div>
                                    <div>
                                        <p className="text-xs font-black uppercase tracking-[0.18em] text-violet-700 dark:text-violet-300">
                                            {tr("entities.detail.enrichment.projection_title", "Proyección de impacto")}
                                        </p>
                                        <p className="mt-1 text-sm font-semibold text-slate-400">
                                            {tr("entities.detail.enrichment.projection_subtitle", "Simulación conectada al registro enriquecido")}
                                        </p>
                                    </div>
                                </div>
                                {entity.enrichment_status !== "pending" && entity.enrichment_status !== "processing" && entity.enrichment_status !== "completed" ? (
                                    <button
                                        onClick={handleEnrich}
                                        disabled={enriching}
                                        className="flex items-center gap-2 rounded-xl bg-violet-600 px-5 py-3 text-sm font-bold text-white shadow-[0_14px_35px_rgba(124,58,237,0.28)] transition hover:bg-violet-700 disabled:opacity-50"
                                    >
                                        {enriching ? <Spinner /> : <IconGlyph name="spark" className="h-4 w-4" />}
                                        {enriching ? tr("entities.detail.btn.enriching", "Enriqueciendo") : tr("entities.detail.btn.enrich_now", "Enriquecer ahora")}
                                    </button>
                                ) : null}
                            </div>
                            {entity.enrichment_status === "completed" ? (
                                <MonteCarloChart productId={entity.id} />
                            ) : (
                                <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 p-8 text-center dark:border-white/10 dark:bg-white/5">
                                    <IconGlyph name="spark" className="mb-4 h-10 w-10 text-violet-500 dark:text-violet-300" />
                                    <p className="max-w-md text-sm font-bold leading-6 text-slate-500 dark:text-slate-400">
                                        {entity.enrichment_status === "failed"
                                            ? tr("entities.detail.projection.empty_failed", "No se pudo completar el enriquecimiento. Reintenta para recalcular conceptos, DOI, citas y proyección.")
                                            : entity.enrichment_status === "pending" || entity.enrichment_status === "processing"
                                            ? tr("entities.detail.projection.empty_pending", "El enriquecimiento sigue en proceso. La proyección aparecerá cuando el estado cambie a completado.")
                                            : tr("entities.detail.projection.empty_idle", "La proyección se activa cuando el registro queda enriquecido con señales académicas confiables.")}
                                    </p>
                                </div>
                            )}
                        </section>
                    </div>
                </div>
            )}

            {/* ── Graph ── */}
            {tab === "graph" && (
                <div className="space-y-6">
                    <section className={`${DETAIL_CARD} overflow-hidden p-6 md:p-8`}>
                        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
                            <div className="flex items-center gap-4">
                                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-600 dark:bg-violet-500/20 dark:text-violet-200">
                                    <IconGlyph name="nodes" className="h-6 w-6" />
                                </div>
                                <div>
                                    <p className="text-xs font-black uppercase tracking-[0.18em] text-violet-700 dark:text-violet-300">
                                        Grafo de conocimiento
                                    </p>
                                    <h2 className="mt-1 text-2xl font-black tracking-tight text-slate-950 dark:text-white">
                                        Relaciones activas del registro
                                    </h2>
                                </div>
                            </div>
                            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-500 dark:bg-white/10 dark:text-slate-300">
                                Registro #{entity.id}
                            </span>
                        </div>
                        <div className="rounded-[1.25rem] border border-slate-100 bg-slate-50/70 p-3 dark:border-white/10 dark:bg-white/5">
                        <EntityGraph key={graphKey} entityId={entity.id} />
                        </div>
                    </section>

                    <section className={`${DETAIL_CARD} p-6 md:p-8`}>
                        <div className="mb-6 flex items-center gap-4">
                            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-600 dark:bg-violet-500/20 dark:text-violet-200">
                                <IconGlyph name="link" className="h-6 w-6" />
                            </div>
                            <div>
                                <p className="text-xs font-black uppercase tracking-[0.18em] text-violet-700 dark:text-violet-300">
                                    {tr("entities.detail.relationships.title", "Gestión de relaciones")}
                                </p>
                                <p className="mt-1 text-sm font-semibold text-slate-400">
                                    {tr("entities.detail.relationships.subtitle", "Crea, edita o refresca conexiones semánticas para este registro.")}
                                </p>
                            </div>
                        </div>
                        <div className="rounded-[1.25rem] border border-slate-100 bg-slate-50/70 p-4 dark:border-white/10 dark:bg-white/5">
                        <RelationshipManager
                            entityId={entity.id}
                            onRefreshGraph={() => setGraphKey((k) => k + 1)}
                        />
                        </div>
                    </section>
                </div>
            )}

            {/* ── Comments ── */}
            {tab === "comments" && (
                <section className={`${DETAIL_CARD} p-6 md:p-8`}>
                    <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-600 dark:bg-violet-500/20 dark:text-violet-200">
                                <IconGlyph name="quote" className="h-6 w-6" />
                            </div>
                            <div>
                                <p className="text-xs font-black uppercase tracking-[0.18em] text-violet-700 dark:text-violet-300">
                                    Comentarios y trazabilidad
                                </p>
                                <h2 className="mt-1 text-2xl font-black tracking-tight text-slate-950 dark:text-white">
                                    Conversacion analitica del registro
                                </h2>
                            </div>
                        </div>
                        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-500 dark:bg-white/10 dark:text-slate-300">
                            {commentCount} notas
                        </span>
                    </div>
                    <div className="rounded-[1.25rem] border border-slate-100 bg-slate-50/70 p-4 dark:border-white/10 dark:bg-white/5">
                        <AnnotationThread entityId={entity.id} />
                    </div>
                </section>
            )}

            {/* ── Authority ── */}
            {tab === "authority" && (
                <section className={`${DETAIL_CARD} p-6 md:p-8`}>
                    <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-600 dark:bg-violet-500/20 dark:text-violet-200">
                                <IconGlyph name="shield" className="h-6 w-6" />
                            </div>
                            <div>
                                <p className="text-xs font-black uppercase tracking-[0.18em] text-violet-700 dark:text-violet-300">
                                    Resolucion de autoridad
                                </p>
                                <h2 className="mt-1 text-2xl font-black tracking-tight text-slate-950 dark:text-white">
                                    Coincidencias y entidades canonicas
                                </h2>
                            </div>
                        </div>
                        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-500 dark:bg-white/10 dark:text-slate-300">
                            {authorityRecords.length} candidatos
                        </span>
                    </div>

                    {authorityLoading ? (
                        <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 p-8 text-center dark:border-white/10 dark:bg-white/5">
                            <Spinner />
                            <p className="mt-4 text-sm font-bold text-slate-500 dark:text-slate-400">
                                Buscando candidatos de autoridad para este registro...
                            </p>
                        </div>
                    ) : authorityRecords.length === 0 ? (
                        <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 p-8 text-center dark:border-white/10 dark:bg-white/5">
                            <IconGlyph name="shield" className="mb-4 h-10 w-10 text-violet-500 dark:text-violet-300" />
                            <p className="max-w-md text-sm font-bold leading-6 text-slate-500 dark:text-slate-400">
                                {t("entities.detail.authority.empty")}
                            </p>
                            <Link href="/disambiguation" className="mt-4 rounded-xl bg-violet-600 px-5 py-3 text-sm font-bold text-white shadow-[0_14px_35px_rgba(124,58,237,0.28)] transition hover:bg-violet-700">
                                {t("entities.detail.authority.resolve_link")}
                            </Link>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {authorityRecords.map((rec) => {
                                const isActing = authorityAction === rec.id;
                                return (
                                    <div
                                        key={rec.id}
                                        className={`rounded-[1.25rem] border bg-slate-50/80 p-5 transition dark:bg-white/5 ${
                                            rec.status === "rejected"
                                                ? "border-slate-200 opacity-60 dark:border-white/10"
                                            : rec.status === "confirmed"
                                                ? "border-emerald-200 bg-emerald-50/70 dark:border-emerald-500/30 dark:bg-emerald-500/10"
                                                : "border-slate-200 dark:border-white/10"
                                        }`}
                                    >
                                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                                            <div className="min-w-0 flex-1 space-y-3">
                                                <div className="flex flex-wrap items-center gap-3">
                                                    <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white text-violet-600 shadow-sm dark:bg-white/10 dark:text-violet-200">
                                                        <IconGlyph name="globe" className="h-5 w-5" />
                                                    </span>
                                                    <Badge variant={sourceVariant(rec.authority_source)}>
                                                        {rec.authority_source.toUpperCase()}
                                                    </Badge>
                                                    <span className="text-base font-black text-slate-900 dark:text-white">
                                                        {rec.canonical_label}
                                                    </span>
                                                    <Badge variant={
                                                        rec.status === "confirmed" ? "success" :
                                                        rec.status === "rejected" ? "default" : "warning"
                                                    }>{rec.status}</Badge>
                                                    {rec.uri && (
                                                        <a href={rec.uri} target="_blank" rel="noopener noreferrer"
                                                            className="rounded-lg p-1 text-slate-400 transition hover:bg-violet-50 hover:text-violet-600 dark:hover:bg-white/10 dark:hover:text-violet-300">
                                                            <IconGlyph name="link" className="h-4 w-4" />
                                                        </a>
                                                    )}
                                                </div>
                                                {rec.description && (
                                                    <p className="max-w-3xl text-sm font-semibold leading-6 text-slate-500 dark:text-slate-400">
                                                        {rec.description}
                                                    </p>
                                                )}
                                                <div className="grid gap-3 sm:grid-cols-[10rem_1fr] sm:items-center">
                                                    <span className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">
                                                        Confianza {Math.round(rec.confidence * 100)}%
                                                    </span>
                                                    <div className="h-2 rounded-full bg-slate-200 dark:bg-white/10">
                                                        <div className="h-2 rounded-full bg-violet-500"
                                                            style={{ width: `${Math.round(rec.confidence * 100)}%` }} />
                                                    </div>
                                                </div>
                                            </div>
                                            {rec.status === "pending" && (
                                                <div className="flex shrink-0 flex-wrap gap-2">
                                                    <button
                                                        onClick={() => confirmAuthority(rec.id)}
                                                        disabled={isActing}
                                                        className="rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-emerald-700 disabled:opacity-50"
                                                    >
                                                        {isActing ? "..." : t("entities.detail.authority.confirm")}
                                                    </button>
                                                    <button
                                                        onClick={() => rejectAuthority(rec.id)}
                                                        disabled={isActing}
                                                        className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50 dark:border-white/10 dark:bg-white/10 dark:text-slate-200 dark:hover:bg-white/15"
                                                    >
                                                        {isActing ? "..." : t("entities.detail.authority.reject")}
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </section>
            )}
            </div>
        </div>
    );
}
