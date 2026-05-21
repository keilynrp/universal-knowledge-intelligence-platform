import type { ReactNode } from "react";

export type PillarProgressItem = {
  id: string;
  label: string;
  subtitle: string;
  percent: number;
  tags: string[];
  tone: "violet" | "sky" | "emerald";
  icon: ReactNode;
};

export type ReadinessDriverItem = {
  label: string;
  percent: number;
  description?: string;
};

export type PipelineHealthMetric = {
  label: string;
  value: number;
};

export type DashboardInsightMetricsProps = {
  pillarTitle: string;
  pillarSubtitle: string;
  readinessTitle: string;
  readinessSubtitle: string;
  readinessBadge: string;
  healthTitle: string;
  healthSubtitle: string;
  liveLabel: string;
  scoreSuffix: string;
  pillars: PillarProgressItem[];
  readinessDrivers: ReadinessDriverItem[];
  healthScore: number;
  healthMetrics: PipelineHealthMetric[];
};

const toneClasses: Record<PillarProgressItem["tone"], { icon: string; bar: string }> = {
  violet: {
    icon: "bg-violet-100 text-violet-700 dark:bg-violet-400/15 dark:text-violet-200",
    bar: "bg-violet-600",
  },
  sky: {
    icon: "bg-sky-100 text-sky-700 dark:bg-sky-400/15 dark:text-sky-200",
    bar: "bg-blue-500",
  },
  emerald: {
    icon: "bg-emerald-100 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-200",
    bar: "bg-emerald-500",
  },
};

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function MetricPanel({ children }: { children: ReactNode }) {
  return (
    <section className="rounded-[var(--ukip-radius-xl)] border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
      {children}
    </section>
  );
}

function IconPath({ path }: { path: string }) {
  return (
    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d={path} />
    </svg>
  );
}

function HealthGauge({ value }: { value: number }) {
  const score = clampPercent(value);
  const circumference = Math.PI * 92;
  const dash = (score / 100) * circumference;
  return (
    <div className="relative mx-auto mt-6 h-36 w-64">
      <svg viewBox="0 0 220 130" className="h-full w-full" role="img" aria-label={`Pipeline health ${score}`}>
        <path d="M 30 110 A 80 80 0 0 1 190 110" fill="none" stroke="currentColor" className="text-slate-100 dark:text-white/10" strokeWidth="28" strokeLinecap="butt" />
        <path
          d="M 30 110 A 80 80 0 0 1 190 110"
          fill="none"
          stroke="rgb(124 58 237)"
          strokeWidth="28"
          strokeLinecap="butt"
          strokeDasharray={`${dash} ${circumference}`}
        />
      </svg>
      <div className="absolute inset-x-0 bottom-0 text-center">
        <p className="font-mono text-4xl font-semibold tracking-[-0.03em] text-slate-950 dark:text-[var(--ukip-text-strong)]">{score}</p>
      </div>
    </div>
  );
}

export default function DashboardInsightMetrics({
  pillarTitle,
  pillarSubtitle,
  readinessTitle,
  readinessSubtitle,
  readinessBadge,
  healthTitle,
  healthSubtitle,
  liveLabel,
  scoreSuffix,
  pillars,
  readinessDrivers,
  healthScore,
  healthMetrics,
}: DashboardInsightMetricsProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <MetricPanel>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold tracking-[-0.02em] text-slate-950 dark:text-[var(--ukip-text-strong)]">{pillarTitle}</h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-[var(--ukip-muted)]">{pillarSubtitle}</p>
          </div>
          <span className="text-xs text-slate-500 dark:text-[var(--ukip-muted)]">%</span>
        </div>
        <div className="mt-6 space-y-6">
          {pillars.map((pillar) => {
            const tone = toneClasses[pillar.tone];
            const percent = clampPercent(pillar.percent);
            return (
              <article key={pillar.id} className="flex gap-4">
                <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${tone.icon}`}>{pillar.icon}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-end justify-between gap-3">
                    <div>
                      <p className="font-semibold text-slate-950 dark:text-[var(--ukip-text-strong)]">{pillar.label}</p>
                      <p className="text-xs uppercase tracking-[0.12em] text-slate-500 dark:text-[var(--ukip-muted)]">{pillar.subtitle}</p>
                    </div>
                    <span className="font-mono text-xl font-semibold text-slate-950 dark:text-[var(--ukip-text-strong)]">{percent}%</span>
                  </div>
                  <div className="mt-3 h-2 rounded-full bg-slate-100 dark:bg-white/10">
                    <div className={`h-2 rounded-full ${tone.bar}`} style={{ width: `${percent}%` }} />
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {pillar.tags.map((tag) => (
                      <span key={tag} className="rounded-full border border-slate-200 px-3 py-0.5 text-[10px] uppercase tracking-[0.12em] text-slate-600 dark:border-white/10 dark:text-[var(--ukip-muted)]">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </MetricPanel>

      <MetricPanel>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold tracking-[-0.02em] text-slate-950 dark:text-[var(--ukip-text-strong)]">{readinessTitle}</h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-[var(--ukip-muted)]">{readinessSubtitle}</p>
          </div>
          <span className="rounded-full border border-slate-200 px-3 py-1 text-xs uppercase tracking-[0.18em] text-slate-500 dark:border-white/10 dark:text-[var(--ukip-muted)]">
            {readinessBadge}
          </span>
        </div>
        <div className="mt-6 space-y-4">
          {readinessDrivers.map((item) => {
            const percent = clampPercent(item.percent);
            return (
              <article key={item.label}>
                <div className="flex items-end justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-950 dark:text-[var(--ukip-text-strong)]">{item.label}</p>
                    {item.description ? (
                      <p className="mt-0.5 text-xs text-slate-500 dark:text-[var(--ukip-muted)]">{item.description}</p>
                    ) : null}
                  </div>
                  <span className="font-mono text-lg font-semibold text-slate-950 dark:text-[var(--ukip-text-strong)]">{percent}%</span>
                </div>
                <div className="mt-2 h-2 rounded-full bg-slate-100 dark:bg-white/10">
                  <div className="h-2 rounded-full bg-violet-600" style={{ width: `${percent}%` }} />
                </div>
              </article>
            );
          })}
        </div>
      </MetricPanel>

      <MetricPanel>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold tracking-[-0.02em] text-slate-950 dark:text-[var(--ukip-text-strong)]">{healthTitle}</h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-[var(--ukip-muted)]">{healthSubtitle}</p>
          </div>
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-200">
            <IconPath path="M4.5 12.75 8.25 16.5 15 7.5l4.5 4.5" />
            {liveLabel}
          </span>
        </div>
        <HealthGauge value={healthScore} />
        <p className="text-center text-xs uppercase tracking-[0.14em] text-slate-500 dark:text-[var(--ukip-muted)]">{scoreSuffix}</p>
        <div className="mt-6 grid grid-cols-3 border-t border-slate-200 pt-4 dark:border-white/10">
          {healthMetrics.map((metric) => (
            <div key={metric.label} className="text-center">
              <p className="font-mono text-lg font-semibold text-slate-950 dark:text-[var(--ukip-text-strong)]">{clampPercent(metric.value)}%</p>
              <p className="mt-1 text-[10px] uppercase tracking-[0.14em] text-slate-500 dark:text-[var(--ukip-muted)]">{metric.label}</p>
            </div>
          ))}
        </div>
      </MetricPanel>
    </div>
  );
}
