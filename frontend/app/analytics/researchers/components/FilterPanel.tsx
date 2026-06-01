import type { FormEvent } from "react";

import type { FilterForm } from "../researchersTypes";

interface FilterPanelProps {
  topicInput: string;
  filters: FilterForm;
  loading: boolean;
  onTopicChange: (value: string) => void;
  onFilterChange: (key: keyof FilterForm, value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onReset: () => void;
}

const FILTER_FIELDS: Array<{ key: keyof FilterForm; label: string; placeholder: string }> = [
  { key: "source", label: "Fuente", placeholder: "openalex" },
  { key: "yearFrom", label: "Desde", placeholder: "2020" },
  { key: "yearTo", label: "Hasta", placeholder: "2026" },
  { key: "country", label: "Pais", placeholder: "China" },
  { key: "institution", label: "Institucion", placeholder: "University" },
  { key: "minCitations", label: "Min. citas", placeholder: "10" },
];

export default function FilterPanel({
  topicInput, filters, loading, onTopicChange, onFilterChange, onSubmit, onReset,
}: FilterPanelProps) {
  return (
    <section className="rounded-xl bg-white px-5 py-5 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-700 ring-1 ring-blue-100 dark:bg-blue-400/10 dark:text-blue-200 dark:ring-blue-400/20">
            <svg className="h-4 w-4" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 7h10M18 7h2M4 17h2M10 17h10M8 5v4M16 15v4" />
            </svg>
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
            className="h-10 rounded-xl bg-white px-4 text-sm font-semibold text-slate-600 ring-1 ring-slate-300 transition hover:bg-slate-50 hover:text-slate-900 dark:bg-slate-950 dark:text-slate-300 dark:ring-white/15 dark:hover:bg-white/5"
          >
            Reiniciar Filtros
          </button>
          <button
            type="submit"
            form="researcher-topic-filter-form"
            disabled={loading || topicInput.trim().length === 0}
            className="inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white shadow-xs transition hover:bg-blue-700 focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60 dark:focus:ring-blue-500/20"
          >
            <svg className="h-4 w-4" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 3v3M12 18v3M4.93 4.93l2.12 2.12M16.95 16.95l2.12 2.12M3 12h3M18 12h3M4.93 19.07l2.12-2.12M16.95 7.05l2.12-2.12M12 8l1.15 2.85L16 12l-2.85 1.15L12 16l-1.15-2.85L8 12l2.85-1.15L12 8Z" />
            </svg>
            {loading ? "Analizando..." : "Analizar Tema"}
          </button>
        </div>
      </div>
      <form id="researcher-topic-filter-form" onSubmit={onSubmit} className="mt-7 border-t border-slate-200 pt-5 dark:border-white/10">
        <div className="grid gap-4 lg:grid-cols-3">
          <label className="sr-only" htmlFor="topic-search">Tema a analizar</label>
          <label className="block lg:col-span-3">
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">Concepto / Tema</span>
            <input
              id="topic-search"
              value={topicInput}
              onChange={(event) => onTopicChange(event.target.value)}
              className="mt-2 h-11 w-full rounded-xl bg-slate-50 px-4 text-sm font-semibold text-slate-900 outline-none ring-1 ring-slate-200 transition focus:bg-white focus:ring-4 focus:ring-blue-100 dark:bg-slate-900 dark:text-white dark:ring-white/10 dark:focus:ring-blue-500/20"
              placeholder="Open Science (Ciencia Abierta)"
            />
          </label>
          {FILTER_FIELDS.map((field) => (
            <label key={field.key} className="block">
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">{field.label}</span>
              <input
                type={field.key === "minCitations" || field.key === "yearFrom" || field.key === "yearTo" ? "number" : "text"}
                value={filters[field.key]}
                onChange={(event) => onFilterChange(field.key, event.target.value)}
                className="mt-2 h-11 w-full rounded-xl bg-slate-50 px-4 text-sm font-semibold text-slate-900 outline-none ring-1 ring-slate-200 transition placeholder:text-slate-400 focus:bg-white focus:ring-4 focus:ring-blue-100 dark:bg-slate-900 dark:text-white dark:ring-white/10 dark:focus:ring-blue-500/20"
                placeholder={field.placeholder}
              />
            </label>
          ))}
        </div>
      </form>
    </section>
  );
}
