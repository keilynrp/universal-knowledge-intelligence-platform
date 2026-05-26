"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { Badge, EmptyState, ErrorBanner, QualityBadge, useToast } from "../../components/ui";
import FacetPanel from "../../components/FacetPanel";
import EntityTableToolbar from "../../components/EntityTableToolbar";
import RecordResultCard from "../../components/RecordResultCard";
import RecordListRow from "../../components/RecordListRow";
import { useAssistantContextRegistration } from "../../contexts/AssistantContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { useAuth } from "../../contexts/AuthContext";

interface CatalogPortal {
  id: number;
  title: string;
  slug: string;
  description: string | null;
  domain_id: string;
  visibility: string;
  source_label: string | null;
  source_context: Record<string, string | number | boolean | null>;
  search: string | null;
  min_quality: number | null;
  ft_entity_type: string | null;
  ft_validation_status: string | null;
  ft_enrichment_status: string | null;
  ft_source: string | null;
  default_sort: string;
  default_order: string;
  featured_facets: string[];
  summary?: {
    total_records: number;
    enriched_records: number;
    enriched_pct: number;
    avg_quality: number | null;
  };
}

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
}

interface CatalogResultsPayload {
  portal: CatalogPortal;
  filters: Record<string, string | number | null>;
  total: number;
  skip: number;
  limit: number;
  items: CatalogRecord[];
  facets: Record<string, { value: string; count: number }[]>;
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

function parseAttributes(raw: string | null): Record<string, unknown> {
  if (!raw) return {};
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function visibilityTone(visibility: string | null | undefined): string {
  switch (visibility) {
    case "public":
      return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300";
    case "org":
      return "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300";
    default:
      return "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300";
  }
}

export default function CatalogPortalPage() {
  const { slug } = useParams<{ slug: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { t } = useLanguage();
  const { isAuthenticated } = useAuth();
  const { toast } = useToast();
  const tr = (key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  };
  const visibilityLabel = (visibility: string | null | undefined) => {
    switch (visibility) {
      case "public":
        return tr("catalogs.visibility.public", "Public read-only");
      case "org":
        return tr("catalogs.visibility.org", "Organization members");
      default:
        return tr("catalogs.visibility.private", "Private workspace");
    }
  };
  const [portal, setPortal] = useState<CatalogPortal | null>(null);
  const [results, setResults] = useState<CatalogResultsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [search, setSearch] = useState(searchParams.get("search") ?? "");
  const [minQuality, setMinQuality] = useState(searchParams.get("min_quality") ?? "");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [activeFacets, setActiveFacets] = useState<Record<string, string | null>>({
    entity_type: searchParams.get("ft_entity_type") ?? null,
    domain: searchParams.get("ft_domain") ?? null,
    validation_status: searchParams.get("ft_validation_status") ?? null,
    enrichment_status: searchParams.get("ft_enrichment_status") ?? null,
    source: searchParams.get("ft_source") ?? null,
  });
  const [editForm, setEditForm] = useState({
    title: "",
    description: "",
    visibility: "private",
    source_label: "",
    search: "",
    min_quality: "",
    ft_entity_type: "",
    ft_validation_status: "",
    ft_enrichment_status: "",
    ft_source: "",
  });

  const currentPage = Number(searchParams.get("page") || "1");
  const limit = 24;

  const loadPortal = async () => {
    setLoading(true);
    setError(null);
    try {
      const portalRes = await apiFetch(`/catalogs/${slug}`);
      if (!portalRes.ok) {
        throw new Error(
          await readCatalogError(
            portalRes,
            tr("catalogs.portal_load_failed", "This catalog portal is not available right now."),
          ),
        );
      }
      const portalPayload = await portalRes.json();
      setPortal(portalPayload);
      setEditForm({
        title: portalPayload.title ?? "",
        description: portalPayload.description ?? "",
        visibility: portalPayload.visibility ?? "private",
        source_label: portalPayload.source_label ?? "",
        search: portalPayload.search ?? "",
        min_quality: portalPayload.min_quality !== null && portalPayload.min_quality !== undefined ? String(portalPayload.min_quality) : "",
        ft_entity_type: portalPayload.ft_entity_type ?? "",
        ft_validation_status: portalPayload.ft_validation_status ?? "",
        ft_enrichment_status: portalPayload.ft_enrichment_status ?? "",
        ft_source: portalPayload.ft_source ?? "",
      });

      const query = new URLSearchParams({
        skip: String((currentPage - 1) * limit),
        limit: String(limit),
      });
      if (search) query.set("search", search);
      if (minQuality) query.set("min_quality", minQuality);
      const facetParamMap: Record<string, string> = {
        entity_type: "ft_entity_type",
        domain: "ft_domain",
        validation_status: "ft_validation_status",
        enrichment_status: "ft_enrichment_status",
        source: "ft_source",
      };
      Object.entries(activeFacets).forEach(([key, value]) => {
        const paramName = facetParamMap[key];
        if (paramName && value) query.set(paramName, value);
      });

      const resultsRes = await apiFetch(`/catalogs/${slug}/results?${query.toString()}`);
      if (!resultsRes.ok) {
        throw new Error(
          await readCatalogError(
            resultsRes,
            tr("catalogs.results_load_failed", "The catalog results could not be loaded right now."),
          ),
        );
      }
      setResults(await resultsRes.json());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : tr("catalogs.portal_load_failed", "Failed to load the catalog portal."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadPortal();
  }, [slug, currentPage]);

  const totalPages = useMemo(() => {
    if (!results) return 1;
    return Math.max(1, Math.ceil(results.total / results.limit));
  }, [results]);
  useAssistantContextRegistration({
    route: `/catalogs/${slug}`,
    domainId: portal?.domain_id || "all",
    moduleLabel: "Catalogo publico",
    totalEntities: portal?.summary?.total_records ?? results?.total ?? null,
    enrichedCount: portal?.summary?.enriched_records ?? null,
    enrichmentPct: portal?.summary?.enriched_pct ?? null,
    qualityPct: portal?.summary?.avg_quality != null ? Math.round(portal.summary.avg_quality * 100) : null,
    activeSources: Object.values(activeFacets).filter(Boolean).length,
    leadingGap: error || null,
    recommendedActions: [
      portal?.title ? `Portal: ${portal.title}` : `Portal ${slug}`,
      search ? `Busqueda activa: ${search}` : "Sin busqueda textual activa",
      minQuality ? `Calidad minima: ${minQuality}` : "Sin umbral de calidad",
    ],
  });

  const applyFilters = () => {
    const next = new URLSearchParams();
    if (search) next.set("search", search);
    if (minQuality) next.set("min_quality", minQuality);
    const facetParamMap: Record<string, string> = {
      entity_type: "ft_entity_type",
      domain: "ft_domain",
      validation_status: "ft_validation_status",
      enrichment_status: "ft_enrichment_status",
      source: "ft_source",
    };
    Object.entries(activeFacets).forEach(([key, value]) => {
      const paramName = facetParamMap[key];
      if (paramName && value) next.set(paramName, value);
    });
    next.set("page", "1");
    router.replace(`/catalogs/${slug}?${next.toString()}`);
    void loadPortal();
  };

  const handleFacetChange = (field: string, value: string | null) => {
    setActiveFacets((prev) => ({ ...prev, [field]: value }));
  };

  const enrichmentVariant = (value: string | null | undefined): "success" | "warning" | "error" | "default" => {
    switch (value) {
      case "completed":
        return "success";
      case "pending":
      case "processing":
        return "warning";
      case "failed":
        return "error";
      default:
        return "default";
    }
  };

  const statusLabel = (field: "validation" | "enrichment", value: string | null | undefined) => {
    if (!value) return tr("page.entity_table.empty_value", "—");
    if (field === "validation") {
      const key = `page.entity_table.status_${value}`;
      const translated = t(key);
      return translated === key ? value : translated;
    }
    const enrichmentKeyMap: Record<string, string> = {
      completed: "entities.filter.enriched",
      pending: "entities.filter.pending",
      processing: "page.entity_table.status_processing",
      failed: "entities.filter.failed",
      none: "page.entity_table.status_not_started",
    };
    const key = enrichmentKeyMap[value] ?? `entities.filter.${value}`;
    const translated = t(key);
    return translated === key ? value : translated;
  };

  const recordStatusTone = (
    validationStatus: string | null | undefined,
    enrichmentStatus: string | null | undefined,
  ): "verified" | "review" | "rejected" | "pending" | "enriched" | "default" => {
    if (validationStatus === "invalid") return "rejected";
    if (validationStatus === "valid") return "verified";
    if (enrichmentStatus === "completed") return "enriched";
    if (enrichmentStatus === "processing" || validationStatus === "pending") return "review";
    if (enrichmentStatus === "pending" || enrichmentStatus === "none") return "pending";
    return "default";
  };

  const goToPage = (page: number) => {
    const next = new URLSearchParams(searchParams.toString());
    next.set("page", String(page));
    router.replace(`/catalogs/${slug}?${next.toString()}`);
  };

  const savePortal = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch(`/catalogs/${slug}`, {
        method: "PUT",
        body: JSON.stringify({
          title: editForm.title,
          description: editForm.description,
          visibility: editForm.visibility,
          source_label: editForm.source_label,
          search: editForm.search || null,
          min_quality: editForm.min_quality ? Number(editForm.min_quality) : null,
          ft_entity_type: editForm.ft_entity_type || null,
          ft_validation_status: editForm.ft_validation_status || null,
          ft_enrichment_status: editForm.ft_enrichment_status || null,
          ft_source: editForm.ft_source || null,
        }),
      });
      if (!res.ok) {
        throw new Error(
          await readCatalogError(
            res,
            tr("catalogs.update_failed", "Failed to update the catalog portal."),
          ),
        );
      }
      setEditing(false);
      await loadPortal();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : tr("catalogs.update_failed", "Failed to update the catalog portal."));
    } finally {
      setSaving(false);
    }
  };

  const deletePortal = async () => {
    if (!portal) return;
    const confirmed = window.confirm(
      tr(
        "catalogs.delete_confirm",
        "Delete this portal only? The imported records and source ingestion will remain untouched.",
      ),
    );
    if (!confirmed) return;

    setDeleting(true);
    setError(null);
    try {
      const res = await apiFetch(`/catalogs/${slug}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        throw new Error(
          await readCatalogError(
            res,
            tr("catalogs.delete_failed", "Failed to delete the catalog portal."),
          ),
        );
      }
      toast(
        `${tr("catalogs.delete_success_title", "Portal deleted")}: ${tr("catalogs.delete_success_body", "The portal was removed, but the imported records remain available in the workspace.")}`,
        "success",
      );
      router.push("/catalogs");
    } catch (deleteError) {
      const message =
        deleteError instanceof Error
          ? deleteError.message
          : tr("catalogs.delete_failed", "Failed to delete the catalog portal.");
      setError(message);
      toast(`${tr("catalogs.delete_failed_title", "Unable to delete portal")}: ${message}`, "error");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-5">
      {error && <ErrorBanner message={error} />}

      {portal && (
        <section className="rounded-[28px] bg-slate-100/70 p-4 dark:bg-black/10">
          <div className="grid gap-4 lg:grid-cols-[1.2fr_repeat(3,minmax(0,0.45fr))]">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
              <div className="flex flex-wrap items-center gap-2">
                <span className="ukip-kicker">{tr("catalogs.hero.eyebrow", "Catalog portal")}</span>
                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${visibilityTone(portal.visibility)}`}>
                  {visibilityLabel(portal.visibility)}
                </span>
              </div>
              <h1 className="mt-3 text-2xl font-bold tracking-[-0.04em] text-slate-950 dark:text-[var(--ukip-text-strong)]">
                {portal.title}
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600 dark:text-[var(--ukip-muted)]">
                {portal.description || tr("catalogs.hero.no_description", "Browse this collection through a calmer discovery view designed for pilot sessions, lightweight consultation, and stakeholder conversations.")}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500 dark:text-[var(--ukip-muted)]">{tr("catalogs.summary.total", "Records")}</p>
              <p className="mt-3 font-mono text-2xl font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">
                {(portal.summary?.total_records ?? results?.total ?? 0).toLocaleString()}
              </p>
              <p className="mt-1 text-xs text-slate-500 dark:text-[var(--ukip-muted)]">{portal.domain_id}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500 dark:text-[var(--ukip-muted)]">{tr("catalogs.summary.enriched", "Enriched")}</p>
              <p className="mt-3 font-mono text-2xl font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">
                {portal.summary ? `${portal.summary.enriched_pct.toFixed(1)}%` : "—"}
              </p>
              <p className="mt-1 text-xs text-slate-500 dark:text-[var(--ukip-muted)]">{portal.summary?.enriched_records?.toLocaleString() ?? "—"} records</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500 dark:text-[var(--ukip-muted)]">{tr("catalogs.results.scope_source", "Collection origin")}</p>
              <p className="mt-3 text-sm font-semibold text-slate-950 dark:text-[var(--ukip-text-strong)]">{portal.source_label || tr("catalogs.results.scope_search_any", "Open discovery")}</p>
              {portal?.visibility === "public" ? (
                <a
                  href={typeof window !== "undefined" ? window.location.href : `/catalogs/${slug}`}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 inline-flex text-xs font-semibold text-violet-600 hover:underline dark:text-violet-300"
                >
                  {tr("catalogs.share.open_public", "Open public view")}
                </a>
              ) : null}
            </div>
          </div>
        </section>
      )}

      <section className="grid gap-5 rounded-[28px] bg-slate-100/70 p-4 dark:bg-black/10 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-[var(--ukip-surface)]">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500 dark:text-gray-400">
                  {tr("catalogs.manage.eyebrow", "Portal settings")}
                </p>
                <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">
                  {tr("catalogs.manage.title", "Adjust this collection")}
                </p>
              </div>
              {isAuthenticated ? (
                <button
                  onClick={() => setEditing((prev) => !prev)}
                    className="rounded-xl border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-white/10 dark:text-[var(--ukip-text)] dark:hover:bg-[var(--ukip-panel-strong)]"
                >
                  {editing ? tr("common.cancel", "Cancel") : tr("common.edit", "Edit")}
                </button>
              ) : (
                <span className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                  {tr("catalogs.visibility.public_readonly", "Public read-only")}
                </span>
              )}
            </div>

            {!isAuthenticated && (
              <p className="mt-3 text-sm text-gray-600 dark:text-gray-300">
                {tr("catalogs.manage.readonly_help", "This public portal is open for consultation only. Sign in to manage filters, visibility, or descriptive settings.")}
              </p>
            )}

            {editing && isAuthenticated && (
              <div className="mt-4 space-y-3">
                <div className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-200">
                  <p className="font-semibold">{tr("catalogs.facets_sync_title", "Knowledge facets stay in sync")}</p>
                  <p className="mt-1">{tr("catalogs.facets_sync_body", "This portal reuses the same facet set shown in the Knowledge panel, so filters stay consistent without duplicating configuration.")}</p>
                </div>
                <input
                  value={editForm.title}
                  onChange={(event) => setEditForm((prev) => ({ ...prev, title: event.target.value }))}
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-gray-700 dark:bg-gray-950 dark:text-white dark:focus:ring-blue-900/40"
                  placeholder={tr("catalogs.field.title", "Title")}
                />
                <textarea
                  rows={3}
                  value={editForm.description}
                  onChange={(event) => setEditForm((prev) => ({ ...prev, description: event.target.value }))}
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-gray-700 dark:bg-gray-950 dark:text-white dark:focus:ring-blue-900/40"
                  placeholder={tr("catalogs.field.description", "Description")}
                />
                <input
                  value={editForm.source_label}
                  onChange={(event) => setEditForm((prev) => ({ ...prev, source_label: event.target.value }))}
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-gray-700 dark:bg-gray-950 dark:text-white dark:focus:ring-blue-900/40"
                  placeholder={tr("catalogs.manage.source_label", "Collection origin label")}
                />
                <select
                  value={editForm.visibility}
                  onChange={(event) => setEditForm((prev) => ({ ...prev, visibility: event.target.value }))}
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-gray-700 dark:bg-gray-950 dark:text-white dark:focus:ring-blue-900/40"
                >
                  <option value="private">{tr("catalogs.visibility.private", "Private workspace")}</option>
                  <option value="org">{tr("catalogs.visibility.org", "Organization members")}</option>
                  <option value="public">{tr("catalogs.visibility.public", "Public read-only")}</option>
                </select>
                <input
                  value={editForm.search}
                  onChange={(event) => setEditForm((prev) => ({ ...prev, search: event.target.value }))}
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-gray-700 dark:bg-gray-950 dark:text-white dark:focus:ring-blue-900/40"
                  placeholder={tr("catalogs.manage.default_search", "Default search")}
                />
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.1"
                  value={editForm.min_quality}
                  onChange={(event) => setEditForm((prev) => ({ ...prev, min_quality: event.target.value }))}
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-gray-700 dark:bg-gray-950 dark:text-white dark:focus:ring-blue-900/40"
                  placeholder={tr("catalogs.field.min_quality", "Minimum quality")}
                />
                <button
                  onClick={savePortal}
                  disabled={saving}
                  className="w-full rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {saving ? tr("catalogs.saving", "Saving...") : tr("catalogs.save", "Save portal")}
                </button>
                <button
                  onClick={deletePortal}
                  disabled={deleting}
                  className="w-full rounded-xl border border-red-200 px-4 py-2.5 text-sm font-medium text-red-700 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-70 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950/30"
                >
                  {deleting ? tr("catalogs.deleting", "Deleting...") : tr("catalogs.delete", "Delete portal")}
                </button>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {tr("catalogs.delete_hint", "Deleting the portal removes only this discovery view. It does not delete imported records or source ingestion data.")}
                </p>
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-[var(--ukip-surface)] dark:text-[var(--ukip-muted)]">
            <p className="font-semibold text-slate-950 dark:text-[var(--ukip-text-strong)]">{tr("catalogs.filters_title", "Catalog filters")}</p>
            <p className="mt-1">{tr("catalogs.vufind_like_hint", "Use the search bar, then narrow by facets on the left. This portal now follows the same consultation pattern as the internal catalog view.")}</p>
          </div>

          <FacetPanel
            activeFacets={activeFacets}
            onFacetChange={handleFacetChange}
            search={search}
            minQuality={minQuality}
            totalCount={results?.total ?? 0}
            visibleCount={results?.items.length ?? 0}
            facetsData={results?.facets ?? null}
          />
        </aside>

        <section className="space-y-4">
          <EntityTableToolbar
            activeFacets={activeFacets}
            search={search}
            minQuality={minQuality}
            page={Math.max(0, currentPage - 1)}
            totalCount={results?.total ?? 0}
            visibleCount={results?.items.length ?? 0}
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            onSearchChange={setSearch}
            onMinQualityChange={setMinQuality}
            onClearFacet={(field) => handleFacetChange(field, null)}
          />

          <div className="flex flex-wrap gap-2">
            <button
              onClick={applyFilters}
              className="rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-violet-700"
            >
              {tr("catalogs.filters.apply", "Apply filters")}
            </button>
            <button
              onClick={() => {
                setSearch("");
                setMinQuality("");
                setActiveFacets({
                  entity_type: null,
                  domain: null,
                  validation_status: null,
                  enrichment_status: null,
                  source: null,
                });
              }}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-white/10 dark:bg-[var(--ukip-panel)] dark:text-[var(--ukip-text)] dark:hover:bg-[var(--ukip-panel-strong)]"
            >
              {tr("catalogs.filters.clear", "Clear filters")}
            </button>
          </div>

          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 shadow-sm dark:border-white/10 dark:bg-black/10">
            <div className="m-3 rounded-xl border border-slate-200 bg-white/95 px-4 py-3 backdrop-blur dark:border-white/10 dark:bg-[var(--ukip-panel)]">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  {results ? results.total.toLocaleString() : "0"}
                </p>
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
                  {tr("catalogs.results.section_eyebrow", "Catalog results")}
                </p>
              </div>
            </div>

            <div className={viewMode === "list" ? "space-y-2 p-3 pt-0" : "grid gap-4 p-3 pt-0 md:grid-cols-2"}>
              {loading ? (
                <div className="space-y-4 p-4">
                  {Array.from({ length: 8 }).map((_, index) => (
                    <div key={index} className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-950">
                      <div className="flex animate-pulse gap-4">
                        <div className="h-16 w-16 rounded-2xl bg-gray-100 dark:bg-gray-800" />
                        <div className="flex-1 space-y-3">
                          <div className="h-4 w-2/3 rounded bg-gray-100 dark:bg-gray-800" />
                          <div className="h-3 w-1/2 rounded bg-gray-100 dark:bg-gray-800" />
                          <div className="grid gap-2 sm:grid-cols-3">
                            <div className="h-10 rounded-xl bg-gray-100 dark:bg-gray-800" />
                            <div className="h-10 rounded-xl bg-gray-100 dark:bg-gray-800" />
                            <div className="h-10 rounded-xl bg-gray-100 dark:bg-gray-800" />
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : results && results.items.length > 0 ? (
                results.items.map((record) => {
                  const attributes = parseAttributes(record.attributes_json);
                  const journal = (attributes.journal as string | undefined) || (attributes.venue as string | undefined);
                  const year = attributes.year as string | number | undefined;
                  const statusTone = recordStatusTone(record.validation_status, record.enrichment_status);
                  const score = record.quality_score !== null && record.quality_score !== undefined ? record.quality_score.toFixed(2) : "—";
                  if (viewMode === "list") {
                    return (
                      <RecordListRow
                        key={record.id}
                        tone={statusTone}
                        onClick={() => router.push(`/catalogs/${slug}/record/${record.id}`)}
                        title={record.primary_label || tr("common.no_data", "No data")}
                        metaLine={
                          <>
                            {record.canonical_id || `#${record.id}`}
                            {record.entity_type ? ` · ${record.entity_type}` : ""}
                            {record.domain ? ` · ${record.domain}` : ""}
                          </>
                        }
                        authorityScore={score}
                        qualityScore={score}
                        statusBadge={
                          <Badge variant={enrichmentVariant(record.enrichment_status)}>
                            {statusLabel("enrichment", record.enrichment_status)}
                          </Badge>
                        }
                        owner={record.secondary_label || record.source || "—"}
                      />
                    );
                  }
                  return (
                    <RecordResultCard
                      key={record.id}
                      onClick={() => router.push(`/catalogs/${slug}/record/${record.id}`)}
                      statusTone={statusTone}
                      title={record.primary_label || tr("common.no_data", "No data")}
                      secondaryLine={
                        <>
                          {record.secondary_label ? <span>{record.secondary_label}</span> : null}
                          {record.secondary_label && (journal || year) ? <span>·</span> : null}
                          {journal ? <span>{journal}</span> : null}
                          {journal && year ? <span>·</span> : null}
                          {year ? <span>{String(year)}</span> : null}
                        </>
                      }
                      statusRow={
                        <>
                          <Badge variant={enrichmentVariant(record.enrichment_status)}>
                            {statusLabel("enrichment", record.enrichment_status)}
                          </Badge>
                          <QualityBadge score={record.quality_score} />
                          {record.entity_type ? <Badge variant="default">{record.entity_type}</Badge> : null}
                        </>
                      }
                      primaryMeta={[
                        {
                          label: tr("page.import.field.canonical_id", "Identifier"),
                          value: (
                            <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                              {record.canonical_id || "—"}
                            </code>
                          ),
                          minWidthClassName: "min-w-[12rem]",
                        },
                        {
                          label: tr("page.entity_table.review_status", "Review status"),
                          value: statusLabel("validation", record.validation_status),
                        },
                        {
                          label: tr("catalogs.record.citations", "Citations"),
                          value: (record.enrichment_citation_count ?? 0).toLocaleString(),
                        },
                        {
                          label: tr("page.import.field.domain", "Domain"),
                          value: record.domain || record.source || "—",
                        },
                      ]}
                      actions={
                        <button
                          className="text-xs font-bold text-violet-600 transition hover:text-violet-800 dark:text-violet-300"
                          onClick={(event) => {
                            event.stopPropagation();
                            router.push(`/catalogs/${slug}/record/${record.id}`);
                          }}
                        >
                          {tr("catalogs.record.open", "Open record")} ↗
                        </button>
                      }
                    />
                  );
                })
              ) : (
                <div className="px-5 py-10">
                  <EmptyState
                    icon="search"
                    color="blue"
                    title={tr("catalogs.results_empty_title", "No records match these filters")}
                    description={tr("catalogs.results_empty_description", "Try a broader query or remove one of the active filters to recover results.")}
                  />
                </div>
              )}
            </div>
          </div>

          {results && results.items.length > 0 && (
            <div className="flex items-center justify-between border-t border-gray-200 pt-4 dark:border-gray-800">
              <button
                onClick={() => goToPage(Math.max(1, currentPage - 1))}
                disabled={currentPage <= 1}
                className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
              >
                {tr("catalogs.pagination.previous", "Previous")}
              </button>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {tr("catalogs.pagination.page", "Page")} {currentPage} / {totalPages}
              </span>
              <button
                onClick={() => goToPage(Math.min(totalPages, currentPage + 1))}
                disabled={currentPage >= totalPages}
                className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
              >
                {tr("catalogs.pagination.next", "Next")}
              </button>
            </div>
          )}
        </section>
      </section>
    </div>
  );
}
