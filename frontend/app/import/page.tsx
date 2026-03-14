"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { PageHeader } from "../components/ui";

// ── Types ──────────────────────────────────────────────────────────────────────

interface PreviewData {
    format: string;
    row_count: number;
    columns: string[];
    sample_rows: Record<string, any>[];
    auto_mapping: Record<string, string | null>;
    is_science_format: boolean;
}

interface Domain {
    id: string;
    name: string;
    icon?: string;
    description?: string;
}

interface ImportResult {
    message: string;
    total_rows: number;
    domain: string;
    matched_columns: string[];
    unmatched_columns: string[];
    format?: string;
}

type WizardStep = 1 | 2 | 3 | 4 | 5;

// ── Constants ─────────────────────────────────────────────────────────────────

const STEPS = [
    { n: 1 as WizardStep, label: "Upload" },
    { n: 2 as WizardStep, label: "Map Fields" },
    { n: 3 as WizardStep, label: "Domain" },
    { n: 4 as WizardStep, label: "Validate" },
    { n: 5 as WizardStep, label: "Import" },
];

const SUPPORTED_FORMATS = [
    { ext: "CSV", color: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400" },
    { ext: "Excel", color: "bg-green-100 text-green-700 dark:bg-green-500/10 dark:text-green-400" },
    { ext: "BibTeX", color: "bg-indigo-100 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400" },
    { ext: "RIS", color: "bg-violet-100 text-violet-700 dark:bg-violet-500/10 dark:text-violet-400" },
    { ext: "JSON", color: "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400" },
    { ext: "XML", color: "bg-orange-100 text-orange-700 dark:bg-orange-500/10 dark:text-orange-400" },
    { ext: "Parquet", color: "bg-pink-100 text-pink-700 dark:bg-pink-500/10 dark:text-pink-400" },
];

const UKIP_FIELDS: { value: string; label: string }[] = [
    { value: "", label: "— skip column —" },
    { value: "primary_label", label: "Primary Label (title / name)" },
    { value: "secondary_label", label: "Secondary Label (brand / author)" },
    { value: "canonical_id", label: "Canonical ID (SKU / DOI / barcode)" },
    { value: "entity_type", label: "Entity Type" },
    { value: "domain", label: "Domain" },
    { value: "enrichment_doi", label: "DOI" },
    { value: "enrichment_citation_count", label: "Citation Count" },
    { value: "enrichment_concepts", label: "Concepts / Keywords" },
    { value: "enrichment_source", label: "Enrichment Source" },
    { value: "creation_date", label: "Creation Date" },
    { value: "validation_status", label: "Validation Status" },
];

const FORMAT_DISPLAY: Record<string, string> = {
    csv: "CSV", excel: "Excel (.xlsx)", json: "JSON", xml: "XML",
    parquet: "Parquet", bibtex: "BibTeX", ris: "RIS", rdf: "RDF/TTL",
};

// ── Step indicator ────────────────────────────────────────────────────────────

function StepBar({ current }: { current: WizardStep }) {
    return (
        <div className="flex items-center gap-0">
            {STEPS.map((s, idx) => (
                <div key={s.n} className="flex items-center">
                    <div className="flex flex-col items-center">
                        <div
                            className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition-colors ${
                                s.n < current
                                    ? "bg-indigo-600 text-white"
                                    : s.n === current
                                    ? "border-2 border-indigo-600 bg-white text-indigo-600 dark:bg-gray-900"
                                    : "border-2 border-gray-200 bg-white text-gray-400 dark:border-gray-700 dark:bg-gray-900"
                            }`}
                        >
                            {s.n < current ? (
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                                </svg>
                            ) : s.n}
                        </div>
                        <span className={`mt-1.5 text-[10px] font-medium ${
                            s.n === current ? "text-indigo-600 dark:text-indigo-400" : "text-gray-400 dark:text-gray-500"
                        }`}>
                            {s.label}
                        </span>
                    </div>
                    {idx < STEPS.length - 1 && (
                        <div className={`mx-2 mb-5 h-0.5 w-10 sm:w-16 transition-colors ${
                            s.n < current ? "bg-indigo-600" : "bg-gray-200 dark:bg-gray-700"
                        }`} />
                    )}
                </div>
            ))}
        </div>
    );
}

// ── Step 1: Upload ────────────────────────────────────────────────────────────

function StepUpload({
    file,
    onFile,
}: {
    file: File | null;
    onFile: (f: File) => void;
}) {
    const [dragging, setDragging] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    function handleDrop(e: React.DragEvent) {
        e.preventDefault();
        setDragging(false);
        const f = e.dataTransfer.files[0];
        if (f) onFile(f);
    }

    function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
        const f = e.target.files?.[0];
        if (f) onFile(f);
    }

    const formatBytes = (b: number) =>
        b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(1)} MB`;

    return (
        <div className="space-y-6">
            <div
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
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
                        <p className="mt-1 text-xs text-indigo-600 dark:text-indigo-400">Click to change file</p>
                    </>
                ) : (
                    <>
                        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-100 dark:bg-indigo-500/10">
                            <svg className="h-7 w-7 text-indigo-600 dark:text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                            </svg>
                        </div>
                        <p className="mt-4 text-base font-semibold text-gray-700 dark:text-gray-200">
                            Drop your file here, or click to browse
                        </p>
                        <p className="mt-1 text-sm text-gray-400 dark:text-gray-500">Maximum 20 MB</p>
                    </>
                )}
                <input ref={inputRef} type="file" className="hidden" onChange={handleChange}
                    accept=".csv,.xlsx,.json,.jsonld,.xml,.parquet,.bib,.ris,.rdf,.ttl" />
            </div>

            <div className="flex flex-wrap justify-center gap-2">
                {SUPPORTED_FORMATS.map((f) => (
                    <span key={f.ext} className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${f.color}`}>
                        {f.ext}
                    </span>
                ))}
            </div>
        </div>
    );
}

// ── Step 2: Field Mapping ─────────────────────────────────────────────────────

function StepMapping({
    preview,
    mapping,
    onMappingChange,
}: {
    preview: PreviewData;
    mapping: Record<string, string>;
    onMappingChange: (m: Record<string, string>) => void;
}) {
    const matched = Object.values(mapping).filter(Boolean).length;
    const total = preview.columns.length;

    if (preview.is_science_format) {
        return (
            <div className="space-y-4">
                <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-4 dark:border-indigo-500/20 dark:bg-indigo-500/5">
                    <p className="text-sm font-medium text-indigo-800 dark:text-indigo-300">
                        Auto-mapped — {FORMAT_DISPLAY[preview.format] ?? preview.format} fields are semantically understood.
                    </p>
                    <p className="mt-0.5 text-xs text-indigo-600 dark:text-indigo-400">
                        {preview.row_count.toLocaleString()} records detected. No manual mapping needed.
                    </p>
                </div>
                <div className="overflow-hidden rounded-xl border border-gray-100 dark:border-gray-800">
                    <table className="w-full text-sm">
                        <thead className="bg-gray-50 dark:bg-gray-800">
                            <tr>
                                <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-gray-500">Source Field</th>
                                <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-gray-500">Maps To</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                            {Object.entries(preview.auto_mapping).map(([src, tgt]) => (
                                <tr key={src} className="bg-white dark:bg-gray-900">
                                    <td className="px-4 py-2.5 font-mono text-xs text-gray-700 dark:text-gray-300">{src}</td>
                                    <td className="px-4 py-2.5">
                                        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400">
                                            {tgt}
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
            <div className="flex items-center gap-3">
                <span className="rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400">
                    {matched} / {total} mapped
                </span>
                <span className="text-xs text-gray-400 dark:text-gray-500">
                    {preview.row_count.toLocaleString()} rows · {FORMAT_DISPLAY[preview.format] ?? preview.format}
                </span>
                {total - matched > 0 && (
                    <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700 dark:bg-amber-500/10 dark:text-amber-400">
                        {total - matched} unmatched — will go to Extended Attributes
                    </span>
                )}
            </div>

            <div className="overflow-hidden rounded-xl border border-gray-100 dark:border-gray-800">
                <table className="w-full text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-800">
                        <tr>
                            <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-gray-500">Source Column</th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-gray-500">Sample Value</th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-gray-500">Maps To</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                        {preview.columns.map((col) => {
                            const sample = preview.sample_rows[0]?.[col];
                            const val = mapping[col] ?? "";
                            const isMatched = Boolean(val);
                            return (
                                <tr key={col} className={`bg-white dark:bg-gray-900 ${isMatched ? "" : "opacity-60"}`}>
                                    <td className="px-4 py-2 font-mono text-xs text-gray-700 dark:text-gray-300">
                                        {col}
                                    </td>
                                    <td className="max-w-[160px] truncate px-4 py-2 text-xs text-gray-400 dark:text-gray-500">
                                        {sample !== undefined && sample !== null ? String(sample).slice(0, 50) : <span className="italic">—</span>}
                                    </td>
                                    <td className="px-4 py-2">
                                        <select
                                            value={val}
                                            onChange={(e) => onMappingChange({ ...mapping, [col]: e.target.value })}
                                            className={`rounded-lg border px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-indigo-400 dark:bg-gray-800 dark:text-white ${
                                                isMatched
                                                    ? "border-indigo-200 bg-indigo-50 text-indigo-800 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-300"
                                                    : "border-gray-200 bg-white text-gray-500 dark:border-gray-700"
                                            }`}
                                        >
                                            {UKIP_FIELDS.map((f) => (
                                                <option key={f.value} value={f.value}>{f.label}</option>
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

// ── Step 3: Domain ────────────────────────────────────────────────────────────

const DOMAIN_ICONS: Record<string, string> = {
    default: "📦", science: "🔬", healthcare: "🏥", business: "💼",
    education: "🎓", legal: "⚖️", finance: "💰", technology: "💻",
};

function StepDomain({
    selected,
    onSelect,
}: {
    selected: string;
    onSelect: (id: string) => void;
}) {
    const [domains, setDomains] = useState<Domain[]>([]);

    useEffect(() => {
        apiFetch("/domains")
            .then((r) => r.ok ? r.json() : [])
            .then(setDomains)
            .catch(() => {});
    }, []);

    return (
        <div className="space-y-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">
                Select the domain to tag imported entities with. You can change this later in the entity list.
            </p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {domains.map((d) => {
                    const icon = d.icon || DOMAIN_ICONS[d.id] || "📂";
                    const isSelected = d.id === selected;
                    return (
                        <button
                            key={d.id}
                            onClick={() => onSelect(d.id)}
                            className={`flex flex-col items-start rounded-xl border p-4 text-left transition-all ${
                                isSelected
                                    ? "border-indigo-400 bg-indigo-50 ring-2 ring-indigo-400/30 dark:border-indigo-500 dark:bg-indigo-500/10"
                                    : "border-gray-200 bg-white hover:border-indigo-200 hover:bg-indigo-50/40 dark:border-gray-700 dark:bg-gray-900 dark:hover:border-indigo-500/30"
                            }`}
                        >
                            <span className="text-2xl">{icon}</span>
                            <span className={`mt-2 text-sm font-semibold ${isSelected ? "text-indigo-700 dark:text-indigo-300" : "text-gray-800 dark:text-gray-200"}`}>
                                {d.name}
                            </span>
                            {d.description && (
                                <span className="mt-0.5 text-[11px] text-gray-400 dark:text-gray-500 line-clamp-2">
                                    {d.description}
                                </span>
                            )}
                            {isSelected && (
                                <span className="mt-2 rounded-full bg-indigo-600 px-2 py-0.5 text-[10px] font-bold text-white">
                                    Selected
                                </span>
                            )}
                        </button>
                    );
                })}
            </div>
        </div>
    );
}

// ── Step 4: Validate ──────────────────────────────────────────────────────────

function StepValidate({
    preview,
    mapping,
    domain,
}: {
    preview: PreviewData;
    mapping: Record<string, string>;
    domain: string;
}) {
    const mappedCols = Object.entries(mapping).filter(([, v]) => Boolean(v));
    const skippedCols = Object.entries(mapping).filter(([, v]) => v === "");
    const unmappedCols = preview.columns.filter((c) => !mapping[c]);

    const primaryLabelCol = mappedCols.find(([, v]) => v === "primary_label")?.[0];

    return (
        <div className="space-y-5">
            {/* Summary cards */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                    { label: "Total Rows", value: preview.row_count.toLocaleString(), color: "text-indigo-600" },
                    { label: "Mapped Columns", value: mappedCols.length, color: "text-emerald-600" },
                    { label: "Skipped Columns", value: skippedCols.length, color: "text-gray-500" },
                    { label: "Unmatched", value: unmappedCols.length, color: "text-amber-600" },
                ].map((s) => (
                    <div key={s.label} className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <p className="text-xs text-gray-500 dark:text-gray-400">{s.label}</p>
                        <p className={`mt-0.5 text-2xl font-bold ${s.color}`}>{s.value}</p>
                    </div>
                ))}
            </div>

            {/* Domain + format */}
            <div className="flex flex-wrap gap-2">
                <span className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-400">
                    Domain: {domain}
                </span>
                <span className="rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs font-semibold text-gray-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400">
                    Format: {FORMAT_DISPLAY[preview.format] ?? preview.format}
                </span>
            </div>

            {/* Warnings */}
            {!primaryLabelCol && !preview.is_science_format && (
                <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-500/30 dark:bg-amber-500/5">
                    <svg className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <div>
                        <p className="text-sm font-medium text-amber-800 dark:text-amber-300">No Primary Label mapped</p>
                        <p className="text-xs text-amber-600 dark:text-amber-400">Consider mapping a column to "Primary Label" so entities have a human-readable name.</p>
                    </div>
                </div>
            )}
            {unmappedCols.length > 0 && (
                <div className="rounded-xl border border-gray-100 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-800/50">
                    <p className="mb-2 text-xs font-semibold text-gray-500 dark:text-gray-400">
                        {unmappedCols.length} column{unmappedCols.length > 1 ? "s" : ""} will be stored in Extended Attributes:
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                        {unmappedCols.map((c) => (
                            <span key={c} className="rounded-full bg-gray-200 px-2 py-0.5 font-mono text-[10px] text-gray-600 dark:bg-gray-700 dark:text-gray-400">
                                {c}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Sample rows */}
            {preview.sample_rows.length > 0 && (
                <div>
                    <p className="mb-2 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Sample Preview (first {Math.min(preview.sample_rows.length, 3)} rows)
                    </p>
                    <div className="overflow-x-auto rounded-xl border border-gray-100 dark:border-gray-800">
                        <table className="w-full text-xs">
                            <thead className="bg-gray-50 dark:bg-gray-800">
                                <tr>
                                    {mappedCols.slice(0, 5).map(([col, model]) => (
                                        <th key={col} className="px-3 py-2 text-left font-bold uppercase tracking-wider text-gray-500">
                                            {model || col}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                                {preview.sample_rows.slice(0, 3).map((row, i) => (
                                    <tr key={i} className="bg-white dark:bg-gray-900">
                                        {mappedCols.slice(0, 5).map(([col]) => (
                                            <td key={col} className="max-w-[140px] truncate px-3 py-2 text-gray-600 dark:text-gray-400">
                                                {row[col] !== undefined && row[col] !== null ? String(row[col]).slice(0, 60) : "—"}
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

// ── Step 5: Import ────────────────────────────────────────────────────────────

function StepImport({
    result,
    importing,
    error,
}: {
    result: ImportResult | null;
    importing: boolean;
    error: string | null;
}) {
    const router = useRouter();

    if (importing) {
        return (
            <div className="flex flex-col items-center gap-4 py-16">
                <svg className="h-10 w-10 animate-spin text-indigo-600" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Importing your data…</p>
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
                    <p className="text-base font-semibold text-gray-900 dark:text-white">Import failed</p>
                    <p className="mt-1 max-w-sm text-sm text-red-600 dark:text-red-400">{error}</p>
                </div>
                <button
                    onClick={() => router.push("/")}
                    className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
                >
                    Back to Knowledge Explorer
                </button>
            </div>
        );
    }

    if (!result) return null;

    return (
        <div className="flex flex-col items-center gap-6 py-8 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-100 dark:bg-emerald-500/10">
                <svg className="h-8 w-8 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
            </div>

            <div>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {result.total_rows.toLocaleString()} entities imported
                </p>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{result.message}</p>
            </div>

            <div className="flex flex-wrap justify-center gap-2">
                <span className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-400">
                    Domain: {result.domain}
                </span>
                <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-400">
                    {result.matched_columns.length} mapped columns
                </span>
                {result.unmatched_columns.length > 0 && (
                    <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-400">
                        {result.unmatched_columns.length} in extended attrs
                    </span>
                )}
            </div>

            <div className="flex gap-3">
                <button
                    onClick={() => router.push("/")}
                    className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-indigo-700"
                >
                    View in Knowledge Explorer →
                </button>
                <button
                    onClick={() => window.location.reload()}
                    className="rounded-lg border border-gray-200 px-5 py-2.5 text-sm font-semibold text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                    Import Another File
                </button>
            </div>
        </div>
    );
}

// ── Main wizard page ──────────────────────────────────────────────────────────

export default function ImportWizardPage() {
    const [step, setStep] = useState<WizardStep>(1);
    const [file, setFile] = useState<File | null>(null);
    const [previewing, setPreviewing] = useState(false);
    const [previewError, setPreviewError] = useState<string | null>(null);
    const [preview, setPreview] = useState<PreviewData | null>(null);
    const [mapping, setMapping] = useState<Record<string, string>>({});
    const [domain, setDomain] = useState("default");
    const [importing, setImporting] = useState(false);
    const [importResult, setImportResult] = useState<ImportResult | null>(null);
    const [importError, setImportError] = useState<string | null>(null);

    // When user selects a file → auto-advance to step 2 and run preview
    const handleFile = useCallback(async (f: File) => {
        setFile(f);
        setPreview(null);
        setPreviewError(null);
        setPreviewing(true);
        setStep(2);

        const form = new FormData();
        form.append("file", f);
        try {
            const res = await apiFetch("/upload/preview", { method: "POST", body: form });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: "Preview failed" }));
                setPreviewError(err.detail ?? "Preview failed");
                return;
            }
            const data: PreviewData = await res.json();
            setPreview(data);
            // Initialise mapping from auto_mapping (null → "" to mean "unmatched")
            const init: Record<string, string> = {};
            for (const [col, model] of Object.entries(data.auto_mapping)) {
                init[col] = model ?? "";
            }
            setMapping(init);
        } catch (e: any) {
            setPreviewError(e.message ?? "Network error");
        } finally {
            setPreviewing(false);
        }
    }, []);

    async function handleImport() {
        if (!file) return;
        setImporting(true);
        setImportError(null);
        setStep(5);

        const form = new FormData();
        form.append("file", file);
        form.append("domain", domain);
        // Only send non-empty mappings
        const cleanMapping: Record<string, string> = {};
        for (const [k, v] of Object.entries(mapping)) {
            if (v) cleanMapping[k] = v;
        }
        form.append("field_mapping", JSON.stringify(cleanMapping));

        try {
            const res = await apiFetch("/upload", { method: "POST", body: form });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: "Import failed" }));
                setImportError(err.detail ?? "Import failed");
                return;
            }
            setImportResult(await res.json());
        } catch (e: any) {
            setImportError(e.message ?? "Network error");
        } finally {
            setImporting(false);
        }
    }

    const canNext: Record<WizardStep, boolean> = {
        1: Boolean(file),
        2: !previewing && !previewError && Boolean(preview),
        3: Boolean(domain),
        4: true,
        5: false,
    };

    function handleNext() {
        if (step === 4) { handleImport(); return; }
        if (step < 5) setStep((s) => (s + 1) as WizardStep);
    }

    function handleBack() {
        if (step > 1) setStep((s) => (s - 1) as WizardStep);
    }

    return (
        <div className="space-y-6">
            <PageHeader
                breadcrumbs={[
                    { label: "Home", href: "/" },
                    { label: "Import Wizard" },
                ]}
                title="Bulk Import Wizard"
                description="Import CSV, Excel, BibTeX, RIS, JSON, XML, or Parquet files with guided field mapping and domain selection."
            />

            {/* Step bar */}
            <div className="flex justify-center py-2">
                <StepBar current={step} />
            </div>

            {/* Step content */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h2 className="mb-5 text-sm font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                    Step {step} — {STEPS[step - 1].label}
                </h2>

                {step === 1 && <StepUpload file={file} onFile={handleFile} />}

                {step === 2 && (
                    previewing ? (
                        <div className="flex flex-col items-center gap-3 py-12">
                            <svg className="h-7 w-7 animate-spin text-indigo-600" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                            <p className="text-sm text-gray-500">Parsing file and detecting columns…</p>
                        </div>
                    ) : previewError ? (
                        <div className="rounded-xl border border-red-200 bg-red-50 p-5 dark:border-red-500/30 dark:bg-red-500/5">
                            <p className="text-sm font-medium text-red-700 dark:text-red-400">{previewError}</p>
                            <button onClick={() => setStep(1)} className="mt-2 text-xs text-red-600 underline dark:text-red-400">
                                ← Go back and try another file
                            </button>
                        </div>
                    ) : preview ? (
                        <StepMapping preview={preview} mapping={mapping} onMappingChange={setMapping} />
                    ) : null
                )}

                {step === 3 && <StepDomain selected={domain} onSelect={setDomain} />}

                {step === 4 && preview && (
                    <StepValidate preview={preview} mapping={mapping} domain={domain} />
                )}

                {step === 5 && (
                    <StepImport result={importResult} importing={importing} error={importError} />
                )}
            </div>

            {/* Navigation */}
            {step < 5 && (
                <div className="flex items-center justify-between">
                    <button
                        onClick={handleBack}
                        disabled={step === 1}
                        className="flex items-center gap-2 rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-40 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800"
                    >
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                        Back
                    </button>

                    <button
                        onClick={handleNext}
                        disabled={!canNext[step]}
                        className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-700 disabled:opacity-40"
                    >
                        {step === 4 ? "Import Now" : "Next"}
                        {step < 4 && (
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                        )}
                    </button>
                </div>
            )}
        </div>
    );
}
