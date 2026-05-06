import type { ReactNode } from "react";
import Link from "next/link";
import { Panel } from "../ui";

export type NarrativeStageStatus = "done" | "current" | "upcoming";

export type NarrativeStage = {
  id: string;
  label: string;
  href: string;
  status: NarrativeStageStatus;
};

export type NarrativeMetric = {
  id: string;
  label: string;
  value: string;
  description?: string;
  percent?: number;
  tone?: "violet" | "emerald" | "sky";
  icon?: ReactNode;
};

export type NarrativeQuickAction = {
  title: string;
  description: string;
  href: string;
  tone: "blue" | "violet" | "emerald";
  iconPath: string;
};

export type AdaptiveNarrativeCopy = {
  brandLabel: string;
  eyebrow: string;
  title: string;
  body: string;
  progressLabel: string;
  stepLabel: string;
  flowLabel: string;
  whyTitle: string;
  context: string;
  info: string;
  quickToolsTitle: string;
  quickToolsDescription: string;
  nextActionEyebrow: string;
};

export type AdaptiveNarrativeBlockProps = {
  progress: number;
  currentStep: number;
  totalSteps: number;
  role?: "research_office" | "library" | "innovation_team" | "general";
  coveragePercent?: number;
  enrichmentCoverage?: number;
  recommendedActionLabel?: string;
  recommendedActionHref?: string;
  recommendedActionTitle?: string;
  recommendedActionReason?: string;
  copy: AdaptiveNarrativeCopy;
  stages: NarrativeStage[];
  metrics: NarrativeMetric[];
  flowItems: string[];
  quickActions: NarrativeQuickAction[];
};

const toneClasses: Record<NonNullable<NarrativeMetric["tone"]>, string> = {
  violet: "bg-violet-100 text-violet-700 dark:bg-violet-400/15 dark:text-violet-200",
  emerald: "bg-emerald-100 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-200",
  sky: "bg-sky-100 text-sky-700 dark:bg-sky-400/15 dark:text-sky-200",
};

const actionToneClasses: Record<NarrativeQuickAction["tone"], string> = {
  blue: "from-blue-600 to-cyan-500 shadow-blue-500/20",
  violet: "from-violet-600 to-purple-500 shadow-violet-500/20",
  emerald: "from-emerald-600 to-teal-500 shadow-emerald-500/20",
};

