interface EnrichmentMeterProps {
  value: number;
  label?: string;
  className?: string;
}

export default function EnrichmentMeter({ value, label = "Enriquecido", className = "" }: EnrichmentMeterProps) {
  const safeValue = Math.max(0, Math.min(100, Math.round(Number.isFinite(value) ? value : 0)));

  return (
    <div className={`inline-flex items-center gap-2 ${className}`}>
      <span className="rounded-full bg-emerald-500/10 px-2 py-1 text-xs font-semibold text-emerald-300">
        {label}
      </span>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-700/70">
        <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-cyan-400" style={{ width: `${safeValue}%` }} />
      </div>
      <span className="text-xs tabular-nums text-[var(--ukip-muted)]">{safeValue}%</span>
    </div>
  );
}

