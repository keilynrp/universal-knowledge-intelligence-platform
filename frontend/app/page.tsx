"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useEnrichment } from "./contexts/EnrichmentContext";
import Link from "next/link";
import EntityTable from "./components/EntityTable";
import ActivityFeed from "./components/ActivityFeed";
import GuidedTour, { resetTour } from "./components/GuidedTour";
import WelcomeModal from "./components/WelcomeModal";
import ScientificIntelligenceCommandCenter from "./components/ScientificIntelligenceCommandCenter";
import { AdaptiveNarrativeBlock, DashboardInsightMetrics } from "./components/ukip";
import { KpiSummaryCard } from "./components/ui";
import DerivedStatusPanel from "./components/DerivedStatusPanel";
import { apiFetch } from "../lib/api";
import { useAuth } from "./contexts/AuthContext";
import { useLanguage } from "./contexts/LanguageContext";
import { useDomain, isAllScope } from "./contexts/DomainContext";
import { Analytics } from "../lib/analytics";
import {
  getStoredPilotPersona,
  pilotPersonaToStakeholder,
  type PilotPersonaId,
} from "./lib/pilotPersona";

interface DashboardStats {
  total_entities: number;
  unique_secondary_labels: number;
  unique_entity_types: number;
  graph_nodes?: number;
  graph_relationships?: number;
  graph_ready?: boolean;
  identifier_coverage?: {
    with_canonical_id: number;
    total: number;
  };
  quality?: {
    average?: number | null;
    distribution?: Record<string, number>;
  };
  domain_distribution?: { domain?: string | null; name?: string | null; count: number }[];
}

interface DemoStatus {
  demo_seeded: boolean;
  demo_entity_count: number;
  catalog_portal?: {
    title: string;
    slug: string;
    url: string;
  } | null;
}

type GuidedStage = {
  id: "import" | "enrich" | "review" | "brief";
  href: string;
  status: "done" | "current" | "upcoming";
};

type GuidedReadiness = "starting" | "building" | "review" | "briefing";

function MetricIcon({ path, className = "h-4 w-4" }: { path: string; className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d={path} />
    </svg>
  );
}

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

