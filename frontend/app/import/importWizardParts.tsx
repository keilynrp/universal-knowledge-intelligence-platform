"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useAuth } from "../contexts/AuthContext";
import { useDomain } from "../contexts/DomainContext";
import { useLanguage } from "../contexts/LanguageContext";

export interface PreviewData {
    format: string;
    row_count: number;
    columns: string[];
    sample_rows: Record<string, unknown>[];
    auto_mapping: Record<string, string | null>;
    is_science_format: boolean;
}

interface Domain {
    id: string;
    name: string;
    icon?: string;
    description?: string;
    primary_entity?: string;
    attributes?: unknown[];
}

export interface ImportResult {
    message: string;
    total_rows: number;
    domain: string;
    matched_columns: string[];
    unmatched_columns: string[];
    format?: string;
}

export type WizardStep = 1 | 2 | 3 | 4 | 5;

const SUPPORTED_FORMATS = [
    { ext: "CSV", color: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400" },
    { ext: "Excel", color: "bg-green-100 text-green-700 dark:bg-green-500/10 dark:text-green-400" },
    { ext: "BibTeX", color: "bg-indigo-100 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400" },
    { ext: "RIS", color: "bg-violet-100 text-violet-700 dark:bg-violet-500/10 dark:text-violet-400" },
    { ext: "Plaintext", color: "bg-sky-100 text-sky-700 dark:bg-sky-500/10 dark:text-sky-400" },
    { ext: "JSON", color: "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400" },
    { ext: "XML", color: "bg-orange-100 text-orange-700 dark:bg-orange-500/10 dark:text-orange-400" },
    { ext: "Parquet", color: "bg-pink-100 text-pink-700 dark:bg-pink-500/10 dark:text-pink-400" },
];

const FORMAT_DISPLAY: Record<string, string> = {
    csv: "CSV",
    excel: "Excel (.xlsx)",
    json: "JSON",
    xml: "XML",
    parquet: "Parquet",
    bibtex: "BibTeX",
    ris: "RIS",
    wos_plaintext: "Plaintext (.txt)",
    rdf: "RDF/TTL",
};

const DOMAIN_ICONS: Record<string, string> = {
    default: "Box",
    science: "Lab",
    healthcare: "Health",
    business: "Biz",
    education: "Edu",
    legal: "Law",
    finance: "Fin",
    technology: "Tech",
};

function getErrorMessage(error: unknown, fallback: string) {
    return error instanceof Error ? error.message : fallback;
}

function formatApiDetail(detail: unknown, fallback: string) {
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail) && detail.length > 0) {
        const first = detail[0];
        if (typeof first === "string") return first;
        if (first && typeof first === "object") {
            const msg = "msg" in first ? first.msg : null;
            const loc = "loc" in first && Array.isArray(first.loc) ? first.loc.join(" > ") : null;
            if (typeof msg === "string" && loc) return `${loc}: ${msg}`;
            if (typeof msg === "string") return msg;
        }
    }
    if (detail && typeof detail === "object") {
        if ("msg" in detail && typeof detail.msg === "string") return detail.msg;
        try {
            return JSON.stringify(detail);
        } catch {
            return fallback;
        }
    }
    return fallback;
}

function translateOrFallback(t: (key: string) => string, key: string, fallback: string) {
    const value = t(key);
    return value === key ? fallback : value;
}

function slugifyDomainId(value: string) {
    return value
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9_-]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 64);
}

export function getSteps(t: (key: string) => string) {
    return [
        { n: 1 as WizardStep, label: translateOrFallback(t, "page.import.step.upload", "Upload") },
        { n: 2 as WizardStep, label: translateOrFallback(t, "page.import.step.map", "Map Fields") },
        { n: 3 as WizardStep, label: translateOrFallback(t, "page.import.step.domain", "Domain") },
        { n: 4 as WizardStep, label: translateOrFallback(t, "page.import.step.validate", "Validate") },
        { n: 5 as WizardStep, label: translateOrFallback(t, "page.import.step.import", "Import") },
    ];
}

function getUkipFields(t: (key: string) => string): { value: string; label: string }[] {
    return [
        { value: "", label: translateOrFallback(t, "page.import.skip_column", "-- skip column --") },
        { value: "primary_label", label: translateOrFallback(t, "page.import.field.primary_label", "Primary Label (title / name)") },
        { value: "secondary_label", label: translateOrFallback(t, "page.import.field.secondary_label", "Secondary Label (brand / author)") },
        { value: "canonical_id", label: translateOrFallback(t, "page.import.field.canonical_id", "Canonical ID (SKU / DOI / barcode)") },
        { value: "entity_type", label: translateOrFallback(t, "page.import.field.entity_type", "Entity Type") },
        { value: "domain", label: translateOrFallback(t, "page.import.field.domain", "Domain") },
        { value: "enrichment_doi", label: translateOrFallback(t, "page.import.field.enrichment_doi", "DOI") },
        { value: "enrichment_citation_count", label: translateOrFallback(t, "page.import.field.enrichment_citation_count", "Citation Count") },
        { value: "enrichment_concepts", label: translateOrFallback(t, "page.import.field.enrichment_concepts", "Concepts / Keywords") },
        { value: "enrichment_source", label: translateOrFallback(t, "page.import.field.enrichment_source", "Enrichment Source") },
        { value: "creation_date", label: translateOrFallback(t, "page.import.field.creation_date", "Creation Date") },
        { value: "validation_status", label: translateOrFallback(t, "page.import.field.validation_status", "Validation Status") },
    ];
}

