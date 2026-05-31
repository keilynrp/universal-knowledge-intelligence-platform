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
  const items: Array<{ label: string; value: string | number; truncate?: boolean }> = [
    { label: "Tema", value: topic, truncate: true },
    { label: "Investigadores", value: researcherCount },
    { label: "Citas totales", value: totalCitations },
    { label: "Densidad red", value: networkDensity },
    { label: "Nivel de confianza", value: confidence },
    { label: "Mejor evidencia", value: topResearcherName, truncate: true },
  ];
  return (
    <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      {items.map((item) => (
        <div key={item.label} className="rounded-xl bg-white p-4 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
          <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{item.label}</p>
          <p className={`mt-2 text-2xl font-bold tabular-nums text-slate-950 dark:text-white ${item.truncate ? "truncate" : ""}`}>
            {item.value}
          </p>
        </div>
      ))}
    </section>
  );
}