export default function Home() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [portfolioStats, setPortfolioStats] = useState<DashboardStats | null>(null);
  const { enrichPct } = useEnrichment();
  const [domainCount, setDomainCount] = useState<number>(0);
  const [demoStatus, setDemoStatus] = useState<DemoStatus | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [pilotPersona, setPilotPersona] = useState<PilotPersonaId>("research");
  const { token } = useAuth();
  const { t } = useLanguage();
  const { activeDomainId } = useDomain();
  const tr = useCallback((key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  }, [t]);
  const hasEntities = (stats?.total_entities ?? 0) > 0;
  const graphReady = Boolean(stats?.graph_ready || (stats?.graph_relationships ?? 0) > 0);
  const stakeholderQuery = useMemo(
    () => `stakeholder=${encodeURIComponent(pilotPersonaToStakeholder(pilotPersona))}`,
    [pilotPersona],
  );
  const personaLabel = useMemo(() => t(`welcome.persona.${pilotPersona}.label`), [pilotPersona, t]);

  const guidedStages = useMemo<GuidedStage[]>(() => {
    const reviewReady = enrichPct >= 30;
    const briefReady = enrichPct >= 60;

    return [
      {
        id: "import",
        href: "/import-export",
        status: hasEntities ? "done" : "current",
      },
      {
        id: "enrich",
        href: "/analytics/dashboard",
        status: !hasEntities ? "upcoming" : briefReady ? "done" : "current",
      },
      {
        id: "review",
        href: "/authority",
        status: !hasEntities ? "upcoming" : reviewReady ? (briefReady ? "done" : "current") : "upcoming",
      },
      {
        id: "brief",
        href: `/reports?preset=pilot-brief&${stakeholderQuery}`,
        status: !hasEntities ? "upcoming" : briefReady ? "current" : "upcoming",
      },
    ];
  }, [enrichPct, hasEntities, stakeholderQuery]);

  const nextGuidedAction = useMemo(() => {
    if (!hasEntities) {
      return {
        title: t("page.home.guided.next.import.title"),
        description: t("page.home.guided.next.import.description"),
        href: "/import-export",
        cta: t("page.home.guided.next.import.cta"),
        hint: t("page.home.guided.next.import.hint"),
      };
    }

    if (enrichPct < 30) {
      return {
        title: t("page.home.guided.next.enrich.title"),
        description: t("page.home.guided.next.enrich.description"),
        href: "/analytics/dashboard",
        cta: t("page.home.guided.next.enrich.cta"),
        hint: t("page.home.guided.next.enrich.hint", { percent: Math.round(enrichPct) }),
      };
    }

    if (enrichPct < 60) {
      return {
        title: t("page.home.guided.next.review.title"),
        description: t("page.home.guided.next.review.description"),
        href: "/authority",
        cta: t("page.home.guided.next.review.cta"),
        hint: t("page.home.guided.next.review.hint", { percent: Math.round(enrichPct) }),
      };
    }

    return {
        title: t("page.home.guided.next.brief.title"),
        description: t("page.home.guided.next.brief.description"),
        href: `/reports?preset=pilot-brief&${stakeholderQuery}`,
        cta: t("page.home.guided.next.brief.cta"),
        hint: t("page.home.guided.next.brief.hint"),
      };
  }, [enrichPct, hasEntities, stakeholderQuery, t]);

  const guidedProgress = useMemo(() => {
    const completed = guidedStages.filter((stage) => stage.status === "done").length;
    const currentStage = guidedStages.find((stage) => stage.status === "current") ?? guidedStages[guidedStages.length - 1];

    let percent = 5;
    let readiness: GuidedReadiness = "starting";

    if (hasEntities) {
      if (enrichPct < 30) {
        percent = 25 + Math.round((Math.max(enrichPct, 0) / 30) * 25);
        readiness = "building";
      } else if (enrichPct < 60) {
        percent = 50 + Math.round(((enrichPct - 30) / 30) * 25);
        readiness = "review";
      } else {
        percent = 75 + Math.round(Math.min((enrichPct - 60) / 40, 1) * 15);
        readiness = "briefing";
      }
    }

    return {
      percent: Math.max(0, Math.min(percent, 90)),
      completed,
      currentStage,
      readiness,
    };
  }, [enrichPct, guidedStages, hasEntities]);

  const fetchDemoStatus = useCallback(async () => {
    try {
      const res = await apiFetch("/demo/status");
      if (res.ok) setDemoStatus(await res.json());
    } catch { /* non-critical */ }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const scopedParams = new URLSearchParams({ domain_id: activeDomainId || "all" });
      const globalParams = new URLSearchParams({ domain_id: "all" });
      const [statsRes, portfolioRes] = await Promise.all([
        apiFetch(`/stats?${scopedParams.toString()}`),
        apiFetch(`/stats?${globalParams.toString()}`),
      ]);
      const s = await statsRes.json();
      const portfolio = await portfolioRes.json();
      setStats(s);
      setPortfolioStats(portfolio);
      setDomainCount(
        Array.isArray(portfolio.domain_distribution)
          ? portfolio.domain_distribution.filter((item: { count: number }) => item.count > 0).length
          : 0,
      );
    } catch {
      // stats are non-critical
    }
  }, [activeDomainId]);

  useEffect(() => {
    if (token) {
      fetchStats();
      fetchDemoStatus();
    }
  }, [token, fetchStats, fetchDemoStatus]);

  useEffect(() => {
    const storedPersona = getStoredPilotPersona();
    if (storedPersona) {
      setPilotPersona(storedPersona);
    }
  }, []);

  const handleLaunchDemo = async () => {
    setDemoLoading(true);
    try {
      const res = await apiFetch("/demo/seed", { method: "POST" });
      if (res.ok) {
        await fetchDemoStatus();
        await fetchStats();
        resetTour(); // reset so tour shows for new demo session
        Analytics.demoSeeded();
      }
    } catch { /* non-critical */ } finally {
      setDemoLoading(false);
    }
  };

  const handleClearDemo = async () => {
    setDemoLoading(true);
    try {
      const res = await apiFetch("/demo/reset", { method: "DELETE" });
      if (res.ok) {
        await fetchDemoStatus();
        await fetchStats();
      }
    } catch { /* non-critical */ } finally {
      setDemoLoading(false);
    }
  };

  const pipelineStages = [
    { label: tr("page.home.pipeline.ingest", "Ingesta"), group: "Knowledge", href: "/import-export", status: hasEntities ? "done" : "current", icon: "M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" },
    { label: tr("page.home.pipeline.authority", "Autoridad"), group: "Knowledge", href: "/authority", status: enrichPct >= 30 ? "done" : hasEntities ? "current" : "upcoming", icon: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" },
    { label: tr("page.home.pipeline.enrichment", "Enriquecimiento"), group: "Knowledge", href: "/analytics/dashboard", status: enrichPct >= 60 ? "done" : hasEntities ? "current" : "upcoming", icon: "M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.456-2.456L14.25 6l1.035-.259a3.375 3.375 0 002.456-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" },
    { label: tr("page.home.pipeline.graph", "Grafo"), group: "Intelligence", href: "/analytics/graph", status: graphReady ? "done" : enrichPct >= 60 ? "current" : "upcoming", icon: "M7.5 7.5h.008v.008H7.5V7.5zm9 0h.008v.008H16.5V7.5zm-9 9h.008v.008H7.5V16.5zm9 0h.008v.008H16.5V16.5zM8 8l8 8m0-8l-8 8" },
    { label: tr("page.home.pipeline.analysis", "Análisis"), group: "Intelligence", href: "/analytics/dashboard", status: graphReady ? "done" : enrichPct >= 30 ? "current" : "upcoming", icon: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" },
    { label: tr("page.home.pipeline.answers", "Respuestas"), group: "Intelligence", href: "/rag", status: enrichPct >= 60 ? "current" : "upcoming", icon: "M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm3.75 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm3.75 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337L3 21l1.087-5.445A7.94 7.94 0 013 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" },
    { label: tr("page.home.pipeline.delivery", "Entrega"), group: "Delivery", href: `/reports?preset=pilot-brief&${stakeholderQuery}`, status: enrichPct >= 60 ? "current" : "upcoming", icon: "M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5A3.375 3.375 0 0010.125 2.25H8.25m.75 12l3 3m0 0l3-3m-3 3v-6m-8.25 6.75h13.5A2.25 2.25 0 0021 15.75V9.75a2.25 2.25 0 00-.659-1.591l-5.25-5.25A2.25 2.25 0 0013.5 2.25H5.25A2.25 2.25 0 003 4.5v15a2.25 2.25 0 002.25 2.25z" },
  ];
  const metricCards = [
    {
      label: tr("page.home.metric_total_entities", "Entidades"),
      value: stats?.total_entities?.toLocaleString() ?? "—",
      tone: "violet" as const,
      icon: "M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4",
    },
    {
      label: tr("page.home.metric_enrichment_coverage", "Enriquecimiento"),
      value: hasEntities ? `${Math.round(enrichPct)}%` : "—",
      tone: "sky" as const,
      icon: "M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z",
    },
    {
      label: tr("page.home.metric_entity_types", "Tipos de entidad"),
      value: stats?.unique_entity_types?.toLocaleString() ?? "—",
      tone: "violet" as const,
      icon: "M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z",
    },
    {
      label: tr("page.home.metric_active_domains", "Dominios activos"),
      value: domainCount > 0 ? domainCount.toLocaleString() : "—",
      tone: "sky" as const,
      icon: "M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418",
    },
  ];
  const narrativeRole =
    pilotPersona === "research"
      ? "research_office"
      : pilotPersona === "library"
        ? "library"
        : "general";
  const narrativeCurrentStep = Math.max(
    1,
    guidedStages.findIndex((stage) => stage.id === guidedProgress.currentStage.id) + 1,
  );
  const pipelineLabelKeyByStage: Record<GuidedStage["id"], string> = {
    import: "page.home.pipeline.ingest",
    enrich: "page.home.pipeline.enrichment",
    review: "page.home.pipeline.authority",
    brief: "page.home.pipeline.delivery",
  };
  const narrativeStages = guidedStages.map((stage) => ({
    ...stage,
    label: t(pipelineLabelKeyByStage[stage.id]),
  }));
  const narrativeCopy = {
    brandLabel: t("page.home.narrative.brand"),
    eyebrow: t("page.home.guided.eyebrow"),
    title: t("page.home.narrative.title"),
    body: t("page.home.narrative.body"),
    progressLabel: t("page.home.narrative.progress"),
    stepLabel: t("page.home.narrative.step", { current: narrativeCurrentStep, total: guidedStages.length }),
    flowLabel: t("page.home.narrative.current_flow"),
    whyTitle: t("page.home.guided.why_now"),
    context: nextGuidedAction.description,
    info: t(`page.home.guided.readiness.${guidedProgress.readiness}`),
    quickToolsTitle: t("page.home.narrative.quick_tools_title"),
    quickToolsDescription: t("page.home.narrative.quick_tools_description"),
    nextActionEyebrow: t("page.home.narrative.next_best_action"),
  };
  const narrativeMetrics = [
    {
      id: "coverage",
      label: t("page.home.narrative.coverage"),
      value: hasEntities ? "100%" : "0%",
      description: t("page.home.narrative.coverage_description"),
      percent: hasEntities ? 100 : 0,
      tone: "emerald" as const,
      icon: <MetricIcon className="h-7 w-7" path="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm6 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-5.25 0a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" />,
    },
    {
      id: "enrichment",
      label: t("page.home.narrative.enrichment"),
      value: hasEntities ? `${Math.round(enrichPct)}%` : "0%",
      description: t("page.home.narrative.enrichment_description"),
      percent: hasEntities ? enrichPct : 0,
      tone: "sky" as const,
      icon: <MetricIcon className="h-7 w-7" path="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.456-2.456L14.25 6l1.035-.259a3.375 3.375 0 0 0 2.456-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z" />,
    },
  ];
  const narrativeQuickActions = [
    {
      title: t("page.home.cta_import_title"),
      description: t("page.home.cta_import_desc"),
      href: "/import-export",
      tone: "blue" as const,
      iconPath: "M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5",
    },
    {
      title: t("page.home.cta_authority_title"),
      description: t("page.home.cta_authority_desc"),
      href: "/authority",
      tone: "violet" as const,
      iconPath: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
    },
    {
      title: t("page.home.cta_olap_title"),
      description: t("page.home.cta_olap_desc"),
      href: "/analytics/olap",
      tone: "emerald" as const,
      iconPath: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z",
    },
  ];
  const activeDomains = (portfolioStats?.domain_distribution ?? stats?.domain_distribution ?? [])
    .filter((domain) => domain.count > 0)
    .sort((a, b) => b.count - a.count);
  const topDomains = activeDomains.slice(0, 6);
  const maxDomainCount = topDomains[0]?.count ?? 1;
  const domainCoverage = topDomains.map((domain) => ({
    label: domain.domain ?? domain.name ?? t("page.home.domain_unknown"),
    percent: clampPercent((domain.count / maxDomainCount) * 100),
  }));
  const ingestionScore = hasEntities ? 100 : 0;
  const domainDiversityScore = clampPercent((Math.min(domainCount, 6) / 6) * 100);
  const entityTypeScore = clampPercent((Math.min(portfolioStats?.unique_entity_types ?? stats?.unique_entity_types ?? 0, 8) / 8) * 100);
  const identifierCoverageScore = clampPercent(
    stats?.identifier_coverage?.total
      ? ((stats.identifier_coverage.with_canonical_id ?? 0) / stats.identifier_coverage.total) * 100
      : 0,
  );
  const metadataScore = hasEntities ? clampPercent((domainDiversityScore + entityTypeScore + identifierCoverageScore) / 3) : 0;
  const enrichmentScore = hasEntities ? clampPercent(enrichPct) : 0;
  const graphScore = graphReady ? 100 : (stats?.graph_nodes ?? 0) > 0 ? 50 : 0;
  const analysisScore = graphReady ? clampPercent((enrichmentScore + graphScore) / 2) : clampPercent(enrichmentScore * 0.45);
  const reportReadinessScore = clampPercent(Math.min(enrichmentScore, analysisScore));
  const knowledgePercent = clampPercent((ingestionScore + metadataScore + enrichmentScore) / 3);
  const intelligencePercent = clampPercent((enrichmentScore + graphScore + analysisScore) / 3);
  const deliveryPercent = clampPercent((reportReadinessScore + (guidedProgress.readiness === "briefing" ? 100 : 0)) / 2);
  const weakestPillarPenalty = Math.min(knowledgePercent, intelligencePercent, deliveryPercent) * 0.15;
  const pipelineHealthScore = clampPercent(
    (knowledgePercent * 0.34) +
    (intelligencePercent * 0.36) +
    (deliveryPercent * 0.15) +
    weakestPillarPenalty,
  );
  const insightPillars = [
    {
      id: "knowledge",
      label: t("page.home.insights.knowledge"),
      subtitle: t("page.home.insights.knowledge_subtitle"),
      percent: knowledgePercent,
      tags: [t("page.home.pipeline.ingest"), t("page.home.pipeline.authority"), t("page.home.pipeline.enrichment")],
      tone: "violet" as const,
      icon: <MetricIcon className="h-5 w-5" path="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625Z" />,
    },
    {
      id: "intelligence",
      label: t("page.home.insights.intelligence"),
      subtitle: t("page.home.insights.intelligence_subtitle"),
      percent: intelligencePercent,
      tags: [t("page.home.pipeline.graph"), t("page.home.pipeline.analysis"), t("page.home.pipeline.answers")],
      tone: "sky" as const,
      icon: <MetricIcon className="h-5 w-5" path="M7.5 7.5h.008v.008H7.5V7.5zm9 0h.008v.008H16.5V7.5zm-9 9h.008v.008H7.5V16.5zm9 0h.008v.008H16.5V16.5zM8 8l8 8m0-8l-8 8" />,
    },
    {
      id: "delivery",
      label: t("page.home.insights.delivery"),
      subtitle: t("page.home.insights.delivery_subtitle"),
      percent: deliveryPercent,
      tags: [t("page.home.pipeline.delivery")],
      tone: "emerald" as const,
      icon: <MetricIcon className="h-5 w-5" path="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />,
    },
  ];
  const healthMetrics = [
    { label: t("page.home.insights.knowledge"), value: knowledgePercent },
    { label: t("page.home.insights.intelligence"), value: intelligencePercent },
    { label: t("page.home.insights.delivery"), value: deliveryPercent },
  ];

  return (
    <div className="space-y-6">
      <WelcomeModal />

      <section className="space-y-6">
        <div className="flex flex-col gap-4 border-b border-slate-200 pb-6 dark:border-white/10 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="ukip-kicker">{tr("page.home.overview", "Overview")}</span>
              <span className="rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700 dark:border-violet-400/20 dark:bg-violet-500/10 dark:text-violet-200">
                {personaLabel}
              </span>
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-[-0.025em] text-slate-950 dark:text-[var(--ukip-text-strong)] sm:text-4xl">
              {tr("page.home.research_intelligence", "Research Intelligence")}
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {demoStatus?.demo_seeded ? (
              <div className="inline-flex items-center gap-1 rounded-xl border border-amber-200 bg-amber-50 py-1 pl-3 pr-1 dark:border-amber-700/40 dark:bg-amber-900/20">
                <span className="h-2 w-2 rounded-full bg-amber-500" />
                <span className="px-1 text-sm font-semibold text-amber-800 dark:text-amber-300">
                  {t('page.home.demo_active_title')}
                </span>
                {demoStatus.catalog_portal?.url ? (
                  <Link
                    href={demoStatus.catalog_portal.url}
                    className="rounded-lg px-2 py-1 text-xs font-semibold text-violet-700 transition-colors hover:bg-violet-100 dark:text-violet-200 dark:hover:bg-violet-800/30"
                  >
                    Portal
                  </Link>
                ) : null}
                <button
                  onClick={handleClearDemo}
                  disabled={demoLoading}
                  className="rounded-lg px-2 py-1 text-xs font-medium text-amber-700 transition-colors hover:bg-amber-100 disabled:opacity-50 dark:text-amber-400 dark:hover:bg-amber-800/30"
                >
                  {demoLoading ? t('page.home.demo_clearing') : t('page.home.demo_clear_button')}
                </button>
              </div>
            ) : demoStatus !== null ? (
              <button
                onClick={handleLaunchDemo}
                disabled={demoLoading}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-950 shadow-sm transition hover:border-violet-300 hover:text-violet-700 disabled:opacity-50 dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-text-strong)]"
              >
                {demoLoading ? (
                  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z" />
                  </svg>
                )}
                Demo
              </button>
            ) : null}
            <Link
              href="/import-export"
              className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-violet-500/20 transition hover:bg-violet-700"
            >
              {tr("page.home.import_button", "Import")}
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
              </svg>
            </Link>
          </div>
        </div>

        <ScientificIntelligenceCommandCenter
          entityCount={stats?.total_entities ?? 0}
          enrichmentPct={hasEntities ? enrichPct : 0}
          domainCount={domainCount}
          graphReady={graphReady}
          reportHref={`/reports?preset=pilot-brief&${stakeholderQuery}`}
          demoSeeded={demoStatus?.demo_seeded === true}
          demoLoading={demoLoading}
          onLaunchDemo={handleLaunchDemo}
          t={tr}
        />

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {metricCards.map((metric) => (
            <KpiSummaryCard
              key={metric.label}
              label={metric.label}
              value={metric.value}
              icon={<MetricIcon path={metric.icon} />}
              tone={metric.tone}
            />
          ))}
        </div>

        {(portfolioStats?.domain_distribution ?? stats?.domain_distribution)?.filter((d) => d.count > 0).length ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
            <h2 className="text-base font-semibold text-slate-950 dark:text-[var(--ukip-text-strong)]">
              {tr("page.home.domain_distribution", "Distribución por dominio")}
            </h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-[var(--ukip-muted)]">
              {tr("page.home.domain_distribution_sub", "Entidades por dominio activo")}
            </p>
            <div className="mt-5 space-y-3">
              {(() => {
                const active = (portfolioStats?.domain_distribution ?? stats?.domain_distribution ?? [])
                  .filter((d) => d.count > 0)
                  .sort((a, b) => b.count - a.count);
                const max = active[0]?.count ?? 1;
                return active.map((d) => (
                  <div key={d.domain ?? d.name ?? "unknown"} className="flex items-center gap-3">
                    <span className="w-28 shrink-0 truncate text-sm font-medium text-slate-700 dark:text-[var(--ukip-muted)]">
                      {d.domain ?? d.name ?? tr("page.home.domain_unknown", "Sin dominio")}
                    </span>
                    <div className="flex-1 h-2 rounded-full bg-slate-100 dark:bg-white/10">
                      <div className="h-2 rounded-full bg-violet-500 transition-all" style={{ width: `${Math.round((d.count / max) * 100)}%` }} />
                    </div>
                    <span className="w-16 text-right text-sm font-semibold tabular-nums text-slate-950 dark:text-[var(--ukip-text-strong)]">
                      {d.count.toLocaleString()}
                    </span>
                  </div>
                ));
              })()}
            </div>
          </div>
        ) : null}

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
          <div className="flex items-center justify-between gap-3">
            <p className="ukip-kicker">{tr("page.home.pipeline_title", "Pipeline UKIP")}</p>
            <span className="text-xs text-slate-500 dark:text-[var(--ukip-muted)]">{tr("page.home.pipeline_subtitle", "raw → answer")}</span>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
            {pipelineStages.map((stage, index) => (
              <Link key={stage.label} href={stage.href} className="rounded-xl border border-slate-200 bg-white p-3 transition hover:border-violet-400/60 hover:bg-violet-50 dark:border-white/10 dark:bg-white/5 dark:hover:border-violet-400/40 dark:hover:bg-violet-500/10">
                <div className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-2 text-[11px] font-semibold text-slate-500 dark:text-[var(--ukip-muted)]">
                    <span className={`h-2 w-2 rounded-full ${stage.status === "done" ? "bg-emerald-500" : stage.status === "current" ? "bg-violet-500" : "bg-slate-400"}`} />
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <svg className="h-4 w-4 text-slate-500 dark:text-[var(--ukip-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={stage.icon} />
                  </svg>
                </div>
                <p className="mt-3 text-sm font-semibold text-slate-950 dark:text-[var(--ukip-text-strong)]">{stage.label}</p>
                <p className="mt-1 text-[11px] uppercase tracking-[0.14em] text-slate-500 dark:text-[var(--ukip-muted)]">{stage.group}</p>
              </Link>
            ))}
          </div>
        </div>

      </section>


      <AdaptiveNarrativeBlock
        progress={guidedProgress.percent}
        currentStep={narrativeCurrentStep}
        totalSteps={guidedStages.length}
        role={narrativeRole}
        coveragePercent={stats?.total_entities ? 100 : 0}
        enrichmentCoverage={enrichPct}
        recommendedActionLabel={nextGuidedAction.cta}
        recommendedActionHref={nextGuidedAction.href}
        recommendedActionTitle={nextGuidedAction.title}
        recommendedActionReason={nextGuidedAction.hint}
        copy={narrativeCopy}
        stages={narrativeStages}
        metrics={narrativeMetrics}
        flowItems={[
          t("page.home.narrative.flow.dataset"),
          t("page.home.pipeline.enrichment"),
          t("page.home.pipeline.authority"),
          t("page.home.narrative.flow.brief"),
        ]}
        quickActions={narrativeQuickActions}
      />

      <DashboardInsightMetrics
        pillarTitle={t("page.home.insights.pillar_title")}
        pillarSubtitle={t("page.home.insights.pillar_subtitle")}
        domainTitle={t("page.home.insights.domain_title")}
        domainSubtitle={t("page.home.insights.domain_subtitle")}
        domainAreaLabel={t("page.home.insights.domain_area_label")}
        healthTitle={t("page.home.insights.health_title")}
        healthSubtitle={t("page.home.insights.health_subtitle")}
        liveLabel={t("page.home.insights.live")}
        scoreSuffix={t("page.home.insights.score_suffix")}
        pillars={insightPillars}
        domains={domainCoverage}
        healthScore={pipelineHealthScore}
        healthMetrics={healthMetrics}
      />

      {/* Entity browser + Activity feed */}
      <div className="grid grid-cols-1 gap-6">
        <div>
          {stats?.total_entities === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-gray-200 bg-gray-50 py-16 dark:border-gray-700 dark:bg-gray-900/20">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
                <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                </svg>
              </div>
              <h3 className="mt-4 text-base font-semibold text-gray-900 dark:text-gray-100">{t('page.home.empty_title')}</h3>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400 text-center max-w-xs">
                {t('page.home.empty_description')}
              </p>
              <div className="mt-6 flex gap-3">
                <Link href="/import-export" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors">
                  {t('page.home.cta_import_title')}
                </Link>
                {demoStatus !== null && !demoStatus.demo_seeded && (
                  <button
                    onClick={handleLaunchDemo}
                    disabled={demoLoading}
                    className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300"
                  >
                    {demoLoading ? t('page.home.empty_loading') : t('page.home.empty_demo_button')}
                  </button>
                )}
              </div>
            </div>
          ) : <EntityTable />}
        </div>
        <div className="w-full max-w-full">
          <ActivityFeed />
        </div>
      </div>

      {/* ── Data Readiness collapsible section (per-domain only) ── */}
      {token && !isAllScope(activeDomainId) && (
        <DataReadinessSection domainId={activeDomainId} />
      )}

      {/* Guided tour — auto-starts after demo is seeded */}
      <GuidedTour autoStart={demoStatus?.demo_seeded === true} />
    </div>
  );
}

function DataReadinessSection({ domainId }: { domainId: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
        aria-expanded={open}
      >
        <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">
          Data Readiness
        </span>
        <svg
          className={`h-4 w-4 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="border-t border-gray-100 dark:border-gray-800">
          <DerivedStatusPanel domainId={domainId} />
        </div>
      )}
    </div>
  );
}