export function StepBar({ current }: { current: WizardStep }) {
    const { t } = useLanguage();
    const steps = getSteps(t);

    return (
        <div className="flex items-center gap-0">
            {steps.map((step, index) => (
                <div key={step.n} className="flex items-center">
                    <div className="flex flex-col items-center">
                        <div
                            className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition-colors ${
                                step.n < current
                                    ? "bg-indigo-600 text-white"
                                    : step.n === current
                                        ? "border-2 border-indigo-600 bg-white text-indigo-600 dark:bg-gray-900"
                                        : "border-2 border-gray-200 bg-white text-gray-400 dark:border-gray-700 dark:bg-gray-900"
                            }`}
                        >
                            {step.n < current ? (
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                                </svg>
                            ) : step.n}
                        </div>
                        <span className={`mt-1.5 text-[10px] font-medium ${step.n === current ? "text-indigo-600 dark:text-indigo-400" : "text-gray-400 dark:text-gray-500"}`}>
                            {step.label}
                        </span>
                    </div>
                    {index < steps.length - 1 && (
                        <div className={`mx-2 mb-5 h-0.5 w-10 transition-colors sm:w-16 ${step.n < current ? "bg-indigo-600" : "bg-gray-200 dark:bg-gray-700"}`} />
                    )}
                </div>
            ))}
        </div>
    );
}

export function StepUpload({
    file,
    onFile,
}: {
    file: File | null;
    onFile: (file: File) => void | Promise<void>;
}) {
    const { t } = useLanguage();
    const tr = (key: string, fallback: string) => translateOrFallback(t, key, fallback);
    const [dragging, setDragging] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    function handleDrop(event: React.DragEvent) {
        event.preventDefault();
        setDragging(false);
        const nextFile = event.dataTransfer.files[0];
        if (nextFile) void onFile(nextFile);
    }

    function handleChange(event: React.ChangeEvent<HTMLInputElement>) {
        const nextFile = event.target.files?.[0];
        if (nextFile) void onFile(nextFile);
    }

    const formatBytes = (bytes: number) =>
        bytes < 1024 ? `${bytes} B` : bytes < 1048576 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1048576).toFixed(1)} MB`;

    return (
        <div className="space-y-6">
            <div
                onDragOver={event => {
                    event.preventDefault();
                    setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                onClick={() => inputRef.current?.click()}
                className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-12 transition-colors ${
                    dragging
                        ? "border-indigo-400 bg-indigo-50 dark:border-indigo-500 dark:bg-indigo-500/10"
                        : file
                            ? "border-emerald-300 bg-emerald-50/50 dark:border-emerald-500/40 dark:bg-emerald-500/5"
                            : "border-gray-200 bg-gray-50 hover:border-indigo-300 hover:bg-indigo-50/40 dark:border-gray-700 dark:bg-gray-800/40 dark:hover:border-indigo-500/40"
                }`}
            >
                {file ? (
                    <>
                        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100 dark:bg-emerald-500/10">
                            <svg className="h-7 w-7 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                        </div>
                        <p className="mt-4 text-base font-semibold text-gray-900 dark:text-white">{file.name}</p>
                        <p className="text-sm text-gray-500 dark:text-gray-400">{formatBytes(file.size)}</p>
                        <p className="mt-1 text-xs text-indigo-600 dark:text-indigo-400">{tr("page.import.upload.change", "Click to change file")}</p>
                    </>
                ) : (
                    <>
                        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-100 dark:bg-indigo-500/10">
                            <svg className="h-7 w-7 text-indigo-600 dark:text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                            </svg>
                        </div>
                        <p className="mt-4 text-base font-semibold text-gray-700 dark:text-gray-200">{tr("page.import.upload.drop", "Drop your file here, or click to browse")}</p>
                        <p className="mt-1 text-sm text-gray-400 dark:text-gray-500">{tr("page.import.upload.max_size", "Maximum 20 MB")}</p>
                    </>
                )}
                <input ref={inputRef} type="file" className="hidden" onChange={handleChange} accept=".csv,.xlsx,.json,.jsonld,.xml,.parquet,.bib,.ris,.txt,.rdf,.ttl" />
            </div>

            <div className="flex flex-wrap justify-center gap-2">
                {SUPPORTED_FORMATS.map(format => (
                    <span key={format.ext} className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${format.color}`}>
                        {format.ext}
                    </span>
                ))}
            </div>
        </div>
    );
}

export function StepMapping({
    preview,
    mapping,
    onMappingChange,
}: {
    preview: PreviewData;
    mapping: Record<string, string>;
    onMappingChange: (mapping: Record<string, string>) => void;
}) {
    const { t } = useLanguage();
    const tr = (key: string, fallback: string) => translateOrFallback(t, key, fallback);
    const [suggesting, setSuggesting] = useState(false);
    const [aiProvider, setAiProvider] = useState<string | null>(null);
    const [aiError, setAiError] = useState<string | null>(null);
    const ukipFields = getUkipFields(t);
    const requiredTargets = ["primary_label", "canonical_id"];
    const mappedTargets = new Set(Object.values(mapping).filter(Boolean));
    const missingRecommended = requiredTargets.filter((target) => !mappedTargets.has(target));

    async function handleAISuggest() {
        setSuggesting(true);
        setAiError(null);
        try {
            const response = await apiFetch("/upload/suggest-mapping", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    columns: preview.columns,
                    sample_rows: preview.sample_rows,
                }),
            });
            if (!response.ok) {
                const errorBody = await response.json().catch(() => ({ detail: "Suggestion failed" })) as { detail?: unknown };
                setAiError(formatApiDetail(errorBody.detail, "AI suggestion failed"));
                return;
            }
            const data = await response.json() as {
                available?: boolean;
                provider?: string | null;
                mapping?: Record<string, string | null>;
            };
            if (!data.available) {
                setAiError(tr("page.import.mapping.ai_no_provider", "No AI provider configured. Add one in Settings -> AI Language Models."));
                return;
            }

            const merged = { ...mapping };
            for (const [column, field] of Object.entries(data.mapping ?? {})) {
                if (!merged[column] && field) {
                    merged[column] = field;
                }
            }
            onMappingChange(merged);
            setAiProvider(data.provider ?? null);
        } catch (error: unknown) {
            setAiError(getErrorMessage(error, "Network error"));
        } finally {
            setSuggesting(false);
        }
    }

    const matched = Object.values(mapping).filter(Boolean).length;
    const total = preview.columns.length;

    if (preview.is_science_format) {
        return (
            <div className="space-y-4">
                <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-4 dark:border-indigo-500/20 dark:bg-indigo-500/5">
                    <p className="text-sm font-medium text-indigo-800 dark:text-indigo-300">
                        {tr("page.import.mapping.auto", "Auto-mapped")} - {FORMAT_DISPLAY[preview.format] ?? preview.format} fields are semantically understood.
                    </p>
                    <p className="mt-0.5 text-xs text-indigo-600 dark:text-indigo-400">
                        {preview.row_count.toLocaleString()} {tr("page.import.mapping.records_detected", "records detected. No manual mapping needed.")}
                    </p>
                </div>
                <div className="overflow-hidden rounded-xl border border-gray-100 dark:border-gray-800">
                    <table className="w-full text-sm">
                        <thead className="bg-gray-50 dark:bg-gray-800">
                            <tr>
                                <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-gray-500">{tr("page.import.mapping.source_field", "Source Field")}</th>
                                <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-gray-500">{tr("page.import.mapping.maps_to", "Maps To")}</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                            {Object.entries(preview.auto_mapping).map(([source, target]) => (
                                <tr key={source} className="bg-white dark:bg-gray-900">
                                    <td className="px-4 py-2.5 font-mono text-xs text-gray-700 dark:text-gray-300">{source}</td>
                                    <td className="px-4 py-2.5">
                                        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400">
                                            {target}
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-gray-950/40">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">
                        {tr("page.import.mapping.summary.mapped", "Mapped now")}
                    </p>
                    <p className="mt-2 text-lg font-semibold text-gray-900 dark:text-white">
                        {matched} / {total}
                    </p>
                </div>
                <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-gray-950/40">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">
                        {tr("page.import.mapping.summary.recommended", "Recommended fields")}
                    </p>
                    <p className="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
                        {missingRecommended.length === 0
                            ? tr("page.import.mapping.summary.ready", "Ready")
                            : tr("page.import.mapping.summary.missing", "Still missing")}
                    </p>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        {missingRecommended.length === 0
                            ? tr("page.import.mapping.summary.ready_body", "Primary label and canonical ID are already covered.")
                            : `${missingRecommended
                                .map((field) => ukipFields.find((item) => item.value === field)?.label ?? field)
                                .join(" · ")}`}
                    </p>
                </div>
                <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-gray-950/40">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">
                        {tr("page.import.mapping.summary.safe_unmatched", "Unmatched columns")}
                    </p>
                    <p className="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
                        {total - matched}
                    </p>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        {tr("page.import.mapping.summary.safe_unmatched_body", "They will still be preserved as extended attributes unless you skip them.")}
                    </p>
                </div>
            </div>

            {missingRecommended.length > 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-500/20 dark:bg-amber-500/5">
                    <p className="text-sm font-semibold text-amber-900 dark:text-amber-200">
                        {tr("page.import.mapping.recommended_title", "Before you continue, cover the minimum fields that make the dataset easier to understand.")}
                    </p>
                    <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
                        {tr("page.import.mapping.recommended_body", "Primary label gives each record a readable name, and canonical ID helps UKIP recognize stable identifiers like DOI, SKU, or barcode.")}
                    </p>
                </div>
            )}

            <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400">
                    {matched} / {total} mapped
                </span>
                <span className="text-xs text-gray-400 dark:text-gray-500">
                    {preview.row_count.toLocaleString()} rows - {FORMAT_DISPLAY[preview.format] ?? preview.format}
                </span>
                {total - matched > 0 && (
                    <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700 dark:bg-amber-500/10 dark:text-amber-400">
                        {total - matched} {tr("page.import.mapping.unmatched_suffix", "unmatched - will go to Extended Attributes")}
                    </span>
                )}

                <button
                    onClick={handleAISuggest}
                    disabled={suggesting}
                    className="ml-auto flex items-center gap-1.5 rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-violet-700 disabled:opacity-50"
                    title={tr("page.import.mapping.ai_suggest", "AI Suggest")}
                >
                    {suggesting ? (
                        <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                    ) : (
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3l14 9-14 9V3z" />
                        </svg>
                    )}
                    {suggesting ? tr("page.import.mapping.ai_asking", "Asking AI...") : tr("page.import.mapping.ai_suggest", "AI Suggest")}
                </button>
            </div>

            {aiProvider && !aiError && (
                <div className="flex items-center gap-2 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 dark:border-violet-500/20 dark:bg-violet-500/5">
                    <svg className="h-4 w-4 text-violet-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <p className="text-xs font-medium text-violet-700 dark:text-violet-300">
                        {tr("page.import.mapping.ai_applied", "AI suggestions applied")} - {tr("page.import.mapping.ai_suggested_by", "suggested by")} <span className="font-bold">{aiProvider}</span>
                    </p>
                    <button onClick={() => setAiProvider(null)} className="ml-auto text-violet-400 hover:text-violet-600 dark:hover:text-violet-300">
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            )}

            {aiError && (
                <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 dark:border-amber-500/20 dark:bg-amber-500/5">
                    <svg className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <p className="text-xs text-amber-700 dark:text-amber-400">{aiError}</p>
                    <button onClick={() => setAiError(null)} className="ml-auto text-amber-400 hover:text-amber-600">
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            )}

            <div className="overflow-hidden rounded-xl border border-gray-100 dark:border-gray-800">
                <table className="w-full text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-800">
                        <tr>
                            <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-gray-500">{tr("page.import.mapping.source_column", "Source Column")}</th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-gray-500">{tr("page.import.mapping.sample_value", "Sample Value")}</th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-gray-500">{tr("page.import.mapping.maps_to", "Maps To")}</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                        {preview.columns.map(column => {
                            const sample = preview.sample_rows[0]?.[column];
                            const selectedValue = mapping[column] ?? "";
                            const isMatched = Boolean(selectedValue);
                            return (
                                <tr key={column} className={`bg-white dark:bg-gray-900 ${isMatched ? "" : "opacity-60"}`}>
                                    <td className="px-4 py-2 font-mono text-xs text-gray-700 dark:text-gray-300">{column}</td>
                                    <td className="max-w-[160px] truncate px-4 py-2 text-xs text-gray-400 dark:text-gray-500">
                                        {sample !== undefined && sample !== null ? String(sample).slice(0, 50) : <span className="italic">-</span>}
                                    </td>
                                    <td className="px-4 py-2">
                                        <select
                                            value={selectedValue}
                                            onChange={event => onMappingChange({ ...mapping, [column]: event.target.value })}
                                            className={`rounded-lg border px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-indigo-400 dark:bg-gray-800 dark:text-white ${
                                                isMatched
                                                    ? "border-indigo-200 bg-indigo-50 text-indigo-800 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-300"
                                                    : "border-gray-200 bg-white text-gray-500 dark:border-gray-700"
                                            }`}
                                        >
                                            {ukipFields.map(field => (
                                                <option key={field.value} value={field.value}>
                                                    {field.label}
                                                </option>
                                            ))}
                                        </select>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

export function StepDomain({
    selected,
    onSelect,
}: {
    selected: string;
    onSelect: (id: string) => void;
}) {
    const { t } = useLanguage();
    const { user } = useAuth();
    const { refreshDomains } = useDomain();
    const tr = (key: string, fallback: string) => translateOrFallback(t, key, fallback);
    const [domains, setDomains] = useState<Domain[]>([]);
    const [showCreate, setShowCreate] = useState(false);
    const [creating, setCreating] = useState(false);
    const [createError, setCreateError] = useState<string | null>(null);
    const [newName, setNewName] = useState("");
    const [newId, setNewId] = useState("");
    const [newDescription, setNewDescription] = useState("");
    const [newEntity, setNewEntity] = useState("record");
    const isAdmin = user?.role === "super_admin" || user?.role === "admin";

    const selectedDomain = domains.find(domain => domain.id === selected);

    const loadDomains = async () => {
        try {
            const response = await apiFetch("/domains");
            if (!response.ok) {
                return;
            }
            setDomains(await response.json() as Domain[]);
        } catch {
            // Ignore domain list failures and keep the wizard usable.
        }
    };

    useEffect(() => {
        void loadDomains();
    }, []);

    function handleNameChange(value: string) {
        setNewName(value);
        setNewId(current => current ? current : slugifyDomainId(value));
    }

    async function handleCreateDomain() {
        const id = slugifyDomainId(newId || newName);
        if (!id || !newName.trim() || !newDescription.trim() || !newEntity.trim()) {
            setCreateError(tr("page.import.domain.create_required", "Name, ID, description, and primary entity are required."));
            return;
        }
        setCreating(true);
        setCreateError(null);
        try {
            const response = await apiFetch("/domains", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    id,
                    name: newName.trim(),
                    description: newDescription.trim(),
                    primary_entity: newEntity.trim(),
                    icon: "File",
                    attributes: [
                        { name: "primary_label", type: "string", label: "Primary Label", required: true, is_core: true },
                        { name: "canonical_id", type: "string", label: "Canonical ID", required: false, is_core: true },
                    ],
                }),
            });
            if (!response.ok) {
                const body = await response.json().catch(() => ({ detail: "Could not create domain" })) as { detail?: unknown };
                setCreateError(formatApiDetail(body.detail, tr("page.import.domain.create_failed", "Could not create domain.")));
                return;
            }
            const created = await response.json() as Domain;
            await refreshDomains();
            await loadDomains();
            onSelect(created.id);
            setShowCreate(false);
            setNewName("");
            setNewId("");
            setNewDescription("");
            setNewEntity("record");
        } catch (error: unknown) {
            setCreateError(getErrorMessage(error, tr("page.import.domain.create_network", "Network error while creating the domain.")));
        } finally {
            setCreating(false);
        }
    }

    useEffect(() => {
        if (!selectedDomain && domains.length > 0 && !domains.some(domain => domain.id === selected)) {
            const defaultDomain = domains.find(domain => domain.id === "default") ?? domains[0];
            onSelect(defaultDomain.id);
        }
    }, [domains, onSelect, selected, selectedDomain]);

    return (
        <div className="space-y-4">
            <div className="rounded-xl border border-indigo-100 bg-indigo-50/70 p-4 dark:border-indigo-500/20 dark:bg-indigo-500/5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-indigo-600 dark:text-indigo-300">
                    {tr("page.import.domain.current_label", "Target domain")}
                </p>
                <p className="mt-1 text-sm font-semibold text-indigo-950 dark:text-indigo-100">
                    {selectedDomain ? `${selectedDomain.name} (${selectedDomain.id})` : selected}
                </p>
                <p className="mt-1 text-sm text-indigo-700 dark:text-indigo-300">
                    {tr("page.import.domain.help", "Select the domain to tag imported entities with. You can change this later in the entity list.")}
                </p>
            </div>

            {isAdmin && (
                <div className="flex justify-end">
                    <button
                        type="button"
                        onClick={() => setShowCreate(value => !value)}
                        className="rounded-lg border border-indigo-200 px-3 py-2 text-xs font-semibold text-indigo-700 hover:bg-indigo-50 dark:border-indigo-500/30 dark:text-indigo-300 dark:hover:bg-indigo-500/10"
                    >
                        {showCreate
                            ? tr("common.cancel", "Cancel")
                            : tr("page.import.domain.create_inline", "Create domain")}
                    </button>
                </div>
            )}

            {showCreate && isAdmin && (
                <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950/40">
                    <div className="grid gap-3 sm:grid-cols-2">
                        <label className="block text-xs font-medium text-gray-600 dark:text-gray-400">
                            {tr("page.domains.form_name_label", "Name")}
                            <input
                                value={newName}
                                onChange={event => handleNameChange(event.target.value)}
                                className="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
                                placeholder={tr("page.domains.form_name_placeholder", "Research Intelligence")}
                            />
                        </label>
                        <label className="block text-xs font-medium text-gray-600 dark:text-gray-400">
                            {tr("page.domains.form_id_label", "Domain ID")}
                            <input
                                value={newId}
                                onChange={event => setNewId(slugifyDomainId(event.target.value))}
                                className="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 font-mono text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
                                placeholder="research-intelligence"
                            />
                        </label>
                    </div>
                    <label className="mt-3 block text-xs font-medium text-gray-600 dark:text-gray-400">
                        {tr("page.domains.form_description_label", "Description")}
                        <textarea
                            value={newDescription}
                            onChange={event => setNewDescription(event.target.value)}
                            className="mt-1 min-h-20 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
                            placeholder={tr("page.domains.form_description_placeholder", "What kind of dataset belongs here?")}
                        />
                    </label>
                    <label className="mt-3 block text-xs font-medium text-gray-600 dark:text-gray-400">
                        {tr("page.domains.form_entity_label", "Primary entity")}
                        <input
                            value={newEntity}
                            onChange={event => setNewEntity(event.target.value)}
                            className="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
                            placeholder="publication"
                        />
                    </label>
                    {createError && (
                        <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-700 dark:border-red-500/30 dark:bg-red-500/5 dark:text-red-300">
                            {createError}
                        </p>
                    )}
                    <button
                        type="button"
                        onClick={handleCreateDomain}
                        disabled={creating}
                        className="mt-3 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                    >
                        {creating
                            ? tr("page.domains.creating", "Creating...")
                            : tr("page.domains.create_button", "Create domain")}
                    </button>
                </div>
            )}

            {!isAdmin && (
                <p className="text-xs text-gray-500 dark:text-gray-400">
                    {tr("page.import.domain.admin_only", "Need a new domain? Ask an administrator to create it before importing.")}
                </p>
            )}

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {domains.map(domain => {
                    const icon = domain.icon || DOMAIN_ICONS[domain.id] || "File";
                    const isSelected = domain.id === selected;
                    return (
                        <button
                            key={domain.id}
                            onClick={() => onSelect(domain.id)}
                            className={`flex flex-col items-start rounded-xl border p-4 text-left transition-all ${
                                isSelected
                                    ? "border-indigo-400 bg-indigo-50 ring-2 ring-indigo-400/30 dark:border-indigo-500 dark:bg-indigo-500/10"
                                    : "border-gray-200 bg-white hover:border-indigo-200 hover:bg-indigo-50/40 dark:border-gray-700 dark:bg-gray-900 dark:hover:border-indigo-500/30"
                            }`}
                        >
                            <span className="text-2xl">{icon}</span>
                            <span className={`mt-2 text-sm font-semibold ${isSelected ? "text-indigo-700 dark:text-indigo-300" : "text-gray-800 dark:text-gray-200"}`}>
                                {domain.name}
                            </span>
                            <span className="mt-0.5 font-mono text-[10px] text-gray-400 dark:text-gray-500">
                                {domain.id}
                            </span>
                            {domain.description && (
                                <span className="mt-0.5 line-clamp-2 text-[11px] text-gray-400 dark:text-gray-500">
                                    {domain.description}
                                </span>
                            )}
                            {isSelected && (
                                <span className="mt-2 rounded-full bg-indigo-600 px-2 py-0.5 text-[10px] font-bold text-white">
                                    {tr("page.import.domain.selected", "Selected")}
                                </span>
                            )}
                        </button>
                    );
                })}
            </div>
        </div>
    );
}

