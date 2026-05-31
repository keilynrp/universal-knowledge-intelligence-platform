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
    <section className="rounded-xl bg-white p-5 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Filtros de busqueda cientifica</p>
        <button
          type="button"
          onClick={onReset}
          className="rounded-lg px-3 py-1 text-xs font-medium text-slate-500 ring-1 ring-slate-200 transition hover:bg-slate-50 hover:text-slate-700 dark:text-slate-400 dark:ring-white/10 dark:hover:bg-white/5"
        >
          Reiniciar filtros
        </button>
      </div>
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
          <label className="sr-only" htmlFor="topic-search">Tema a analizar</label>
          <input
            id="topic-search"
            value={topicInput}
            onChange={(event) => onTopicChange(event.target.value)}
            className="h-11 rounded-xl bg-white px-4 text-sm font-medium text-slate-900 outline-none ring-1 ring-slate-200 transition focus:ring-4 focus:ring-blue-100 dark:bg-slate-900 dark:text-white dark:ring-white/10 dark:focus:ring-blue-500/20"
            placeholder="Buscar por tema: open science, quantum materials, knowledge graphs"
          />
          <button
            type="submit"
            disabled={loading || topicInput.trim().length === 0}
            className="h-11 rounded-xl bg-blue-600 px-6 text-sm font-semibold text-white transition hover:bg-blue-700 focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60 dark:focus:ring-blue-500/20"
          >
            {loading ? "Analizando..." : "Analizar tema"}
          </button>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          {FILTER_FIELDS.map((field) => (
            <label key={field.key} className="block">
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{field.label}</span>
              <input
                value={filters[field.key]}
                onChange={(event) => onFilterChange(field.key, event.target.value)}
                className="mt-1 h-10 w-full rounded-lg bg-white px-3 text-sm font-medium text-slate-900 outline-none ring-1 ring-slate-200 transition focus:ring-4 focus:ring-blue-100 dark:bg-slate-900 dark:text-white dark:ring-white/10 dark:focus:ring-blue-500/20"
                placeholder={field.placeholder}
              />
            </label>
          ))}
        </div>
      </form>
    </section>
  );
}
