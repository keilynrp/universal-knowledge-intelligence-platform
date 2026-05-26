"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { PageHeader, EmptyState, ErrorBanner, useToast } from "../components/ui";
import { useAssistantContextRegistration } from "../contexts/AssistantContext";
import { useDomain } from "../contexts/DomainContext";
import { useLanguage } from "../contexts/LanguageContext";

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
  created_at: string | null;
}

interface CatalogImportCandidate {
  kind: string;
  batch_id: number | null;
  domain_id: string;
  source: string;
  entity_type: string | null;
  total_records: number;
  avg_quality: number | null;
  source_label: string;
  search: string | null;
  min_quality: number | null;
  ft_source: string | null;
  ft_entity_type: string | null;
  created_at?: string | null;
  file_format?: string | null;
}

const KNOWLEDGE_PANEL_FACETS = ["entity_type", "validation_status", "enrichment_status", "source"];
const SEEDED_QUERY_KEYS = [
  "domain_id",
  "title",
  "slug",
  "description",
  "visibility",
  "source_label",
  "source_format",
  "source_rows",
  "source_batch_id",
  "seeded_from",
  "search",
  "min_quality",
  "ft_entity_type",
  "ft_validation_status",
  "ft_enrichment_status",
  "ft_source",
  "default_sort",
  "default_order",
];

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

