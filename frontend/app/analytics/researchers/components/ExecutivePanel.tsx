import type { ExecutiveSummary } from "../researchersTypes";
import { scoreTone } from "../researchersUtils";

export default function ExecutivePanel({ summary }: { summary: ExecutiveSummary | null }) {
  const confidence = summary?.confidence ?? 0;
  const metrics = [
    { label: "Cobertura", value: summary?.coverage_score ?? 0 },
    { label: "Alta confianza", value: summary?.high_confidence_researchers ?? 0 },
    { label: "Citas", value: summary?.total_citations ?? 0 },
    { label: "Densidad red", value: summary?.network_density_score ?? 0 },
  ];
  return (
    <section className="rounded-xl bg-white p-5 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
      <div className="grid gap-5 lg:grid-cols-[220px_1fr]">
        <div className={`rounded-xl p-5 ring-1 ${scoreTone(confidence)}`}>
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
