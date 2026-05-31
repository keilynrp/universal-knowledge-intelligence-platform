import type { FilterForm } from "./researchersTypes";

export function scoreTone(score: number): string {
  if (score >= 70) return "text-emerald-700 bg-emerald-50 ring-emerald-200 dark:text-emerald-200 dark:bg-emerald-400/10 dark:ring-emerald-400/20";
  if (score >= 40) return "text-amber-700 bg-amber-50 ring-amber-200 dark:text-amber-200 dark:bg-amber-400/10 dark:ring-amber-400/20";
  return "text-red-700 bg-red-50 ring-red-200 dark:text-red-200 dark:bg-red-400/10 dark:ring-red-400/20";
}

export function barColor(score: number): string {
  if (score >= 70) return "bg-emerald-500";
  if (score >= 40) return "bg-amber-500";
  return "bg-red-500";
}

export function externalHref(id: string | null): string | null {
  if (!id) return null;
  if (id.startsWith("http")) return id;
  if (id.startsWith("0000-")) return `https://orcid.org/${id}`;
  return id;
}

export function buildQuery(topic: string, domainId: string, filters: FilterForm, limit: string, minWeight?: string): URLSearchParams {
  const params = new URLSearchParams({ topic, domain_id: domainId, limit });
  if (minWeight) params.set("min_weight", minWeight);
  if (filters.source.trim()) params.set("source", filters.source.trim());
  if (filters.yearFrom.trim()) params.set("year_from", filters.yearFrom.trim());
  if (filters.yearTo.trim()) params.set("year_to", filters.yearTo.trim());
  if (filters.country.trim()) params.set("country", filters.country.trim());
  if (filters.institution.trim()) params.set("institution", filters.institution.trim());
  if (filters.minCitations.trim()) params.set("min_citations", filters.minCitations.trim());
  return params;
}