export function StepValidate({
    preview,
    mapping,
    domain,
}: {
    preview: PreviewData;
    mapping: Record<string, string>;
    domain: string;
}) {
    const { t } = useLanguage();
    const tr = (key: string, fallback: string) => translateOrFallback(t, key, fallback);
    const mappedColumns = Object.entries(mapping).filter(([, value]) => Boolean(value));
    const skippedColumns = Object.entries(mapping).filter(([, value]) => value === "");
    const unmappedColumns = preview.columns.filter(column => !mapping[column]);
    const primaryLabelColumn = mappedColumns.find(([, value]) => value === "primary_label")?.[0];
    const canonicalIdColumn = mappedColumns.find(([, value]) => value === "canonical_id")?.[0];
    const isReadyForImport = preview.is_science_format || Boolean(primaryLabelColumn && canonicalIdColumn);

    return (
        <div className="space-y-5">
            <div className={`rounded-2xl border p-4 ${
                isReadyForImport
                    ? "border-emerald-200 bg-emerald-50 dark:border-emerald-500/20 dark:bg-emerald-500/5"
                    : "border-amber-200 bg-amber-50 dark:border-amber-500/20 dark:bg-amber-500/5"
            }`}>
                <p className={`text-[11px] font-bold uppercase tracking-[0.18em] ${
                    isReadyForImport
                        ? "text-emerald-700 dark:text-emerald-300"
                        : "text-amber-700 dark:text-amber-300"
                }`}>
                    {tr("page.import.validate.eyebrow", "Import readiness")}
                </p>
                <p className={`mt-1 text-sm font-semibold ${
                    isReadyForImport
                        ? "text-emerald-900 dark:text-emerald-100"
                        : "text-amber-900 dark:text-amber-100"
                }`}>
                    {isReadyForImport
                        ? tr("page.import.validate.ready_title", "This import already has enough structure for a useful first pass.")
                        : tr("page.import.validate.needs_attention_title", "This import can continue, but one or two mapping fixes will make the result much easier to read.")}
                </p>
                <p className={`mt-1 text-sm ${
                    isReadyForImport
                        ? "text-emerald-700 dark:text-emerald-300"
                        : "text-amber-700 dark:text-amber-300"
                }`}>
                    {isReadyForImport
                        ? tr("page.import.validate.ready_body", "You can import now and move directly to dashboard, review, and briefing.")
                        : tr("page.import.validate.needs_attention_body", "If possible, map a human-readable label and a stable identifier before importing.")}
                </p>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                    { label: tr("page.import.validate.total_rows", "Total Rows"), value: preview.row_count.toLocaleString(), color: "text-indigo-600" },
                    { label: tr("page.import.validate.mapped_columns", "Mapped Columns"), value: mappedColumns.length, color: "text-emerald-600" },
                    { label: tr("page.import.validate.skipped_columns", "Skipped Columns"), value: skippedColumns.length, color: "text-gray-500" },
                    { label: tr("page.import.validate.unmatched", "Unmatched"), value: unmappedColumns.length, color: "text-amber-600" },
                ].map(summary => (
                    <div key={summary.label} className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <p className="text-xs text-gray-500 dark:text-gray-400">{summary.label}</p>
                        <p className={`mt-0.5 text-2xl font-bold ${summary.color}`}>{summary.value}</p>
                    </div>
                ))}
            </div>

            <div className="flex flex-wrap gap-2">
                <span className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-400">
                    {tr("page.import.field.domain", "Domain")}: {domain}
                </span>
                <span className="rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs font-semibold text-gray-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400">
                    Format: {FORMAT_DISPLAY[preview.format] ?? preview.format}
                </span>
            </div>

            {!primaryLabelColumn && !preview.is_science_format && (
                <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-500/30 dark:bg-amber-500/5">
                    <svg className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <div>
                        <p className="text-sm font-medium text-amber-800 dark:text-amber-300">{tr("page.import.validate.no_primary_title", "No Primary Label mapped")}</p>
                        <p className="text-xs text-amber-600 dark:text-amber-400">
                            {tr("page.import.validate.no_primary_hint", "Consider mapping a column to Primary Label so entities have a human-readable name.")}
                        </p>
                    </div>
                </div>
            )}

            {!canonicalIdColumn && !preview.is_science_format && (
                <div className="flex items-start gap-3 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950/40">
                    <svg className="mt-0.5 h-4 w-4 shrink-0 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7h16M4 12h10m-10 5h16" />
                    </svg>
                    <div>
                        <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{tr("page.import.validate.no_canonical_title", "No stable identifier mapped")}</p>
                        <p className="text-xs text-gray-600 dark:text-gray-400">
                            {tr("page.import.validate.no_canonical_hint", "If your file has DOI, SKU, barcode, or another stable key, map it to Canonical ID to make dedupe and follow-up easier later.")}
                        </p>
                    </div>
                </div>
            )}

            {unmappedColumns.length > 0 && (
                <div className="rounded-xl border border-gray-100 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-800/50">
                    <p className="mb-2 text-xs font-semibold text-gray-500 dark:text-gray-400">
                        {unmappedColumns.length} column{unmappedColumns.length > 1 ? "s" : ""} {tr("page.import.validate.extended_attributes", "will be stored in Extended Attributes:")}
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                        {unmappedColumns.map(column => (
                            <span key={column} className="rounded-full bg-gray-200 px-2 py-0.5 font-mono text-[10px] text-gray-600 dark:bg-gray-700 dark:text-gray-400">
                                {column}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {preview.sample_rows.length > 0 && (
                <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                        {tr("page.import.validate.sample_preview", "Sample Preview")} ({tr("page.import.validate.first_rows", "first rows")} {Math.min(preview.sample_rows.length, 3)})
                    </p>
                    <div className="overflow-x-auto rounded-xl border border-gray-100 dark:border-gray-800">
                        <table className="w-full text-xs">
                            <thead className="bg-gray-50 dark:bg-gray-800">
                                <tr>
                                    {mappedColumns.slice(0, 5).map(([column, model]) => (
                                        <th key={column} className="px-3 py-2 text-left font-bold uppercase tracking-wider text-gray-500">
                                            {model || column}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                                {preview.sample_rows.slice(0, 3).map((row, index) => (
                                    <tr key={index} className="bg-white dark:bg-gray-900">
                                        {mappedColumns.slice(0, 5).map(([column]) => (
                                            <td key={column} className="max-w-[140px] truncate px-3 py-2 text-gray-600 dark:text-gray-400">
                                                {row[column] !== undefined && row[column] !== null ? String(row[column]).slice(0, 60) : "-"}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}

export function StepImport({
    result,
    importing,
    error,
}: {
    result: ImportResult | null;
    importing: boolean;
    error: string | null;
}) {
    const router = useRouter();
    const { setActiveDomainId } = useDomain();
    const { t } = useLanguage();
    const tr = (key: string, fallback: string) => translateOrFallback(t, key, fallback);

    if (importing) {
        return (
            <div className="flex flex-col items-center gap-4 py-16">
                <svg className="h-10 w-10 animate-spin text-indigo-600" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">{tr("page.import.importing", "Importing your data...")}</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex flex-col items-center gap-4 py-12 text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-red-100 dark:bg-red-500/10">
                    <svg className="h-8 w-8 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                    </svg>
                </div>
                <div>
                    <p className="text-base font-semibold text-gray-900 dark:text-white">{tr("page.import.import_failed", "Import failed")}</p>
                    <p className="mt-1 max-w-sm text-sm text-red-600 dark:text-red-400">{error}</p>
                </div>
                <button
                    onClick={() => router.push("/")}
                    className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
                >
                    {tr("page.import.back_to_explorer", "Back to Knowledge Explorer")}
                </button>
            </div>
        );
    }

    if (!result) return null;

    const openExecutiveDashboard = () => {
        setActiveDomainId(result.domain);
        router.push(
            `/analytics/dashboard?imported=1&domain=${encodeURIComponent(result.domain)}&rows=${result.total_rows}`,
        );
    };

    const openBriefBuilder = () => {
        setActiveDomainId(result.domain);
        router.push(
            `/reports?preset=pilot-brief&domain=${encodeURIComponent(result.domain)}&rows=${result.total_rows}&format=pdf&title=${encodeURIComponent(`UKIP Pilot Brief — ${result.domain}`)}`,
        );
    };

    return (
        <div className="flex flex-col items-center gap-6 py-8 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-100 dark:bg-emerald-500/10">
                <svg className="h-8 w-8 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
            </div>

            <div>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{result.total_rows.toLocaleString()} {tr("page.import.entities_imported", "entities imported")}</p>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{result.message}</p>
            </div>

            <div className="grid w-full max-w-3xl grid-cols-1 gap-3 md:grid-cols-3">
                {[
                    {
                        step: "1",
                        title: tr("page.import.success.read_kpis", "Read the KPIs"),
                        detail: tr("page.import.success.review_dashboard_detail", "Check coverage, quality, concepts, and impact before drawing conclusions."),
                    },
                    {
                        step: "2",
                        title: tr("page.import.success.open_brief", "Prepare Executive Brief"),
                        detail: tr("page.import.success.prepare_brief_detail", "Load the pilot brief preset with the most useful sections already selected."),
                    },
                    {
                        step: "3",
                        title: tr("page.import.success.share_result", "Share the result"),
                        detail: tr("page.import.success.share_result_detail", "Export a PDF brief once the first readout looks solid enough for stakeholders."),
                    },
                ].map((item) => (
                    <div
                        key={item.step}
                        className="rounded-2xl border border-gray-200 bg-white p-4 text-left shadow-sm dark:border-gray-800 dark:bg-gray-900"
                    >
                        <div className="flex items-center gap-3">
                            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-violet-100 text-xs font-bold text-violet-700 dark:bg-violet-500/10 dark:text-violet-300">
                                {item.step}
                            </span>
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">{item.title}</p>
                        </div>
                        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">{item.detail}</p>
                    </div>
                ))}
            </div>

            <div className="flex flex-wrap justify-center gap-2">
                <span className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-400">
                    {tr("page.import.field.domain", "Domain")}: {result.domain}
                </span>
                <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-400">
                    {result.matched_columns.length} {tr("page.import.validate.mapped_columns", "Mapped Columns").toLowerCase()}
                </span>
                {result.unmatched_columns.length > 0 && (
                    <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-400">
                        {result.unmatched_columns.length} {tr("page.import.validate.extended_attributes", "will be stored in Extended Attributes:").replace("will be stored in ", "").replace(":", "")}
                    </span>
                )}
            </div>

            <div className="rounded-2xl border border-violet-200 bg-violet-50/70 p-4 text-left shadow-sm dark:border-violet-500/20 dark:bg-violet-500/5">
                <p className="text-sm font-semibold text-violet-900 dark:text-violet-200">
                    {tr("page.import.success.next_steps", "Suggested next steps")}
                </p>
                <p className="mt-1 text-sm text-violet-700 dark:text-violet-300">
                    {tr("page.import.success.pilot_flow_detail", "Start with the Executive Dashboard for the fast readout, then move to the brief builder when you are ready to package the result.")}
                </p>
            </div>

            <div className="flex flex-wrap justify-center gap-3">
                <button
                    onClick={openExecutiveDashboard}
                    className="rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-violet-700"
                >
                    {tr("page.import.success.open_dashboard", "Open Executive Dashboard")}
                </button>
                <button
                    onClick={openBriefBuilder}
                    className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-700"
                >
                    {tr("page.import.success.open_brief", "Prepare Executive Brief")}
                </button>
                <button
                    onClick={() => router.push("/")}
                    className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-indigo-700"
                >
                    {tr("page.import.back_to_explorer", "Back to Knowledge Explorer")}
                </button>
                <button
                    onClick={() => window.location.reload()}
                    className="rounded-lg border border-gray-200 px-5 py-2.5 text-sm font-semibold text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                    {tr("common.retry", "Retry")}
                </button>
            </div>
        </div>
    );
}
