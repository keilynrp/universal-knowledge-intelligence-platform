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
  const items: Array<{ label: string; value: string | number; accent?: string; truncate?: boolean }> = [
    { label: "Tema analizado", value: topic, truncate: true },
    { label: "Investigadores totales", value: researcherCount },
    { label: "Mejor evidencia", value: topResearcherName, accent: "text-emerald-700 dark:text-emerald-300", truncate: true },
    { label: "Citas totales", value: totalCitations },
    { label: "Densidad red", value: networkDensity },
    { label: "Nivel de confianza", value: confidence },
  ];

  return (
    <section className="rounded-xl bg-white p-5 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        {items.map((item) => (
          <div key={item.label} className="min-w-0 border-l border-slate-200 pl-4 first:border-l-0 first:pl-0 dark:border-white/10">
            <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{item.label}</p>
            <p className={`mt-2 text-xl font-bold tabular-nums text-slate-950 dark:text-white ${item.accent ?? ""} ${item.truncate ? "truncate" : ""}`}>
              {item.value}
            </p>
          </div>
        ))}
      </div>
      <div className="mt-5 flex items-center gap-2 border-t border-slate-100 pt-4 text-xs text-slate-500 dark:border-white/10 dark:text-slate-400">
        <svg className="h-4 w-4 shrink-0" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
        </svg>
        <p>
          Actualizado de acuerdo a la ingesta y enriquecimiento disponibles para el dominio activo.
        </p>
      </div>
    </section>
  );
}
