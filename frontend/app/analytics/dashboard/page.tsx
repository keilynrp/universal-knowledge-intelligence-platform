"use client";

import type { ReactNode } from "react";
import { useState, useEffect, useCallback, useMemo, useRef } from "react";
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
import { ErrorBanner, SkeletonCard, useToast } from "../../components/ui";
import ConceptCloud from "../../components/ConceptCloud";
import { useDomain } from "../../contexts/DomainContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { apiFetch } from "@/lib/api";
import { Analytics } from "@/lib/analytics";

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
  external_attention?: {
    summary: {
      active_entities: number;
      avg_attention_score: number;
      total_mentions: number;
      top_score: number;
    };
    top_entities: {
      id: number;
      label: string;
      attention_score: number;
      category: string;
      total_mentions: number;
      active_sources: number;
      last_seen_at: string | null;
    }[];
    alerts: {
      type: string;
      severity: "low" | "medium" | "high";
      confidence: "low" | "medium" | "high";
      label: string;
      evidence: string;
      period: string | null;
      priority: number;
      entity_id: number;
      entity_label: string;
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

function stripInlineHtml(value: string): string {
  return value
    .replace(/<\s*br\s*\/?\s*>/gi, " ")
    .replace(/<\s*\/?\s*(sup|sub|i|em|b|strong|span)\b[^>]*>/gi, "")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

const showcaseCardClass = "rounded-2xl border border-[var(--ukip-border)] bg-white shadow-[0_16px_50px_rgb(91_72_163/0.05)]";
const showcaseSectionClass = `${showcaseCardClass} p-5`;
const showcaseLabelClass = "text-[11px] font-semibold uppercase tracking-[0.12em] text-violet-600";
const showcaseBlueLabelClass = "text-[11px] font-semibold uppercase tracking-[0.12em] text-blue-600";

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
    <div className="rounded-xl border border-[var(--ukip-border)] bg-white p-5">
      <div className="flex items-start gap-3">
        <NarrativeIcon name={icon} tone={tone} />
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">{label}</p>
          <p className="mt-4 text-4xl font-semibold leading-none tracking-normal text-slate-950">{value}</p>
          <p className="mt-2 text-sm text-slate-500">{description}</p>
          {footer ? <div className="mt-3">{footer}</div> : null}
        </div>
      </div>
    </div>
  );
}

function ReferenceRing({ value, label }: { value: number; label: string }) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const boundedValue = Math.max(0, Math.min(100, value));
  const offset = circumference * (1 - boundedValue / 100);

  return (
    <div className="relative h-48 w-48">
      <svg className="h-full w-full -rotate-90" viewBox="0 0 100 100" aria-hidden="true">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#eadcff" strokeWidth="8" />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke="#7c3aed"
          strokeLinecap="round"
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <p className="text-5xl font-semibold text-violet-600">{Math.round(boundedValue)}%</p>
        <p className="mt-1 text-xs font-medium text-slate-600">{label}</p>
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
  const dashboardRequestId = useRef(0);
  const importedFlag = searchParams.get("imported") === "1";
  const importedDomain = searchParams.get("domain");
  const importedRows = searchParams.get("rows");
  const dashboardDomainId = importedDomain || "all";
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
    const requestId = dashboardRequestId.current + 1;
    dashboardRequestId.current = requestId;
    if (preserveData) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);
    try {
      const params = new URLSearchParams({
        domain_id: dashboardDomainId,
        _sync: `${Date.now()}-${requestId}`,
      });
      if (selectedBenchmarkProfile) params.set("profile_id", selectedBenchmarkProfile);
      if (forceRefresh) params.set("force_refresh", "true");
      const res = await apiFetch(`/dashboard/summary?${params.toString()}`, {
        cache: "no-store",
        headers: {
          "Cache-Control": "no-cache",
          "Pragma": "no-cache",
        },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const nextData = await res.json();
      if (dashboardRequestId.current === requestId) {
        setData(nextData);
        setCountdown(REFRESH_INTERVAL_SEC);
      }
    } catch (error: unknown) {
      if (dashboardRequestId.current === requestId) {
        setError(error instanceof Error ? error.message : tr("page.exec_dashboard.dashboard_load_failed", "Failed to load dashboard"));
      }
    } finally {
      if (dashboardRequestId.current === requestId) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [dashboardDomainId, selectedBenchmarkProfile, tr]);

  useEffect(() => { void fetchDashboard({ forceRefresh: true }); }, [fetchDashboard]);

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
    Analytics.dashboardExportPDF(dashboardDomainId);
    try {
      const res = await apiFetch("/exports/pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain_id: dashboardDomainId,
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
      a.download = `dashboard_${dashboardDomainId}_${new Date().toISOString().slice(0, 10)}.pdf`;
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
      if (dashboardDomainId) {
        params.set("domain_id", dashboardDomainId);
      }
      const response = await apiFetch(`/enrich/bulk?${params.toString()}`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      const queuedIds = Array.isArray(payload.queued_ids)
        ? payload.queued_ids.filter((id: unknown): id is number => typeof id === "number")
        : [];
      toast(
        t("page.exec_dashboard.bulk_enrich_success", { count: payload.queued_records ?? 0 }),
        "success",
      );
      if (queuedIds.length === 0) {
        await fetchDashboard({ forceRefresh: true, preserveData: true });
        return;
      }

      for (let attempt = 0; attempt < 80; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const progress = await apiFetch("/enrich/progress", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids: queuedIds }),
        });
        if (!progress.ok) break;
        const status = await progress.json();
        if ((status.pending ?? 0) + (status.processing ?? 0) === 0) {
          await fetchDashboard({ forceRefresh: true, preserveData: true });
          break;
        }
      }
    } catch {
      toast(tr("page.exec_dashboard.bulk_enrich_failed", "Bulk enrichment could not be queued."), "error");
    } finally {
      setQueueingBulkEnrichment(false);
    }
  }, [dashboardDomainId, fetchDashboard, t, toast, tr]);

  // Compute heatmap max for scaling
  const heatMax = data
    ? Math.max(1, ...data.brand_year_matrix.matrix.flat())
    : 1;
  const briefBuilderHref = `/reports?preset=pilot-brief&domain=${encodeURIComponent(dashboardDomainId)}&rows=${encodeURIComponent(importedRows ?? String(data?.kpis.total_entities ?? 0))}&format=pdf&benchmark_profile=${encodeURIComponent(selectedBenchmarkProfile)}&title=${encodeURIComponent(`UKIP Pilot Brief — ${dashboardDomainId}`)}`;
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
    violet: "border-violet-200 bg-violet-50 text-violet-900",
    amber: "border-amber-200 bg-amber-50 text-amber-900",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-900",
  };
  const leadingGap = data?.institutional_benchmark?.top_gaps?.[0] ?? null;
  const signalToneStyles: Record<"high" | "medium" | "low", string> = {
    high: "border-emerald-200 bg-emerald-50 text-emerald-900",
    medium: "border-violet-200 bg-violet-50 text-violet-900",
    low: "border-amber-200 bg-amber-50 text-amber-900",
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
    <main className="min-h-screen bg-[radial-gradient(circle_at_22%_0%,rgba(124,58,237,0.08),transparent_28%),linear-gradient(180deg,#fbfbff_0%,#ffffff_52%,#fbfbff_100%)] px-5 py-7 text-[var(--ukip-text)] sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1240px] space-y-6">
        <header className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-semibold tracking-normal text-slate-950">
                {tr("page.exec_dashboard.title", "Executive Dashboard")}
              </h1>
              <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--ukip-border)] bg-white text-violet-500">
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M11.48 3.499a.6.6 0 011.04 0l2.125 3.78 4.252.85a.6.6 0 01.321 1.008l-2.946 3.18.5 4.31a.6.6 0 01-.841.619L12 15.42l-3.93 1.826a.6.6 0 01-.842-.619l.5-4.31-2.946-3.18a.6.6 0 01.321-1.008l4.252-.85 2.125-3.78z" />
                </svg>
              </span>
            </div>
            <p className="mt-3 text-sm text-slate-500">
              {tr("page.exec_dashboard.description", "Signal, readiness, impact, and next action.")}
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            {/* Auto-refresh toggle */}
            <button
              onClick={() => setAutoRefresh(v => !v)}
              title={autoRefresh ? `${tr("page.exec_dashboard.auto_refresh_active", "Auto-refresh on")} — next in ${mm}:${ss}` : tr("page.exec_dashboard.auto_refresh_enable", "Enable auto-refresh every 5 min")}
              className={`inline-flex h-11 items-center gap-2 rounded-lg border px-4 text-sm font-medium shadow-sm transition ${
                autoRefresh
                  ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400"
                  : "border-[var(--ukip-border)] bg-white text-[var(--ukip-text)] hover:bg-violet-50"
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
              className="inline-flex h-11 items-center gap-2 rounded-lg border border-[var(--ukip-border)] bg-white px-5 text-sm font-medium text-[var(--ukip-text)] transition hover:bg-violet-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <svg className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
              {refreshing
                ? tr("page.exec_dashboard.refreshing", "Refreshing...")
                : tr("page.exec_dashboard.refresh", "Refresh")}
            </button>

            <button
              type="button"
              onClick={() => {
                if (typeof navigator !== "undefined" && navigator.share) {
                  void navigator.share({ title: tr("page.exec_dashboard.title", "Executive Dashboard"), url: window.location.href });
                } else if (typeof navigator !== "undefined" && navigator.clipboard) {
                  void navigator.clipboard.writeText(window.location.href);
                  toast(tr("page.exec_dashboard.share_link_copied", "Dashboard link copied."), "success");
                }
              }}
              className="inline-flex h-11 items-center gap-2 rounded-lg border border-[var(--ukip-border)] bg-white px-5 text-sm font-medium text-[var(--ukip-text)] transition hover:bg-violet-50"
            >
              <svg className="h-4 w-4" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.935-2.186 2.25 2.25 0 00-3.935 2.186z" />
              </svg>
              {tr("page.exec_dashboard.share", "Compartir")}
            </button>

            {/* Export Dashboard PDF */}
            <button
              onClick={handleExportPDF}
              disabled={exporting || loading || !data}
              className="inline-flex h-11 items-center gap-2 rounded-lg border border-violet-600 bg-violet-600 px-5 text-sm font-medium text-white shadow-[0_12px_26px_rgb(124_58_237/0.22)] transition hover:bg-violet-700 disabled:opacity-50"
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
        </header>

      {error && <ErrorBanner message={error} onRetry={fetchDashboard} variant="card" />}

      {data && (
        <div className={showcaseSectionClass}>
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <p className={showcaseLabelClass}>{tr("page.exec_dashboard.executive_signal", "Señal ejecutiva")}</p>
              <h2 className="mt-1 text-xl font-semibold text-slate-950">
                {tr("page.exec_dashboard.story_title", "La historia del portafolio en una lectura")}
              </h2>
            </div>
            <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] ${readinessStatusTone}`}>
              {executiveStoryStatus}
            </span>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.1fr_1fr_1fr_1fr_1fr]">
            <div className="relative overflow-hidden rounded-xl border border-violet-200 bg-violet-50 p-5">
              <div className="absolute right-4 top-4 h-24 w-24 rounded-full bg-violet-200/70 blur-xl" />
              <div className="flex items-start justify-between gap-3">
                <NarrativeIcon name="eye" />
                <span className="rounded-full bg-white/80 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-violet-700 shadow-sm">
                  {tr("page.exec_dashboard.observation_badge", "Observación")}
                </span>
              </div>
              <h3 className="relative mt-5 text-xl font-semibold text-slate-950">
                {tr("page.exec_dashboard.observation_title", "Panorama actual")}
              </h3>
              <p className="relative mt-1 text-xs leading-5 text-slate-600">
                {executiveStoryLine}
              </p>
              <div className="relative mt-5 h-12">
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
            <div className="rounded-xl border border-[var(--ukip-border)] bg-white p-5">
              <div className="flex items-start gap-3">
                <NarrativeIcon name={leadingGap ? "alert" : "check"} tone={leadingGap ? "amber" : "emerald"} />
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                    {tr("page.exec_dashboard.benchmark_leading_gap", "Principal restricción actual")}
                  </p>
                  <p className="mt-4 text-base font-semibold leading-5 text-slate-950">
                    {leadingGap ? translateRuleLabel(leadingGap.id, leadingGap.label) : tr("page.exec_dashboard.no_active_gap", "Sin restricción activa")}
                  </p>
                  <p className="mt-1 text-sm text-slate-500">
                    {leadingGap ? translateBenchmarkEvidence(data.institutional_benchmark.profile_id, leadingGap) : tr("page.exec_dashboard.story_clear_path", "La evidencia permite avanzar hacia recomendación ejecutiva.")}
                  </p>
                  <Link href={nextPilotStep.href} className="mt-5 inline-flex rounded-lg bg-violet-600 px-4 py-3 text-xs font-semibold text-white transition hover:bg-violet-700">
                    {nextPilotStep.cta}
                  </Link>
                </div>
              </div>
            </div>
          </div>

          {executiveStoryAction && (
            <div className="mt-5 rounded-xl border border-violet-200 bg-violet-50/60 p-5">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div className="flex items-start gap-3">
                  <NarrativeIcon name="spark" tone="violet" />
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-violet-600">
                      {tr("page.exec_dashboard.elevator_pitch", "Elevator pitch analítico")}
                    </p>
                    <p className="mt-2 text-sm font-semibold text-slate-950">{executiveStoryAction.title}</p>
                    <p className="mt-1 text-xs leading-5 text-slate-600">{executiveStoryAction.evidence}</p>
                  </div>
                </div>
                <Link href={briefBuilderHref} className="inline-flex shrink-0 rounded-lg border border-[var(--ukip-border)] bg-white px-4 py-2 text-xs font-semibold text-violet-600 transition hover:bg-violet-50">
                  {tr("page.exec_dashboard.view_story_recommendations", "Ver recomendaciones estratégicas")}
                </Link>
              </div>
            </div>
          )}
        </div>
      )}

      {importedFlag && (
        <div className="flex flex-col gap-4 rounded-xl border border-violet-200 bg-violet-50 px-6 py-5 text-sm font-medium text-violet-700 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-sm font-semibold text-violet-800">
                {tr("page.exec_dashboard.fresh_import_title", "Fresh import ready for pilot review")}
              </p>
              <p className="mt-1 text-sm text-violet-700">
                {tr("page.exec_dashboard.fresh_import_description", "Check coverage, impact, and next actions.")}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                href={briefBuilderHref}
                className="rounded-lg bg-white px-5 py-3 text-sm font-semibold text-violet-600 shadow-sm"
              >
                {tr("page.import.success.open_brief", "Prepare Executive Brief")}
              </Link>
              <Link
                href={latestImportExplorerHref}
                className="rounded-lg border border-violet-200 bg-white/70 px-5 py-3 text-sm font-semibold text-violet-600"
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
        <div className={`${showcaseCardClass} p-6`}>
          <p className={showcaseLabelClass}>{tr("page.exec_dashboard.benchmark_baseline", "Línea base de referencia institucional")}</p>
          <div className="mt-6 grid gap-6 xl:grid-cols-[1.35fr_0.75fr_1fr]">
            <div className="min-w-0 xl:border-r xl:border-slate-200 xl:pr-8">
              <h2 className="text-2xl font-semibold tracking-normal text-slate-950">
                {translateBenchmarkProfileName(
                  data.institutional_benchmark.profile_id,
                  data.institutional_benchmark.profile_name,
                )}
              </h2>
              <span className="mt-4 inline-flex rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold uppercase text-violet-600">
                {translateBenchmarkStatus(data.institutional_benchmark.status)}
              </span>
              <div className="mt-5 max-w-xl">
                <label className="block text-sm font-medium text-slate-700">
                  {tr("page.exec_dashboard.benchmark_profile", "Perfil de referencia")}
                </label>
                <select
                  value={selectedBenchmarkProfile}
                  onChange={(e) => setSelectedBenchmarkProfile(e.target.value)}
                  className="mt-2 h-12 w-full rounded-lg border border-[var(--ukip-border)] bg-white px-4 text-sm text-slate-700 outline-none focus:border-violet-300 focus:ring-2 focus:ring-violet-100"
                >
                  {benchmarkProfiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {translateBenchmarkProfileName(profile.id, profile.name)}
                    </option>
                  ))}
                </select>
              </div>
              <p className="mt-5 text-sm font-medium text-violet-700">
                {t("page.exec_dashboard.readiness_summary", {
                  readiness: data.institutional_benchmark.readiness_pct,
                  passed: data.institutional_benchmark.passed_rules,
                  total: data.institutional_benchmark.total_rules,
                })}
              </p>
              <div className="mt-7 rounded-xl border border-[var(--ukip-border)] bg-white p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-base font-semibold text-slate-950">
                    {leadingGap ? translateRuleLabel(leadingGap.id, leadingGap.label) : tr("page.exec_dashboard.no_active_gap", "Sin restricción activa")}
                  </p>
                  {leadingGap && (
                    <span className="rounded-md bg-orange-100 px-2 py-1 text-xs font-semibold uppercase text-orange-500">
                      {translatePriority(leadingGap.priority)}
                    </span>
                  )}
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-500">
                  {leadingGap
                    ? translateBenchmarkEvidence(data.institutional_benchmark.profile_id, leadingGap)
                    : tr("page.exec_dashboard.story_clear_path", "La evidencia permite avanzar hacia recomendación ejecutiva.")}
                </p>
              </div>
            </div>

            <div className="flex flex-col items-center justify-center border-slate-200 xl:border-r xl:px-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                {tr("page.exec_dashboard.benchmark_score", "Puntaje de referencia")}
              </p>
              <ReferenceRing
                value={data.institutional_benchmark.readiness_pct}
                label={tr("page.exec_dashboard.benchmark_percentile", "Percentil")}
              />
            </div>

            <div className="min-w-0 xl:pl-2">
              <p className="text-sm font-semibold text-violet-700">
                {tr("page.exec_dashboard.rules_currently_met", "Reglas actualmente satisfechas")}
              </p>
              <div className="mt-5 space-y-5">
                {data.institutional_benchmark.top_gaps.slice(0, 3).map((gap) => (
                  <div key={gap.id} className="flex items-center gap-3">
                    <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm ${
                      gap.passed
                        ? "border-emerald-300 bg-emerald-50 text-emerald-600"
                        : "border-slate-200 bg-white text-slate-300"
                    }`}>
                      ✓
                    </span>
                    <span className="text-sm text-slate-600">{translateRuleLabel(gap.id, gap.label)}</span>
                  </div>
                ))}
                {data.institutional_benchmark.top_gaps.length === 0 && (
                  <p className="rounded-xl border border-dashed border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
                    {tr("page.exec_dashboard.all_rules_met", "Todas las reglas principales están satisfechas.")}
                  </p>
                )}
              </div>
            </div>
          </div>

          {decisionHighlights.length > 0 && (
            <div className="mt-8 grid grid-cols-1 gap-5 xl:grid-cols-3">
              {decisionHighlights.slice(0, 3).map((highlight) => (
                <div
                  key={highlight.title}
                  className={`rounded-xl border p-5 ${toneStyles[highlight.tone]}`}
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-violet-500">
                    {tr("page.exec_dashboard.suggested_next_action", "Acción sugerida")}
                  </p>
                  <p className="mt-2 text-sm font-semibold text-slate-950">{highlight.title}</p>
                  <p className="mt-2 text-xs leading-5 text-slate-600">{highlight.evidence}</p>
                  <p className="mt-4 text-xs font-semibold text-slate-800">
                    {tr("page.exec_dashboard.expected_impact", "Impacto esperado: +6-12pp")}
                  </p>
                  {highlight.id === "bulk_enrichment" && (
                    <button
                      onClick={handleBulkEnrichment}
                      disabled={queueingBulkEnrichment}
                      className="mt-4 inline-flex h-10 items-center rounded-lg bg-white px-4 text-xs font-semibold text-slate-900 transition hover:bg-violet-50 disabled:cursor-not-allowed disabled:opacity-60"
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
        </div>
      )}





      {/* ── Section 1: Signal KPIs ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} lines={2} />)
        ) : data ? (
          <>
            <StoryMetricCard
              icon="route"
              tone="cyan"
              label={tr("page.exec_dashboard.kpi.total_entities", "Total Entities")}
              value={data.kpis.total_entities.toLocaleString()}
              description={tr("page.exec_dashboard.volume_signal", "Volume")}
            />
            <StoryMetricCard
              icon="target"
              tone="violet"
              label={tr("page.exec_dashboard.kpi.avg_citations", "Avg Citations")}
              value={data.kpis.avg_citations}
              description={tr("page.exec_dashboard.impact_signal", "Impact")}
            />
            <StoryMetricCard
              icon="spark"
              tone="amber"
              label={tr("page.exec_dashboard.kpi.distinct_concepts", "Distinct Concepts")}
              value={data.kpis.total_concepts.toLocaleString()}
              description={tr("page.exec_dashboard.semantic_signal", "Semantic signal")}
            />
            {/* Quality KPI */}
            <div className="rounded-xl border border-[var(--ukip-border)] bg-white p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-500/10">
                  <svg className="h-5 w-5 text-violet-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                  </svg>
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">{tr("page.exec_dashboard.kpi.avg_quality", "Avg Quality")}</p>
                  <p className="mt-4 text-4xl font-semibold leading-none tracking-normal text-slate-950">
                    {data.quality?.average != null ? `${Math.round(data.quality.average * 100)}%` : "—"}
                  </p>
                  <p className="mt-2 text-sm text-slate-500">{tr("page.exec_dashboard.quality_signal", "Confidence")}</p>
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



      {(data?.impact_projection || (data?.hidden_patterns && data.hidden_patterns.patterns.length > 0)) && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          {data?.impact_projection && (
          <div className={`${showcaseCardClass} overflow-hidden p-6`}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className={showcaseLabelClass}>{tr("page.exec_dashboard.impact_projection_eyebrow", "Monte Carlo projection")}</p>
                <h3 className="mt-1 text-lg font-semibold text-slate-950">
                  {tr("page.exec_dashboard.impact_projection_title", "Impact Projection")}
                </h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  {data.impact_projection.explanation}
                </p>
              </div>
              <div className="shrink-0 rounded-xl border border-[var(--ukip-border)] bg-white px-5 py-4 text-center">
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  {tr("page.exec_dashboard.impact_expected", "Expected")}
                </p>
                <p className="mt-1 text-4xl font-semibold text-slate-950">
                  {data.impact_projection.score}
                </p>
                <p className="text-xs text-slate-500">/100</p>
              </div>
            </div>
            <div className="mt-6">
              <div className="relative h-28">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={storySparklineData} margin={{ top: 8, right: 4, left: 4, bottom: 0 }}>
                    <defs>
                      <linearGradient id="impactMiniFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.28} />
                        <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="count" stroke="#8b5cf6" strokeWidth={2.5} fill="url(#impactMiniFill)" dot={{ r: 2, fill: "#8b5cf6", strokeWidth: 0 }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <div className="relative mt-3 h-3 rounded-full bg-slate-100">
                <div
                  className="absolute top-0 h-3 rounded-full bg-violet-300/40"
                  style={{
                    left: `${data.impact_projection.range.p10}%`,
                    width: `${Math.max(2, data.impact_projection.range.p90 - data.impact_projection.range.p10)}%`,
                  }}
                />
                <div
                  className="absolute top-1/2 h-5 w-5 -translate-y-1/2 rounded-full border-4 border-white bg-violet-600 shadow-lg"
                  style={{ left: `calc(${data.impact_projection.score}% - 10px)` }}
                />
              </div>
              <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                <span>{tr("page.exec_dashboard.impact_conservative", "Conservative")} {data.impact_projection.conservative}</span>
                <span>{tr("page.exec_dashboard.impact_probable_range", "Probable range")} {data.impact_projection.range.p10}–{data.impact_projection.range.p90}</span>
                <span>{tr("page.exec_dashboard.impact_optimistic", "Optimistic")} {data.impact_projection.optimistic}</span>
              </div>
            </div>
          </div>
          )}
          {data?.impact_projection && (
          <div className={`${showcaseCardClass} p-6`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className={showcaseLabelClass}>{tr("page.exec_dashboard.impact_brief_connection", "Brief connection")}</p>
                <h3 className="mt-1 text-base font-semibold text-slate-950">
                  {tr("page.exec_dashboard.impact_brief_angle", "Narrative angle")}
                </h3>
              </div>
              <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">
                {translateConfidence(data.impact_projection.confidence)} · {data.impact_projection.confidence_score}/100
              </span>
            </div>
            <p className="mt-4 text-sm font-semibold text-slate-950">
              {data.impact_projection.recommendation}
            </p>
            <p className="mt-3 text-sm text-slate-500">
              {data.impact_projection.brief_angle}
            </p>
            <Link
              href={briefBuilderHref}
              className="mt-5 inline-flex h-11 items-center rounded-lg bg-violet-600 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-violet-500"
            >
              {tr("page.exec_dashboard.open_brief_with_projection", "Open brief with projection")}
            </Link>
          </div>
          )}
          {data?.hidden_patterns && data.hidden_patterns.patterns.length > 0 && (
            <div className={`${showcaseCardClass} p-6`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className={showcaseLabelClass}>{tr("page.exec_dashboard.hidden_patterns_eyebrow", "Distribución de impacto")}</p>
                  <h3 className="mt-1 text-lg font-semibold text-slate-950">
                    {tr("page.exec_dashboard.hidden_patterns_title", "Patrones ocultos")}
                  </h3>
                </div>
                <span className="rounded-full border border-[var(--ukip-border)] bg-white px-3 py-1 text-xs font-semibold text-slate-600">
                  {data.hidden_patterns.summary.patterns_found} {tr("page.exec_dashboard.hidden_patterns_found", "señales")}
                </span>
              </div>
              <p className="mt-4 text-sm leading-6 text-slate-500">
                {tr("page.exec_dashboard.hidden_patterns_body", "Clústeres, valores atípicos, brechas y señales de grano no evidentes.")}
              </p>
              <div className="mt-5 space-y-3">
                {data.hidden_patterns.patterns.slice(0, 3).map((pattern) => (
                  <div key={pattern.id} className="grid grid-cols-[1fr_auto] gap-3 rounded-xl bg-slate-50 px-4 py-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-800">{pattern.label}</p>
                      <p className="mt-1 text-xs text-slate-500">{translatePatternType(pattern.type)}</p>
                    </div>
                    <span className="text-right text-sm text-slate-500">
                      {pattern.impact_score >= 70 ? tr("page.exec_dashboard.high_impact", "Alto impacto") : tr("page.exec_dashboard.medium_impact", "Medio impacto")}
                    </span>
                  </div>
                ))}
              </div>
              <Link href="/analytics/dashboard" className="mt-5 inline-flex w-full justify-end text-sm font-semibold text-violet-600 hover:text-violet-700">
                {tr("page.exec_dashboard.view_all_signals", "Ver todas las señales")}
              </Link>
            </div>
          )}
        </div>
      )}



      {/* ── Section 2: Impact Over Time ── */}
      <div className={`${showcaseCardClass} p-6`}>
        <h3 className="mb-1 text-base font-semibold text-slate-950">
          {tr("page.exec_dashboard.entities_over_time", "Entities Over Time")}
        </h3>
        <p className={`mb-5 ${showcaseBlueLabelClass}`}>{tr("page.exec_dashboard.temporal_signal", "Temporal signal")}</p>
        {loading ? (
          <SkeletonCard lines={4} />
        ) : !data || data.entities_by_year.length === 0 ? (
          <div className="flex h-52 items-center justify-center text-sm text-slate-400">
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
      <div className={`${showcaseCardClass} p-6`}>
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-slate-950">
              {tr("page.exec_dashboard.emerging_signals", "Emerging Topic Signals")}
            </h3>
            <p className={`mt-1 ${showcaseBlueLabelClass}`}>{tr("page.exec_dashboard.acceleration", "Acceleration")}</p>
          </div>
          {data?.emerging_topic_signals?.is_experimental && (
            <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600">
              {tr("page.exec_dashboard.experimental", "Experimental")}
            </span>
          )}
        </div>
        {loading ? (
          <SkeletonCard lines={3} />
        ) : !data ? null : data.emerging_topic_signals.signals.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[var(--ukip-border)] bg-slate-50/80 p-5">
            <p className="text-sm font-semibold text-slate-700">
              {tr("page.exec_dashboard.experimental_note_title", "Experimental module waiting for stronger signal")}
            </p>
            <p className="mt-2 text-sm text-slate-500">
              {tr("page.exec_dashboard.no_signals", "No reliable early signals yet. UKIP needs concept coverage across multiple years before surfacing acceleration.")}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            {data.emerging_topic_signals.signals.map((signal) => (
              <div
                key={signal.concept}
                className={`rounded-xl border p-5 ${signalToneStyles[signal.confidence]}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] opacity-70">
                      {tr("page.exec_dashboard.experimental", "Experimental")}
                    </p>
                    <p className="text-base font-semibold">{signal.concept}</p>
                  </div>
                  <span className="rounded-full bg-white/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-current">
                    {translateConfidence(signal.confidence)}
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-3 text-center">
                  <div className="rounded-xl bg-white/80 p-3">
                    <p className="text-xs opacity-70">{tr("page.exec_dashboard.acceleration", "Acceleration")}</p>
                    <p className="mt-1 text-lg font-semibold">+{signal.acceleration_score}%</p>
                  </div>
                  <div className="rounded-xl bg-white/80 p-3">
                    <p className="text-xs opacity-70">{tr("page.exec_dashboard.recent_share", "Recent share")}</p>
                    <p className="mt-1 text-lg font-semibold">{signal.recent_share}%</p>
                  </div>
                  <div className="rounded-xl bg-white/80 p-3">
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
          <p className="mt-4 text-xs text-slate-500">
            {t("page.exec_dashboard.comparing_ranges", {
              recentStart: data.emerging_topic_signals.recent_years[0],
              recentEnd: data.emerging_topic_signals.recent_years[data.emerging_topic_signals.recent_years.length - 1],
              baselineStart: data.emerging_topic_signals.baseline_years[0],
              baselineEnd: data.emerging_topic_signals.baseline_years[data.emerging_topic_signals.baseline_years.length - 1],
            })}
          </p>
        )}
      </div>

      <div className={`${showcaseCardClass} p-6`}>
        <h3 className="mb-1 text-base font-semibold text-slate-950">
          {tr("page.exec_dashboard.top_labels_by_year", "Top Primary Labels by Year")}
        </h3>
        <p className={`mb-5 ${showcaseBlueLabelClass}`}>{tr("page.exec_dashboard.density_map", "Density map")}</p>
        {loading ? (
          <SkeletonCard lines={3} />
        ) : !data || data.brand_year_matrix.brands.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-sm text-slate-400">
            {tr("common.no_data", "No data available")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr>
                  <th className="border border-slate-100 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-500">
                    {tr("page.exec_dashboard.label", "Label")}
                  </th>
                  {data.brand_year_matrix.years.map((yr) => (
                    <th
                      key={yr}
                      className="border border-slate-100 bg-slate-50 px-3 py-2 text-center text-xs font-semibold text-slate-500"
                    >
                      {yr}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.brand_year_matrix.brands.map((brand, bi) => (
                  <tr key={brand}>
                    <td className="border border-slate-100 px-3 py-2 text-xs font-semibold text-slate-700">
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
      <div className={`${showcaseCardClass} p-6`}>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-slate-950">
              {tr("page.exec_dashboard.knowledge_concept_map", "Knowledge Concept Map")}
            </h3>
            <p className={showcaseBlueLabelClass}>{tr("page.exec_dashboard.semantic_signal", "Semantic signal")}</p>
          </div>
          {data && (
            <Link
              href="/analytics/topics"
              className="text-xs font-medium text-violet-600 hover:text-violet-700"
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
      <div className={`${showcaseCardClass} p-6`}>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-slate-950">
              {tr("page.exec_dashboard.top_entities_impact", "Top Entities by Impact")}
            </h3>
            <p className={showcaseBlueLabelClass}>{tr("page.exec_dashboard.impact_rank", "Impact rank")}</p>
          </div>
            <Link
              href={enrichedExplorerHref}
              className="text-xs font-medium text-violet-600 hover:text-violet-700"
            >
              {tr("page.exec_dashboard.view_all", "View all →")}
          </Link>
        </div>
        {loading ? (
          <SkeletonCard lines={4} />
        ) : !data || data.top_entities.length === 0 ? (
          <div className="flex h-32 items-center justify-center text-sm text-slate-400">
            {tr("page.exec_dashboard.no_top_entities", "No enriched entities yet. Run enrichment to populate this table.")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100">
                  <th className="pb-3 pr-4 text-xs font-semibold uppercase tracking-wide text-slate-500">#</th>
                  <th className="pb-3 pr-4 text-xs font-semibold uppercase tracking-wide text-slate-500">{tr("page.exec_dashboard.entity", "Entity")}</th>
                  <th className="pb-3 pr-4 text-xs font-semibold uppercase tracking-wide text-slate-500">{tr("page.exec_dashboard.primary_label", "Primary Label")}</th>
                  <th className="pb-3 pr-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">{tr("page.exec_dashboard.citations", "Citations")}</th>
                  <th className="pb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">{tr("page.exec_dashboard.source", "Source")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.top_entities.map((e, i) => (
                  <tr key={e.id} className="hover:bg-violet-50/40">
                    <td className="py-3 pr-4 text-xs font-bold text-slate-400">{i + 1}</td>
                    <td className="py-3 pr-4">
                      <Link
                        href={`/entities/${e.id}`}
                        className="text-sm font-medium text-slate-950 hover:text-violet-600"
                      >
                        {stripInlineHtml(e.entity_name || e.primary_label || `Entity #${e.id}`)}
                      </Link>
                    </td>
                    <td className="py-3 pr-4 text-sm text-slate-500">
                      {stripInlineHtml(e.brand || e.primary_label || "-")}
                    </td>
                    <td className="py-3 pr-4 text-right">
                      <span className="text-sm font-bold text-violet-600">
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
    </main>
  );
}
