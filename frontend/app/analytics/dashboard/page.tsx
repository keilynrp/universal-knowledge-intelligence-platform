"use client";

import type { ReactNode } from "react";
import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { PageHeader, StatCard, ErrorBanner, SkeletonCard, useToast } from "../../components/ui";
import ConceptCloud from "../../components/ConceptCloud";
import { useDomain } from "../../contexts/DomainContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { apiFetch } from "@/lib/api";
import { Analytics } from "@/lib/analytics";
import { AgenticResearchChat } from "../../components/ukip";

const REFRESH_INTERVAL_SEC = 5 * 60; // 5 minutes

// ── Types ─────────────────────────────────────────────────────────────────────

interface DashboardData {
  domain_id: string;
  kpis: {
    total_entities: number;
    enriched_count: number;
    enrichment_pct: number;
    avg_citations: number;
    total_concepts: number;
  };
  entities_by_year: { year: number; count: number }[];
  brand_year_matrix: {
    brands: string[];
    years: number[];
    matrix: number[][];
  };
  top_concepts: { concept: string; count: number; pct: number }[];
  emerging_topic_signals: {
    is_experimental: boolean;
    years_available: number[];
    baseline_years: number[];
    recent_years: number[];
    signals: {
      concept: string;
      recent_count: number;
      baseline_count: number;
      recent_share: number;
      baseline_share: number;
      acceleration_score: number;
      confidence: "high" | "medium" | "low";
      evidence: string;
    }[];
  };
  top_entities: {
    id: number;
    entity_name?: string | null;
    primary_label?: string | null;
    brand?: string | null;
    citation_count: number;
    source: string | null;
  }[];
  quality?: {
    average: number | null;
    distribution: { high: number; medium: number; low: number };
  };
  recommended_actions: {
    id: string;
    title: string;
    detail: string;
    evidence: string;
    priority: "high" | "medium" | "low";
    category: string;
    meta?: Record<string, string | number>;
  }[];
  institutional_benchmark: {
    profile_id: string;
    profile_name: string;
    description: string;
    region: string;
    status: "ready" | "watch" | "gap";
    readiness_pct: number;
    passed_rules: number;
    total_rules: number;
    top_gaps: {
      id: string;
      label: string;
      priority: "high" | "medium" | "low";
      threshold: number;
      observed: number;
      passed: boolean;
      message: string;
      evidence: string;
    }[];
  };
  impact_projection?: {
    score: number;
    expected: number;
    conservative: number;
    optimistic: number;
    confidence: "high" | "medium" | "low";
    confidence_score: number;
    range: { p10: number; p50: number; p90: number };
    drivers: { coverage: number; quality: number; citation_signal: number; concentration: number };
    recommendation: string;
    brief_angle: string;
    explanation: string;
    simulations: number;
  };
  hidden_patterns?: {
    summary: { records_analyzed: number; patterns_found: number; highest_impact_score: number };
    patterns: {
      id: string;
      type: string;
      label: string;
      confidence: "high" | "medium" | "low";
      impact_score: number;
      evidence: string;
      recommended_action: string;
      entities: { id: number; label: string; entity_type?: string | null }[];
    }[];
  };
}

interface BenchmarkProfile {
  id: string;
  name: string;
  description: string;
  region: string;
  rules_count: number;
  is_default: boolean;
}

interface BenchmarkGap {
  id: string;
  label: string;
  priority: "high" | "medium" | "low";
  threshold: number;
  observed: number;
  passed: boolean;
  message: string;
  evidence: string;
}

// ── Heatmap cell with violet color scale ─────────────────────────────────────

function HeatCell({ value, max }: { value: number; max: number }) {
  const alpha = max > 0 ? 0.08 + (value / max) * 0.82 : 0.08;
  const isHigh = max > 0 && value / max > 0.6;
  return (
    <td
      className="border border-gray-100 px-3 py-2 text-center text-xs font-medium dark:border-gray-800"
      style={{ backgroundColor: `rgba(139,92,246,${alpha})` }}
    >
      <span className={isHigh ? "text-white" : "text-gray-700 dark:text-gray-200"}>
        {value > 0 ? value.toLocaleString() : "—"}
      </span>
    </td>
  );
}

// ── Source badge ──────────────────────────────────────────────────────────────

const SOURCE_COLORS: Record<string, string> = {
  openalex: "bg-violet-100 text-violet-700 dark:bg-violet-500/20 dark:text-violet-300",
  wos: "bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300",
  scholar: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300",
};

function SourceBadge({ source }: { source: string | null }) {
  if (!source) return <span className="text-xs text-gray-400">—</span>;
  const cls = SOURCE_COLORS[source.toLowerCase()] ??
    "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {source}
    </span>
  );
}

type NarrativeIconName = "eye" | "target" | "shield" | "spark" | "route" | "check" | "alert";

function NarrativeIcon({ name, tone = "violet" }: { name: NarrativeIconName; tone?: "violet" | "emerald" | "amber" | "cyan" }) {
  const toneClass = {
    violet: "bg-violet-500/10 text-violet-600 dark:text-violet-300",
    emerald: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
    amber: "bg-amber-500/10 text-amber-600 dark:text-amber-300",
    cyan: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-300",
  }[tone];
  const paths: Record<NarrativeIconName, ReactNode> = {
    eye: (
      <>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M2.25 12s3.75-6.75 9.75-6.75S21.75 12 21.75 12 18 18.75 12 18.75 2.25 12 2.25 12z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </>
    ),
    target: (
      <>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M12 21a9 9 0 100-18 9 9 0 000 18z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M12 17a5 5 0 100-10 5 5 0 000 10zM12 13a1 1 0 100-2 1 1 0 000 2z" />
      </>
    ),
    shield: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M12 3.75l7.25 2.6v5.4c0 4.35-2.93 8.22-7.25 9.5-4.32-1.28-7.25-5.15-7.25-9.5v-5.4L12 3.75zM9.25 12.1l1.85 1.85 3.95-4.15" />
    ),
    spark: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M12 3l1.35 5.15L18.5 9.5l-5.15 1.35L12 16l-1.35-5.15L5.5 9.5l5.15-1.35L12 3zM18.5 14.5l.7 2.3 2.3.7-2.3.7-.7 2.3-.7-2.3-2.3-.7 2.3-.7.7-2.3zM5.5 14.5l.55 1.95L8 17l-1.95.55L5.5 19.5l-.55-1.95L3 17l1.95-.55L5.5 14.5z" />
    ),
    route: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M6.5 7.5a2.75 2.75 0 100-5.5 2.75 2.75 0 000 5.5zM17.5 22a2.75 2.75 0 100-5.5 2.75 2.75 0 000 5.5zM6.5 7.5v2.25A3.25 3.25 0 009.75 13h4.5a3.25 3.25 0 013.25 3.25v.25" />
    ),
    check: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M20 6.75L9.5 17.25 4 11.75" />
    ),
    alert: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M12 8v4m0 4h.01M10.45 3.85L2.7 17.25A2 2 0 004.43 20.25h15.14a2 2 0 001.73-3L13.55 3.85a1.8 1.8 0 00-3.1 0z" />
    ),
  };

  return (
    <span className={`inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${toneClass}`}>
      <svg className="h-5 w-5" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        {paths[name]}
      </svg>
    </span>
  );
}

