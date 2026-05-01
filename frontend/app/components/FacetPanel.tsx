"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { useLanguage } from "../contexts/LanguageContext";

export interface FacetValue { value: string; count: number; }
export interface FacetData { [field: string]: FacetValue[]; }
export interface ActiveFacets { [field: string]: string | null; }

const FIELD_LABELS: Record<string, string> = {
  entity_type:       "page.import.field.entity_type",
  domain:            "page.import.field.domain",
  validation_status: "page.entity_table.review_status",
  enrichment_status: "page.entity_table.system_status",
  source:            "page.exec_dashboard.source",
};

const FIELD_COLORS: Record<string, string> = {
  entity_type:       "text-violet-700 dark:text-violet-200",
  domain:            "text-blue-700 dark:text-blue-200",
  validation_status: "text-amber-700 dark:text-amber-200",
  enrichment_status: "text-emerald-700 dark:text-emerald-200",
  source:            "text-slate-600 dark:text-[var(--ukip-muted)]",
};

interface FacetPanelProps {
  activeFacets: ActiveFacets;
  onFacetChange: (field: string, value: string | null) => void;
  search?: string;
  minQuality?: string;
  totalCount?: number;
  visibleCount?: number;
  refreshKey?: number; // increment to trigger re-fetch
  facetsData?: FacetData | null;
}

const FIELD_ORDER = ["entity_type", "domain", "validation_status", "enrichment_status", "source"];

