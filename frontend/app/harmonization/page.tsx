"use client";

import { useState } from "react";
import { PageHeader, Badge, useToast, EmptyState } from "../components/ui";
import { apiFetch } from "@/lib/api";
import { useLanguage } from "../contexts/LanguageContext";

interface HarmonizationChange {
    record_id: number;
    field: string;
    old_value: string | null;
    new_value: string | null;
}

interface StepDefinition {
    step_id: string;
    name: string;
    description: string;
    order: number;
    status: "pending" | "completed";
    last_run: string | null;
    last_records_updated: number | null;
}

interface PipelineStatus {
    steps: StepDefinition[];
    total_products: number;
}

interface PreviewResult {
    step_id: string;
    step_name: string;
    total_affected: number;
    sample_changes: HarmonizationChange[];
}

interface ApplyResult {
    step_id: string;
    step_name: string;
    records_updated: number;
    fields_modified: string[];
    log_id?: number;
}

interface LogEntry {
    id: number;
    step_id: string;
    step_name: string;
    records_updated: number;
    fields_modified: string[];
    executed_at: string | null;
    reverted: boolean;
}

interface UndoRedoResult {
    log_id: number;
    action: string;
    records_restored: number;
    step_id: string;
    step_name: string;
}

const STEP_ICONS: Record<string, React.ReactNode> = {
    consolidate_brands: (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 6h.008v.008H6V6z" />
        </svg>
    ),
    clean_entity_names: (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
        </svg>
    ),
    standardize_volumes: (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
        </svg>
    ),
    consolidate_gtin: (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
        </svg>
    ),
    fix_export_typos: (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125" />
        </svg>
    ),
};

function Spinner({ className = "h-4 w-4" }: { className?: string }) {
    return (
        <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
    );
}