function StoryMetricCard({
  icon,
  label,
  value,
  description,
  tone = "violet",
  footer,
}: {
  icon: NarrativeIconName;
  label: string;
  value: ReactNode;
  description: string;
  tone?: "violet" | "emerald" | "amber" | "cyan";
  footer?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-[var(--ukip-border)] bg-[var(--ukip-panel)] p-4 shadow-[var(--ukip-shadow-soft)]">
      <div className="flex items-start gap-3">
        <NarrativeIcon name={icon} tone={tone} />
        <div className="min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--ukip-muted)]">{label}</p>
          <p className="mt-2 text-3xl font-black leading-none text-[var(--ukip-text-strong)]">{value}</p>
          <p className="mt-2 text-xs text-[var(--ukip-muted)]">{description}</p>
          {footer ? <div className="mt-3">{footer}</div> : null}
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ExecutiveDashboardPage() {
  const { activeDomainId, setActiveDomainId } = useDomain();
  const { t } = useLanguage();
  const { toast } = useToast();
  const searchParams = useSearchParams();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL_SEC);
  const [exporting, setExporting] = useState(false);
  const [queueingBulkEnrichment, setQueueingBulkEnrichment] = useState(false);
  const [benchmarkProfiles, setBenchmarkProfiles] = useState<BenchmarkProfile[]>([]);
  const [selectedBenchmarkProfile, setSelectedBenchmarkProfile] = useState(
    searchParams.get("benchmark_profile") || "",
  );
  const importedFlag = searchParams.get("imported") === "1";
  const importedDomain = searchParams.get("domain");
  const importedRows = searchParams.get("rows");
  const tr = useCallback((key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  }, [t]);
  const formatObservedValue = (value: number) => (
    Number.isInteger(value)
      ? value.toLocaleString()
      : value.toLocaleString(undefined, { maximumFractionDigits: 1 })
  );
  const translateBenchmarkProfileName = (profileId: string, fallback: string) => (
    tr(`page.exec_dashboard.benchmark_profile_name.${profileId}`, fallback)
  );
  const translateBenchmarkStatus = (status: string) => (
    tr(`page.exec_dashboard.benchmark_status.${status}`, status)
  );
  const translatePriority = (priority: string) => (
    tr(`page.exec_dashboard.priority.${priority}`, priority)
  );
  const translateRuleLabel = (ruleId: string, fallback: string) => (
    tr(`page.exec_dashboard.benchmark_rule_label.${ruleId}`, fallback)
  );
  const translateBenchmarkEvidence = (profileId: string, gap: BenchmarkGap) => (
    t("page.exec_dashboard.benchmark_evidence", {
      label: translateRuleLabel(gap.id, gap.label),
      observed: formatObservedValue(gap.observed),
      threshold: formatObservedValue(gap.threshold),
      profile: translateBenchmarkProfileName(profileId, profileId),
    })
  );
  const translateConfidence = (confidence: "high" | "medium" | "low") => (
    tr(`page.exec_dashboard.confidence.${confidence}`, confidence)
  );
  const translatePatternType = (type: string) => (
    tr(`page.exec_dashboard.pattern_type.${type}`, type.replaceAll("_", " "))
  );
  const translateActionText = useCallback((
    action: DashboardData["recommended_actions"][number],
    field: "title" | "detail" | "evidence",
  ) => {
    const key = `page.exec_dashboard.action.${action.id}.${field}`;
    const raw = t(key, action.meta ?? {});
    return raw === key ? action[field] : raw;
  }, [t]);

  const fetchDashboard = useCallback(async (options?: { forceRefresh?: boolean; preserveData?: boolean }) => {
    const forceRefresh = options?.forceRefresh ?? false;
    const preserveData = options?.preserveData ?? false;
    if (preserveData) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);
    try {
      const profileQuery = selectedBenchmarkProfile
        ? `&profile_id=${encodeURIComponent(selectedBenchmarkProfile)}`
        : "";
      const forceQuery = forceRefresh ? "&force_refresh=true" : "";
      const res = await apiFetch(`/dashboard/summary?domain_id=${activeDomainId}${profileQuery}${forceQuery}`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (error: unknown) {
      setError(error instanceof Error ? error.message : tr("page.exec_dashboard.dashboard_load_failed", "Failed to load dashboard"));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activeDomainId, selectedBenchmarkProfile, tr]);

  useEffect(() => { void fetchDashboard(); }, [fetchDashboard]);

  useEffect(() => {
    let cancelled = false;
    const loadProfiles = async () => {
      const res = await apiFetch("/analytics/benchmarks/profiles");
      if (!res.ok) return;
      const profiles: BenchmarkProfile[] = await res.json();
      if (!cancelled) {
        setBenchmarkProfiles(profiles);
        if (!searchParams.get("benchmark_profile")) {
          const defaultProfile = profiles.find((profile) => profile.is_default)?.id ?? profiles[0]?.id;
          if (defaultProfile) setSelectedBenchmarkProfile(defaultProfile);
        }
      }
    };
    loadProfiles();
    return () => { cancelled = true; };
  }, [searchParams]);

  useEffect(() => {
    if (importedDomain && importedDomain !== activeDomainId) {
      setActiveDomainId(importedDomain);
    }
  }, [activeDomainId, importedDomain, setActiveDomainId]);

  // Auto-refresh countdown
  useEffect(() => {
    if (!autoRefresh) { setCountdown(REFRESH_INTERVAL_SEC); return; }
    const tick = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) { void fetchDashboard({ forceRefresh: true, preserveData: true }); return REFRESH_INTERVAL_SEC; }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(tick);
  }, [autoRefresh, fetchDashboard]);

  const mm = String(Math.floor(countdown / 60)).padStart(2, "0");
  const ss = String(countdown % 60).padStart(2, "0");

  const handleExportPDF = async () => {
    if (!data) return;
    setExporting(true);
    Analytics.dashboardExportPDF(activeDomainId);
    try {
      const res = await apiFetch("/exports/pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain_id: activeDomainId,
          benchmark_profile_id: selectedBenchmarkProfile,
          sections: ["entity_stats", "enrichment_coverage", "decision_recommendations", "institutional_benchmark", "top_brands", "topic_clusters"],
          title: tr("page.exec_dashboard.export_title", "Executive Dashboard Report"),
        }),
      });
      if (!res.ok) {
        let detail = tr("page.exec_dashboard.pdf_export_failed", "PDF export failed.");
        try {
          const payload = await res.json();
          detail = payload.detail || detail;
        } catch {
          const text = await res.text();
          if (text) detail = text;
        }
        setError(detail);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `dashboard_${activeDomainId}_${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setError(error instanceof Error ? error.message : tr("page.exec_dashboard.pdf_export_error", "PDF export error"));
    } finally {
      setExporting(false);
    }
  };

  const handleBulkEnrichment = useCallback(async () => {
    setQueueingBulkEnrichment(true);
    try {
      const params = new URLSearchParams({ limit: "250" });
      if (activeDomainId) {
        params.set("domain_id", activeDomainId);
      }
      const response = await apiFetch(`/enrich/bulk?${params.toString()}`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      toast(
        t("page.exec_dashboard.bulk_enrich_success", { count: payload.queued_records ?? 0 }),
        "success",
      );
      await fetchDashboard();
    } catch {
      toast(tr("page.exec_dashboard.bulk_enrich_failed", "Bulk enrichment could not be queued."), "error");
    } finally {
      setQueueingBulkEnrichment(false);
    }
  }, [activeDomainId, fetchDashboard, t, toast, tr]);

  // Compute heatmap max for scaling
  const heatMax = data
    ? Math.max(1, ...data.brand_year_matrix.matrix.flat())
    : 1;
  const briefBuilderHref = `/reports?preset=pilot-brief&domain=${encodeURIComponent(importedDomain ?? activeDomainId)}&rows=${encodeURIComponent(importedRows ?? String(data?.kpis.total_entities ?? 0))}&format=pdf&benchmark_profile=${encodeURIComponent(selectedBenchmarkProfile)}&title=${encodeURIComponent(`UKIP Pilot Brief — ${importedDomain ?? activeDomainId}`)}`;
  const enrichedExplorerHref = "/?ft_enrichment_status=completed&min_quality=0.7";
  const latestImportExplorerHref = importedDomain
    ? `/?ft_domain=${encodeURIComponent(importedDomain)}`
    : "/";
  const decisionHighlights = useMemo(() => {
    if (!data) return [];

    return data.recommended_actions.map((action) => {
      const tone: "amber" | "emerald" | "violet" =
        action.priority === "high"
          ? "amber"
          : action.category === "impact"
            ? "emerald"
            : "violet";

      return {
        ...action,
        title: translateActionText(action, "title"),
        evidence: translateActionText(action, "evidence"),
        tone,
      };
    });
  }, [data, translateActionText]);

  const toneStyles: Record<"violet" | "amber" | "emerald", string> = {
    violet: "border-violet-200 bg-violet-50 text-violet-900 dark:border-violet-500/20 dark:bg-violet-500/5 dark:text-violet-200",
    amber: "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-500/20 dark:bg-amber-500/5 dark:text-amber-200",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-500/20 dark:bg-emerald-500/5 dark:text-emerald-200",
  };
  const benchmarkTone =
    !data ? toneStyles.violet :
    data.institutional_benchmark.status === "ready" ? toneStyles.emerald :
    data.institutional_benchmark.status === "watch" ? toneStyles.violet :
    toneStyles.amber;
  const leadingGap = data?.institutional_benchmark?.top_gaps?.[0] ?? null;
  const signalToneStyles: Record<"high" | "medium" | "low", string> = {
    high: "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-500/20 dark:bg-emerald-500/5 dark:text-emerald-200",
    medium: "border-violet-200 bg-violet-50 text-violet-900 dark:border-violet-500/20 dark:bg-violet-500/5 dark:text-violet-200",
    low: "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-500/20 dark:bg-amber-500/5 dark:text-amber-200",
  };
  const nextPilotStep = data?.kpis.enrichment_pct && data.kpis.enrichment_pct >= 60
    ? {
        href: briefBuilderHref,
        title: tr("page.exec_dashboard.next.brief.title", "Move from analysis to a brief"),
        body: tr("page.exec_dashboard.next.brief.body", "Coverage is strong enough to turn this workspace into a stakeholder-facing summary."),
        cta: tr("page.exec_dashboard.next.brief.cta", "Open brief builder"),
      }
    : {
        href: "/authority",
        title: tr("page.exec_dashboard.next.review.title", "Review the records that still need human attention"),
        body: tr("page.exec_dashboard.next.review.body", "Use authority and review queues to clean the weakest records before sharing conclusions."),
        cta: tr("page.exec_dashboard.next.review.cta", "Open review"),
      };
  const qualityPct = data?.quality?.average != null ? Math.round(data.quality.average * 100) : null;
  const readinessStatusTone =
    data?.institutional_benchmark.status === "ready"
      ? "text-emerald-300 bg-emerald-500/10 border-emerald-400/20"
      : data?.institutional_benchmark.status === "gap"
        ? "text-amber-300 bg-amber-500/10 border-amber-400/20"
        : "text-violet-300 bg-violet-500/10 border-violet-400/20";
  const executiveStoryStatus = data ? translateBenchmarkStatus(data.institutional_benchmark.status) : "";
  const executiveStoryAction = decisionHighlights[0] ?? null;
  const executiveStoryLine = data
    ? data.institutional_benchmark.status === "ready"
      ? tr("page.exec_dashboard.story_ready", "El portafolio ya sostiene una narrativa ejecutiva clara; la oportunidad ahora es convertirla en recomendación accionable.")
      : data.institutional_benchmark.status === "gap"
        ? tr("page.exec_dashboard.story_gap", "La lectura ejecutiva muestra una brecha concreta: elevar calidad y cobertura antes de presentar conclusiones finales.")
        : tr("page.exec_dashboard.story_watch", "El portafolio tiene señales útiles, pero necesita una capa más de validación para convertir análisis en decisión.")
    : "";
  const storySparklineData = data?.entities_by_year?.length
    ? data.entities_by_year.slice(-10)
    : [
        { year: 1, count: 3 },
        { year: 2, count: 6 },
        { year: 3, count: 5 },
        { year: 4, count: 11 },
        { year: 5, count: 9 },
        { year: 6, count: 14 },
      ];

  return (
    <div className="flex flex-col gap-6 pb-10">
      <PageHeader
        title={tr("page.exec_dashboard.title", "Executive Dashboard")}
        description={tr("page.exec_dashboard.description", "Signal, readiness, impact, and next action.")}
        breadcrumbs={[
          { label: tr("page.exec_dashboard.breadcrumb_analytics", "Analytics"), href: "/analytics" },
          { label: tr("page.exec_dashboard.title", "Executive Dashboard") },
        ]}
        actions={
          <div className="flex items-center gap-2">
            {/* Auto-refresh toggle */}
            <button
              onClick={() => setAutoRefresh(v => !v)}
              title={autoRefresh ? `${tr("page.exec_dashboard.auto_refresh_active", "Auto-refresh on")} — next in ${mm}:${ss}` : tr("page.exec_dashboard.auto_refresh_enable", "Enable auto-refresh every 5 min")}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium shadow-sm transition ${
                autoRefresh
                  ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400"
                  : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              }`}
            >
              <svg className={`h-3.5 w-3.5 ${autoRefresh ? "animate-spin" : ""}`} aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
              <span className="tabular-nums">{autoRefresh ? `${mm}:${ss}` : tr("page.exec_dashboard.auto_label", "Auto")}</span>
            </button>

            {/* Manual refresh */}
            <button
              onClick={() => void fetchDashboard({ forceRefresh: true, preserveData: true })}
              disabled={refreshing || loading}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
            >
              <svg className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
              {refreshing
                ? tr("page.exec_dashboard.refreshing", "Refreshing...")
                : tr("page.exec_dashboard.refresh", "Refresh")}
            </button>

            {/* Export Dashboard PDF */}
            <button
              onClick={handleExportPDF}
              disabled={exporting || loading || !data}
              className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-violet-700 disabled:opacity-50"
            >
              {exporting ? (
                <svg className="h-4 w-4 animate-spin" aria-hidden="true" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
              ) : (
                <svg className="h-4 w-4" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
              )}
              {exporting ? tr("page.exec_dashboard.exporting", "Exporting…") : tr("page.exec_dashboard.export_pdf", "Export PDF")}
            </button>
          </div>
        }
      />

      {error && <ErrorBanner message={error} onRetry={fetchDashboard} variant="card" />}

      {data && (
        <div className="rounded-[var(--ukip-radius-2xl)] border border-violet-200/70 bg-[var(--ukip-panel)] p-5 shadow-[var(--ukip-shadow-panel)] dark:border-violet-500/20">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <p className="ukip-kicker">{tr("page.exec_dashboard.executive_signal", "Señal ejecutiva")}</p>
              <h2 className="mt-1 text-xl font-black text-[var(--ukip-text-strong)]">
                {tr("page.exec_dashboard.story_title", "La historia del portafolio en una lectura")}
              </h2>
            </div>
            <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] ${readinessStatusTone}`}>
              {executiveStoryStatus}
            </span>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.1fr_1fr_1fr_1fr_1fr]">
            <div className="relative overflow-hidden rounded-2xl border border-violet-200/70 bg-gradient-to-br from-violet-50 via-white to-cyan-50 p-4 dark:border-violet-500/20 dark:from-violet-500/10 dark:via-[var(--ukip-panel)] dark:to-cyan-500/10">
              <div className="flex items-start justify-between gap-3">
                <NarrativeIcon name="eye" />
                <span className="rounded-full bg-white/80 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.12em] text-violet-700 shadow-sm dark:bg-white/10 dark:text-violet-200">
                  {tr("page.exec_dashboard.observation_badge", "Observación")}
                </span>
              </div>
              <h3 className="mt-4 text-lg font-black text-[var(--ukip-text-strong)]">
                {tr("page.exec_dashboard.observation_title", "Panorama actual")}
              </h3>
              <p className="mt-2 text-xs leading-5 text-[var(--ukip-muted)]">
                {executiveStoryLine}
              </p>
              <div className="mt-4 h-16">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={storySparklineData} margin={{ top: 6, right: 0, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="storySparkline" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.34} />
                        <stop offset="95%" stopColor="#7c3aed" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="count" stroke="#7c3aed" strokeWidth={2} fill="url(#storySparkline)" dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <StoryMetricCard
              icon="target"
              label={tr("page.exec_dashboard.benchmark_score", "Puntaje de referencia")}
              value={`${Math.round(data.institutional_benchmark.readiness_pct)}%`}
              description={tr("page.exec_dashboard.benchmark_percentile", "Percentil global")}
              footer={
                <span className="rounded-full bg-cyan-500/10 px-2.5 py-1 text-[11px] font-bold text-cyan-700 dark:text-cyan-300">
                  {data.institutional_benchmark.passed_rules}/{data.institutional_benchmark.total_rules} {tr("page.exec_dashboard.rules_met_short", "reglas")}
                </span>
              }
              tone="violet"
            />
            <StoryMetricCard
              icon="route"
              label={tr("page.exec_dashboard.kpi.enrichment_coverage", "Cobertura de enriquecimiento")}
              value={`${data.kpis.enrichment_pct}%`}
              description={tr("page.exec_dashboard.enriched_entities", "Entidades enriquecidas")}
              footer={
                <div className="h-1.5 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
                  <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-cyan-400" style={{ width: `${data.kpis.enrichment_pct}%` }} />
                </div>
              }
              tone="emerald"
            />
            <StoryMetricCard
              icon="shield"
              label={tr("page.exec_dashboard.kpi.avg_quality", "Calidad promedio")}
              value={qualityPct != null ? `${qualityPct}%` : "—"}
              description={tr("page.exec_dashboard.content_quality", "Calidad del contenido")}
              footer={
                <span className="rounded-full bg-amber-500/10 px-2.5 py-1 text-[11px] font-bold text-amber-700 dark:text-amber-300">
                  {tr("page.exec_dashboard.records_scored", "registros evaluados")}
                </span>
              }
              tone={qualityPct != null && qualityPct >= 70 ? "emerald" : "amber"}
            />
            <div className="rounded-2xl border border-[var(--ukip-border)] bg-[var(--ukip-panel)] p-4 shadow-[var(--ukip-shadow-soft)]">
              <div className="flex items-start gap-3">
                <NarrativeIcon name={leadingGap ? "alert" : "check"} tone={leadingGap ? "amber" : "emerald"} />
                <div className="min-w-0">
                  <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--ukip-muted)]">
                    {tr("page.exec_dashboard.benchmark_leading_gap", "Principal restricción actual")}
                  </p>
                  <p className="mt-2 text-sm font-black leading-5 text-[var(--ukip-text-strong)]">
                    {leadingGap ? translateRuleLabel(leadingGap.id, leadingGap.label) : tr("page.exec_dashboard.no_active_gap", "Sin restricción activa")}
                  </p>
                  <p className="mt-2 text-xs text-[var(--ukip-muted)]">
                    {leadingGap ? translateBenchmarkEvidence(data.institutional_benchmark.profile_id, leadingGap) : tr("page.exec_dashboard.story_clear_path", "La evidencia permite avanzar hacia recomendación ejecutiva.")}
                  </p>
                  <Link href={nextPilotStep.href} className="mt-4 inline-flex rounded-xl bg-violet-600 px-3 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-violet-500">
                    {nextPilotStep.cta}
                  </Link>
                </div>
              </div>
            </div>
          </div>

          {executiveStoryAction && (
            <div className="mt-4 rounded-2xl border border-violet-200/70 bg-violet-50/70 p-4 dark:border-violet-500/20 dark:bg-violet-500/10">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div className="flex items-start gap-3">
                  <NarrativeIcon name="spark" tone="violet" />
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-violet-700 dark:text-violet-300">
                      {tr("page.exec_dashboard.elevator_pitch", "Elevator pitch analítico")}
                    </p>
                    <p className="mt-1 text-sm font-bold text-[var(--ukip-text-strong)]">{executiveStoryAction.title}</p>
                    <p className="mt-1 text-xs text-[var(--ukip-muted)]">{executiveStoryAction.evidence}</p>
                  </div>
                </div>
                <Link href={briefBuilderHref} className="inline-flex shrink-0 rounded-xl border border-violet-200 bg-white px-4 py-2 text-xs font-bold text-violet-700 shadow-sm transition hover:bg-violet-50 dark:border-violet-500/20 dark:bg-white/10 dark:text-violet-200 dark:hover:bg-white/15">
                  {tr("page.exec_dashboard.view_story_recommendations", "Ver recomendaciones estratégicas")}
                </Link>
              </div>
            </div>
          )}
        </div>
      )}

      {importedFlag && (
        <div className="rounded-2xl border border-violet-400/20 bg-violet-500/10 p-4 shadow-sm">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-sm font-semibold text-[var(--ukip-text-strong)]">
                {tr("page.exec_dashboard.fresh_import_title", "Fresh import ready for pilot review")}
              </p>
              <p className="mt-1 text-sm text-[var(--ukip-muted)]">
                {tr("page.exec_dashboard.fresh_import_description", "Check coverage, impact, and next actions.")}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                href={briefBuilderHref}
                className="rounded-lg border border-violet-400/30 bg-violet-500/10 px-4 py-2 text-sm font-medium text-violet-200 transition-colors hover:bg-violet-500/20"
              >
                {tr("page.import.success.open_brief", "Prepare Executive Brief")}
              </Link>
              <Link
                href={latestImportExplorerHref}
                className="rounded-lg border border-violet-400/30 bg-violet-500/10 px-4 py-2 text-sm font-medium text-violet-200 transition-colors hover:bg-violet-500/20"
              >
                {tr("page.exec_dashboard.open_explorer", "Open Knowledge Explorer")}
              </Link>
              <button
                onClick={handleExportPDF}
                disabled={exporting || loading || !data}
                className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-700 disabled:opacity-50"
              >
                {exporting ? tr("page.exec_dashboard.exporting", "Exporting…") : tr("page.exec_dashboard.export_brief", "Export PDF brief")}
              </button>
            </div>
          </div>
        </div>
      )}

      {data?.institutional_benchmark && (
        <div className={`rounded-2xl border p-5 shadow-sm ${benchmarkTone}`}>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-2xl">
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] opacity-70">
                {tr("page.exec_dashboard.benchmark_baseline", "Institutional Benchmark Baseline")}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <p className="text-lg font-semibold">
                  {translateBenchmarkProfileName(
                    data.institutional_benchmark.profile_id,
                    data.institutional_benchmark.profile_name,
                  )}
                </p>
                <span className="rounded-full bg-white/80 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-current dark:bg-gray-900/60">
                  {translateBenchmarkStatus(data.institutional_benchmark.status)}
                </span>
              </div>
              <div className="mt-3 max-w-sm">
                <label className="mb-1 block text-xs font-semibold uppercase tracking-[0.16em] opacity-70">
                  {tr("page.exec_dashboard.benchmark_profile", "Benchmark profile")}
                </label>
                <select
                  value={selectedBenchmarkProfile}
                  onChange={(e) => setSelectedBenchmarkProfile(e.target.value)}
                  className="w-full rounded-xl border border-white/70 bg-white/80 px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-violet-400 focus:outline-none dark:border-gray-700 dark:bg-gray-900/80 dark:text-white"
                >
                  {benchmarkProfiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {translateBenchmarkProfileName(profile.id, profile.name)}
                    </option>
                  ))}
                </select>
              </div>
              <p className="mt-3 text-sm font-medium opacity-90">
                {t("page.exec_dashboard.readiness_summary", {
                  readiness: data.institutional_benchmark.readiness_pct,
                  passed: data.institutional_benchmark.passed_rules,
                  total: data.institutional_benchmark.total_rules,
                })}
              </p>
            </div>
            <div className="min-w-[180px] rounded-2xl bg-white/80 p-4 text-center shadow-sm dark:bg-gray-900/70">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">
                {tr("page.exec_dashboard.benchmark_score", "Benchmark Score")}
              </p>
              <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">
                {Math.round(data.institutional_benchmark.readiness_pct)}%
              </p>
            </div>
          </div>

          {data.institutional_benchmark.top_gaps.length > 0 && (
            <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-3">
              {data.institutional_benchmark.top_gaps.map((gap) => (
                <div key={gap.id} className="rounded-2xl bg-white/80 p-4 shadow-sm dark:bg-gray-900/70">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-gray-900 dark:text-white">
                      {translateRuleLabel(gap.id, gap.label)}
                    </p>
                    <span className="rounded-full bg-amber-100 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-700 dark:bg-amber-500/20 dark:text-amber-300">
                      {translatePriority(gap.priority)}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                    {translateBenchmarkEvidence(data.institutional_benchmark.profile_id, gap)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {decisionHighlights.length > 0 && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          {decisionHighlights.map((highlight) => (
            <div
              key={highlight.title}
              className={`rounded-2xl border p-5 shadow-sm ${toneStyles[highlight.tone]}`}
            >
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] opacity-70">
                {tr("page.exec_dashboard.suggested_next_action", "Suggested Next Action")}
              </p>
              <p className="text-sm font-semibold">{highlight.title}</p>
              <p className="mt-3 text-xs font-medium opacity-75">{highlight.evidence}</p>
              {highlight.id === "bulk_enrichment" && (
                <button
                  onClick={handleBulkEnrichment}
                  disabled={queueingBulkEnrichment}
                  className="mt-4 inline-flex items-center rounded-lg bg-white/80 px-3 py-2 text-xs font-semibold text-gray-900 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60 dark:bg-gray-900/70 dark:text-white dark:hover:bg-gray-900"
                >
                  {queueingBulkEnrichment
                    ? tr("page.exec_dashboard.bulk_enrich_queueing", "Queueing enrichment…")
                    : tr("page.exec_dashboard.bulk_enrich_cta", "Queue bulk enrichment")}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── Section 1: Signal KPIs ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} lines={2} />)
        ) : data ? (
          <>
            <StatCard
              iconColor="blue"
              icon={
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                </svg>
              }
              label={tr("page.exec_dashboard.kpi.total_entities", "Total Entities")}
              value={data.kpis.total_entities.toLocaleString()}
              subtitle={tr("page.exec_dashboard.volume_signal", "Volume")}
            />
            <StatCard
              iconColor="violet"
              icon={
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
                </svg>
              }
              label={tr("page.exec_dashboard.kpi.avg_citations", "Avg Citations")}
              value={data.kpis.avg_citations}
              subtitle={tr("page.exec_dashboard.impact_signal", "Impact")}
            />
            <StatCard
              iconColor="amber"
              icon={
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              }
              label={tr("page.exec_dashboard.kpi.distinct_concepts", "Distinct Concepts")}
              value={data.kpis.total_concepts.toLocaleString()}
              subtitle={tr("page.exec_dashboard.semantic_signal", "Semantic signal")}
            />
            {/* Quality KPI */}
            <div className="ukip-panel-soft p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-500/10">
                  <svg className="h-5 w-5 text-violet-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                  </svg>
                </div>
                <div className="min-w-0">
                  <p className="text-xs text-[var(--ukip-muted)]">{tr("page.exec_dashboard.kpi.avg_quality", "Avg Quality")}</p>
                  <p className="text-2xl font-bold text-[var(--ukip-text-strong)]">
                    {data.quality?.average != null ? `${Math.round(data.quality.average * 100)}%` : "—"}
                  </p>
                  <p className="mt-1 text-xs text-[var(--ukip-muted)]">{tr("page.exec_dashboard.quality_signal", "Confidence")}</p>
                </div>
              </div>
              {data.quality?.distribution && (
                <div className="mt-3 flex gap-1" title={tr("page.exec_dashboard.quality_distribution_title", "High / Medium / Low quality distribution")}>
                  {(() => {
                    const { high, medium, low } = data.quality.distribution;
                    const total = high + medium + low;
                    if (total === 0) return <span className="text-xs text-gray-400">{tr("page.exec_dashboard.no_scored_entities", "No scored entities")}</span>;
                    return (
                      <div className="flex w-full overflow-hidden rounded-full h-2 gap-px">
                        {high > 0 && <div className="bg-emerald-500 h-2 rounded-l-full" style={{ width: `${(high / total) * 100}%` }} title={t("page.exec_dashboard.quality_segment", { label: tr("page.exec_dashboard.quality_high", "High"), count: high })} />}
                        {medium > 0 && <div className="bg-amber-400 h-2" style={{ width: `${(medium / total) * 100}%` }} title={t("page.exec_dashboard.quality_segment", { label: tr("page.exec_dashboard.quality_medium", "Medium"), count: medium })} />}
                        {low > 0 && <div className="bg-red-500 h-2 rounded-r-full" style={{ width: `${(low / total) * 100}%` }} title={t("page.exec_dashboard.quality_segment", { label: tr("page.exec_dashboard.quality_low", "Low"), count: low })} />}
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>
          </>
        ) : null}
      </div>

      {data?.impact_projection && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="ukip-panel-soft overflow-hidden p-6">
            <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="ukip-kicker">{tr("page.exec_dashboard.impact_projection_eyebrow", "Monte Carlo projection")}</p>
                <h3 className="mt-1 text-lg font-bold text-[var(--ukip-text-strong)]">
                  {tr("page.exec_dashboard.impact_projection_title", "Impact Projection")}
                </h3>
                <p className="mt-2 max-w-2xl text-sm text-[var(--ukip-muted)]">
                  {data.impact_projection.explanation}
                </p>
              </div>
              <div className="rounded-3xl border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-7 py-5 text-center shadow-sm">
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--ukip-muted)]">
                  {tr("page.exec_dashboard.impact_expected", "Expected")}
                </p>
                <p className="mt-1 text-4xl font-black text-[var(--ukip-text-strong)]">
                  {data.impact_projection.score}
                </p>
                <p className="text-xs text-[var(--ukip-muted)]">/100</p>
              </div>
            </div>
            <div className="mt-6">
              <div className="relative h-3 rounded-full bg-gray-200 dark:bg-gray-800">
                <div
                  className="absolute top-0 h-3 rounded-full bg-violet-300/40"
                  style={{
                    left: `${data.impact_projection.range.p10}%`,
                    width: `${Math.max(2, data.impact_projection.range.p90 - data.impact_projection.range.p10)}%`,
                  }}
                />
                <div
                  className="absolute top-1/2 h-5 w-5 -translate-y-1/2 rounded-full border-4 border-white bg-violet-600 shadow-lg dark:border-gray-950"
                  style={{ left: `calc(${data.impact_projection.score}% - 10px)` }}
                />
              </div>
              <div className="mt-3 flex items-center justify-between text-xs text-[var(--ukip-muted)]">
                <span>{tr("page.exec_dashboard.impact_conservative", "Conservative")} {data.impact_projection.conservative}</span>
                <span>{tr("page.exec_dashboard.impact_probable_range", "Probable range")} {data.impact_projection.range.p10}–{data.impact_projection.range.p90}</span>
                <span>{tr("page.exec_dashboard.impact_optimistic", "Optimistic")} {data.impact_projection.optimistic}</span>
              </div>
            </div>
          </div>
          <div className="ukip-panel-soft p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="ukip-kicker">{tr("page.exec_dashboard.impact_brief_connection", "Brief connection")}</p>
                <h3 className="mt-1 text-base font-bold text-[var(--ukip-text-strong)]">
                  {tr("page.exec_dashboard.impact_brief_angle", "Narrative angle")}
                </h3>
              </div>
              <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                {translateConfidence(data.impact_projection.confidence)} · {data.impact_projection.confidence_score}/100
              </span>
            </div>
            <p className="mt-4 text-sm font-semibold text-[var(--ukip-text-strong)]">
              {data.impact_projection.recommendation}
            </p>
            <p className="mt-3 text-sm text-[var(--ukip-muted)]">
              {data.impact_projection.brief_angle}
            </p>
            <Link
              href={briefBuilderHref}
              className="mt-5 inline-flex rounded-xl bg-violet-600 px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-violet-500"
            >
              {tr("page.exec_dashboard.open_brief_with_projection", "Open brief with projection")}
            </Link>
          </div>
        </div>
      )}

      {data?.hidden_patterns && data.hidden_patterns.patterns.length > 0 && (
        <div className="ukip-panel-soft p-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="ukip-kicker">{tr("page.exec_dashboard.hidden_patterns_eyebrow", "Pattern discovery")}</p>
              <h3 className="mt-1 text-lg font-bold text-[var(--ukip-text-strong)]">
                {tr("page.exec_dashboard.hidden_patterns_title", "Hidden Patterns")}
              </h3>
              <p className="mt-2 max-w-2xl text-sm text-[var(--ukip-muted)]">
                {tr("page.exec_dashboard.hidden_patterns_body", "Non-obvious clusters, outliers, gaps and graph signals detected from the current portfolio.")}
              </p>
            </div>
            <div className="rounded-2xl border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-4 py-3 text-sm font-bold text-[var(--ukip-text-strong)]">
              {data.hidden_patterns.summary.patterns_found} {tr("page.exec_dashboard.hidden_patterns_found", "signals")}
            </div>
          </div>
          <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-3">
            {data.hidden_patterns.patterns.slice(0, 6).map((pattern) => (
              <div key={pattern.id} className="rounded-2xl border border-[var(--ukip-border)] bg-[var(--ukip-panel)] p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--ukip-muted)]">
                      {translatePatternType(pattern.type)}
                    </p>
                    <h4 className="mt-1 text-sm font-bold text-[var(--ukip-text-strong)]">{pattern.label}</h4>
                  </div>
                  <span className="rounded-full bg-violet-100 px-2.5 py-1 text-[11px] font-bold text-violet-700 dark:bg-violet-500/15 dark:text-violet-300">
                    {translateConfidence(pattern.confidence)}
                  </span>
                </div>
                <p className="mt-3 text-xs leading-5 text-[var(--ukip-muted)]">{pattern.evidence}</p>
                <div className="mt-4">
                  <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--ukip-muted)]">
                    <span>{tr("page.exec_dashboard.hidden_patterns_impact", "Impact")}</span>
                    <span>{pattern.impact_score}</span>
                  </div>
                  <div className="mt-2 h-2 rounded-full bg-gray-200 dark:bg-gray-800">
                    <div className="h-2 rounded-full bg-violet-500" style={{ width: `${pattern.impact_score}%` }} />
                  </div>
                </div>
                <p className="mt-4 text-xs font-semibold text-[var(--ukip-text-strong)]">
                  {pattern.recommended_action}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      <AgenticResearchChat
        domainId={activeDomainId}
        title={tr("page.exec_dashboard.agentic_chat_title", "Ask your research portfolio")}
      />

      {/* ── Section 2: Impact Over Time ── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <h3 className="mb-1 text-base font-semibold text-gray-900 dark:text-white">
          {tr("page.exec_dashboard.entities_over_time", "Entities Over Time")}
        </h3>
        <p className="mb-5 ukip-kicker">{tr("page.exec_dashboard.temporal_signal", "Temporal signal")}</p>
        {loading ? (
          <SkeletonCard lines={4} />
        ) : !data || data.entities_by_year.length === 0 ? (
          <div className="flex h-52 items-center justify-center text-sm text-gray-400">
            {tr("page.exec_dashboard.no_date_data", "No date data available — upload entities with a creation_date field.")}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={data.entities_by_year} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gradEntities" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
              <XAxis dataKey="year" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "#6b7280" }} />
              <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "#6b7280" }} />
              <Tooltip
                contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)", fontSize: "12px" }}
                formatter={(v) => [(Number(v) || 0).toLocaleString(), tr("page.exec_dashboard.tooltip.entities", "Entities")]}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#8b5cf6"
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#gradEntities)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ── Section 3: Brand × Year Heatmap ── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
              {tr("page.exec_dashboard.emerging_signals", "Emerging Topic Signals")}
            </h3>
            <p className="mt-1 ukip-kicker">{tr("page.exec_dashboard.acceleration", "Acceleration")}</p>
          </div>
          {data?.emerging_topic_signals?.is_experimental && (
            <span className="rounded-full bg-gray-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-600 dark:bg-gray-800 dark:text-gray-300">
              {tr("page.exec_dashboard.experimental", "Experimental")}
            </span>
          )}
        </div>
        {loading ? (
          <SkeletonCard lines={3} />
        ) : !data ? null : data.emerging_topic_signals.signals.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50/80 p-5 dark:border-gray-800 dark:bg-gray-950/30">
            <p className="text-sm font-semibold text-gray-700 dark:text-gray-200">
              {tr("page.exec_dashboard.experimental_note_title", "Experimental module waiting for stronger signal")}
            </p>
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              {tr("page.exec_dashboard.no_signals", "No reliable early signals yet. UKIP needs concept coverage across multiple years before surfacing acceleration.")}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            {data.emerging_topic_signals.signals.map((signal) => (
              <div
                key={signal.concept}
                className={`rounded-2xl border p-5 shadow-sm ${signalToneStyles[signal.confidence]}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.18em] opacity-70">
                      {tr("page.exec_dashboard.experimental", "Experimental")}
                    </p>
                    <p className="text-base font-semibold">{signal.concept}</p>
                  </div>
                  <span className="rounded-full bg-white/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-current dark:bg-gray-900/60">
                    {translateConfidence(signal.confidence)}
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-3 text-center">
                  <div className="rounded-xl bg-white/80 p-3 dark:bg-gray-900/70">
                    <p className="text-xs opacity-70">{tr("page.exec_dashboard.acceleration", "Acceleration")}</p>
                    <p className="mt-1 text-lg font-semibold">+{signal.acceleration_score}%</p>
                  </div>
                  <div className="rounded-xl bg-white/80 p-3 dark:bg-gray-900/70">
                    <p className="text-xs opacity-70">{tr("page.exec_dashboard.recent_share", "Recent share")}</p>
                    <p className="mt-1 text-lg font-semibold">{signal.recent_share}%</p>
                  </div>
                  <div className="rounded-xl bg-white/80 p-3 dark:bg-gray-900/70">
                    <p className="text-xs opacity-70">{tr("page.exec_dashboard.baseline_share", "Baseline share")}</p>
                    <p className="mt-1 text-lg font-semibold">{signal.baseline_share}%</p>
                  </div>
                </div>
                <p className="mt-4 text-sm opacity-90">{signal.evidence}</p>
              </div>
            ))}
          </div>
        )}
        {!!data?.emerging_topic_signals?.recent_years.length && !!data?.emerging_topic_signals?.baseline_years.length && (
          <p className="mt-4 text-xs text-gray-500 dark:text-gray-400">
            {t("page.exec_dashboard.comparing_ranges", {
              recentStart: data.emerging_topic_signals.recent_years[0],
              recentEnd: data.emerging_topic_signals.recent_years[data.emerging_topic_signals.recent_years.length - 1],
              baselineStart: data.emerging_topic_signals.baseline_years[0],
              baselineEnd: data.emerging_topic_signals.baseline_years[data.emerging_topic_signals.baseline_years.length - 1],
            })}
          </p>
        )}
      </div>

      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <h3 className="mb-1 text-base font-semibold text-gray-900 dark:text-white">
          {tr("page.exec_dashboard.top_labels_by_year", "Top Primary Labels by Year")}
        </h3>
        <p className="mb-5 ukip-kicker">{tr("page.exec_dashboard.density_map", "Density map")}</p>
        {loading ? (
          <SkeletonCard lines={3} />
        ) : !data || data.brand_year_matrix.brands.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-sm text-gray-400">
            {tr("common.no_data", "No data available")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr>
                  <th className="border border-gray-100 bg-gray-50 px-3 py-2 text-xs font-semibold text-gray-500 dark:border-gray-800 dark:bg-gray-800 dark:text-gray-400">
                    {tr("page.exec_dashboard.label", "Label")}
                  </th>
                  {data.brand_year_matrix.years.map((yr) => (
                    <th
                      key={yr}
                      className="border border-gray-100 bg-gray-50 px-3 py-2 text-center text-xs font-semibold text-gray-500 dark:border-gray-800 dark:bg-gray-800 dark:text-gray-400"
                    >
                      {yr}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.brand_year_matrix.brands.map((brand, bi) => (
                  <tr key={brand}>
                    <td className="border border-gray-100 px-3 py-2 text-xs font-semibold text-gray-700 dark:border-gray-800 dark:text-gray-200">
                      {brand}
                    </td>
                    {data.brand_year_matrix.matrix[bi].map((val, yi) => (
                      <HeatCell key={yi} value={val} max={heatMax} />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Section 4: Concept Cloud ── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
              {tr("page.exec_dashboard.knowledge_concept_map", "Knowledge Concept Map")}
            </h3>
            <p className="ukip-kicker">{tr("page.exec_dashboard.semantic_signal", "Semantic signal")}</p>
          </div>
          {data && (
            <Link
              href="/analytics/topics"
              className="text-xs font-medium text-violet-600 hover:text-violet-700 dark:text-violet-400"
            >
              {tr("page.exec_dashboard.full_analysis", "Full analysis →")}
            </Link>
          )}
        </div>
        {loading ? (
          <SkeletonCard lines={2} />
        ) : (
          <ConceptCloud concepts={data?.top_concepts ?? []} maxItems={40} />
        )}
      </div>

      {/* ── Section 5: Top Entities by Citations ── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
              {tr("page.exec_dashboard.top_entities_impact", "Top Entities by Impact")}
            </h3>
            <p className="ukip-kicker">{tr("page.exec_dashboard.impact_rank", "Impact rank")}</p>
          </div>
            <Link
              href={enrichedExplorerHref}
              className="text-xs font-medium text-violet-600 hover:text-violet-700 dark:text-violet-400"
            >
              {tr("page.exec_dashboard.view_all", "View all →")}
          </Link>
        </div>
        {loading ? (
          <SkeletonCard lines={4} />
        ) : !data || data.top_entities.length === 0 ? (
          <div className="flex h-32 items-center justify-center text-sm text-gray-400">
            {tr("page.exec_dashboard.no_top_entities", "No enriched entities yet. Run enrichment to populate this table.")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-800">
                  <th className="pb-3 pr-4 text-xs font-semibold uppercase tracking-wide text-gray-500">#</th>
                  <th className="pb-3 pr-4 text-xs font-semibold uppercase tracking-wide text-gray-500">{tr("page.exec_dashboard.entity", "Entity")}</th>
                  <th className="pb-3 pr-4 text-xs font-semibold uppercase tracking-wide text-gray-500">{tr("page.exec_dashboard.primary_label", "Primary Label")}</th>
                  <th className="pb-3 pr-4 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">{tr("page.exec_dashboard.citations", "Citations")}</th>
                  <th className="pb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">{tr("page.exec_dashboard.source", "Source")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                {data.top_entities.map((e, i) => (
                  <tr key={e.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                    <td className="py-3 pr-4 text-xs font-bold text-gray-400">{i + 1}</td>
                    <td className="py-3 pr-4">
                      <Link
                        href={`/entities/${e.id}`}
                        className="text-sm font-medium text-gray-900 hover:text-violet-600 dark:text-white dark:hover:text-violet-400"
                      >
                        {e.entity_name || e.primary_label || `Entity #${e.id}`}
                      </Link>
                    </td>
                    <td className="py-3 pr-4 text-sm text-gray-500 dark:text-gray-400">
                      {e.brand || e.primary_label || "—"}
                    </td>
                    <td className="py-3 pr-4 text-right">
                      <span className="text-sm font-bold text-violet-600 dark:text-violet-400">
                        {e.citation_count.toLocaleString()}
                      </span>
                    </td>
                    <td className="py-3">
                      <SourceBadge source={e.source} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
