"use client";

import { useLanguage } from "../contexts/LanguageContext";
import { useAssistantContextRegistration } from "../contexts/AssistantContext";
import { PageHeader } from "../components/ui";
import {
    getSteps,
    StepBar,
    StepDomain,
    StepImport,
    StepMapping,
    StepUpload,
    StepValidate,
} from "./importWizardParts";
import useImportWizardController from "./useImportWizardController";

export default function ImportWizardPage() {
    const { t } = useLanguage();
    const tr = (key: string, fallback: string) => {
        const value = t(key);
        return value === key ? fallback : value;
    };
    const {
        step,
        file,
        previewing,
        previewError,
        preview,
        mapping,
        domain,
        importing,
        importResult,
        importError,
        canNext,
        setStep,
        setMapping,
        setDomain,
        handleFile,
        handleNext,
        handleBack,
    } = useImportWizardController();
    const steps = getSteps(t);
    useAssistantContextRegistration({
        route: "/import",
        domainId: domain || "default",
        moduleLabel: "Ingesta y mapeo",
        totalEntities: preview?.row_count ?? importResult?.total_rows ?? null,
        activeSources: file ? 1 : 0,
        leadingGap: previewError || importError || null,
        recommendedActions: [
            `Paso actual: ${steps[step - 1]?.label ?? step}`,
            preview ? `${Object.values(mapping).filter(Boolean).length}/${preview.columns.length} columnas mapeadas` : "Cargar preview para detectar columnas",
            domain ? `Dominio destino: ${domain}` : "Confirmar dominio destino",
        ],
    });
    const stepGuidance: Record<number, { title: string; body: string }> = {
        1: {
            title: t("page.import.guided.upload.title"),
            body: t("page.import.guided.upload.body"),
        },
        2: {
            title: t("page.import.guided.mapping.title"),
            body: t("page.import.guided.mapping.body"),
        },
        3: {
            title: t("page.import.guided.domain.title"),
            body: t("page.import.guided.domain.body"),
        },
        4: {
            title: t("page.import.guided.validate.title"),
            body: t("page.import.guided.validate.body"),
        },
        5: {
            title: t("page.import.guided.import.title"),
            body: t("page.import.guided.import.body"),
        },
    };
    const wizardSummary = [
        {
            label: tr("page.import.summary.file", "File"),
            value: file?.name ?? tr("page.import.summary.file_empty", "Not selected"),
            detail: file ? tr("page.import.summary.file_ready", "The import source is already loaded.") : tr("page.import.summary.file_waiting", "Choose the file that will anchor this import."),
        },
        {
            label: tr("page.import.summary.mapping", "Mapping"),
            value: preview ? `${Object.values(mapping).filter(Boolean).length}/${preview.columns.length}` : "—",
            detail: preview
                ? tr("page.import.summary.mapping_ready", "UKIP already knows how many columns are mapped.")
                : tr("page.import.summary.mapping_waiting", "Preview is needed before field mapping can start."),
        },
        {
            label: tr("page.import.summary.domain", "Domain"),
            value: domain,
            detail: step >= 3
                ? tr("page.import.summary.domain_ready", "This is where the imported records will land.")
                : tr("page.import.summary.domain_waiting", "You will confirm the target domain before importing."),
        },
    ];

    return (
        <div className="space-y-6">
            <PageHeader
                breadcrumbs={[
                    { label: t("nav.home"), href: "/" },
                    { label: t("page.import.title") },
                ]}
                title={t("page.import.title")}
                description={t("page.import.description")}
            />

            <div className="flex justify-center py-2">
                <StepBar current={step} />
            </div>

            <div className="rounded-2xl border border-indigo-200 bg-indigo-50/80 p-4 shadow-sm dark:border-indigo-500/20 dark:bg-indigo-500/5">
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-indigo-600 dark:text-indigo-300">
                    {t("page.import.guided.eyebrow")}
                </p>
                <p className="mt-1 text-sm font-semibold text-indigo-900 dark:text-indigo-100">
                    {stepGuidance[step].title}
                </p>
                <p className="mt-1 text-sm text-indigo-700 dark:text-indigo-300">
                    {stepGuidance[step].body}
                </p>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
                {wizardSummary.map((card) => (
                    <div
                        key={card.label}
                        className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900"
                    >
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-gray-400 dark:text-gray-500">
                            {card.label}
                        </p>
                        <p className="mt-2 truncate text-sm font-semibold text-gray-900 dark:text-white">
                            {card.value}
                        </p>
                        <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
                            {card.detail}
                        </p>
                    </div>
                ))}
            </div>

            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h2 className="mb-5 text-sm font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                    {t("page.import.step_label")} {step} - {steps[step - 1].label}
                </h2>

                {step === 1 && <StepUpload file={file} onFile={handleFile} />}

                {step === 2 && (
                    previewing ? (
                        <div className="flex flex-col items-center gap-3 py-12">
                            <svg className="h-7 w-7 animate-spin text-indigo-600" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                            <p className="text-sm text-gray-500">{t("page.import.loading_preview")}</p>
                        </div>
                    ) : previewError ? (
                        <div className="rounded-xl border border-red-200 bg-red-50 p-5 dark:border-red-500/30 dark:bg-red-500/5">
                            <p className="text-sm font-medium text-red-700 dark:text-red-400">{previewError}</p>
                            <button onClick={() => setStep(1)} className="mt-2 text-xs text-red-600 underline dark:text-red-400">
                                {t("page.import.try_another_file")}
                            </button>
                        </div>
                    ) : preview ? (
                        <StepMapping preview={preview} mapping={mapping} onMappingChange={setMapping} />
                    ) : null
                )}

                {step === 3 && <StepDomain selected={domain} onSelect={setDomain} />}

                {step === 4 && preview && <StepValidate preview={preview} mapping={mapping} domain={domain} />}

                {step === 5 && <StepImport result={importResult} importing={importing} error={importError} />}
            </div>

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
                        {t("common.back")}
                    </button>

                    <button
                        onClick={handleNext}
                        disabled={!canNext[step]}
                        className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-700 disabled:opacity-40"
                    >
                        {step === 4 ? t("page.import.import_now") : t("common.next")}
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