export default function HarmonizationPage() {
    const { t } = useLanguage();
    const { toast } = useToast();
    const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
    const [loading, setLoading] = useState(false);
    const [previewing, setPreviewing] = useState<string | null>(null);
    const [previewData, setPreviewData] = useState<Record<string, PreviewResult>>({});
    const [applying, setApplying] = useState<string | null>(null);
    const [applyResults, setApplyResults] = useState<Record<string, ApplyResult>>({});
    const [expandedStep, setExpandedStep] = useState<string | null>(null);
    const [runningAll, setRunningAll] = useState(false);
    const [runAllResults, setRunAllResults] = useState<ApplyResult[] | null>(null);
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [showHistory, setShowHistory] = useState(false);
    const [undoingId, setUndoingId] = useState<number | null>(null);
    const [redoingId, setRedoingId] = useState<number | null>(null);

    async function fetchPipeline() {
        setLoading(true);
        try {
            const res = await apiFetch("/harmonization/steps");
            if (!res.ok) throw new Error("Failed to load pipeline");
            const data: PipelineStatus = await res.json();
            setPipeline(data);
        } catch (error) {
            toast("Error loading pipeline status", "error");
        } finally {
            setLoading(false);
        }
    }

    async function previewStep(stepId: string) {
        setPreviewing(stepId);
        try {
            const res = await apiFetch(`/harmonization/preview/${stepId}`, { method: "POST" });
            if (!res.ok) throw new Error("Preview failed");
            const data: PreviewResult = await res.json();
            setPreviewData((prev) => ({ ...prev, [stepId]: data }));
            setExpandedStep(stepId);
        } catch (error) {
            toast("Error previewing step", "error");
        } finally {
            setPreviewing(null);
        }
    }

    async function applyStep(stepId: string) {
        setApplying(stepId);
        try {
            const res = await apiFetch(`/harmonization/apply/${stepId}`, { method: "POST" });
            if (!res.ok) throw new Error("Apply failed");
            const data: ApplyResult = await res.json();
            setApplyResults((prev) => ({ ...prev, [stepId]: data }));
            // Clear preview since data changed
            setPreviewData((prev) => {
                const next = { ...prev };
                delete next[stepId];
                return next;
            });
            setExpandedStep(null);
            // Refresh pipeline status
            fetchPipeline();
        } catch (error) {
            toast("Error applying step", "error");
        } finally {
            setApplying(null);
        }
    }

    async function runAllSteps() {
        setRunningAll(true);
        setRunAllResults(null);
        try {
            const res = await apiFetch("/harmonization/apply-all", { method: "POST" });
            if (!res.ok) throw new Error("Pipeline failed");
            const data = await res.json();
            setRunAllResults(data.results);
            // Map results to applyResults
            const newResults: Record<string, ApplyResult> = {};
            for (const r of data.results) {
                newResults[r.step_id] = r;
            }
            setApplyResults(newResults);
            setPreviewData({});
            fetchPipeline();
        } catch (error) {
            toast("Error running pipeline", "error");
        } finally {
            setRunningAll(false);
        }
    }

    async function fetchLogs() {
        try {
            const res = await apiFetch("/harmonization/logs");
            if (!res.ok) throw new Error("Failed to load logs");
            const data: LogEntry[] = await res.json();
            setLogs(data);
        } catch (error) {
        }
    }

    async function undoLog(logId: number) {
        setUndoingId(logId);
        try {
            const res = await apiFetch(`/harmonization/undo/${logId}`, { method: "POST" });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Undo failed");
            }
            const data: UndoRedoResult = await res.json();
            toast(`Undo: ${data.records_restored} records restored for "${data.step_name}"`, "success");
            fetchLogs();
            fetchPipeline();
        } catch (error: unknown) {
            const message = error instanceof Error ? error.message : "Error undoing operation";
            toast(message, "error");
        } finally {
            setUndoingId(null);
        }
    }

    async function redoLog(logId: number) {
        setRedoingId(logId);
        try {
            const res = await apiFetch(`/harmonization/redo/${logId}`, { method: "POST" });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Redo failed");
            }
            const data: UndoRedoResult = await res.json();
            toast(`Redo: ${data.records_restored} records re-applied for "${data.step_name}"`, "success");
            fetchLogs();
            fetchPipeline();
        } catch (error: unknown) {
            const message = error instanceof Error ? error.message : "Error redoing operation";
            toast(message, "error");
        } finally {
            setRedoingId(null);
        }
    }

    const completedCount = pipeline ? pipeline.steps.filter((s) => s.status === "completed" || applyResults[s.step_id]).length : 0;
    const totalModified = Object.values(applyResults).reduce((sum, r) => sum + r.records_updated, 0);

    return (
        <div className="space-y-6">
            <PageHeader
                breadcrumbs={[{ label: "Home", href: "/" }, { label: t('page.harmonization.breadcrumb') }]}
                title={t('page.harmonization.title')}
                description={t('page.harmonization.description')}
                actions={
                    <button
                        onClick={fetchPipeline}
                        disabled={loading}
                        className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                    >
                        {loading ? <><Spinner /> Loading...</> : (
                            <>
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
                                </svg>
                                {pipeline ? t('page.harmonization.refresh_button') : t('page.harmonization.load_button')}
                            </>
                        )}
                    </button>
                }
            />

            {/* Stats row */}
            {pipeline && (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <p className="text-xs font-medium text-gray-500 dark:text-gray-400">{t('page.harmonization.stat_total_products')}</p>
                        <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{pipeline.total_products.toLocaleString()}</p>
                    </div>
                    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <p className="text-xs font-medium text-gray-500 dark:text-gray-400">{t('page.harmonization.stat_steps_completed')}</p>
                        <p className="mt-1 text-2xl font-bold text-green-600 dark:text-green-400">{completedCount} <span className="text-sm font-normal text-gray-400">/ {pipeline.steps.length}</span></p>
                    </div>
                    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <p className="text-xs font-medium text-gray-500 dark:text-gray-400">{t('page.harmonization.stat_steps_pending')}</p>
                        <p className="mt-1 text-2xl font-bold text-amber-600 dark:text-amber-400">{pipeline.steps.length - completedCount}</p>
                    </div>
                    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <p className="text-xs font-medium text-gray-500 dark:text-gray-400">{t('page.harmonization.stat_records_modified')}</p>
                        <p className="mt-1 text-2xl font-bold text-blue-600 dark:text-blue-400">{totalModified.toLocaleString()}</p>
                    </div>
                </div>
            )}

            {/* Run All results banner */}
            {runAllResults && (
                <div className="rounded-2xl border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-500/5">
                    <div className="flex items-center gap-2 mb-2">
                        <svg className="h-5 w-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span className="text-sm font-semibold text-green-800 dark:text-green-300">Pipeline completed successfully</span>
                    </div>
                    <div className="flex flex-wrap gap-3">
                        {runAllResults.map((r) => (
                            <span key={r.step_id} className="inline-flex items-center gap-1 rounded-lg bg-green-100 px-2.5 py-1 text-xs font-medium text-green-700 dark:bg-green-500/10 dark:text-green-400">
                                {r.step_name}: {r.records_updated} updated
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Pipeline steps */}
            {pipeline && (
                <div className="space-y-4">
                    {pipeline.steps.map((step, idx) => {
                        const isCompleted = step.status === "completed" || !!applyResults[step.step_id];
                        const hasPreview = !!previewData[step.step_id];
                        const isExpanded = expandedStep === step.step_id;

                        return (
                            <div key={step.step_id} className="relative">
                                {/* Connector line */}
                                {idx < pipeline.steps.length - 1 && (
                                    <div className="absolute left-[29px] top-[60px] h-[calc(100%-36px)] w-0.5 bg-gray-200 dark:bg-gray-800" />
                                )}

                                <div className={`rounded-2xl border bg-white p-5 transition-shadow dark:bg-gray-900 ${isCompleted
                                        ? "border-green-200 dark:border-green-800"
                                        : hasPreview
                                            ? "border-blue-200 dark:border-blue-800"
                                            : "border-gray-200 dark:border-gray-800"
                                    }`}>
                                    {/* Step header */}
                                    <div className="flex items-start justify-between gap-4">
                                        <div className="flex items-start gap-3">
                                            <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${isCompleted
                                                    ? "bg-green-100 text-green-600 dark:bg-green-500/10 dark:text-green-400"
                                                    : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
                                                }`}>
                                                {isCompleted ? (
                                                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                                    </svg>
                                                ) : (
                                                    STEP_ICONS[step.step_id] || <span className="text-sm font-bold">{step.order}</span>
                                                )}
                                            </div>
                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{step.name}</h3>
                                                    {isCompleted && (
                                                        <Badge variant="success">{t('page.harmonization.step_status_completed')}</Badge>
                                                    )}
                                                    {hasPreview && !isCompleted && (
                                                        <Badge variant="info">{t('page.harmonization.step_status_previewed')}</Badge>
                                                    )}
                                                </div>
                                                <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{step.description}</p>
                                                {step.last_run && (
                                                    <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                                                        Last run: {new Date(step.last_run).toLocaleString()} ({step.last_records_updated} records)
                                                    </p>
                                                )}
                                            </div>
                                        </div>

                                        {/* Actions */}
                                        <div className="flex shrink-0 items-center gap-2">
                                            <button
                                                onClick={() => previewStep(step.step_id)}
                                                disabled={previewing === step.step_id}
                                                className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-gray-200 px-3 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                                            >
                                                {previewing === step.step_id ? <><Spinner /> {t('page.harmonization.previewing')}</> : (
                                                    <>
                                                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                        </svg>
                                                        {t('page.harmonization.preview_button')}
                                                    </>
                                                )}
                                            </button>
                                            <button
                                                onClick={() => applyStep(step.step_id)}
                                                disabled={applying === step.step_id}
                                                className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-blue-600 px-3 text-xs font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                                            >
                                                {applying === step.step_id ? <><Spinner /> {t('page.harmonization.applying')}</> : t('page.harmonization.apply_button')}
                                            </button>
                                        </div>
                                    </div>

                                    {/* Apply result */}
                                    {applyResults[step.step_id] && (
                                        <div className="mt-3 rounded-xl border border-green-200 bg-green-50 p-3 dark:border-green-800 dark:bg-green-500/5">
                                            <div className="flex items-center gap-2">
                                                <svg className="h-4 w-4 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4" />
                                                </svg>
                                                <span className="text-xs font-medium text-green-700 dark:text-green-400">
                                                    {applyResults[step.step_id].records_updated} records updated
                                                    {applyResults[step.step_id].fields_modified.length > 0 && (
                                                        <> &middot; Fields: {applyResults[step.step_id].fields_modified.join(", ")}</>
                                                    )}
                                                </span>
                                            </div>
                                        </div>
                                    )}

                                    {/* Preview data (collapsible) */}
                                    {hasPreview && (
                                        <div className="mt-3">
                                            <button
                                                onClick={() => setExpandedStep(isExpanded ? null : step.step_id)}
                                                className="flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                                            >
                                                <svg className={`h-3.5 w-3.5 transition-transform ${isExpanded ? "rotate-90" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                                </svg>
                                                {previewData[step.step_id].total_affected} records will be modified
                                                {isExpanded ? " (click to collapse)" : " (click to expand)"}
                                            </button>

                                            {isExpanded && (
                                                <div className="mt-2 max-h-80 table-container rounded-xl border border-gray-100 bg-gray-50 dark:border-gray-800 dark:bg-gray-800">
                                                    <table className="w-full min-w-[600px] text-left text-xs">
                                                        <thead>
                                                            <tr className="border-b border-gray-200 dark:border-gray-700">
                                                                <th className="px-3 py-2 font-semibold text-gray-500 dark:text-gray-400">{t('page.harmonization.preview_table_id')}</th>
                                                                <th className="px-3 py-2 font-semibold text-gray-500 dark:text-gray-400">{t('page.harmonization.preview_table_field')}</th>
                                                                <th className="px-3 py-2 font-semibold text-gray-500 dark:text-gray-400">{t('page.harmonization.preview_table_before')}</th>
                                                                <th className="px-3 py-2 font-semibold text-gray-500 dark:text-gray-400">{t('page.harmonization.preview_table_after')}</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                                                            {previewData[step.step_id].sample_changes.map((change, i) => (
                                                                <tr key={i} className="hover:bg-gray-100 dark:hover:bg-gray-700/50">
                                                                    <td className="px-3 py-1.5 text-gray-500 dark:text-gray-400">#{change.record_id}</td>
                                                                    <td className="px-3 py-1.5">
                                                                        <code className="rounded bg-gray-200 px-1 py-0.5 text-gray-700 dark:bg-gray-700 dark:text-gray-300">{change.field}</code>
                                                                    </td>
                                                                    <td className="px-3 py-1.5 text-red-600 line-through dark:text-red-400">{change.old_value || "null"}</td>
                                                                    <td className="px-3 py-1.5 font-medium text-green-600 dark:text-green-400">{change.new_value}</td>
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                    {previewData[step.step_id].total_affected > previewData[step.step_id].sample_changes.length && (
                                                        <div className="border-t border-gray-200 px-3 py-2 text-xs text-gray-400 dark:border-gray-700 dark:text-gray-500">
                                                            Showing {previewData[step.step_id].sample_changes.length} of {previewData[step.step_id].total_affected} changes
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* History section */}
            {pipeline && (
                <div className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
                    <button
                        onClick={() => {
                            setShowHistory(!showHistory);
                            if (!showHistory) fetchLogs();
                        }}
                        className="flex w-full items-center justify-between p-5"
                    >
                        <div className="flex items-center gap-3">
                            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100 dark:bg-amber-500/10">
                                <svg className="h-5 w-5 text-amber-600 dark:text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                            </div>
                            <div className="text-left">
                                <h2 className="text-base font-semibold text-gray-900 dark:text-white">{t('page.harmonization.history_title')}</h2>
                                <p className="text-xs text-gray-500 dark:text-gray-400">{t('page.harmonization.history_description')}</p>
                            </div>
                        </div>
                        <svg className={`h-5 w-5 text-gray-400 transition-transform ${showHistory ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                    </button>

                    {showHistory && (
                        <div className="border-t border-gray-200 dark:border-gray-800">
                            {logs.length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-10">
                                    <svg className="mb-2 h-8 w-8 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                    <p className="text-sm text-gray-500 dark:text-gray-400">{t('page.harmonization.no_operations')}</p>
                                </div>
                            ) : (
                                <div className="divide-y divide-gray-100 dark:divide-gray-800">
                                    {logs.map((log) => (
                                        <div key={log.id} className="flex items-center justify-between px-5 py-3">
                                            <div className="flex items-center gap-3">
                                                <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${log.reverted
                                                        ? "bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500"
                                                        : "bg-green-100 text-green-600 dark:bg-green-500/10 dark:text-green-400"
                                                    }`}>
                                                    {log.reverted ? (
                                                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3" />
                                                        </svg>
                                                    ) : (
                                                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                                        </svg>
                                                    )}
                                                </div>
                                                <div>
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm font-medium text-gray-900 dark:text-white">{log.step_name}</span>
                                                        {log.reverted && (
                                                            <Badge variant="default">Reverted</Badge>
                                                        )}
                                                    </div>
                                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                                        {log.records_updated} records &middot; {log.fields_modified.join(", ")}
                                                        {log.executed_at && <> &middot; {new Date(log.executed_at).toLocaleString()}</>}
                                                    </p>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {!log.reverted ? (
                                                    <button
                                                        onClick={() => undoLog(log.id)}
                                                        disabled={undoingId === log.id}
                                                        className="inline-flex h-7 items-center gap-1 rounded-lg border border-red-200 px-2.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-500/5"
                                                    >
                                                        {undoingId === log.id ? <Spinner /> : (
                                                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3" />
                                                            </svg>
                                                        )}
                                                        {t('page.harmonization.undo_button')}
                                                    </button>
                                                ) : (
                                                    <button
                                                        onClick={() => redoLog(log.id)}
                                                        disabled={redoingId === log.id}
                                                        className="inline-flex h-7 items-center gap-1 rounded-lg border border-blue-200 px-2.5 text-xs font-medium text-blue-600 transition-colors hover:bg-blue-50 disabled:opacity-50 dark:border-blue-800 dark:text-blue-400 dark:hover:bg-blue-500/5"
                                                    >
                                                        {redoingId === log.id ? <Spinner /> : (
                                                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l6-6m0 0l-6-6m6 6H9a6 6 0 000 12h3" />
                                                            </svg>
                                                        )}
                                                        {t('page.harmonization.redo_button')}
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* Empty state */}
            {!pipeline && !loading && (
                <EmptyState
                  icon="document"
                  title={t('page.harmonization.empty_title')}
                  description={t('page.harmonization.empty_description')}
                  size="page"
                />
            )}

            {/* Loading state */}
            {loading && !pipeline && (
                <div className="flex h-64 items-center justify-center">
                    <Spinner className="h-8 w-8 text-blue-600" />
                </div>
            )}

            {/* Sticky bottom bar */}
            {pipeline && (
                <div className="sticky bottom-0 rounded-2xl border border-gray-200 bg-white p-4 shadow-lg dark:border-gray-800 dark:bg-gray-900">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-gray-900 dark:text-white">
                                {completedCount} of {pipeline.steps.length} steps completed
                            </p>
                            {totalModified > 0 && (
                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                    {totalModified.toLocaleString()} total records modified in this session
                                </p>
                            )}
                        </div>
                        <button
                            onClick={runAllSteps}
                            disabled={runningAll}
                            className="inline-flex h-10 items-center gap-2 rounded-lg bg-green-600 px-5 text-sm font-medium text-white transition-colors hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {runningAll ? (
                                <><Spinner /> {t('page.harmonization.running')}</>
                            ) : (
                                <>
                                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3l14 9-14 9V3z" />
                                    </svg>
                                    {t('page.harmonization.run_all_button')}
                                </>
                            )}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
