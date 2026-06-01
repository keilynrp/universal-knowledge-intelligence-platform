import ResearchIcon from "./ResearchersIcons";

interface KpiStripProps {
  topic: string;
  researcherCount: number;
  totalCitations: number;
  networkDensity: number;
  confidence: number;
  topResearcherName: string;
}

export default function KpiStrip({
  topic,
  researcherCount,
  totalCitations,
  networkDensity,
  confidence,
  topResearcherName,
}: KpiStripProps) {
  const items: Array<{ label: string; value: string | number; icon: "target" | "users" | "award" | "file" | "network" | "chart"; accent?: string; truncate?: boolean }> = [
    { label: "Tema analizado", value: topic, icon: "target", truncate: true },
    { label: "Investigadores totales", value: researcherCount, icon: "users" },
    { label: "Mejor evidencia", value: topResearcherName, icon: "award", accent: "text-emerald-700 dark:text-emerald-300", truncate: true },
    { label: "Citas totales", value: totalCitations, icon: "file" },
    { label: "Densidad red", value: networkDensity, icon: "network" },
    { label: "Nivel de confianza", value: confidence, icon: "chart" },
  ];

  return (
    <section className="rounded-xl bg-white p-5 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        {items.map((item) => (
          <div key={item.label} className="min-w-0 border-l border-slate-200 pl-4 first:border-l-0 first:pl-0 dark:border-white/10">
            <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-50 text-slate-500 ring-1 ring-slate-200 dark:bg-white/5 dark:text-slate-300 dark:ring-white/10">
              <ResearchIcon name={item.icon} />
            </div>
            <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{item.label}</p>
            <p className={`mt-2 text-xl font-bold tabular-nums text-slate-950 dark:text-white ${item.accent ?? ""} ${item.truncate ? "truncate" : ""}`}>
              {item.value}
            </p>
          </div>
        ))}
      </div>
      <div className="mt-5 flex items-center gap-2 border-t border-slate-100 pt-4 text-xs text-slate-500 dark:border-white/10 dark:text-slate-400">
        <ResearchIcon name="database" className="h-4 w-4 shrink-0" />
        <p>
          Actualizado de acuerdo a la ingesta y enriquecimiento disponibles para el dominio activo.
        </p>
      </div>
    </section>
  );
}
