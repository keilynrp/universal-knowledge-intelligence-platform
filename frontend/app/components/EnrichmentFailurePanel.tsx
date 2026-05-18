"use client";

import { useState } from "react";
import { useLanguage } from "../contexts/LanguageContext";

interface EnrichmentFailure {
    code: string;
    evidence: string;
    recommendations: string[];
    provider_attempts: string[];
    record_snapshot?: {
        primary_label?: string;
        canonical_id?: string;
        enrichment_doi?: string;
        domain?: string;
    };
    failed_at?: string;
}

export function EnrichmentFailureIcon({
    failure,
    onToggle,
    expanded,
}: {
    failure: EnrichmentFailure | null;
    onToggle: () => void;
    expanded: boolean;
}) {
    return (
        <button
            onClick={onToggle}
            className={`ml-1 inline-flex h-5 w-5 items-center justify-center rounded-full text-xs transition-colors ${
                expanded
                    ? "bg-red-200 text-red-800 dark:bg-red-700 dark:text-red-200"
                    : "bg-red-100 text-red-600 hover:bg-red-200 dark:bg-red-900/40 dark:text-red-400 dark:hover:bg-red-800/60"
            }`}
            title={failure ? failure.code : "Enrichment failed"}
        >
            !
        </button>
    );
}

export function EnrichmentFailureDetails({ failure }: { failure: EnrichmentFailure }) {
    const { t } = useLanguage();
    const codeLabel = t(`page.entity_table.enrichment_failure_code.${failure.code}`) || failure.code;

    return (
        <div className="mt-2 rounded-xl border border-red-200 bg-red-50/50 p-3 text-xs dark:border-red-800/40 dark:bg-red-900/10">
            <div className="flex items-center gap-2">
                <span className="font-bold text-red-700 dark:text-red-400">{codeLabel}</span>
                {failure.failed_at && (
                    <span className="text-red-400 dark:text-red-500">
                        {new Date(failure.failed_at).toLocaleString()}
                    </span>
                )}
            </div>

            <p className="mt-1.5 text-red-700/80 dark:text-red-300/70">
                <span className="font-semibold">{t("page.entity_table.enrichment_failure_evidence")}:</span>{" "}
                {failure.evidence}
            </p>

            {failure.provider_attempts.length > 0 && (
                <p className="mt-1 text-red-600/70 dark:text-red-400/60">
                    <span className="font-semibold">{t("page.entity_table.enrichment_failure_providers")}:</span>{" "}
                    {failure.provider_attempts.join(", ")}
                </p>
            )}

            {failure.recommendations.length > 0 && (
                <div className="mt-2">
                    <p className="font-semibold text-red-700 dark:text-red-400">
                        {t("page.entity_table.enrichment_failure_recommendations")}:
                    </p>
                    <ul className="mt-1 list-inside list-disc space-y-0.5 text-red-700/80 dark:text-red-300/70">
                        {failure.recommendations.map((rec, i) => (
                            <li key={i}>{rec}</li>
                        ))}
                    </ul>
                </div>
            )}

            {failure.record_snapshot && (
                <div className="mt-2 rounded-lg bg-red-100/50 p-2 dark:bg-red-900/20">
                    <p className="font-semibold text-red-700 dark:text-red-400">
                        {t("page.entity_table.enrichment_failure_snapshot")}:
                    </p>
                    <div className="mt-1 space-y-0.5 text-red-600/80 dark:text-red-300/60">
                        {failure.record_snapshot.primary_label && <p>Title: {failure.record_snapshot.primary_label}</p>}
                        {failure.record_snapshot.canonical_id && <p>ID: {failure.record_snapshot.canonical_id}</p>}
                        {failure.record_snapshot.enrichment_doi && <p>DOI: {failure.record_snapshot.enrichment_doi}</p>}
                    </div>
                </div>
            )}
        </div>
    );
}

export function useFailurePanelState() {
    const [expandedFailureId, setExpandedFailureId] = useState<number | null>(null);

    function toggleFailure(entityId: number) {
        setExpandedFailureId((prev) => (prev === entityId ? null : entityId));
    }

    return { expandedFailureId, toggleFailure };
}

export function parseEnrichmentFailure(attributesJson: string | null | undefined): EnrichmentFailure | null {
    if (!attributesJson) return null;
    try {
        const attrs = JSON.parse(attributesJson);
        return attrs.enrichment_failure ?? null;
    } catch {
        return null;
    }
}
