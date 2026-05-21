"use client";

import Link from "next/link";

type WorkflowStatus = "ready" | "active" | "locked";

type Workflow = {
  id: string;
  title: string;
  body: string;
  href: string;
  cta: string;
  status: WorkflowStatus;
  metric: string;
  icon: string;
};

interface ScientificIntelligenceCommandCenterProps {
  entityCount: number;
  enrichmentPct: number;
  domainCount: number;
  graphReady: boolean;
  reportHref: string;
  demoSeeded: boolean;
  demoLoading: boolean;
  onLaunchDemo: () => void;
  t: (key: string, fallback: string) => string;
}

const statusStyles: Record<WorkflowStatus, string> = {
  ready: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-300/30 dark:bg-emerald-300/10 dark:text-emerald-200",
  active: "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-300/30 dark:bg-violet-300/10 dark:text-violet-100",
  locked: "border-slate-200 bg-slate-50 text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-muted)]",
};

function Icon({ path }: { path: string }) {
  return (
    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d={path} />
    </svg>
  );
}

function statusLabel(status: WorkflowStatus, t: (key: string, fallback: string) => string) {
  if (status === "ready") return t("page.home.command.status.ready", "Ready");
  if (status === "active") return t("page.home.command.status.active", "Active");
  return t("page.home.command.status.locked", "Needs data");
}

function NarrativeOrb({ readinessScore }: { readinessScore: number }) {
  const safeScore = Math.max(0, Math.min(100, readinessScore));
  return (
    <div className="pointer-events-none absolute right-[-3.25rem] top-[-3rem] hidden h-64 w-64 opacity-95 sm:block">
      <div className="absolute inset-0 rounded-full bg-white/12 blur-2xl" />
      <svg viewBox="0 0 220 220" className="relative h-full w-full" aria-hidden="true">
        <defs>
          <linearGradient id="ukip-orb-gradient" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.78" />
            <stop offset="48%" stopColor="#a5b4fc" stopOpacity="0.58" />
            <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.52" />
          </linearGradient>
        </defs>
        <circle cx="110" cy="110" r="78" fill="none" stroke="url(#ukip-orb-gradient)" strokeWidth="1.5" />
        <circle cx="110" cy="110" r="52" fill="rgba(255,255,255,0.10)" stroke="rgba(255,255,255,0.28)" strokeWidth="1.5" />
        <path d="M42 122c36-26 76-33 138-20" fill="none" stroke="rgba(255,255,255,0.46)" strokeWidth="2" strokeLinecap="round" />
        <path d="M62 150c32-20 67-27 116-16" fill="none" stroke="rgba(34,211,238,0.38)" strokeWidth="2" strokeLinecap="round" />
        <circle cx="72" cy="96" r="7" fill="#ffffff" />
        <circle cx="144" cy="76" r="5" fill="#c4b5fd" />
        <circle cx="158" cy="145" r="6" fill="#67e8f9" />
        <text x="110" y="116" textAnchor="middle" className="fill-white font-mono text-3xl font-semibold">
          {safeScore}
        </text>
      </svg>
    </div>
  );
}

