import type { ReactNode } from "react";

interface MetricProps {
  label: ReactNode;
  value: ReactNode;
  description?: ReactNode;
  icon?: ReactNode;
  tone?: "violet" | "cyan" | "emerald" | "amber";
  className?: string;
}

const tones = {
  violet: "from-violet-500/20 to-violet-500/5 text-violet-300",
  cyan: "from-cyan-500/20 to-cyan-500/5 text-cyan-300",
  emerald: "from-emerald-500/20 to-emerald-500/5 text-emerald-300",
  amber: "from-amber-500/20 to-amber-500/5 text-amber-300",
};

export default function Metric({ label, value, description, icon, tone = "violet", className = "" }: MetricProps) {
  return (
    <div className={`rounded-[var(--ukip-radius-xl)] border border-[var(--ukip-border)] bg-gradient-to-br p-4 shadow-[var(--ukip-shadow-soft)] ${tones[tone]} ${className}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--ukip-muted)]">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--ukip-text-strong)]">{value}</p>
        </div>
        {icon ? <div className="rounded-xl bg-white/10 p-2">{icon}</div> : null}
      </div>
      {description ? <p className="mt-2 text-xs text-[var(--ukip-muted)]">{description}</p> : null}
    </div>
  );
}

