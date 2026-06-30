"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { EntityConcept, ErrorBanner, PageHeader, QualityBadge } from "../../../../components/ui";
import { JournalSignalBadge } from "../../../../components/JournalSignalBadge";
import { JournalMetricsSection } from "../../../../components/JournalMetricsSection";
import { useLanguage } from "../../../../contexts/LanguageContext";

interface CatalogRecord {
  id: number;
  primary_label: string | null;
  secondary_label: string | null;
  canonical_id: string | null;
  entity_type: string | null;
  domain: string | null;
  validation_status: string | null;
  enrichment_status: string | null;
  enrichment_citation_count: number | null;
  quality_score: number | null;
  source: string | null;
  attributes_json: string | null;
  normalized_json: string | null;
  enrichment_issn_l?: string | null;
  journal_nif_bayes_ready?: boolean;
  journal_display_name?: string | null;
  journal_nif?: number | null;
  journal_nif_bayes?: number | null;
  journal_nif_ci_low?: number | null;
  journal_nif_ci_high?: number | null;
}

async function readCatalogError(
  response: Response,
  fallback: string,
): Promise<string> {
  const payload = await response.json().catch(() => null);
  const detail =
    typeof payload?.detail === "string"
      ? payload.detail
      : typeof payload?.message === "string"
        ? payload.message
        : null;
  if (response.status === 404) {
    return fallback;
  }
  return detail || fallback;
}

