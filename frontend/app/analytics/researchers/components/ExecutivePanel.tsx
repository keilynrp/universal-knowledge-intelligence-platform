import type { ExecutiveSummary } from "../researchersTypes";
import { scoreTone } from "../researchersUtils";

import ResearchIcon from "./ResearchersIcons";

export default function ExecutivePanel({ summary }: { summary: ExecutiveSummary | null }) {
  const confidence = summary?.confidence ?? 0;
  const metrics = [
    { label: "Cobertura", value: summary?.coverage_score ?? 0, icon: "target" as const },
    { label: "Alta confianza", value: summary?.high_confidence_researchers ?? 0, icon: "check" as const },
    { label: "Citas", value: summary?.total_citations ?? 0, icon: "file" as const },
    { label: "Densidad red", value: summary?.network_density_score ?? 0, icon: "network" as const },
  ];
  return (
    <section className="rounded-xl bg-white p-5 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
      <div className="grid gap-5 lg:grid-cols-[220px_1fr]">
        <div className={`rounded-xl p-5 ring-1 ${scoreTone(confidence)}`}>
          <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-white/60 ring-1 ring-current/15 dark:bg-white/10">
            <ResearchIcon name="chart" className="h-5 w-5" />
          </div>
          <p className="text-[10px] font-mono uppercase tracking-wider">Metrica ejecutiva</p>
          <p className="mt-3 text-5xl font-bold tabular-nums">{confidence}</p>
          <p className="mt-1 text-sm font-medium">confianza del mapa</p>
        </div>
        <div className="min-w-0">
          <h2 className="text-xl font-bold tracking-tight text-slate-950 dark:text-white">
            {summary?.headline ?? "Ejecuta una busqueda para generar el mapa ejecutivo."}
          </h2>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            {summary?.stakeholder_value ?? "La metrica resume cobertura, autoridad, citas, evidencia y densidad de red para briefs y conversaciones ejecutivas."}
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-4">
            {metrics.map((metric) => (
              <div key={metric.label} className="rounded-lg bg-slate-50 p-3 dark:bg-white/5">
                <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-lg bg-white text-slate-500 ring-1 ring-slate-200 dark:bg-slate-950 dark:text-slate-300 dark:ring-white/10">
                  <ResearchIcon name={metric.icon} />
                </div>
                <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{metric.label}</p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-slate-950 dark:text-white">{metric.value}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