export default function FacetPanel({ activeFacets, onFacetChange, search, minQuality, totalCount, visibleCount, refreshKey, facetsData }: FacetPanelProps) {
  const { t } = useLanguage();
  const [facets, setFacets] = useState<FacetData>({});
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);

  const fetchFacets = useCallback(async () => {
    try {
      const queryParams = new URLSearchParams();
      if (search) queryParams.append("search", search);
      if (minQuality) queryParams.append("min_quality", minQuality);
      if (activeFacets.entity_type) queryParams.append("ft_entity_type", activeFacets.entity_type);
      if (activeFacets.domain) queryParams.append("ft_domain", activeFacets.domain);
      if (activeFacets.validation_status) queryParams.append("ft_validation_status", activeFacets.validation_status);
      if (activeFacets.enrichment_status) queryParams.append("ft_enrichment_status", activeFacets.enrichment_status);
      if (activeFacets.source) queryParams.append("ft_source", activeFacets.source);
      const res = await apiFetch(`/entities/facets${queryParams.size > 0 ? `?${queryParams}` : ""}`);
      if (res.ok) setFacets(await res.json());
    } catch { /* non-critical */ } finally {
      setLoading(false);
    }
  }, [activeFacets.domain, activeFacets.enrichment_status, activeFacets.entity_type, activeFacets.source, activeFacets.validation_status, minQuality, search]);

  useEffect(() => {
    if (facetsData) {
      setFacets(facetsData);
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchFacets();
  }, [facetsData, fetchFacets, refreshKey]);

  const toggleCollapse = (field: string) =>
    setCollapsed(prev => ({ ...prev, [field]: !prev[field] }));

  const activeCount = Object.values(activeFacets).filter(Boolean).length;

  const translateFacetLabel = (field: string) => {
    const explicitLabels: Record<string, string> = {
      entity_type: "Tipo de entidad",
      domain: "Dominio",
    };
    if (explicitLabels[field]) return explicitLabels[field];
    const key = FIELD_LABELS[field];
    return key ? t(key) : field;
  };

  const translateFacetValue = (field: string, value: string) => {
    if (!value) return t("page.entity_table.empty_value");

    const valueMap: Record<string, Record<string, string>> = {
      entity_type: {
        publication: "Publicación",
        author: "Autor",
        affiliation: "Afiliación",
        dataset: "Dataset",
        patent: "Patente",
        organization: "Organización",
        journal_article: "Publicación",
      },
      domain: {
        technology: "Tecnología",
        tecnologia: "Tecnología",
        health: "Salud",
        healthcare: "Salud",
        salud: "Salud",
        science: "Ciencia",
        ciencia: "Ciencia",
        engineering: "Ingeniería",
        ingenieria: "Ingeniería",
        humanities: "Humanidades",
        humanidades: "Humanidades",
      },
    };
    if (valueMap[field]?.[value]) return valueMap[field][value];

    if (field === "entity_type") {
      const translated = t(`page.authority.entity_type_${value}`);
      return translated === `page.authority.entity_type_${value}` ? value : translated;
    }

    if (field === "validation_status") {
      const statusKey = `page.entity_table.status_${value}`;
      const translated = t(statusKey);
      return translated === statusKey ? value : translated;
    }

    if (field === "enrichment_status") {
      const enrichmentKeyMap: Record<string, string> = {
        completed: "entities.filter.enriched",
        pending: "entities.filter.pending",
        processing: "page.entity_table.status_processing",
        failed: "entities.filter.failed",
        none: "page.entity_table.status_not_started",
      };
      const translated = t(enrichmentKeyMap[value] ?? `entities.filter.${value}`);
      return translated === (enrichmentKeyMap[value] ?? `entities.filter.${value}`) ? value : translated;
    }

    return value;
  };

  return (
    <aside className="h-full min-h-[72rem] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-slate-200 px-5 py-4 dark:border-white/10">
        <div>
          <h3 className="text-base font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">Filtros</h3>
        </div>
        {activeCount > 0 && (
          <button
            onClick={() => Object.keys(activeFacets).forEach(f => onFacetChange(f, null))}
            className="text-xs font-semibold text-violet-600 hover:underline dark:text-violet-300"
          >
            {t("page.facets.clear_all", { count: activeCount })}
          </button>
        )}
      </div>

      {loading && (
        <div className="animate-pulse px-5 py-4 text-xs text-slate-400">{t("page.facets.loading")}</div>
      )}

      <div className="max-h-[calc(100vh-8rem)] overflow-y-auto px-5 py-4">
        {FIELD_ORDER.map((field) => {
          const values = facets[field] ?? [];
          if (values.length === 0) return null;
          const isCollapsed = collapsed[field];
          const active = activeFacets[field];
          const chipColor = FIELD_COLORS[field] ?? "text-slate-600";

          return (
            <div
              key={field}
              className="border-b border-slate-200 py-4 last:border-b-0 dark:border-white/10"
            >
              <button
                onClick={() => toggleCollapse(field)}
                className="flex w-full items-center justify-between text-left"
              >
                <span className="text-sm font-bold uppercase tracking-[0.14em] text-slate-600 dark:text-[var(--ukip-muted)]">{translateFacetLabel(field)}</span>
                <span className="text-sm text-slate-500">{isCollapsed ? "⌄" : "⌃"}</span>
              </button>

              {!isCollapsed && (
                <ul className="mt-3 space-y-3">
                  {values.slice(0, 8).map(({ value, count }) => {
                    const isActive = active === value;
                    return (
                      <li key={value}>
                        <button
                          onClick={() => onFacetChange(field, isActive ? null : value)}
                          className={`flex w-full items-center justify-between rounded-lg text-left text-sm transition-colors ${
                            isActive
                              ? "font-semibold text-violet-700 dark:text-violet-200"
                              : "text-slate-700 hover:text-violet-700 dark:text-[var(--ukip-text)]"
                          }`}
                        >
                          <span className="flex min-w-0 items-center gap-3">
                            <span className={`h-4 w-4 rounded-full border ${isActive ? "border-violet-600 bg-violet-50 ring-2 ring-violet-100" : "border-violet-500"}`} />
                            <span className="truncate">{translateFacetValue(field, value)}</span>
                          </span>
                          <span
                            className={`ml-2 shrink-0 font-mono text-xs ${
                              isActive ? "text-violet-700 dark:text-violet-200" : chipColor
                            }`}
                          >
                            {count}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                  {values.length > 8 && (
                    <li className="px-2 pt-0.5 text-[10px] text-slate-400">
                      {t("page.facets.read_more", { count: values.length - 8 })}
                    </li>
                  )}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
