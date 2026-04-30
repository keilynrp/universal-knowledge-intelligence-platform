import Link from "next/link";
import { Panel } from "../ui";

export type AdaptiveNarrativeBlockProps = {
  progress: number;
  currentStep: number;
  totalSteps: number;
  role?: "research_office" | "library" | "innovation_team" | "general";
  coveragePercent?: number;
  enrichmentCoverage?: number;
  recommendedActionLabel?: string;
  recommendedActionHref?: string;
};

const BASE_COPY =
  "UKIP transforma registros de publicaciones dispersos en un portafolio estructurado, enriquecido y listo para analisis. Desde la primera importacion hasta la generacion de insights ejecutivos, el sistema guia un flujo continuo que reduce friccion operativa y mejora la calidad de la informacion.";

const ROLE_CONTEXT: Record<NonNullable<AdaptiveNarrativeBlockProps["role"]>, string> = {
  research_office: "En este contexto, la prioridad es convertir evidencia academica en una lectura institucional confiable para planeacion, evaluacion y toma de decisiones.",
  library: "En este contexto, la prioridad es mejorar control bibliografico, autoridad, normalizacion y recuperacion de informacion para servicios academicos.",
  innovation_team: "En este contexto, la prioridad es detectar capacidades, brechas y oportunidades que conecten investigacion con innovacion aplicada.",
  general: "En este contexto, la prioridad es pasar de datos dispersos a una base comun de conocimiento operable por distintos equipos.",
};

function clampPercent(value: number | undefined): number {
  if (typeof value !== "number" || Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function recommendationFor(enrichmentCoverage: number) {
  if (enrichmentCoverage < 20) {
    return {
      label: "Ejecuta enrichment antes de leer demasiado el dato.",
      reason: "La cobertura actual todavia es baja para una lectura ejecutiva confiable.",
      fallbackCta: "Ejecutar enrichment",
      fallbackHref: "/analytics/dashboard",
    };
  }

  if (enrichmentCoverage < 60) {
    return {
      label: "Revisa calidad y autoridad de los registros.",
      reason: "Ya existe suficiente base enriquecida para detectar brechas, inconsistencias y entidades de baja confianza.",
      fallbackCta: "Revisar autoridad",
      fallbackHref: "/authority",
    };
  }

  return {
    label: "Genera un brief ejecutivo para stakeholders.",
    reason: "El portafolio ya tiene suficiente profundidad para transformar los datos en una narrativa accionable.",
    fallbackCta: "Generar brief ejecutivo",
    fallbackHref: "/reports?preset=pilot-brief",
  };
}

export default function AdaptiveNarrativeBlock({
  progress,
  currentStep,
  totalSteps,
  role = "general",
  coveragePercent,
  enrichmentCoverage,
  recommendedActionLabel,
  recommendedActionHref,
}: AdaptiveNarrativeBlockProps) {
  const safeProgress = clampPercent(progress);
  const safeCoverage = clampPercent(coveragePercent);
  const safeEnrichment = clampPercent(enrichmentCoverage);
  const safeTotalSteps = Math.max(1, totalSteps);
  const safeCurrentStep = Math.max(1, Math.min(currentStep, safeTotalSteps));
  const recommendation = recommendationFor(safeEnrichment);
  const ctaLabel = recommendedActionLabel || recommendation.fallbackCta;
  const ctaHref = recommendedActionHref || recommendation.fallbackHref;

  return (
    <Panel variant="soft" className="overflow-hidden p-0">
      <div className="grid gap-0 xl:grid-cols-[1.35fr_0.65fr]">
        <div className="p-5 lg:p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="ukip-kicker">Ruta guiada UKIP</p>
              <h2 className="mt-2 text-2xl font-bold tracking-[-0.035em] text-[var(--ukip-text-strong)]">
                Inteligencia de Investigacion para decisiones confiables
              </h2>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--ukip-muted)]">
                {BASE_COPY}
              </p>
            </div>
            <div className="min-w-[11rem] rounded-[var(--ukip-radius-lg)] border border-[var(--ukip-border)] bg-[var(--ukip-panel)] p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--ukip-muted)]">
                  Progreso
                </span>
                <span className="font-mono text-lg font-bold text-[var(--ukip-text-strong)]">{safeProgress}%</span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--ukip-panel-strong)]">
                <div
                  className="h-full rounded-full bg-[var(--ukip-primary)] transition-[width]"
                  style={{ width: `${safeProgress}%` }}
                />
              </div>
              <p className="mt-3 text-xs text-[var(--ukip-muted)]">
                Paso {safeCurrentStep} de {safeTotalSteps}
              </p>
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <div className="rounded-[var(--ukip-radius-lg)] border border-[var(--ukip-border)] bg-[var(--ukip-panel)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ukip-muted)]">
                Flujo actual
              </p>
              <p className="mt-2 text-sm font-semibold text-[var(--ukip-text-strong)]">
                Dataset → Enrichment → Autoridad → Brief
              </p>
            </div>
            <div className="rounded-[var(--ukip-radius-lg)] border border-[var(--ukip-border)] bg-[var(--ukip-panel)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ukip-muted)]">
                Cobertura
              </p>
              <p className="mt-2 font-mono text-xl font-bold text-[var(--ukip-text-strong)]">{safeCoverage}%</p>
            </div>
            <div className="rounded-[var(--ukip-radius-lg)] border border-[var(--ukip-border)] bg-[var(--ukip-panel)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ukip-muted)]">
                Enrichment
              </p>
              <p className="mt-2 font-mono text-xl font-bold text-[var(--ukip-text-strong)]">{safeEnrichment}%</p>
            </div>
          </div>

          <p className="mt-5 text-sm leading-6 text-[var(--ukip-muted)]">
            Comienza cargando un dataset inicial con publicaciones, autores y afiliaciones. A partir de ahi, ejecuta procesos de enrichment que integran identificadores, citas y metadatos clave desde fuentes academicas confiables. Con los datos enriquecidos, puedes establecer reglas de armonizacion para normalizar entidades y automatizar futuras importaciones.
          </p>
        </div>

        <aside className="border-t border-[var(--ukip-border)] bg-[var(--ukip-panel)] p-5 lg:p-6 xl:border-l xl:border-t-0">
          <p className="ukip-kicker">Siguiente mejor accion</p>
          <h3 className="mt-2 text-xl font-bold tracking-[-0.03em] text-[var(--ukip-text-strong)]">
            {recommendation.label}
          </h3>
          <div className="mt-4 rounded-[var(--ukip-radius-lg)] border border-[var(--ukip-border)] bg-[var(--ukip-surface)] p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ukip-muted)]">
              Por que importa ahora
            </p>
            <p className="mt-2 text-sm leading-6 text-[var(--ukip-text)]">
              {recommendation.reason}
            </p>
          </div>
          <p className="mt-4 text-sm leading-6 text-[var(--ukip-muted)]">
            {ROLE_CONTEXT[role]}
          </p>
          <Link
            href={ctaHref}
            className="ukip-focus mt-5 inline-flex w-full items-center justify-center gap-2 rounded-[var(--ukip-radius-md)] border border-transparent bg-[var(--ukip-primary)] px-4 py-2.5 text-sm font-semibold text-white shadow-[var(--ukip-glow-violet)] transition hover:bg-[var(--ukip-primary-strong)]"
          >
            {ctaLabel}
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
            </svg>
          </Link>
        </aside>
      </div>
    </Panel>
  );
}
