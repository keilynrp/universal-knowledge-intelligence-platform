import type { ReactNode } from "react";

interface CognitiveKpiProps {
  label: ReactNode;
  value: ReactNode;
  delta?: ReactNode;
  tone?: "violet" | "cyan" | "emerald";
}

const toneClass = {
  violet: "text-violet-300",
  cyan: "text-cyan-300",
  emerald: "text-emerald-300",
};

export default function CognitiveKpi({ label, value, delta, tone = "violet" }: CognitiveKpiProps) {
  return (
    <div className="rounded-[var(--ukip-radius-lg)] border border-[var(--ukip-border)] bg-[var(--ukip-panel)] p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--ukip-muted)]">{label}</p>
      <p className={`mt-2 text-3xl font-bold ${toneClass[tone]}`}>{value}</p>
      {delta ? <p className="mt-1 text-xs text-[var(--ukip-muted)]">{delta}</p> : null}
    </div>
  );
}

