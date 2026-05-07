import type { ReactNode } from "react";
import DeltaBadge from "./DeltaBadge";

type KpiTone = "violet" | "amber" | "emerald" | "sky";
type DeltaDirection = "up" | "down" | "neutral";

interface KpiSummaryCardProps {
  label: ReactNode;
  value: ReactNode;
  icon: ReactNode;
  tone?: KpiTone;
  deltaValue?: ReactNode;
  deltaDirection?: DeltaDirection;
  deltaLabel?: ReactNode;
}

const iconToneClass: Record<KpiTone, string> = {
  violet: "bg-violet-100 text-violet-700 dark:bg-violet-400/15 dark:text-violet-200",
  amber: "bg-amber-100 text-amber-700 dark:bg-amber-400/15 dark:text-amber-200",
  emerald: "bg-emerald-100 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-200",
  sky: "bg-sky-100 text-sky-700 dark:bg-sky-400/15 dark:text-sky-200",
};

export default function KpiSummaryCard({
  label,
  value,
  icon,
  tone = "violet",
  deltaValue,
  deltaDirection = "up",
  deltaLabel,
}: KpiSummaryCardProps) {
  return (
    <article className="rounded-[22px] border border-slate-200 bg-white p-5 shadow-sm transition hover:border-violet-200 hover:shadow-md dark:border-white/10 dark:bg-[var(--ukip-panel)] dark:hover:border-violet-400/30">
      <div className="flex items-start justify-between gap-4">
        <p className="text-sm font-semibold text-slate-600 dark:text-[var(--ukip-muted)]">{label}</p>
        <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${iconToneClass[tone]}`}>
          {icon}
        </span>
      </div>

      <p className="mt-4 font-mono text-4xl font-semibold tracking-[-0.035em] text-slate-950 dark:text-[var(--ukip-text-strong)]">
        {value}
      </p>

      {deltaValue ? (
        <div className="mt-3">
          <DeltaBadge value={deltaValue} direction={deltaDirection}>
            {deltaLabel}
          </DeltaBadge>
        </div>
      ) : null}
    </article>
  );
}
