"use client";

import { useState, useRef, useEffect } from "react";
import { PageHeader, useToast, ErrorBanner } from "../components/ui";
import DataSourceSchemaAnalyzer from "../components/DataSourceSchemaAnalyzer";
import { useDomain } from "../contexts/DomainContext";
import { apiFetch } from "@/lib/api";
import { useLanguage } from "../contexts/LanguageContext";

interface UploadResult {
    message: string;
    total_rows: number;
    matched_columns: string[];
    unmatched_columns: string[];
    format?: string;
    domain?: string;
}

interface PurgeResult {
    products_deleted: number;
    rules_deleted: number;
}

export default function ImportExportPage() {
    const { activeDomain } = useDomain();
    const { toast } = useToast();
    const { t } = useLanguage();
    const [dragOver, setDragOver] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const [exporting, setExporting] = useState(false);
    const [exportSearch, setExportSearch] = useState("");
    const [totalProducts, setTotalProducts] = useState<number | null>(null);
    const [purging, setPurging] = useState(false);
    const [purgeConfirm, setPurgeConfirm] = useState(false);
    const [purgeRules, setPurgeRules] = useState(false);
    const [purgeResult, setPurgeResult] = useState<PurgeResult | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        async function fetchCount() {
            try {
                const res = await apiFetch("/stats");
                if (res.ok) {
                    const data = await res.json();
                    setTotalProducts(data.total_entities ?? data.total_products ?? null);
                }
            } catch {
                // silently fail
            }
        }
        fetchCount();
    }, [uploadResult, purgeResult]);

    async function handleUpload(file: File) {
        const allowed = [".xlsx", ".csv", ".json", ".xml", ".parquet", ".jsonld", ".rdf", ".ttl", ".bib", ".ris"];
        const isAllowed = allowed.some(ext => file.name.toLowerCase().endsWith(ext));
        if (!isAllowed) {
            setUploadError(`Only supported formats (${allowed.join(", ")}) are allowed.`);
            return;
        }

        setUploading(true);
        setUploadResult(null);
        setUploadError(null);

        try {
            const formData = new FormData();
            formData.append("file", file);

            const res = await apiFetch("/upload", {
                method: "POST",
                body: formData,
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Upload failed");
            }

            const data: UploadResult = await res.json();
            setUploadResult(data);
        } catch (error) {
            setUploadError(error instanceof Error ? error.message : "Upload failed");
        } finally {
            setUploading(false);
        }
    }

    function handleDrop(e: React.DragEvent) {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file) handleUpload(file);
    }

    function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0];
        if (file) handleUpload(file);
        e.target.value = "";
    }

    async function handleExport() {
        setExporting(true);
        try {
            const params = exportSearch ? `?search=${encodeURIComponent(exportSearch)}` : "";
            const res = await apiFetch(`/export${params}`);
            if (!res.ok) throw new Error("Export failed");

            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "products_export.xlsx";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (error) {
            toast(error instanceof Error ? error.message : "Export failed", "error");
        } finally {
            setExporting(false);
        }
    }

    async function handlePurge() {
        setPurging(true);
        setPurgeResult(null);
        try {
            const params = purgeRules ? "?include_rules=true" : "";
            const res = await apiFetch(`/entities/all${params}`, {
                method: "DELETE",
            });
            if (!res.ok) throw new Error("Purge failed");
            const data: PurgeResult = await res.json();
            setPurgeResult(data);
            setPurgeConfirm(false);
            setUploadResult(null);
        } catch (error) {
            toast(error instanceof Error ? error.message : "Purge failed", "error");
        } finally {
            setPurging(false);
        }
    }

    return (
        <div className="space-y-6">
            <PageHeader
                breadcrumbs={[{ label: "Home", href: "/" }, { label: t('page.import_export.title') }]}
                title={t('page.import_export.title')}
                description="Upload and download dataset in Excel, CSV, JSON-LD, Parquet, and RDF formats"
            />
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                {/* Import section */}
                <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                    <div className="mb-5 flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-green-100 dark:bg-green-500/10">
                            <svg className="h-5 w-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                            </svg>
                        </div>
                        <div>
                            <h3 className="text-base font-semibold text-gray-900 dark:text-white">{t('page.import_export.import_title')}</h3>
                            <p className="text-xs text-gray-500 dark:text-gray-400">Excel, CSV, JSON, XML, Parquet, RDF · BibTeX, RIS (Science)</p>
                        </div>
                    </div>

                    {/* Drop zone */}
                    <div
                        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                        onDragLeave={() => setDragOver(false)}
                        onDrop={handleDrop}
                        onClick={() => fileInputRef.current?.click()}
                        className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-12 transition-colors ${dragOver
                            ? "border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-500/5"
                            : "border-gray-300 hover:border-gray-400 dark:border-gray-700 dark:hover:border-gray-600"
                            }`}
                    >
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".xlsx,.csv,.json,.xml,.parquet,.jsonld,.rdf,.ttl,.bib,.ris"
                            onChange={handleFileSelect}
                            className="hidden"
                        />
                        {uploading ? (
                            <>
                                <svg className="mb-3 h-8 w-8 animate-spin text-blue-600" aria-hidden="true" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('page.import_export.uploading')}</p>
                                <span className="sr-only">Processing file upload</span>
                            </>
                        ) : (
                            <>
                                <svg className="mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12l-3-3m0 0l-3 3m3-3v6m-1.5-15H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                                </svg>
                                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                                    {t('page.import_export.drop_zone_text')}
                                </p>
                                <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">Excel · CSV · JSON · XML · Parquet · RDF</p>
                                <p className="mt-0.5 text-xs text-violet-500 dark:text-violet-400">BibTeX (.bib) · RIS (.ris) — auto-maps to Science domain</p>
                            </>
                        )}
                    </div>

                    {/* Upload result */}
                    {uploadResult && (
                        <div className="mt-4 rounded-xl border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-500/5">
                            <div className="flex items-center gap-2 mb-3">
                                <svg className="h-5 w-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                <span className="text-sm font-semibold text-green-800 dark:text-green-300">{t('page.import_export.import_success')}</span>
                                {uploadResult.domain === "science" && (
                                    <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-violet-100 px-2.5 py-0.5 text-xs font-medium text-violet-700 dark:bg-violet-500/10 dark:text-violet-400">
                                        <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1 1 .03 2.798-1.414 2.798H4.212c-1.444 0-2.414-1.798-1.414-2.798L4.2 15.3" />
                                        </svg>
                                        Science Domain · {uploadResult.format?.toUpperCase()}
                                    </span>
                                )}
                            </div>
                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-green-700 dark:text-green-400">{t('page.import_export.records_imported_label')}</span>
                                    <span className="font-semibold text-green-900 dark:text-green-200">{uploadResult.total_rows.toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-green-700 dark:text-green-400">{t('page.import_export.fields_mapped_label')}</span>
                                    <span className="font-semibold text-green-900 dark:text-green-200">{uploadResult.matched_columns.length}</span>
                                </div>
                                {uploadResult.domain === "science" && (
                                    <div className="mt-2 pt-2 border-t border-green-200 dark:border-green-800">
                                        <p className="text-xs text-green-600 dark:text-green-400">
                                            Mapped: title → primary_label · DOI → canonical_id · first author → secondary_label · keywords → enrichment_concepts
                                        </p>
                                    </div>
                                )}
                                {uploadResult.unmatched_columns.length > 0 && (
                                    <div className="mt-2 pt-2 border-t border-green-200 dark:border-green-800">
                                        <p className="text-xs font-medium text-amber-700 dark:text-amber-400 mb-1">
                                            Unrecognized columns ({uploadResult.unmatched_columns.length}):
                                        </p>
                                        <div className="flex flex-wrap gap-1.5">
                                            {uploadResult.unmatched_columns.map((col) => (
                                                <span key={col} className="inline-flex rounded-md bg-amber-100 px-2 py-0.5 text-xs text-amber-700 dark:bg-amber-500/10 dark:text-amber-400">
                                                    {col}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Upload error */}
                    {uploadError && (
                        <div className="mt-4">
                            <ErrorBanner message="Import Failed" detail={uploadError} variant="card" />
                        </div>
                    )}
                </div>

                <DataSourceSchemaAnalyzer />

                {/* Export section */}
                <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                    <div className="mb-5 flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-500/10">
                            <svg className="h-5 w-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                            </svg>
                        </div>
                        <div>
                            <h3 className="text-base font-semibold text-gray-900 dark:text-white">{t('page.import_export.export_title')}</h3>
                            <p className="text-xs text-gray-500 dark:text-gray-400">Download products as Excel with original column headers</p>
                        </div>
                    </div>

                    {/* Info card */}
                    <div className="mb-5 rounded-xl bg-gray-50 p-4 dark:bg-gray-800">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-gray-500 dark:text-gray-400">{t('page.import_export.total_records_label')}</p>
                                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                                    {totalProducts != null ? totalProducts.toLocaleString() : "—"}
                                </p>
                            </div>
                            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-500/10">
                                <svg className="h-6 w-6 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                                </svg>
                            </div>
                        </div>
                    </div>

                    {/* Search filter */}
                    <div className="mb-4">
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Filter before export (optional)
                        </label>
                        <div className="relative">
                            <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                            <input
                                type="text"
                                placeholder="Search dataset by attribute keywords..."
                                value={exportSearch}
                                onChange={(e) => setExportSearch(e.target.value)}
                                className="h-10 w-full rounded-lg border border-gray-200 bg-white pl-10 pr-4 text-sm text-gray-700 placeholder-gray-400 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:placeholder-gray-500"
                            />
                        </div>
                        {exportSearch && (
                            <p className="mt-1.5 text-xs text-gray-400 dark:text-gray-500">
                                Only matching products will be exported
                            </p>
                        )}
                    </div>

                    {/* Export button */}
                    <button
                        onClick={handleExport}
                        disabled={exporting || totalProducts === 0}
                        className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {exporting ? (
                            <>
                                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                                {t('page.import_export.exporting')}
                            </>
                        ) : (
                            <>
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                </svg>
                                {t('page.import_export.export_button')}
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* Danger zone */}
            <div className="rounded-2xl border border-red-200 bg-white dark:border-red-900 dark:bg-gray-900">
                <div className="border-b border-red-200 px-5 py-4 dark:border-red-900">
                    <div className="flex items-center gap-2">
                        <svg className="h-5 w-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                        </svg>
                        <h3 className="text-base font-semibold text-red-700 dark:text-red-400">{t('page.import_export.danger_zone_title')}</h3>
                    </div>
                    <p className="mt-0.5 text-xs text-red-500 dark:text-red-500">Irreversible actions - proceed with caution</p>
                </div>
                <div className="p-5">
                    {purgeResult ? (
                        <div className="mb-4 rounded-xl border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-500/5">
                            <div className="flex items-center gap-2">
                                <svg className="h-5 w-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                <span className="text-sm font-semibold text-green-800 dark:text-green-300">{t('page.import_export.purge_success')}</span>
                            </div>
                            <p className="mt-1 text-sm text-green-700 dark:text-green-400">
                                {purgeResult.products_deleted.toLocaleString()} products deleted
                                {purgeResult.rules_deleted > 0 && `, ${purgeResult.rules_deleted} rules deleted`}
                            </p>
                        </div>
                    ) : null}

                    {!purgeConfirm ? (
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium text-gray-900 dark:text-white">Delete all product records</p>
                                <p className="text-xs text-gray-500 dark:text-gray-400">Remove all products from the database to start a fresh import</p>
                            </div>
                            <button
                                onClick={() => setPurgeConfirm(true)}
                                disabled={totalProducts === 0}
                                className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-red-200 px-4 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-500/5"
                            >
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                                </svg>
                                {t('page.import_export.purge_button')}
                            </button>
                        </div>
                    ) : (
                        <div className="rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-500/5">
                            <p className="mb-3 text-sm font-semibold text-red-800 dark:text-red-300">
                                Are you sure? This will permanently delete all {totalProducts?.toLocaleString()} product records.
                            </p>
                            <label className="mb-4 flex items-center gap-2 text-sm text-red-700 dark:text-red-400">
                                <input
                                    type="checkbox"
                                    checked={purgeRules}
                                    onChange={(e) => setPurgeRules(e.target.checked)}
                                    className="h-4 w-4 rounded border-red-300 text-red-600 focus:ring-red-500"
                                />
                                Also delete all normalization rules
                            </label>
                            <div className="flex gap-2">
                                <button
                                    onClick={handlePurge}
                                    disabled={purging}
                                    className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-red-600 px-4 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
                                >
                                    {purging ? (
                                        <>
                                            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                            </svg>
                                            {t('page.import_export.deleting')}
                                        </>
                                    ) : (
                                        t('page.import_export.purge_confirm_button')
                                    )}
                                </button>
                                <button
                                    onClick={() => { setPurgeConfirm(false); setPurgeRules(false); }}
                                    className="inline-flex h-9 items-center rounded-lg border border-gray-200 px-4 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                                >
                                    Cancel
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Science Import card */}
            <div className="rounded-2xl border border-violet-200 bg-violet-50 p-5 dark:border-violet-900 dark:bg-violet-500/5">
                <div className="flex items-start gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-100 dark:bg-violet-500/10">
                        <svg className="h-5 w-5 text-violet-600 dark:text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1 1 .03 2.798-1.414 2.798H4.212c-1.444 0-2.414-1.798-1.414-2.798L4.2 15.3" />
                        </svg>
                    </div>
                    <div className="flex-1">
                        <h3 className="text-base font-semibold text-violet-900 dark:text-violet-200">Science Domain Import — BibTeX & RIS</h3>
                        <p className="mt-1 text-sm text-violet-700 dark:text-violet-400">
                            Drop a <strong>.bib</strong> (BibTeX) or <strong>.ris</strong> file exported from Zotero, Mendeley, EndNote, or any reference manager. UKIP auto-maps academic fields to the Science domain schema.
                        </p>
                        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                            {[
                                { from: "title", to: "primary_label" },
                                { from: "doi", to: "canonical_id" },
                                { from: "author / AU", to: "secondary_label" },
                                { from: "keywords / KW", to: "enrichment_concepts" },
                                { from: "journal / JO", to: "attrs · journal" },
                                { from: "year / PY", to: "attrs · year" },
                                { from: "abstract / AB", to: "attrs · abstract" },
                                { from: "entry type / TY", to: "entity_type" },
                            ].map(({ from, to }) => (
                                <div key={from} className="rounded-lg border border-violet-200 bg-white px-3 py-2 dark:border-violet-800 dark:bg-gray-900">
                                    <code className="block text-xs font-medium text-violet-600 dark:text-violet-400">{from}</code>
                                    <span className="text-xs text-gray-400">→</span>
                                    <code className="block text-xs text-gray-600 dark:text-gray-400">{to}</code>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* Column mapping reference */}
            <div className="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
                    <h3 className="text-base font-semibold text-gray-900 dark:text-white">{t('page.import_export.reference_title')}</h3>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Expected Excel columns mapped to database fields</p>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                        <thead>
                            <tr className="border-b border-gray-200 dark:border-gray-800">
                                <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">{t('page.import_export.reference_header_excel')}</th>
                                <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">{t('page.import_export.reference_header_field')}</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                            {activeDomain ? (
                                activeDomain.attributes.map((attr) => (
                                    <tr key={attr.name} className="transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50">
                                        <td className="px-5 py-2.5 font-medium text-gray-900 dark:text-white">{attr.label}</td>
                                        <td className="px-5 py-2.5">
                                            <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-blue-600 dark:bg-gray-800 dark:text-blue-400">
                                                {attr.name}
                                            </code>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={2} className="px-5 py-4 text-center text-sm text-gray-500">
                                        {t('page.import_export.loading_schema')}
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
                <div className="border-t border-gray-200 px-5 py-3 dark:border-gray-800">
                    <p className="text-xs text-gray-400 dark:text-gray-500">Showing 17 of 34 mapped columns. Additional GTIN, product code, and configuration columns are also supported.</p>
                </div>
            </div>
        </div>
    );
}