function parseJson(raw: string | null): Record<string, unknown> {
  if (!raw) return {};
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatQualityPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value * 100)}%`;
}

function resolveEnrichmentHeading(
  t: (key: string) => string,
  fallback: string,
  status: string | null | undefined,
): string {
  if (status === "completed") {
    const translated = t("entities.filter.enriched");
    return translated === "entities.filter.enriched" ? fallback : translated;
  }
  return fallback;
}

function buildEnrichmentSummary(
  t: (key: string) => string,
  status: string | null | undefined,
  score: number | null | undefined,
): string {
  const label = resolveEnrichmentHeading(t, "Enriquecido", status);
  const percent = formatQualityPercent(score);
  return `${label} ${percent}`;
}

export default function CatalogRecordPage() {
  const { slug, id } = useParams<{ slug: string; id: string }>();
  const { t } = useLanguage();
  const tr = useCallback((key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  }, [t]);

  const [record, setRecord] = useState<CatalogRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadRecord = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await apiFetch(`/catalogs/${slug}/records/${id}`);
        if (!res.ok) {
          throw new Error(
            await readCatalogError(
              res,
              tr("catalogs.record_load_failed", "This catalog record is not available right now."),
            ),
          );
        }
        setRecord(await res.json());
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : tr("catalogs.record_load_failed", "Failed to load this catalog record."));
      } finally {
        setLoading(false);
      }
    };
    void loadRecord();
  }, [slug, id, tr]);

  const mergedAttributes = useMemo(() => {
    if (!record) return {};
    return {
      ...parseJson(record.attributes_json),
      ...parseJson(record.normalized_json),
    };
  }, [record]);

  // Prefer the attached enrichment_issn_l; fall back to attributes_json.issn_l
  // (same shape the entity detail page reads) so the journal metrics card shows
  // wherever the record resolved to a journal.
  const issnL = useMemo(() => {
    if (!record) return null;
    if (record.enrichment_issn_l && record.enrichment_issn_l.trim()) {
      return record.enrichment_issn_l.trim();
    }
    const fromAttrs = mergedAttributes.issn_l;
    return typeof fromAttrs === "string" && fromAttrs.trim() ? fromAttrs.trim() : null;
  }, [record, mergedAttributes]);

  // Prefer the authoritative journal name resolved from enrichment_issn_l.
  const journalName = record
    ? record.journal_display_name
      || (typeof mergedAttributes.journal === "string" ? mergedAttributes.journal : null)
      || (typeof mergedAttributes.venue === "string" ? mergedAttributes.venue : null)
    : null;

  const coreFields = record ? [
    { key: "primary_label", label: tr("entities.primary_label", "Primary label"), value: record.primary_label },
    { key: "secondary_label", label: tr("page.import.field.secondary_label", "Secondary label"), value: record.secondary_label },
    ...(journalName ? [{ key: "journal", label: tr("catalogs.record.journal", "Journal"), value: journalName }] : []),
    { key: "canonical_id", label: tr("page.import.field.canonical_id", "Canonical ID"), value: record.canonical_id },
    { key: "entity_type", label: tr("page.import.field.entity_type", "Entity type"), value: record.entity_type },
    { key: "domain", label: tr("page.import.field.domain", "Domain"), value: record.domain },
  ] : [];

  const systemFields = record ? [
    { label: tr("entities.enrichment_status", "System status"), value: record.enrichment_status },
    { label: tr("page.exec_dashboard.source", "Source"), value: record.source },
    { label: tr("page.import.field.enrichment_citation_count", "Citation count"), value: record.enrichment_citation_count },
    { label: resolveEnrichmentHeading(t, "Enriquecido", record.enrichment_status), value: formatQualityPercent(record.quality_score), isQuality: true },
    { label: tr("page.import.field.validation_status", "Validation status"), value: record.validation_status },
  ] : [];

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumbs={[
          { label: tr("nav.home", "Knowledge Explorer"), href: "/" },
          { label: tr("nav.catalogs", "Catalog Portals"), href: "/catalogs" },
          { label: slug, href: `/catalogs/${slug}` },
          { label: record?.primary_label || tr("catalogs.record_title_loading", "Record detail") },
        ]}
        title={record?.primary_label || tr("catalogs.record_title_loading", "Catalog record")}
        description={tr("catalogs.record_subtitle", "Expanded record metadata for a friendlier, catalog-style consultation flow.")}
      />

      {error && <ErrorBanner message={error} />}

      {loading && (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-24 animate-pulse rounded-2xl bg-gray-100 dark:bg-gray-800" />
          ))}
        </div>
      )}

      {record && (
        <>
          <div className="flex items-center justify-between">
            <Link
              href={`/catalogs/${slug}`}
              className="inline-flex items-center rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
            >
              ← {tr("catalogs.back_to_results", "Back to results")}
            </Link>
          </div>

          <section className="rounded-2xl border border-sky-200 bg-sky-50/80 px-5 py-4 shadow-sm dark:border-sky-900/40 dark:bg-sky-950/20">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-700 dark:text-sky-400">
                  {tr("catalogs.record.readiness_eyebrow", "Record readiness")}
                </p>
                <h2 className="mt-1 text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {tr("catalogs.record.readiness_title", "Enrichment signal for this record")}
                </h2>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                  {tr("catalogs.record.readiness_body", "This percentage reflects how complete and ready the record is for consultation inside the catalog experience.")}
                </p>
                {record.journal_nif_bayes_ready ? (
                  <div className="mt-3">
                    <JournalSignalBadge
                      ready
                      nif={record.journal_nif}
                      nifBayes={record.journal_nif_bayes}
                      ciLow={record.journal_nif_ci_low}
                      ciHigh={record.journal_nif_ci_high}
                      journalName={record.journal_display_name}
                      size="md"
                    />
                  </div>
                ) : null}
              </div>
              <div className="rounded-2xl border border-white/70 bg-white/80 px-4 py-3 dark:border-slate-800 dark:bg-slate-900/70">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
                  {resolveEnrichmentHeading(t, "Enriquecido", record.enrichment_status)}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <QualityBadge score={record.quality_score} />
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                    {buildEnrichmentSummary(t, record.enrichment_status, record.quality_score)}
                  </span>
                </div>
              </div>
            </div>
          </section>

          {issnL && (
            <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
              <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
                {tr("catalogs.record.section_journal_metrics", "Journal metrics")}
              </h2>
              <JournalMetricsSection issnL={issnL} />
            </section>
          )}

          <section className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                {tr("catalogs.record.section_core", "Core record")}
              </h2>
              <div className="mt-4 space-y-4">
                {coreFields.map((field) => (
                  <div key={field.key} className="border-b border-gray-100 pb-3 dark:border-gray-800">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-400">
                      {field.key === "entity_type" ? <EntityConcept>{field.label}</EntityConcept> : field.label}
                    </p>
                    <p className="mt-1 text-sm text-gray-700 dark:text-gray-300">{formatValue(field.value)}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                {tr("catalogs.record.section_system", "System signals")}
              </h2>
              <div className="mt-4 space-y-4">
                {systemFields.map((field) => (
                  <div key={field.label} className="border-b border-gray-100 pb-3 dark:border-gray-800">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-400">{field.label}</p>
                    {field.isQuality ? (
                      <div className="mt-2 flex flex-wrap items-center gap-3">
                        <QualityBadge score={record.quality_score} />
                        <span className="text-sm text-gray-700 dark:text-gray-300">{formatValue(field.value)}</span>
                      </div>
                    ) : (
                      <p className="mt-1 text-sm text-gray-700 dark:text-gray-300">{formatValue(field.value)}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              {tr("catalogs.record.section_extended", "Extended metadata")}
            </h2>
            <div className="mt-5 grid gap-x-8 gap-y-4 md:grid-cols-2">
              {Object.entries(mergedAttributes).length > 0 ? (
                Object.entries(mergedAttributes).map(([key, value]) => (
                  <div key={key} className="border-b border-gray-100 pb-3 dark:border-gray-800">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-400">
                      {key.replaceAll("_", " ")}
                    </p>
                    <p className="mt-1 text-sm text-gray-700 dark:text-gray-300 break-words">
                      {formatValue(value)}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {tr("catalogs.record.no_extended", "No extended metadata was stored for this record.")}
                </p>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
