"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  Area,
  AreaChart,
  Cell,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import EntityTable from "./components/EntityTable";
import EntityVariantView from "./components/EntityVariantView";
import ActivityFeed from "./components/ActivityFeed";
import GuidedTour, { resetTour } from "./components/GuidedTour";
import WelcomeModal from "./components/WelcomeModal";
import { AdaptiveNarrativeBlock } from "./components/ukip";
import { apiFetch } from "../lib/api";
import { useAuth } from "./contexts/AuthContext";
import { useLanguage } from "./contexts/LanguageContext";
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
  domain_distribution?: { domain: string | null; count: number }[];
}

interface DemoStatus {
  demo_seeded: boolean;
  demo_entity_count: number;
}

type GuidedStage = {
  id: "import" | "enrich" | "review" | "brief";
  href: string;
  status: "done" | "current" | "upcoming";
};

type GuidedReadiness = "starting" | "building" | "review" | "briefing";

export default function Home() {
  const [viewMode, setViewMode] = useState<"table" | "variants">("table");
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [enrichPct, setEnrichPct] = useState<number>(0);
  const [domainCount, setDomainCount] = useState<number>(0);
  const [demoStatus, setDemoStatus] = useState<DemoStatus | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [pilotPersona, setPilotPersona] = useState<PilotPersonaId>("research");
  const { token } = useAuth();
  const { t } = useLanguage();
  const tr = useCallback((key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  }, [t]);
  const hasEntities = (stats?.total_entities ?? 0) > 0;
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
      const [statsRes, enrichRes] = await Promise.all([
        apiFetch("/stats"),
        apiFetch("/enrich/stats").catch(() => null),
      ]);
      const s = await statsRes.json();
      setStats(s);
      setDomainCount(
        Array.isArray(s.domain_distribution)
          ? s.domain_distribution.filter((item: { count: number }) => item.count > 0).length
          : 0,
      );
      if (enrichRes && enrichRes.ok) {
        const e = await enrichRes.json();
        setEnrichPct(e.enrichment_coverage_pct ?? 0);
      }
    } catch {
      // stats are non-critical
    }
  }, []);

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

  const viewToggle = (
    <div className="inline-flex rounded-lg border border-[var(--ukip-border)] bg-[var(--ukip-panel)] p-1">
      <button
        onClick={() => setViewMode("table")}
        className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
          viewMode === "table"
            ? "bg-violet-500 text-white"
            : "text-[var(--ukip-muted)] hover:bg-[var(--ukip-panel-strong)] hover:text-[var(--ukip-text)]"
        }`}
      >
        {t('page.home.view_table')}
      </button>
      <button
        onClick={() => setViewMode("variants")}
        className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
          viewMode === "variants"
            ? "bg-violet-500 text-white"
            : "text-[var(--ukip-muted)] hover:bg-[var(--ukip-panel-strong)] hover:text-[var(--ukip-text)]"
        }`}
      >
        {t('page.home.view_variants')}
      </button>
    </div>
  );
  const pipelineStages = [
    { label: tr("page.home.pipeline.ingest", "Ingesta"), group: "Knowledge", href: "/import-export", status: hasEntities ? "done" : "current", icon: "M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" },
    { label: tr("page.home.pipeline.authority", "Autoridad"), group: "Knowledge", href: "/authority", status: enrichPct >= 30 ? "done" : hasEntities ? "current" : "upcoming", icon: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" },
    { label: tr("page.home.pipeline.enrichment", "Enriquecimiento"), group: "Knowledge", href: "/analytics/dashboard", status: enrichPct >= 60 ? "done" : hasEntities ? "current" : "upcoming", icon: "M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.456-2.456L14.25 6l1.035-.259a3.375 3.375 0 002.456-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" },
    { label: tr("page.home.pipeline.graph", "Grafo"), group: "Intelligence", href: "/analytics/graph", status: enrichPct >= 60 ? "current" : "upcoming", icon: "M7.5 7.5h.008v.008H7.5V7.5zm9 0h.008v.008H16.5V7.5zm-9 9h.008v.008H7.5V16.5zm9 0h.008v.008H16.5V16.5zM8 8l8 8m0-8l-8 8" },
    { label: tr("page.home.pipeline.analysis", "Análisis"), group: "Intelligence", href: "/analytics/dashboard", status: enrichPct >= 30 ? "current" : "upcoming", icon: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" },
    { label: tr("page.home.pipeline.answers", "Respuestas"), group: "Intelligence", href: "/rag", status: enrichPct >= 60 ? "current" : "upcoming", icon: "M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm3.75 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm3.75 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337L3 21l1.087-5.445A7.94 7.94 0 013 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" },
    { label: tr("page.home.pipeline.delivery", "Entrega"), group: "Delivery", href: `/reports?preset=pilot-brief&${stakeholderQuery}`, status: enrichPct >= 60 ? "current" : "upcoming", icon: "M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5A3.375 3.375 0 0010.125 2.25H8.25m.75 12l3 3m0 0l3-3m-3 3v-6m-8.25 6.75h13.5A2.25 2.25 0 0021 15.75V9.75a2.25 2.25 0 00-.659-1.591l-5.25-5.25A2.25 2.25 0 0013.5 2.25H5.25A2.25 2.25 0 003 4.5v15a2.25 2.25 0 002.25 2.25z" },
  ];
  const pillarProgress = [
    { label: "Knowledge", value: hasEntities ? Math.max(35, Math.min(100, Math.round(45 + enrichPct * 0.45))) : 8, count: 3, icon: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" },
    { label: "Intelligence", value: hasEntities ? Math.max(12, Math.min(100, Math.round(enrichPct * 0.75))) : 0, count: 3, icon: "M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" },
    { label: "Delivery", value: enrichPct >= 60 ? 42 : hasEntities ? 12 : 0, count: 1, icon: "M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5A3.375 3.375 0 0010.125 2.25H8.25m.75 12l3 3m0 0l3-3m-3 3v-6" },
  ];
  const sourceMix = [
    { label: "OpenAlex", value: 45, color: "#7c3aed" },
    { label: "Crossref", value: 25, color: "#228be6" },
    { label: "Scopus", value: 20, color: "#f2a72b" },
    { label: "WoS", value: 10, color: "#2fad72" },
  ];
  const metricCards = [
    { label: tr("page.home.metric_total_entities", "Entidades"), value: stats?.total_entities?.toLocaleString() ?? "-", delta: hasEntities ? "+ live" : tr("common.pending", "pendiente"), icon: "M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" },
    { label: tr("page.home.metric_enrichment_coverage", "Enriquecimiento"), value: `${Math.round(enrichPct)}%`, delta: "5 fuentes activas", icon: "M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" },
    { label: tr("page.home.metric_primary_labels", "Autoridad"), value: stats?.unique_secondary_labels?.toLocaleString() ?? "-", delta: "labels", icon: "M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z" },
    { label: tr("page.home.metric_active_domains", "Dominios"), value: domainCount || "-", delta: "workspace", icon: "M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375" },
  ];
  const totalEntities = stats?.total_entities ?? 0;
  const enrichedEntities = Math.round(totalEntities * (Math.max(0, enrichPct) / 100));
  const chartMax = Math.max(totalEntities, enrichedEntities, 100);
  const growthData = ["Jul", "Ago", "Sep", "Oct", "Nov", "Dic", "Ene", "Feb"].map((month, index) => {
    const factor = [0.2, 0.28, 0.31, 0.45, 0.58, 0.7, 0.86, 1][index];
    return {
      month,
      entidades: Math.round(totalEntities * factor),
      enriquecidas: Math.round(enrichedEntities * factor),
    };
  });
  const domainCoverage = [
    { subject: "Biomed", value: 72 },
    { subject: "CS", value: 68 },
    { subject: "Fisica", value: 54 },
    { subject: "Quimica", value: 70 },
    { subject: "Social", value: 42 },
    { subject: "Ing.", value: 64 },
  ];
  const pipelineHealth = Math.round(
    (Math.min(98, hasEntities ? 98 : 12) + Math.min(100, 40 + enrichPct * 0.55) + Math.min(100, enrichPct)) / 3,
  );
  const gaugeOffset = 220 - (Math.max(0, Math.min(100, pipelineHealth)) / 100) * 220;
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
            <h1 className="mt-3 text-3xl font-bold tracking-[-0.04em] text-slate-950 dark:text-[var(--ukip-text-strong)] sm:text-4xl">
              {tr("page.home.research_intelligence", "Research Intelligence")}
            </h1>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleLaunchDemo}
              disabled={demoLoading}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-950 shadow-sm transition hover:border-violet-300 hover:text-violet-700 disabled:opacity-50 dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-text-strong)]"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z" />
              </svg>
              Demo
            </button>
            <Link
              href="/import-export"
              className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-violet-500/20 transition hover:bg-violet-700"
            >
              Importar
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
              </svg>
            </Link>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {metricCards.map((metric, index) => (
            <div key={metric.label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium text-slate-600 dark:text-[var(--ukip-muted)]">{metric.label}</p>
                <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
                  index === 1
                    ? "bg-cyan-100 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-200"
                    : index === 2
                      ? "bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-200"
                      : index === 3
                        ? "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-200"
                        : "bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-200"
                }`}>
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={metric.icon} />
                  </svg>
                </span>
              </div>
              <p className="mt-5 font-mono text-4xl font-bold tracking-[-0.06em] text-slate-950 dark:text-[var(--ukip-text-strong)]">{metric.value}</p>
              <div className="mt-3 flex items-center gap-2 text-xs">
                <span className="rounded-full bg-emerald-100 px-2 py-1 font-semibold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200">
                  ↗ {index === 3 ? "-1.3%" : index === 0 ? "+19.7%" : index === 1 ? "+8.1%" : "+4.2%"}
                </span>
                <span className="text-slate-500 dark:text-[var(--ukip-muted)]">{metric.delta}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">{tr("page.home.catalog_growth", "Crecimiento del catálogo")}</h2>
                <div className="mt-3 flex flex-wrap gap-5 text-sm">
                  <span className="flex items-center gap-2 font-semibold text-slate-950 dark:text-[var(--ukip-text-strong)]">
                    <span className="h-2 w-2 rounded-full bg-violet-600" />
                    {(stats?.total_entities ?? 0).toLocaleString()} <span className="text-xs font-medium text-slate-500">entidades</span>
                  </span>
                  <span className="flex items-center gap-2 font-semibold text-slate-950 dark:text-[var(--ukip-text-strong)]">
                    <span className="h-2 w-2 rounded-full bg-blue-500" />
                    {enrichedEntities.toLocaleString()} <span className="text-xs font-medium text-slate-500">enriquecidas</span>
                  </span>
                </div>
              </div>
              <div className="flex gap-2 text-slate-500">
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M7.5 12L12 16.5m0 0l4.5-4.5M12 16.5V3" />
                </svg>
                <span className="text-lg leading-none">...</span>
              </div>
            </div>
            <div className="mt-5 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={growthData} margin={{ top: 10, right: 18, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="homeEntitiesGradient" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.24} />
                      <stop offset="95%" stopColor="#7c3aed" stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="homeEnrichedGradient" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="5%" stopColor="#228be6" stopOpacity={0.18} />
                      <stop offset="95%" stopColor="#228be6" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: "#64748b", fontSize: 12 }} />
                  <YAxis axisLine={false} domain={[0, chartMax]} tickLine={false} tick={{ fill: "#64748b", fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ background: "#0f172a", border: "0", borderRadius: 14, color: "#fff", boxShadow: "0 18px 40px rgba(15, 23, 42, 0.25)" }}
                    labelStyle={{ color: "#cbd5e1", fontWeight: 700 }}
                  />
                  <Area type="monotone" dataKey="entidades" stroke="#7c3aed" strokeWidth={2.5} fill="url(#homeEntitiesGradient)" />
                  <Area type="monotone" dataKey="enriquecidas" stroke="#228be6" strokeWidth={2.5} fill="url(#homeEnrichedGradient)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
            <h2 className="text-base font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">{tr("page.home.source_mix", "Mezcla de fuentes")}</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-[var(--ukip-muted)]">Cobertura por proveedor</p>
            <div className="relative mt-5 h-52">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={sourceMix} dataKey="value" innerRadius={62} outerRadius={88} paddingAngle={3}>
                    {sourceMix.map((entry) => (
                      <Cell key={entry.label} fill={entry.color} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="font-mono text-2xl font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">100%</span>
                <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">cobertura</span>
              </div>
            </div>
            <div className="mt-3 space-y-2">
              {sourceMix.map((source) => (
                <div key={source.label} className="flex items-center justify-between gap-3 text-sm">
                  <span className="flex items-center gap-2 text-slate-700 dark:text-[var(--ukip-muted)]">
                    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: source.color }} />
                    {source.label}
                  </span>
                  <span className="font-medium text-slate-600 dark:text-[var(--ukip-muted)]">{source.value}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
          <div className="flex items-center justify-between gap-3">
            <p className="ukip-kicker">{tr("page.home.pipeline_title", "Pipeline UKIP")}</p>
            <span className="text-xs text-slate-500 dark:text-[var(--ukip-muted)]">raw → answer</span>
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

        <div className="grid gap-4 xl:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
            <h2 className="text-base font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">{tr("page.home.pillar_progress", "Avance por pilar")}</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-[var(--ukip-muted)]">Knowledge · Intelligence · Delivery</p>
            <div className="mt-6 space-y-6">
              {pillarProgress.map((pillar, index) => (
                <div key={pillar.label}>
                  <div className="flex items-center justify-between gap-3">
                    <span className="flex items-center gap-3 text-sm font-semibold text-slate-950 dark:text-[var(--ukip-text-strong)]">
                      <span className={`flex h-9 w-9 items-center justify-center rounded-xl ${
                        index === 0
                          ? "bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-200"
                          : index === 1
                            ? "bg-cyan-100 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-200"
                            : "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200"
                      }`}>
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={pillar.icon} />
                        </svg>
                      </span>
                      <span>
                        {pillar.label}
                        <span className="block text-xs font-medium text-slate-500">{pillar.count} etapas</span>
                      </span>
                    </span>
                    <span className="font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">{pillar.value}%</span>
                  </div>
                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-white/10">
                    <div className="h-full rounded-full bg-violet-600 dark:bg-violet-400" style={{ width: `${pillar.value}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">Cobertura por dominio</h2>
                <p className="mt-1 text-sm text-slate-500 dark:text-[var(--ukip-muted)]">Calidad de metadatos</p>
              </div>
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">6 áreas</span>
            </div>
            <div className="mt-5 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={domainCoverage} outerRadius={94}>
                  <PolarGrid stroke="#e2e8f0" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: "#64748b", fontSize: 12 }} />
                  <Radar dataKey="value" stroke="#7c3aed" strokeWidth={2} fill="#7c3aed" fillOpacity={0.22} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)]">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">Salud del pipeline</h2>
                <p className="mt-1 text-sm text-slate-500 dark:text-[var(--ukip-muted)]">Score global</p>
              </div>
              <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200">Live</span>
            </div>
            <div className="relative mx-auto mt-8 h-44 max-w-[260px]">
              <svg className="h-full w-full" viewBox="0 0 220 140">
                <path d="M30 110a80 80 0 0 1 160 0" fill="none" stroke="#f1f5f9" strokeLinecap="round" strokeWidth="28" />
                <path
                  d="M30 110a80 80 0 0 1 160 0"
                  fill="none"
                  stroke="#7c3aed"
                  strokeDasharray="220"
                  strokeDashoffset={gaugeOffset}
                  strokeLinecap="round"
                  strokeWidth="28"
                />
              </svg>
              <div className="absolute inset-x-0 bottom-5 text-center">
                <p className="font-mono text-4xl font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">{pipelineHealth}</p>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">de 100</p>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-3 border-t border-slate-200 pt-4 text-center dark:border-white/10">
              <div>
                <p className="font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">{hasEntities ? "98%" : "12%"}</p>
                <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Ingesta</p>
              </div>
              <div>
                <p className="font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">{Math.min(100, 40 + enrichPct * 0.55).toFixed(0)}%</p>
                <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Calidad</p>
              </div>
              <div>
                <p className="font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">{Math.round(enrichPct)}%</p>
                <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Enriq.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Demo mode banner */}
      {demoStatus !== null && (
        !demoStatus.demo_seeded ? (
          <div className="flex items-center justify-between rounded-xl border border-indigo-200 bg-indigo-50 px-5 py-4 dark:border-indigo-900/40 dark:bg-indigo-900/10">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-100 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-indigo-900 dark:text-indigo-200">{t('page.home.demo_banner_title')}</p>
                <p className="text-xs text-indigo-600 dark:text-indigo-400">{t('page.home.demo_banner_description')}</p>
              </div>
            </div>
            <button
              onClick={handleLaunchDemo}
              disabled={demoLoading}
              className="flex shrink-0 items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors disabled:opacity-50"
            >
              {demoLoading ? (
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : t('page.home.demo_launch_button')}
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 px-5 py-3.5 dark:border-amber-900/40 dark:bg-amber-900/10">
            <div className="flex items-center gap-3">
              <span className="text-lg">demo</span>
              <div>
                <p className="text-sm font-medium text-amber-900 dark:text-amber-200">{t('page.home.demo_active_title')}</p>
                <p className="text-xs text-amber-600 dark:text-amber-400">{demoStatus.demo_entity_count.toLocaleString()} {t('page.home.demo_active_description')}</p>
              </div>
            </div>
            <button
              onClick={handleClearDemo}
              disabled={demoLoading}
              className="flex shrink-0 items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-4 py-2 text-sm font-medium text-amber-700 hover:bg-amber-50 transition-colors disabled:opacity-50 dark:border-amber-700 dark:bg-amber-900/20 dark:text-amber-300"
            >
              {demoLoading ? t('page.home.demo_clearing') : t('page.home.demo_clear_button')}
            </button>
          </div>
        )
      )}

      <AdaptiveNarrativeBlock
        progress={guidedProgress.percent}
        currentStep={narrativeCurrentStep}
        totalSteps={guidedStages.length}
        role={narrativeRole}
        coveragePercent={stats?.total_entities ? 100 : 0}
        enrichmentCoverage={enrichPct}
        recommendedActionLabel={nextGuidedAction.cta}
        recommendedActionHref={nextGuidedAction.href}
      />

      {/* Quick action cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Link href="/import-export" className="group rounded-2xl bg-gradient-to-br from-blue-600 to-cyan-500 p-5 text-white shadow-sm transition-shadow hover:shadow-md">
          <div className="flex items-center gap-3">
            <svg className="h-8 w-8 opacity-80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
            </svg>
            <div>
              <p className="font-semibold">{t('page.home.cta_import_title')}</p>
              <p className="text-sm text-white/70">{t('page.home.cta_import_desc')}</p>
            </div>
          </div>
        </Link>
        <Link href="/authority" className="group rounded-2xl bg-gradient-to-br from-violet-600 to-purple-500 p-5 text-white shadow-sm transition-shadow hover:shadow-md">
          <div className="flex items-center gap-3">
            <svg className="h-8 w-8 opacity-80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            <div>
              <p className="font-semibold">{t('page.home.cta_authority_title')}</p>
              <p className="text-sm text-white/70">{t('page.home.cta_authority_desc')}</p>
            </div>
          </div>
        </Link>
        <Link href="/analytics/olap" className="group rounded-2xl bg-gradient-to-br from-emerald-600 to-teal-500 p-5 text-white shadow-sm transition-shadow hover:shadow-md">
          <div className="flex items-center gap-3">
            <svg className="h-8 w-8 opacity-80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
            </svg>
            <div>
              <p className="font-semibold">{t('page.home.cta_olap_title')}</p>
              <p className="text-sm text-white/70">{t('page.home.cta_olap_desc')}</p>
            </div>
          </div>
        </Link>
      </div>

      {/* Activity feed + Entity browser */}
      <div className="grid grid-cols-1 gap-6 2xl:grid-cols-[1fr_280px]">
        <div>
          <div className="mb-4 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-[var(--ukip-panel)] sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="ukip-kicker">Catálogo interno</p>
              <h2 className="mt-1 text-lg font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">Exploración de entidades</h2>
            </div>
            {viewToggle}
          </div>
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
          ) : viewMode === "table" ? <EntityTable /> : <EntityVariantView />}
        </div>
        <div>
          <ActivityFeed />
        </div>
      </div>

      {/* Guided tour — auto-starts after demo is seeded */}
      <GuidedTour autoStart={demoStatus?.demo_seeded === true} />
    </div>
  );
}