export default function ScientificIntelligenceCommandCenter({
  entityCount,
  enrichmentPct,
  domainCount,
  graphReady,
  reportHref,
  demoSeeded,
  demoLoading,
  onLaunchDemo,
  t,
}: ScientificIntelligenceCommandCenterProps) {
  const hasEntities = entityCount > 0;
  const roundedEnrichment = Math.round(enrichmentPct);
  const readinessScore = hasEntities
    ? Math.round((Math.min(roundedEnrichment, 100) * 0.55) + (graphReady ? 25 : 0) + (domainCount > 0 ? 20 : 0))
    : 0;

  const workflows: Workflow[] = [
    {
      id: "corpus",
      title: t("page.home.command.workflow.corpus.title", "Build the scientific corpus"),
      body: t("page.home.command.workflow.corpus.body", "Import publications, authors, affiliations, and identifiers into one normalized workspace."),
      href: "/import/scientific",
      cta: t("page.home.command.workflow.corpus.cta", "Open scientific import"),
      status: hasEntities ? "ready" : "active",
      metric: hasEntities ? entityCount.toLocaleString() : t("page.home.command.metric.waiting", "Waiting"),
      icon: "M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5",
    },
    {
      id: "domain",
      title: t("page.home.command.workflow.domain.title", "Read the domain intelligence"),
      body: t("page.home.command.workflow.domain.body", "Review coverage, emerging concepts, impact signals, data readiness, and recommended actions."),
      href: "/analytics/dashboard",
      cta: t("page.home.command.workflow.domain.cta", "Open executive dashboard"),
      status: hasEntities ? "active" : "locked",
      metric: hasEntities ? `${roundedEnrichment}%` : "0%",
      icon: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z",
    },
    {
      id: "brief",
      title: t("page.home.command.workflow.brief.title", "Package the executive brief"),
      body: t("page.home.command.workflow.brief.body", "Turn validated signals into a stakeholder-ready report with evidence, gaps, and next moves."),
      href: reportHref,
      cta: t("page.home.command.workflow.brief.cta", "Open reports"),
      status: roundedEnrichment >= 60 ? "active" : "locked",
      metric: `${readinessScore}%`,
      icon: "M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5A3.375 3.375 0 0 0 10.125 2.25H6.75A2.25 2.25 0 0 0 4.5 4.5v15A2.25 2.25 0 0 0 6.75 21h10.5A2.25 2.25 0 0 0 19.5 18.75v-4.5ZM9 15.75h6M9 12h3",
    },
  ];

  return (
    <section>
      <div className="overflow-hidden rounded-[1.75rem] border border-violet-200/70 bg-white shadow-[0_24px_80px_rgb(88_28_135_/_0.13)] dark:border-white/10 dark:bg-[var(--ukip-panel)]">
        <div className="grid lg:grid-cols-[minmax(0,0.98fr)_minmax(0,1.22fr)]">
          <div className="relative flex min-h-[26rem] flex-col justify-between overflow-hidden bg-[radial-gradient(circle_at_12%_8%,rgba(255,255,255,0.22),transparent_28%),linear-gradient(135deg,#6d28d9_0%,#7c3aed_48%,#2f1b8f_100%)] p-6 text-white sm:p-8">
            <NarrativeOrb readinessScore={readinessScore} />
            <div className="relative z-10 max-w-xl">
              <span className="inline-flex rounded-full border border-white/25 bg-white/12 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.18em] text-violet-50 backdrop-blur">
                {t("page.home.command.eyebrow", "Scientific intelligence command center")}
              </span>
              <h2 className="mt-8 max-w-lg text-4xl font-semibold leading-[1.05] tracking-[-0.025em] text-white sm:text-5xl">
              {t("page.home.command.title", "From corpus to decision in one guided path")}
              </h2>
              <p className="mt-5 max-w-md text-base leading-7 text-violet-50/86">
                {t("page.home.command.body", "Use UKIP as an operating flow: assemble the corpus, read domain-level intelligence, then package a brief that leadership can act on.")}
              </p>
            </div>

            <div className="relative z-10 mt-10 space-y-4">
              {!demoSeeded && (
                <button
                  type="button"
                  onClick={onLaunchDemo}
                  disabled={demoLoading}
                  className="ukip-focus inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-white/25 bg-white px-5 text-sm font-bold text-violet-700 shadow-[0_18px_45px_rgb(15_23_42_/_0.18)] transition hover:bg-violet-50 disabled:opacity-60"
                >
                  <Icon path="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653z" />
                  {demoLoading ? t("page.home.command.demo.loading", "Starting demo...") : t("page.home.command.demo.cta", "Launch realistic demo")}
                </button>
              )}
              <div className="grid grid-cols-3 gap-2.5">
                <div className="rounded-2xl border border-white/18 bg-white/14 p-3.5 shadow-sm backdrop-blur">
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-violet-50/75">
                    {t("page.home.command.kpi.records", "Records")}
                  </p>
                  <p className="mt-2 font-mono text-2xl font-semibold tracking-[-0.03em] text-white">
                    {entityCount.toLocaleString()}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/18 bg-white/14 p-3.5 shadow-sm backdrop-blur">
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-violet-50/75">
                    {t("page.home.command.kpi.enrichment", "Enriched")}
                  </p>
                  <p className="mt-2 font-mono text-2xl font-semibold tracking-[-0.03em] text-white">{roundedEnrichment}%</p>
                </div>
                <div className="rounded-2xl border border-white/18 bg-white/14 p-3.5 shadow-sm backdrop-blur">
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-violet-50/75">
                    {t("page.home.command.kpi.ready", "Ready")}
                  </p>
                  <p className="mt-2 font-mono text-2xl font-semibold tracking-[-0.03em] text-white">{readinessScore}%</p>
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-4 bg-slate-50 p-4 dark:bg-white/[0.03] sm:p-5">
            {workflows.map((workflow, index) => (
              <Link
                key={workflow.id}
                href={workflow.href}
                className="group relative overflow-hidden rounded-[1.35rem] border border-slate-200 bg-white p-5 transition hover:-translate-y-0.5 hover:border-violet-300 hover:shadow-[0_18px_45px_rgb(88_28_135_/_0.12)] dark:border-white/10 dark:bg-white/5 dark:hover:border-violet-300/50"
              >
                <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
                  <div className="flex items-start gap-4 sm:flex-1">
                    <span className="font-mono text-4xl font-semibold leading-none tracking-[-0.06em] text-violet-200 transition group-hover:text-violet-300 dark:text-violet-300/40">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusStyles[workflow.status]}`}>
                          {statusLabel(workflow.status, t)}
                        </span>
                        <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-violet-50 text-violet-700 dark:bg-violet-300/10 dark:text-violet-200">
                          <Icon path={workflow.icon} />
                        </span>
                      </div>
                      <h3 className="mt-3 text-xl font-semibold tracking-[-0.02em] text-slate-950 dark:text-[var(--ukip-text-strong)]">
                        {workflow.title}
                      </h3>
                      <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 dark:text-[var(--ukip-muted)]">
                        {workflow.body}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between gap-4 sm:min-w-36 sm:flex-col sm:items-end">
                    <span className="font-mono text-2xl font-semibold tabular-nums tracking-[-0.04em] text-slate-950 dark:text-[var(--ukip-text-strong)]">
                      {workflow.metric}
                    </span>
                    <span className="inline-flex min-h-10 items-center gap-2 rounded-full border border-violet-200 px-4 text-sm font-bold text-violet-700 transition group-hover:bg-violet-600 group-hover:text-white dark:border-violet-300/30 dark:text-violet-200 dark:group-hover:bg-violet-500">
                      {workflow.cta}
                      <Icon path="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
