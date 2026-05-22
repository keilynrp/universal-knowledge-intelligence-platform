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
      icon: "M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5",
    },
    {
      id: "domain",
      title: t("page.home.command.workflow.domain.title", "Read the domain intelligence"),
      body: t("page.home.command.workflow.domain.body", "Review coverage, emerging concepts, impact signals, data readiness, and recommended actions."),
      href: "/analytics/dashboard",
      cta: t("page.home.command.workflow.domain.cta", "Open executive dashboard"),
      status: hasEntities ? "active" : "locked",
      icon: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z",
    },
    {
      id: "brief",
      title: t("page.home.command.workflow.brief.title", "Package the executive brief"),
      body: t("page.home.command.workflow.brief.body", "Turn validated signals into a stakeholder-ready report with evidence, gaps, and next moves."),
      href: reportHref,
      cta: t("page.home.command.workflow.brief.cta", "Open reports"),
      status: roundedEnrichment >= 60 ? "active" : "locked",
      icon: "M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5A3.375 3.375 0 0 0 10.125 2.25H6.75A2.25 2.25 0 0 0 4.5 4.5v15A2.25 2.25 0 0 0 6.75 21h10.5A2.25 2.25 0 0 0 19.5 18.75v-4.5ZM9 15.75h6M9 12h3",
    },
  ];

  return (
    <section>
      <div className="overflow-hidden rounded-[1.75rem] border border-violet-200/70 bg-[linear-gradient(135deg,#ffffff_0%,#f8f5ff_48%,#eefcff_100%)] shadow-[0_24px_80px_rgb(88_28_135_/_0.12)] dark:border-white/10 dark:bg-[var(--ukip-panel)] dark:bg-none">
        <div className="relative p-5 sm:p-6">
          <div className="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-violet-300 to-transparent dark:via-violet-300/40" />
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
            <div className="max-w-3xl">
              <span className="inline-flex rounded-full border border-violet-200 bg-white/80 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.18em] text-violet-700 shadow-sm dark:border-violet-300/20 dark:bg-white/10 dark:text-violet-100">
                {t("page.home.command.eyebrow", "Scientific intelligence command center")}
              </span>
              <h2 className="mt-4 text-3xl font-semibold leading-tight tracking-[-0.025em] text-slate-950 dark:text-[var(--ukip-text-strong)] sm:text-4xl">
                {t("page.home.command.title", "From corpus to decision in one guided path")}
              </h2>
              <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600 dark:text-[var(--ukip-muted)]">
                {t("page.home.command.body", "Use UKIP as an operating flow: assemble the corpus, read domain-level intelligence, then package a brief that leadership can act on.")}
              </p>
            </div>

            <dl className="grid gap-0 overflow-hidden rounded-2xl border border-white bg-white/78 shadow-sm ring-1 ring-slate-200/70 backdrop-blur dark:border-white/10 dark:bg-white/[0.06] dark:ring-white/10 sm:grid-cols-3 lg:min-w-[28rem]">
              {[
                { label: t("page.home.command.kpi.records", "Records"), value: entityCount.toLocaleString() },
                { label: t("page.home.command.kpi.enrichment", "Enriched"), value: `${roundedEnrichment}%` },
                { label: t("page.home.command.kpi.ready", "Ready"), value: `${readinessScore}%` },
              ].map((metric, metricIndex) => (
                <div key={metric.label} className={`p-4 ${metricIndex > 0 ? "border-t border-slate-200/80 dark:border-white/10 sm:border-l sm:border-t-0" : ""}`}>
                  <dt className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-[var(--ukip-muted)]">{metric.label}</dt>
                  <dd className="mt-2 font-mono text-2xl font-semibold tracking-[-0.04em] text-slate-950 dark:text-[var(--ukip-text-strong)]">{metric.value}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="mt-6 grid gap-3 lg:grid-cols-3">
            {workflows.map((workflow, index) => (
              <Link
                key={workflow.id}
                href={workflow.href}
                className="group relative min-h-[18rem] overflow-hidden rounded-[1.35rem] border border-white bg-white/82 p-5 shadow-sm ring-1 ring-slate-200/70 transition hover:-translate-y-0.5 hover:border-violet-300 hover:shadow-[0_18px_45px_rgb(88_28_135_/_0.12)] dark:border-white/10 dark:bg-white/[0.06] dark:ring-white/10 dark:hover:border-violet-300/50"
              >
                {index < workflows.length - 1 ? (
                  <span className="absolute right-[-1.5rem] top-10 hidden h-px w-6 bg-violet-200 lg:block dark:bg-violet-300/20" />
                ) : null}
                <div className="flex h-full flex-col">
                  <div className="flex items-start justify-between gap-3">
                    <span className="font-mono text-5xl font-semibold leading-none tracking-[-0.08em] text-violet-200 transition group-hover:text-violet-300 dark:text-violet-300/40">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusStyles[workflow.status]}`}>
                      {statusLabel(workflow.status, t)}
                    </span>
                  </div>

                  <div className="mt-6 flex h-11 w-11 items-center justify-center rounded-2xl bg-violet-600 text-white shadow-lg shadow-violet-500/20 dark:bg-violet-500">
                    <Icon path={workflow.icon} />
                  </div>

                  <h3 className="mt-5 text-xl font-semibold tracking-[-0.02em] text-slate-950 dark:text-[var(--ukip-text-strong)]">
                    {workflow.title}
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-[var(--ukip-muted)]">
                    {workflow.body}
                  </p>

                  <div className="mt-auto flex items-center justify-between gap-4 pt-6">
                    <span className="text-sm font-bold text-violet-700 transition group-hover:text-violet-800 dark:text-violet-200">
                      {workflow.cta}
                    </span>
                    <span className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-violet-200 text-violet-700 transition group-hover:bg-violet-600 group-hover:text-white dark:border-violet-300/30 dark:text-violet-200 dark:group-hover:bg-violet-500">
                      <Icon path="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>

          {!demoSeeded && (
            <button
              type="button"
              onClick={onLaunchDemo}
              disabled={demoLoading}
              className="ukip-focus mt-5 inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-violet-600 px-5 text-sm font-bold text-white shadow-[0_18px_45px_rgb(88_28_135_/_0.18)] transition hover:bg-violet-700 disabled:opacity-60"
            >
              <Icon path="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653z" />
              {demoLoading ? t("page.home.command.demo.loading", "Starting demo...") : t("page.home.command.demo.cta", "Launch realistic demo")}
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
