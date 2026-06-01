import type { FormEvent } from "react";

import type { FilterForm } from "../researchersTypes";

import ResearchIcon from "./ResearchersIcons";

interface FilterPanelProps {
  topicInput: string;
  filters: FilterForm;
  loading: boolean;
  onTopicChange: (value: string) => void;
  onFilterChange: (key: keyof FilterForm, value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onReset: () => void;
}

const FILTER_FIELDS: Array<{ key: keyof FilterForm; label: string; placeholder: string; icon: "database" | "calendar" | "globe" | "institution" | "chart" }> = [
  { key: "source", label: "Fuente", placeholder: "openalex", icon: "database" },
  { key: "yearFrom", label: "Desde", placeholder: "2020", icon: "calendar" },
  { key: "yearTo", label: "Hasta", placeholder: "2026", icon: "calendar" },
  { key: "country", label: "Pais", placeholder: "China", icon: "globe" },
  { key: "institution", label: "Institucion", placeholder: "University", icon: "institution" },
  { key: "minCitations", label: "Min. citas", placeholder: "10", icon: "chart" },
];

export default function FilterPanel({
  topicInput, filters, loading, onTopicChange, onFilterChange, onSubmit, onReset,
}: FilterPanelProps) {
  return (
    <section className="rounded-xl bg-white px-5 py-5 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-700 ring-1 ring-blue-100 dark:bg-blue-400/10 dark:text-blue-200 dark:ring-blue-400/20">
            <ResearchIcon name="search" />
          </span>
          <div className="min-w-0">
            <p className="text-lg font-bold tracking-tight text-slate-950 dark:text-white">Filtros de Busqueda Cientifica</p>
            <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Investigadores por tema</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onReset}
            className="inline-flex h-10 items-center gap-2 rounded-xl bg-white px-4 text-sm font-semibold text-slate-600 ring-1 ring-slate-300 transition hover:bg-slate-50 hover:text-slate-900 dark:bg-slate-950 dark:text-slate-300 dark:ring-white/15 dark:hover:bg-white/5"
          >
            <ResearchIcon name="refresh" />
            Reiniciar Filtros
          </button>
          <button
            type="submit"
            form="researcher-topic-filter-form"
            disabled={loading || topicInput.trim().length === 0}
            className="inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white shadow-xs transition hover:bg-blue-700 focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60 dark:focus:ring-blue-500/20"
          >
            <ResearchIcon name="spark" />
            {loading ? "Analizando..." : "Analizar Tema"}
          </button>
        </div>
      </div>
      <form id="researcher-topic-filter-form" onSubmit={onSubmit} className="mt-7 border-t border-slate-200 pt-5 dark:border-white/10">
        <div className="grid gap-4 lg:grid-cols-3">
          <label className="sr-only" htmlFor="topic-search">Tema a analizar</label>
          <label className="block lg:col-span-3">
            <span className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">
              <ResearchIcon name="target" className="h-3.5 w-3.5" />
              Concepto / Tema
            </span>
            <div className="relative mt-2">
              <ResearchIcon name="search" className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="topic-search"
                value={topicInput}
                onChange={(event) => onTopicChange(event.target.value)}
                className="h-11 w-full rounded-xl bg-slate-50 px-10 text-sm font-semibold text-slate-900 outline-none ring-1 ring-slate-200 transition focus:bg-white focus:ring-4 focus:ring-blue-100 dark:bg-slate-900 dark:text-white dark:ring-white/10 dark:focus:ring-blue-500/20"
                placeholder="Open Science (Ciencia Abierta)"
              />
            </div>
          </label>
          {FILTER_FIELDS.map((field) => (
            <label key={field.key} className="block">
              <span className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">
                <ResearchIcon name={field.icon} className="h-3.5 w-3.5" />
                {field.label}
              </span>
              <div className="relative mt-2">
                <ResearchIcon name={field.icon} className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type={field.key === "minCitations" || field.key === "yearFrom" || field.key === "yearTo" ? "number" : "text"}
                  value={filters[field.key]}
                  onChange={(event) => onFilterChange(field.key, event.target.value)}
                  className="h-11 w-full rounded-xl bg-slate-50 px-10 text-sm font-semibold text-slate-900 outline-none ring-1 ring-slate-200 transition placeholder:text-slate-400 focus:bg-white focus:ring-4 focus:ring-blue-100 dark:bg-slate-900 dark:text-white dark:ring-white/10 dark:focus:ring-blue-500/20"
                  placeholder={field.placeholder}
                />
              </div>
            </label>
          ))}
        </div>
      </form>
    </section>
  );
}