function clampPercent(value: number | undefined): number {
  if (typeof value !== "number" || Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function ProgressBar({ value, tone = "violet" }: { value: number; tone?: NarrativeMetric["tone"] }) {
  const fillClass = tone === "emerald" ? "bg-emerald-500" : tone === "sky" ? "bg-blue-500" : "bg-violet-500";
  return (
    <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-white/10">
      <div className={`h-full rounded-full ${fillClass} transition-[width]`} style={{ width: `${clampPercent(value)}%` }} />
    </div>
  );
}

function StepDots({ stages }: { stages: NarrativeStage[] }) {
  return (
    <div className="flex items-center gap-0">
      {stages.map((stage, index) => (
        <div key={stage.id} className="flex items-center">
          <span
            className={`h-3.5 w-3.5 rounded-full border transition ${
              stage.status === "done" || stage.status === "current"
                ? "border-violet-500 bg-violet-600 shadow-[0_0_0_4px_rgb(124_58_237_/_0.12)]"
                : "border-slate-200 bg-slate-200 dark:border-white/15 dark:bg-white/15"
            }`}
          />
          {index < stages.length - 1 ? (
            <span className="h-px w-9 bg-slate-200 dark:bg-white/15" />
          ) : null}
        </div>
      ))}
    </div>
  );
}

function IconFromPath({ path, className = "h-7 w-7" }: { path: string; className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d={path} />
    </svg>
  );
}

export default function AdaptiveNarrativeBlock({
  progress,
  currentStep,
  totalSteps,
  recommendedActionLabel,
  recommendedActionHref,
  recommendedActionTitle,
  recommendedActionReason,
  copy,
  stages,
  metrics,
  flowItems,
  quickActions,
}: AdaptiveNarrativeBlockProps) {
  const safeProgress = clampPercent(progress);
  const safeTotalSteps = Math.max(1, totalSteps);
  const safeCurrentStep = Math.max(1, Math.min(currentStep, safeTotalSteps));
  const ctaHref = recommendedActionHref || stages.find((stage) => stage.status === "current")?.href || "/";
  const ctaLabel = recommendedActionLabel || copy.nextActionEyebrow;
  const actionTitle = recommendedActionTitle || ctaLabel;
  const reason = recommendedActionReason || copy.context;
  const flowText = flowItems.length > 0 ? flowItems.join(" → ") : stages.map((stage) => stage.label).join(" → ");

  return (
    <Panel variant="soft" className="overflow-hidden border-slate-200 bg-white p-0 shadow-[0_22px_70px_rgb(15_23_42_/_0.08)] dark:border-white/10 dark:bg-[var(--ukip-panel)]">
      <div className="grid lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.75fr)]">
        <div className="space-y-6 p-6 lg:p-8">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
            <div className="max-w-3xl">
              <div className="flex flex-wrap items-center gap-3">
                <span className="inline-flex items-center gap-2 text-xl font-black tracking-[-0.04em] text-slate-950 dark:text-[var(--ukip-text-strong)]">
                  <span className="h-5 w-5 rounded-[0.35rem] bg-gradient-to-br from-violet-500 to-blue-500 shadow-[var(--ukip-glow-violet)]" />
                  {copy.brandLabel}
                </span>
                <span className="rounded-full border border-violet-200 bg-violet-50 px-4 py-1.5 text-sm font-semibold text-violet-700 dark:border-violet-400/25 dark:bg-violet-500/10 dark:text-violet-200">
                  {copy.eyebrow}
                </span>
              </div>
              <h2 className="mt-8 max-w-2xl text-4xl font-black leading-[1.08] tracking-[-0.06em] text-slate-950 dark:text-[var(--ukip-text-strong)] sm:text-5xl">
                {copy.title}
              </h2>
              <p className="mt-5 max-w-3xl text-base leading-8 text-slate-600 dark:text-[var(--ukip-muted)]">
                {copy.body}
              </p>
            </div>

            <div className="w-full rounded-[var(--ukip-radius-xl)] border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/5 xl:max-w-[18rem]">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500 dark:text-[var(--ukip-muted)]">
                {copy.progressLabel}
              </p>
              <p className="mt-3 font-mono text-3xl font-black tracking-[-0.08em] text-slate-950 dark:text-[var(--ukip-text-strong)]">
                {safeProgress}%
              </p>
              <div className="mt-4">
                <ProgressBar value={safeProgress} />
              </div>
              <p className="mt-5 text-sm text-slate-600 dark:text-[var(--ukip-muted)]">
                {copy.stepLabel}
              </p>
              <div className="mt-3">
                <StepDots stages={stages} />
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <article className="rounded-[var(--ukip-radius-xl)] border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-white/5">
              <div className="flex items-start gap-4">
                <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-violet-100 text-violet-700 dark:bg-violet-400/15 dark:text-violet-200">
                  <IconFromPath path="M4.5 12h15m0 0-5-5m5 5-5 5M6 6.75h3.75M6 17.25h3.75" />
                </span>
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-violet-600 dark:text-violet-200">
                    {copy.flowLabel}
                  </p>
                  <p className="mt-2 text-base font-bold leading-7 text-slate-950 dark:text-[var(--ukip-text-strong)]">
                    {flowText}
                  </p>
                  <span className="mt-4 inline-flex rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-sm font-semibold text-violet-700 dark:border-violet-400/25 dark:bg-violet-500/10 dark:text-violet-200">
                    {copy.stepLabel}
                  </span>
                </div>
              </div>
            </article>

            {metrics.map((metric) => (
              <article key={metric.id} className="rounded-[var(--ukip-radius-xl)] border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-white/5">
                <div className="flex items-start gap-4">
                  <span className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl ${toneClasses[metric.tone || "violet"]}`}>
                    {metric.icon}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500 dark:text-[var(--ukip-muted)]">
                      {metric.label}
                    </p>
                    <p className="mt-3 font-mono text-3xl font-black tracking-[-0.08em] text-slate-950 dark:text-[var(--ukip-text-strong)]">
                      {metric.value}
                    </p>
                    {metric.description ? (
                      <p className="mt-1 text-sm text-slate-500 dark:text-[var(--ukip-muted)]">{metric.description}</p>
                    ) : null}
                    {typeof metric.percent === "number" ? (
                      <div className="mt-4">
                        <ProgressBar value={metric.percent} tone={metric.tone} />
                      </div>
                    ) : null}
                  </div>
                </div>
              </article>
            ))}
          </div>

          <div className="flex gap-4 rounded-[var(--ukip-radius-xl)] border border-violet-200 bg-violet-50/60 p-5 text-slate-700 dark:border-violet-400/25 dark:bg-violet-500/10 dark:text-[var(--ukip-text)]">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-violet-600 text-lg font-black text-white">
              i
            </span>
            <p className="max-w-5xl text-sm leading-7">{copy.info}</p>
          </div>
        </div>

        <aside className="border-t border-slate-200 bg-slate-50/70 p-6 dark:border-white/10 dark:bg-white/[0.03] lg:border-l lg:border-t-0 lg:p-8">
          <div className="sticky top-24">
            <p className="flex items-center gap-3 text-xs font-black uppercase tracking-[0.2em] text-violet-600 dark:text-violet-200">
              <svg className="h-7 w-7" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 2l1.55 5.33L19 9l-5.45 1.67L12 16l-1.55-5.33L5 9l5.45-1.67L12 2zm6.5 11l.82 2.68L22 16.5l-2.68.82L18.5 20l-.82-2.68L15 16.5l2.68-.82L18.5 13zM5.5 13l.82 2.68L9 16.5l-2.68.82L5.5 20l-.82-2.68L2 16.5l2.68-.82L5.5 13z" />
              </svg>
              {copy.nextActionEyebrow}
            </p>
            <h3 className="mt-8 text-3xl font-black leading-tight tracking-[-0.05em] text-slate-950 dark:text-[var(--ukip-text-strong)]">
              {actionTitle}
            </h3>
            <div className="mt-8 rounded-[var(--ukip-radius-xl)] border border-violet-200 bg-white p-5 shadow-sm dark:border-violet-400/25 dark:bg-[var(--ukip-panel)]">
              <p className="flex items-center gap-2 text-xs font-black uppercase tracking-[0.2em] text-violet-600 dark:text-violet-200">
                <IconFromPath path="M12 18h.01M9.75 15.75h4.5m-4.5-3.375a2.25 2.25 0 1 1 4.5 0c0 1.125-1.125 1.688-1.688 2.25-.337.337-.562.787-.562 1.125" className="h-5 w-5" />
                {copy.whyTitle}
              </p>
              <p className="mt-4 text-base leading-7 text-slate-700 dark:text-[var(--ukip-text)]">
                {reason}
              </p>
            </div>
            <p className="mt-8 text-base leading-8 text-slate-600 dark:text-[var(--ukip-muted)]">
              {copy.context}
            </p>
            <Link
              href={ctaHref}
              className="ukip-focus mt-10 inline-flex w-full items-center justify-between gap-4 rounded-[var(--ukip-radius-lg)] bg-gradient-to-r from-violet-600 to-blue-600 px-6 py-5 text-base font-bold text-white shadow-[var(--ukip-glow-violet)] transition hover:brightness-110"
            >
              <span className="inline-flex items-center gap-3">
                <IconFromPath path="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
                {ctaLabel}
              </span>
              <IconFromPath path="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" className="h-6 w-6" />
            </Link>
          </div>
        </aside>
      </div>

      {quickActions.length > 0 ? (
        <div className="grid gap-4 border-t border-slate-200 bg-white p-6 dark:border-white/10 dark:bg-[var(--ukip-panel)] lg:grid-cols-[minmax(220px,0.65fr)_1fr] lg:p-8">
          <div>
            <h3 className="text-lg font-black tracking-[-0.04em] text-slate-950 dark:text-[var(--ukip-text-strong)]">
              {copy.quickToolsTitle}
            </h3>
            <p className="mt-2 max-w-sm text-sm leading-6 text-slate-600 dark:text-[var(--ukip-muted)]">
              {copy.quickToolsDescription}
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {quickActions.map((action) => (
              <Link
                key={action.href}
                href={action.href}
                className={`group rounded-[var(--ukip-radius-lg)] bg-gradient-to-br ${actionToneClasses[action.tone]} p-5 text-white shadow-lg transition hover:-translate-y-0.5 hover:shadow-xl`}
              >
                <div className="flex items-center gap-4">
                  <IconFromPath path={action.iconPath} className="h-9 w-9 opacity-90" />
                  <div className="min-w-0 flex-1">
                    <p className="font-bold">{action.title}</p>
                    <p className="mt-1 text-sm text-white/80">{action.description}</p>
                  </div>
                  <IconFromPath path="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" className="h-5 w-5 transition group-hover:translate-x-1" />
                </div>
              </Link>
            ))}
          </div>
        </div>
      ) : null}
    </Panel>
  );
}
