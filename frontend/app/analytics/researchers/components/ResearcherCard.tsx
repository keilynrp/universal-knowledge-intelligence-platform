import Link from "next/link";

import type { Researcher } from "../researchersTypes";
import { DRIVER_LABELS } from "../researchersTypes";
import { barColor, externalHref, scoreTone } from "../researchersUtils";

export interface ResearcherCardProps {
  researcher: Researcher;
  rank: number;
}

export default function ResearcherCard({ researcher, rank }: ResearcherCardProps) {
  return (
    <article className="rounded-xl bg-white p-5 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 font-mono text-sm font-bold text-blue-700 ring-1 ring-blue-100 dark:bg-blue-400/10 dark:text-blue-200 dark:ring-blue-400/20">
              {rank}
            </span>
            <div className="min-w-0">
              <h3 className="truncate text-base font-bold tracking-tight text-slate-950 dark:text-white">{researcher.name}</h3>
              <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Investigador identificado</p>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2 text-xs font-medium">
            {researcher.orcid && (
              <a href={externalHref(researcher.orcid) ?? "#"} target="_blank" rel="noreferrer" className="rounded-full bg-slate-100 px-3 py-1 text-slate-700 hover:text-blue-700 dark:bg-white/10 dark:text-slate-200">
                ORCID {researcher.orcid}
              </a>
            )}
            {researcher.openalex_id && (
              <a href={externalHref(researcher.openalex_id) ?? "#"} target="_blank" rel="noreferrer" className="rounded-full bg-slate-100 px-3 py-1 text-slate-700 hover:text-blue-700 dark:bg-white/10 dark:text-slate-200">
                OpenAlex
              </a>
            )}
          </div>
        </div>
        <div className={`rounded-lg px-4 py-3 text-center ring-1 ${scoreTone(researcher.topic_score)}`}>
          <p className="text-3xl font-bold tabular-nums">{researcher.topic_score}</p>
          <p className="text-[10px] font-mono uppercase tracking-wider">score</p>
        </div>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-3">
        {[
          { label: "Registros", value: researcher.records_count },
          { label: "Citas", value: researcher.citation_count },
          { label: "Evidencias", value: researcher.evidence.length },
        ].map((m) => (
          <div key={m.label} className="rounded-lg bg-slate-50 p-3 dark:bg-white/5">
            <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{m.label}</p>
            <p className="mt-1 text-xl font-bold tabular-nums text-slate-950 dark:text-white">{m.value}</p>
          </div>
        ))}
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {DRIVER_LABELS.map(({ key, label }) => (
          <div key={key}>
            <div className="mb-1 flex justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>{label}</span>
              <span className="tabular-nums text-slate-500">{researcher.drivers[key]}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-slate-100 dark:bg-white/10">
              <div className={`h-full rounded-full ${barColor(researcher.drivers[key])}`} style={{ width: `${researcher.drivers[key]}%` }} />
            </div>
          </div>
        ))}
      </div>
      {researcher.evidence.length > 0 && (
        <div className="mt-5 space-y-2">
          <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Evidencia</p>
          {researcher.evidence.map((item) => (
            <Link
              key={item.entity_id}
              href={`/entities/${item.entity_id}`}
              className="block rounded-lg px-3 py-2 text-sm text-slate-700 ring-1 ring-slate-100 transition hover:bg-blue-50 hover:ring-blue-200 dark:text-slate-200 dark:ring-white/10 dark:hover:bg-blue-400/10"
            >
              <span className="font-medium">{item.title || `Registro ${item.entity_id}`}</span>
              <span className="ml-2 text-xs text-slate-400">{item.citations} citas</span>
            </Link>
          ))}
        </div>
      )}
    </article>
  );
}