export default function CatalogPortalsPage() {
  const { domains, activeDomainId } = useDomain();
  const { t } = useLanguage();
  const { toast } = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();
  const tr = (key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  };
  const normalizeFeedback = (message: string | null | undefined, fallback: string) => {
    const normalized = message?.trim();
    if (!normalized) return fallback;
    if (/^https?:\/\//i.test(normalized)) return fallback;
    if (typeof window !== "undefined") {
      const currentUrl = window.location.href;
      const currentPath = `${window.location.origin}${window.location.pathname}`;
      if (normalized === currentUrl || normalized === currentPath || normalized === window.location.pathname) {
        return fallback;
      }
    }
    return normalized;
  };

  const [portals, setPortals] = useState<CatalogPortal[]>([]);
  const [candidates, setCandidates] = useState<CatalogImportCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deletingSlug, setDeletingSlug] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    title: searchParams.get("title") ?? "",
    slug: searchParams.get("slug") ?? "",
    description: searchParams.get("description") ?? "",
    domain_id: activeDomainId || "default",
    visibility: searchParams.get("visibility") ?? "private",
    source_label: searchParams.get("source_label") ?? "",
    source_batch_id: searchParams.get("source_batch_id") ?? "",
    search: searchParams.get("search") ?? "",
    min_quality: searchParams.get("min_quality") ?? "",
    ft_entity_type: searchParams.get("ft_entity_type") ?? "",
    ft_validation_status: searchParams.get("ft_validation_status") ?? "",
    ft_enrichment_status: searchParams.get("ft_enrichment_status") ?? "",
    ft_source: searchParams.get("ft_source") ?? "",
    default_sort: searchParams.get("default_sort") ?? "primary_label",
    default_order: searchParams.get("default_order") ?? "asc",
  });

  useEffect(() => {
    setForm((prev) => ({
      ...prev,
      domain_id: searchParams.get("domain_id") || prev.domain_id || activeDomainId || "default",
    }));
  }, [activeDomainId, searchParams]);

  useEffect(() => {
    const hasSeededParams = SEEDED_QUERY_KEYS.some((key) => searchParams.get(key) !== null);
    if (hasSeededParams) {
      router.replace("/catalogs", { scroll: false });
    }
  }, [router, searchParams]);

  const loadPortals = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/catalogs");
      if (!res.ok) {
        throw new Error(
          await readCatalogError(
            res,
            tr("catalogs.load_failed", "Catalog portals are not available right now. Refresh the app or restart the backend and try again."),
          ),
        );
      }
      setPortals(await res.json());
      const candidatesRes = await apiFetch("/catalogs/import-candidates");
      if (candidatesRes.ok) {
        setCandidates(await candidatesRes.json());
      } else {
        setCandidates([]);
      }
    } catch (loadError) {
      setError(
        normalizeFeedback(
          loadError instanceof Error ? loadError.message : null,
          tr("catalogs.load_failed", "Catalog portals are not available right now. Refresh the app or restart the backend and try again."),
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  const seedFromCandidate = (candidate: CatalogImportCandidate) => {
    const slugBase = `${candidate.domain_id}-${candidate.source}${candidate.entity_type ? `-${candidate.entity_type}` : ""}`
      .toLowerCase()
      .replace(/[^a-z0-9-]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 70);
    const timestamp = Date.now();
    setForm((prev) => ({
      ...prev,
      title: `${candidate.domain_id} ${candidate.entity_type || tr("catalogs.candidate.collection", "collection")}`.replace(/\b\w/g, (char) => char.toUpperCase()),
      slug: `catalog-${slugBase || "import"}-${timestamp}`.slice(0, 120),
      description: tr(
        "catalogs.candidate.description",
        "Catalog portal seeded from an existing imported collection so the team can browse it in a friendlier discovery view.",
      ),
      domain_id: candidate.domain_id,
      source_label: candidate.source_label,
      source_batch_id: candidate.batch_id !== null ? String(candidate.batch_id) : "",
      search: candidate.search ?? "",
      min_quality: candidate.min_quality !== null && candidate.min_quality !== undefined ? String(candidate.min_quality) : "",
      ft_entity_type: candidate.ft_entity_type ?? "",
      ft_validation_status: "",
      ft_enrichment_status: "",
      ft_source: candidate.ft_source ?? "",
      default_sort: "primary_label",
      default_order: "asc",
    }));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  useEffect(() => {
    void loadPortals();
  }, []);

  const domainOptions = useMemo(
    () => domains.map((domain) => ({ id: domain.id, name: domain.name })),
    [domains],
  );
  useAssistantContextRegistration({
    route: "/catalogs",
    domainId: form.domain_id || activeDomainId || "all",
    moduleLabel: "Catalogos publicables",
    totalEntities: candidates.reduce((sum, candidate) => sum + candidate.total_records, 0) || null,
    activeSources: portals.length,
    leadingGap: error,
    recommendedActions: [
      portals.length ? `${portals.length} portales disponibles` : "Crear el primer portal de catalogo",
      candidates.length ? `${candidates.length} importaciones candidatas` : "Importar datos para sembrar portales",
      form.visibility ? `Visibilidad propuesta: ${form.visibility}` : "Definir visibilidad del portal",
    ],
  });

  const handleCreate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = {
        ...form,
        source_batch_id: form.source_batch_id ? Number(form.source_batch_id) : null,
        min_quality: form.min_quality ? Number(form.min_quality) : null,
        source_context: {
          format: searchParams.get("source_format") ?? null,
          rows: searchParams.get("source_rows") ? Number(searchParams.get("source_rows")) : null,
          source_batch_id: form.source_batch_id ? Number(form.source_batch_id) : null,
          seeded_from: searchParams.get("seeded_from") ?? null,
        },
        featured_facets: KNOWLEDGE_PANEL_FACETS,
      };
      const res = await apiFetch("/catalogs", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        throw new Error(
          await readCatalogError(
            res,
            tr("catalogs.create_failed", "Could not create the catalog portal. Please review the form and try again."),
          ),
        );
      }
      const created = await res.json();
      toast(
        `${tr("catalogs.created_title", "Catalog portal created")}: ${tr("catalogs.created_description", "The portal is ready to browse and share internally.")}`,
        "success",
      );
      await loadPortals();
      router.push(`/catalogs/${created.slug}`);
    } catch (saveError) {
      const message = normalizeFeedback(
        saveError instanceof Error ? saveError.message : null,
        tr("catalogs.create_failed", "Failed to create catalog portal."),
      );
      setError(message);
      toast(`${tr("catalogs.create_failed_title", "Unable to create portal")}: ${message}`, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePortal = async (portal: CatalogPortal) => {
    const confirmed = window.confirm(
      tr(
        "catalogs.delete_confirm",
        `Delete "${portal.title}"? This only removes the catalog portal. Imported records and ingestion data will stay intact.`,
      ),
    );
    if (!confirmed) return;

    setDeletingSlug(portal.slug);
    setError(null);
    try {
      const res = await apiFetch(`/catalogs/${portal.slug}`, { method: "DELETE" });
      if (!res.ok) {
        throw new Error(
          await readCatalogError(
            res,
            tr("catalogs.delete_failed", "Could not delete the catalog portal. Please try again."),
          ),
        );
      }
      setPortals((current) => current.filter((item) => item.slug !== portal.slug));
      toast(
        `${tr("catalogs.delete_success_title", "Catalog portal deleted")}: ${tr("catalogs.delete_success_body", "The portal was removed without touching ingestion data.")}`,
        "success",
      );
    } catch (deleteError) {
      const message = normalizeFeedback(
        deleteError instanceof Error ? deleteError.message : null,
        tr("catalogs.delete_failed", "Could not delete the catalog portal. Please try again."),
      );
      setError(message);
      toast(`${tr("catalogs.delete_failed_title", "Unable to delete portal")}: ${message}`, "error");
    } finally {
      setDeletingSlug(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumbs={[
          { label: tr("nav.home", "Knowledge Explorer"), href: "/" },
          { label: tr("nav.catalogs", "Catalog Portals") },
        ]}
        title={tr("catalogs.title", "Catalog Portals")}
        description={tr("catalogs.subtitle", "Turn a scoped set of records into a friendlier discovery portal for pilot sessions and internal access.")}
      />

      {error && <ErrorBanner message={error} />}

      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <form
          onSubmit={handleCreate}
          className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900"
        >
          <div className="mb-6">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-blue-600 dark:text-blue-400">
              {tr("catalogs.create_eyebrow", "New portal")}
            </p>
            <h2 className="mt-2 text-xl font-semibold text-gray-900 dark:text-white">
              {tr("catalogs.create_title", "Publish a scoped catalog view")}
            </h2>
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
              {tr("catalogs.create_help", "Start with one domain and a few saved filters. We will keep this first cut private to your workspace.")}
            </p>
            <div className="mt-4 rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-200">
              <p className="font-semibold">{tr("catalogs.facets_sync_title", "Knowledge facets stay in sync")}</p>
              <p className="mt-1">{tr("catalogs.facets_sync_body", "This portal reuses the same facet set shown in the Knowledge panel, so filters stay consistent without duplicating configuration.")}</p>
            </div>
            {form.source_label && (
              <div className="mt-4 rounded-2xl border border-violet-200 bg-violet-50 px-4 py-3 text-sm text-violet-800 dark:border-violet-800 dark:bg-violet-950/30 dark:text-violet-200">
                <p className="font-semibold">{tr("catalogs.source_seeded", "Seeded from import")}</p>
                <p className="mt-1">{form.source_label}</p>
              </div>
            )}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
              <span>{tr("catalogs.field.title", "Title")}</span>
              <input
                required
                value={form.title}
                onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-gray-700 dark:bg-gray-950 dark:text-white dark:focus:ring-blue-900/40"
                placeholder={tr("catalogs.field.title_placeholder", "Research portfolio catalog")}
              />
            </label>
            <label className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
              <span>{tr("catalogs.field.slug", "Slug")}</span>
              <input
                required
                value={form.slug}
                onChange={(event) => setForm((prev) => ({ ...prev, slug: event.target.value.toLowerCase().replace(/\s+/g, "-") }))}
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-gray-700 dark:bg-gray-950 dark:text-white dark:focus:ring-blue-900/40"
                placeholder="udg-science-portal"
              />
            </label>
            <label className="space-y-2 text-sm text-gray-700 dark:text-gray-300 md:col-span-2">
              <span>{tr("catalogs.field.description", "Description")}</span>
              <textarea
                rows={3}
                value={form.description}
                onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-gray-700 dark:bg-gray-950 dark:text-white dark:focus:ring-blue-900/40"
                placeholder={tr("catalogs.field.description_placeholder", "A focused catalog for stakeholders who need broad discovery instead of the operational datatable.")}
              />
            </label>
            <label className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
              <span>{tr("catalogs.field.domain", "Domain")}</span>
              <select
                value={form.domain_id}
                onChange={(event) => setForm((prev) => ({ ...prev, domain_id: event.target.value }))}
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-gray-700 dark:bg-gray-950 dark:text-white dark:focus:ring-blue-900/40"
              >
                {domainOptions.map((domain) => (
                  <option key={domain.id} value={domain.id}>
                    {domain.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
              <span>{tr("catalogs.field.visibility", "Visibility")}</span>
              <select
                value={form.visibility}
                onChange={(event) => setForm((prev) => ({ ...prev, visibility: event.target.value }))}
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-gray-700 dark:bg-gray-950 dark:text-white dark:focus:ring-blue-900/40"
              >
                <option value="private">{tr("catalogs.visibility.private", "Private workspace")}</option>
                <option value="org">{tr("catalogs.visibility.org", "Organization members")}</option>
                <option value="public">{tr("catalogs.visibility.public", "Public read-only")}</option>
              </select>
            </label>
            <label className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
              <span>{tr("catalogs.field.entity_type", "Entity type filter")}</span>
              <input
                value={form.ft_entity_type}
                onChange={(event) => setForm((prev) => ({ ...prev, ft_entity_type: event.target.value }))}
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-gray-700 dark:bg-gray-950 dark:text-white dark:focus:ring-blue-900/40"
                placeholder={tr("catalogs.field.entity_type_placeholder", "publication")}
              />
            </label>
            <label className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
              <span>{tr("catalogs.field.min_quality", "Minimum quality")}</span>
              <input
                type="number"
                min="0"
                max="1"
                step="0.1"
                value={form.min_quality}
                onChange={(event) => setForm((prev) => ({ ...prev, min_quality: event.target.value }))}
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-gray-700 dark:bg-gray-950 dark:text-white dark:focus:ring-blue-900/40"
                placeholder="0.6"
              />
            </label>
            <label className="space-y-2 text-sm text-gray-700 dark:text-gray-300 md:col-span-2">
              <span>{tr("catalogs.field.search", "Default search hint")}</span>
              <input
                value={form.search}
                onChange={(event) => setForm((prev) => ({ ...prev, search: event.target.value }))}
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-gray-700 dark:bg-gray-950 dark:text-white dark:focus:ring-blue-900/40"
                placeholder={tr("catalogs.field.search_placeholder", "CRISPR, education, materials science...")}
              />
            </label>
          </div>

          <div className="mt-6 rounded-2xl bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-gray-950 dark:text-gray-300">
            <p className="mb-3">{tr("catalogs.create_note", "Use private for internal setup, org for member access, or public for a read-only portal you can share during pilot sessions.")}</p>
            <button
              type="submit"
              disabled={saving}
              className="w-full rounded-xl bg-blue-600 px-4 py-2.5 font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {saving ? tr("catalogs.creating", "Creating...") : tr("catalogs.create_submit", "Create portal")}
            </button>
          </div>
        </form>

        <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <div className="mb-6">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-violet-600 dark:text-violet-400">
              {tr("catalogs.list_eyebrow", "Existing portals")}
            </p>
            <h2 className="mt-2 text-xl font-semibold text-gray-900 dark:text-white">
              {tr("catalogs.list_title", "Discovery spaces already available")}
            </h2>
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
              {tr("catalogs.list_help", "Use these portals during demos and stakeholder sessions when the datatable feels too operational.")}
            </p>
          </div>

          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="h-24 animate-pulse rounded-2xl bg-gray-100 dark:bg-gray-800" />
              ))}
            </div>
          ) : portals.length === 0 ? (
            <EmptyState
              icon="document"
              color="violet"
              size="compact"
              title={tr("catalogs.empty_title", "No catalog portals yet")}
              description={tr("catalogs.empty_description", "Create the first portal on the left to turn your current workspace into a friendlier discovery view.")}
            />
          ) : (
            <div className="space-y-3">
              {portals.map((portal) => (
                <article
                  key={portal.id}
                  className="rounded-2xl border border-gray-200 p-4 transition hover:border-blue-300 hover:bg-blue-50/50 dark:border-gray-800 dark:hover:border-blue-700 dark:hover:bg-blue-950/20"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-base font-semibold text-gray-900 dark:text-white">{portal.title}</h3>
                        <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                          {portal.domain_id}
                        </span>
                        <span className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                          {portal.visibility}
                        </span>
                      </div>
                      {portal.source_label && (
                        <p className="text-xs font-medium text-violet-700 dark:text-violet-300">
                          {portal.source_label}
                        </p>
                      )}
                      <p className="text-sm text-gray-600 dark:text-gray-300">
                        {portal.description || tr("catalogs.no_description", "No description yet.")}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
                      <Link
                        href={`/catalogs/${portal.slug}`}
                        className="inline-flex items-center justify-center rounded-xl border border-blue-200 px-3 py-2 text-sm font-medium text-blue-700 transition hover:border-blue-300 hover:bg-blue-50 dark:border-blue-900 dark:text-blue-300 dark:hover:bg-blue-950/40"
                      >
                        {tr("catalogs.open", "Open")} →
                      </Link>
                      <button
                        type="button"
                        disabled={deletingSlug === portal.slug}
                        onClick={() => void handleDeletePortal(portal)}
                        className="inline-flex items-center justify-center rounded-xl border border-red-200 px-3 py-2 text-sm font-medium text-red-700 transition hover:border-red-300 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-red-900/80 dark:text-red-300 dark:hover:bg-red-950/30"
                      >
                        {deletingSlug === portal.slug
                          ? tr("catalogs.deleting", "Deleting...")
                          : tr("catalogs.delete", "Delete")}
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-600 dark:text-emerald-400">
            {tr("catalogs.candidate.eyebrow", "Previous imports")}
          </p>
          <h2 className="mt-2 text-xl font-semibold text-gray-900 dark:text-white">
            {tr("catalogs.candidate.title", "Seed a portal from data already in the workspace")}
          </h2>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
            {tr("catalogs.candidate.body", "Pick an existing imported collection and we will prefill the portal scope with the same domain and source filters. This is the fastest way to build a catalog from earlier ingestion work.")}
          </p>
        </div>

        {candidates.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {tr("catalogs.candidate.empty", "We do not have prior imported collections to suggest yet. Import data first, then come back here to seed a portal from it.")}
          </p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {candidates.map((candidate) => (
              <div
                key={`${candidate.domain_id}-${candidate.source}-${candidate.entity_type || "any"}`}
                className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                    {candidate.domain_id}
                  </span>
                  <span className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                    {candidate.source}
                  </span>
                  {candidate.entity_type && (
                    <span className="rounded-full bg-violet-100 px-2.5 py-1 text-xs font-medium text-violet-700 dark:bg-violet-900/30 dark:text-violet-300">
                      {candidate.entity_type}
                    </span>
                  )}
                </div>
                <p className="mt-3 text-sm font-semibold text-gray-900 dark:text-white">
                  {candidate.source_label}
                </p>
                <div className="mt-2 space-y-1 text-sm text-gray-600 dark:text-gray-300">
                  <p>
                    {tr("catalogs.candidate.records", "Records")}: {candidate.total_records.toLocaleString()}
                  </p>
                  <p>
                    {tr("catalogs.candidate.quality", "Average quality")}: {candidate.avg_quality !== null ? candidate.avg_quality.toFixed(2) : "—"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => seedFromCandidate(candidate)}
                  className="mt-4 w-full rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-700"
                >
                  {tr("catalogs.candidate.use", "Use for portal")}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
