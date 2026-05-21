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
  ready: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-300",
  active: "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-400/20 dark:bg-violet-500/10 dark:text-violet-300",
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
      <div className="grid gap-5 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.35fr)]">
        <div className="flex flex-col justify-between gap-5 rounded-xl border border-slate-200 bg-slate-50 p-5 dark:border-white/10 dark:bg-white/5">
          <div>
            <p className="ukip-kicker">{t("page.home.command.eyebrow", "Scientific intelligence command center")}</p>
            <h2 className="mt-3 text-2xl font-semibold tracking-normal text-slate-950 dark:text-[var(--ukip-text-strong)]">
              {t("page.home.command.title", "From corpus to decision in one guided path")}
            </h2>
            <p className="mt-3 max-w-xl text-sm leading-6 text-slate-600 dark:text-[var(--ukip-muted)]">
              {t("page.home.command.body", "Use UKIP as an operating flow: assemble the corpus, read domain-level intelligence, then package a brief that leadership can act on.")}
            </p>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-white/10 dark:bg-[var(--ukip-panel)]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-[var(--ukip-muted)]">
                {t("page.home.command.kpi.records", "Records")}
              </p>
              <p className="mt-2 text-xl font-semibold text-slate-950 dark:text-[var(--ukip-text-strong)]">
                {entityCount.toLocaleString()}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-white/10 dark:bg-[var(--ukip-panel)]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-[var(--ukip-muted)]">
                {t("page.home.command.kpi.enrichment", "Enriched")}
              </p>
              <p className="mt-2 text-xl font-semibold text-violet-700 dark:text-violet-300">{roundedEnrichment}%</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-white/10 dark:bg-[var(--ukip-panel)]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-[var(--ukip-muted)]">
                {t("page.home.command.kpi.ready", "Ready")}
              </p>
              <p className="mt-2 text-xl font-semibold text-emerald-700 dark:text-emerald-300">{readinessScore}%</p>
            </div>
          </div>

          {!demoSeeded && (
            <button
              type="button"
              onClick={onLaunchDemo}
              disabled={demoLoading}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-violet-200 bg-white px-4 text-sm font-semibold text-violet-700 transition hover:border-violet-300 hover:bg-violet-50 disabled:opacity-50 dark:border-violet-400/20 dark:bg-white/5 dark:text-violet-200 dark:hover:bg-violet-500/10"
            >
              <Icon path="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653z" />
              {demoLoading ? t("page.home.command.demo.loading", "Starting demo...") : t("page.home.command.demo.cta", "Launch realistic demo")}
            </button>
          )}
        </div>

        <div className="grid gap-3">
          {workflows.map((workflow, index) => (
            <Link
              key={workflow.id}
              href={workflow.href}
              className="group grid gap-4 rounded-xl border border-slate-200 bg-white p-4 transition hover:border-violet-300 hover:shadow-sm dark:border-white/10 dark:bg-white/5 dark:hover:border-violet-400/40 sm:grid-cols-[auto_minmax(0,1fr)_auto]"
            >
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-slate-700 group-hover:bg-violet-50 group-hover:text-violet-700 dark:bg-white/10 dark:text-[var(--ukip-text)] dark:group-hover:bg-violet-500/10 dark:group-hover:text-violet-200">
                <Icon path={workflow.icon} />
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold text-slate-400">{String(index + 1).padStart(2, "0")}</span>
                  <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${statusStyles[workflow.status]}`}>
                    {statusLabel(workflow.status, t)}
                  </span>
                </div>
                <h3 className="mt-2 text-base font-semibold text-slate-950 dark:text-[var(--ukip-text-strong)]">
                  {workflow.title}
                </h3>
                <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-[var(--ukip-muted)]">
                  {workflow.body}
                </p>
              </div>
              <div className="flex items-center justify-between gap-4 sm:flex-col sm:items-end">
                <span className="text-xl font-semibold tabular-nums text-slate-950 dark:text-[var(--ukip-text-strong)]">
                  {workflow.metric}
                </span>
                <span className="inline-flex items-center gap-1 text-sm font-semibold text-violet-700 group-hover:text-violet-800 dark:text-violet-300">
                  {workflow.cta}
                  <Icon path="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
