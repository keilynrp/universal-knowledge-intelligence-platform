"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { PageHeader, Badge } from "../components/ui";
import PilotFlowCard from "../components/PilotFlowCard";
import { apiFetch } from "../../lib/api";
import { useDomain } from "../contexts/DomainContext";
import { useToast } from "../components/ui";
import { useLanguage } from "../contexts/LanguageContext";
import {
  getStoredPilotPersona,
  pilotPersonaToStakeholder,
  type StakeholderProfile,
} from "../lib/pilotPersona";

// ── Template types ─────────────────────────────────────────────────────────────

interface ArtifactTemplate {
  id: number;
  name: string;
  description: string;
  sections: string[];
  default_title: string;
  is_builtin: boolean;
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface Section {
  id: string;
  label: string;
}

interface BenchmarkProfile {
  id: string;
  name: string;
  description: string;
  region: string;
  rules_count: number;
  is_default: boolean;
}

const SECTION_ICONS: Record<string, string> = {
  institutional_benchmark: "🏛️",
  impact_projection: "📈",
  hidden_patterns: "🔎",
  agentic_trace: "🤖",
  entity_stats:         "📊",
  enrichment_coverage:  "🔬",
  decision_recommendations: "🧭",
  top_brands:           "🏷️",
  topic_clusters:       "🧩",
  harmonization_log:    "⚙️",
};

// ── Format types ──────────────────────────────────────────────────────────────

type ExportFormat = "html" | "pdf" | "excel" | "pptx";

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const { activeDomainId, setActiveDomainId } = useDomain();
  const { toast } = useToast();
  const { t } = useLanguage();
  const tr = useCallback((key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  }, [t]);
  const searchParams = useSearchParams();

  const [sections, setSections] = useState<Section[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [title, setTitle] = useState("");
  const [format, setFormat] = useState<ExportFormat>("html");
  const [generating, setGenerating] = useState(false);
  const [loadingSections, setLoadingSections] = useState(true);

  // Templates panel
  const [templates, setTemplates] = useState<ArtifactTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [newTemplateName, setNewTemplateName] = useState("");
  const [presetApplied, setPresetApplied] = useState(false);
  const [benchmarkProfiles, setBenchmarkProfiles] = useState<BenchmarkProfile[]>([]);
  const [selectedBenchmarkProfile, setSelectedBenchmarkProfile] = useState("research_portfolio_baseline");
  const [selectedStakeholderProfile, setSelectedStakeholderProfile] = useState<StakeholderProfile>("leadership");
  const [rememberedPersonaLabel, setRememberedPersonaLabel] = useState<string | null>(null);

  const preset = searchParams.get("preset");
  const presetDomain = searchParams.get("domain");
  const importedRows = searchParams.get("rows");
  const presetTitle = searchParams.get("title");
  const presetFormat = searchParams.get("format");
  const presetBenchmarkProfile = searchParams.get("benchmark_profile");
  const presetStakeholderProfile = searchParams.get("stakeholder");
  const presetSections = useMemo(() => {
    const explicit = searchParams.get("sections");
    if (explicit) {
      return explicit.split(",").map((value) => value.trim()).filter(Boolean);
    }
    if (preset === "pilot-brief") {
      return ["entity_stats", "enrichment_coverage", "impact_projection", "hidden_patterns", "agentic_trace", "decision_recommendations", "institutional_benchmark", "top_brands", "topic_clusters"];
    }
    return [];
  }, [preset, searchParams]);
  const sectionDescriptions = useMemo<Record<string, string>>(() => ({
    institutional_benchmark: tr("page.reports.section.institutional_benchmark", "Institutional readiness baseline with explicit framework gaps"),
    impact_projection: tr("page.reports.section.impact_projection", "Monte Carlo impact projection with probable range and brief angle"),
    hidden_patterns: tr("page.reports.section.hidden_patterns", "Explainable hidden signals: clusters, outliers, gaps, bridges, and duplicates"),
    agentic_trace: tr("page.reports.section.agentic_trace", "Saved agentic chat answers with sources, tools, and audit trace"),
    entity_stats: tr("page.reports.section.entity_stats", "Total entities, validation status breakdown, distribution chart"),
    enrichment_coverage: tr("page.reports.section.enrichment_coverage", "Coverage %, average citations, top enriched entities"),
    decision_recommendations: tr("page.reports.section.decision_recommendations", "Short, explainable next actions derived from current KPI signals"),
    top_brands: tr("page.reports.section.top_brands", "Top 15 primary labels or classifications by entity count"),
    topic_clusters: tr("page.reports.section.topic_clusters", "Most frequent concepts from enrichment data"),
    harmonization_log: tr("page.reports.section.harmonization_log", "Last 10 harmonization steps with status"),
  }), [tr]);
  const formatOptions: { value: ExportFormat; label: string; desc: string; icon: string }[] = useMemo(() => ([
    { value: "html",  label: "HTML",       desc: tr("page.reports.format.html", "Preview in browser, Ctrl+P to print"), icon: "🌐" },
    { value: "pdf",   label: "PDF",        desc: tr("page.reports.format.pdf", "Professional branded PDF download"), icon: "📄" },
    { value: "excel", label: "Excel",      desc: tr("page.reports.format.excel", "Multi-sheet workbook with KPIs, entities & concepts"), icon: "📊" },
    { value: "pptx",  label: "PowerPoint", desc: tr("page.reports.format.pptx", "Branded slide deck for presentations"), icon: "📑" },
  ]), [tr]);
  const stakeholderOptions: { value: StakeholderProfile; label: string; desc: string }[] = useMemo(() => ([
    {
      value: "leadership",
      label: t("page.reports.stakeholder.leadership.label"),
      desc: t("page.reports.stakeholder.leadership.desc"),
    },
    {
      value: "research_office",
      label: t("page.reports.stakeholder.research_office.label"),
      desc: t("page.reports.stakeholder.research_office.desc"),
    },
    {
      value: "library",
      label: t("page.reports.stakeholder.library.label"),
      desc: t("page.reports.stakeholder.library.desc"),
    },
    {
      value: "innovation",
      label: t("page.reports.stakeholder.innovation.label"),
      desc: t("page.reports.stakeholder.innovation.desc"),
    },
  ]), [t]);
  const activeStakeholder = stakeholderOptions.find((option) => option.value === selectedStakeholderProfile) ?? stakeholderOptions[0];
  const stakeholderReadingPoints = useMemo(() => ([
    t(`page.reports.stakeholder.${selectedStakeholderProfile}.point1`),
    t(`page.reports.stakeholder.${selectedStakeholderProfile}.point2`),
    t(`page.reports.stakeholder.${selectedStakeholderProfile}.point3`),
  ]), [selectedStakeholderProfile, t]);
  const stakeholderNarrativeGoal = useMemo(
    () => t(`page.reports.stakeholder.${selectedStakeholderProfile}.goal`),
    [selectedStakeholderProfile, t],
  );
  const activeBenchmarkProfile = useMemo(
    () => benchmarkProfiles.find((profile) => profile.id === selectedBenchmarkProfile) ?? null,
    [benchmarkProfiles, selectedBenchmarkProfile],
  );
  const benchmarkProfileNarrative = useMemo(() => {
    if (!activeBenchmarkProfile) {
      return t("page.reports.benchmark_profile_pending");
    }
    return t("page.reports.benchmark_profile_summary", {
      name: activeBenchmarkProfile.name,
      rules: activeBenchmarkProfile.rules_count,
      region: activeBenchmarkProfile.region,
    });
  }, [activeBenchmarkProfile, t]);
  const briefChecklist = useMemo(() => {
    const hasEnoughSections = selected.size >= 4;
    const usingBriefPreset = preset === "pilot-brief";
    const hasTitle = title.trim().length > 0;

    return [
      {
        key: "preset",
        done: usingBriefPreset,
        label: t("page.reports.brief_checklist.preset"),
      },
      {
        key: "sections",
        done: hasEnoughSections,
        label: t("page.reports.brief_checklist.sections", { count: selected.size }),
      },
      {
        key: "title",
        done: hasTitle,
        label: t("page.reports.brief_checklist.title", { title: hasTitle ? title.trim() : t("page.reports.brief_checklist.title_missing") }),
      },
      {
        key: "format",
        done: format === "pdf" || format === "pptx" || format === "html",
        label: t("page.reports.brief_checklist.format", { format: format.toUpperCase() }),
      },
    ];
  }, [format, preset, selected.size, t, title]);
  const briefReady = briefChecklist.filter((item) => item.done).length >= 3;
  const pilotExitSummary = useMemo(() => {
    if (briefReady) {
      return {
        tone: "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-100",
        title: tr("page.reports.exit_summary.ready_title", "This brief is in a good state for a stakeholder session"),
        body: tr("page.reports.exit_summary.ready_body", "You already have enough structure to generate a credible pilot artifact. Use the final pass mainly to tighten framing and audience fit."),
      };
    }
    return {
      tone: "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-100",
      title: tr("page.reports.exit_summary.pending_title", "This brief still needs a little framing before you share it"),
      body: tr("page.reports.exit_summary.pending_body", "Complete the missing checklist items so the exported artifact reads as intentional rather than exploratory."),
    };
  }, [briefReady, tr]);
  const presetHref = `/reports?preset=pilot-brief&domain=${encodeURIComponent(activeDomainId)}&format=pdf&benchmark_profile=${encodeURIComponent(selectedBenchmarkProfile)}&stakeholder=${encodeURIComponent(selectedStakeholderProfile)}`;
  const reportOverviewCards = useMemo(() => ([
    {
      title: t("page.reports.overview.story_title"),
      body: t("page.reports.overview.story_body"),
    },
    {
      title: t("page.reports.overview.sections_title"),
      body: t("page.reports.overview.sections_body"),
    },
    {
      title: t("page.reports.overview.output_title"),
      body: t("page.reports.overview.output_body"),
    },
  ]), [t]);
  const configSummary = useMemo(() => {
    const sectionCount = sections.length;
    const selectedFormat = formatOptions.find((option) => option.value === format);

    return [
      {
        label: t("page.reports.summary.sections"),
        value: `${selected.size}/${sectionCount || 0}`,
        detail: selected.size >= 4
          ? t("page.reports.summary.sections_ready")
          : t("page.reports.summary.sections_light"),
      },
      {
        label: t("page.reports.summary.audience"),
        value: activeStakeholder.label,
        detail: activeStakeholder.desc,
      },
      {
        label: t("page.reports.summary.output"),
        value: format.toUpperCase(),
        detail: selectedFormat?.desc ?? "",
      },
    ];
  }, [activeStakeholder.desc, activeStakeholder.label, format, formatOptions, sections.length, selected.size, t]);

  // Fetch available sections from backend
  const loadSections = useCallback(async () => {
    try {
      const res = await apiFetch("/reports/sections");
      if (res.ok) {
        const data: Section[] = await res.json();
        setSections(data);
        setSelected(new Set(data.map((s) => s.id)));
      }
    } finally {
      setLoadingSections(false);
    }
  }, []);

  useEffect(() => { loadSections(); }, [loadSections]);

  useEffect(() => {
    let cancelled = false;
    const loadProfiles = async () => {
      const res = await apiFetch("/analytics/benchmarks/profiles");
      if (!res.ok) return;
      const data: BenchmarkProfile[] = await res.json();
      if (!cancelled) {
        setBenchmarkProfiles(data);
        if (!presetBenchmarkProfile) {
          const defaultProfile = data.find((profile) => profile.is_default)?.id ?? data[0]?.id;
          if (defaultProfile) setSelectedBenchmarkProfile(defaultProfile);
        }
      }
    };
    loadProfiles();
    return () => { cancelled = true; };
  }, [presetBenchmarkProfile]);

  useEffect(() => {
    if (presetDomain && presetDomain !== activeDomainId) {
      setActiveDomainId(presetDomain);
    }
  }, [activeDomainId, presetDomain, setActiveDomainId]);

  useEffect(() => {
    if (loadingSections || presetApplied || sections.length === 0) return;
    if (!preset && !presetTitle && !presetFormat && presetSections.length === 0) return;

    const validSections = presetSections.filter((sectionId) =>
      sections.some((section) => section.id === sectionId),
    );
    if (validSections.length > 0) {
      setSelected(new Set(validSections));
    }
    if (presetTitle) {
      setTitle(presetTitle);
    }
    if (presetFormat === "pdf" || presetFormat === "html" || presetFormat === "excel" || presetFormat === "pptx") {
      setFormat(presetFormat);
    }
    if (presetBenchmarkProfile) {
      setSelectedBenchmarkProfile(presetBenchmarkProfile);
    }
    if (
      presetStakeholderProfile === "leadership"
      || presetStakeholderProfile === "research_office"
      || presetStakeholderProfile === "library"
      || presetStakeholderProfile === "innovation"
    ) {
      setSelectedStakeholderProfile(presetStakeholderProfile);
    }
    setPresetApplied(true);
  }, [loadingSections, presetApplied, preset, presetBenchmarkProfile, presetFormat, presetSections, presetStakeholderProfile, presetTitle, sections]);

  useEffect(() => {
    if (presetStakeholderProfile) return;
    const storedPersona = getStoredPilotPersona();
    if (!storedPersona) return;
    setSelectedStakeholderProfile(pilotPersonaToStakeholder(storedPersona));
    setRememberedPersonaLabel(t(`welcome.persona.${storedPersona}.label`));
  }, [presetStakeholderProfile, t]);

  const loadTemplates = useCallback(async () => {
    if (templates.length > 0) return; // already loaded
    setLoadingTemplates(true);
    try {
      const res = await apiFetch("/artifacts/templates");
      if (res.ok) setTemplates(await res.json());
    } finally {
      setLoadingTemplates(false);
    }
  }, [templates.length]);

  const applyTemplate = (tpl: ArtifactTemplate) => {
    setSelected(new Set(tpl.sections));
    if (tpl.default_title) setTitle(tpl.default_title);
    setShowTemplates(false);
    toast(`${tr("page.reports.toast.template_applied", "Template applied")}: "${tpl.name}"`, "success");
  };

  const saveAsTemplate = async () => {
    if (!newTemplateName.trim()) {
      toast(tr("page.reports.toast.enter_template_name", "Enter a template name"), "warning");
      return;
    }
    setSavingTemplate(true);
    try {
      const res = await apiFetch("/artifacts/templates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newTemplateName.trim(),
          sections: Array.from(selected),
          default_title: title || "",
          description: "",
        }),
      });
      if (res.ok) {
        const created = await res.json();
        setTemplates((prev) => [...prev, created]);
        setNewTemplateName("");
        toast(tr("page.reports.toast.template_saved", "Template saved"), "success");
      } else {
        const err = await res.text();
        toast(`${tr("page.reports.toast.template_save_failed", "Failed to save template")}: ${err}`, "error");
      }
    } finally {
      setSavingTemplate(false);
    }
  };

  const toggleSection = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });

  const selectAll = () => setSelected(new Set(sections.map((s) => s.id)));
  const clearAll  = () => setSelected(new Set());

  const handleGenerate = async () => {
    if (selected.size === 0) {
      toast(tr("page.reports.toast.select_section", "Select at least one section"), "warning");
      return;
    }
    setGenerating(true);
    try {
      const endpoint =
        format === "pdf"   ? "/exports/pdf"     :
        format === "excel" ? "/exports/excel"   :
        format === "pptx"  ? "/exports/pptx"    :
                             "/reports/generate";

      const res = await apiFetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain_id: activeDomainId || "default",
          sections: Array.from(selected),
          title: title.trim() || null,
          benchmark_profile_id: selectedBenchmarkProfile,
          stakeholder_profile: selectedStakeholderProfile,
        }),
      });
      if (!res.ok) {
        const err = await res.text();
        toast(`${tr("page.reports.toast.generation_failed", "Generation failed")}: ${err}`, "error");
        return;
      }

      const buffer = await res.arrayBuffer();
      const mimeType =
        format === "pdf"   ? "application/pdf" :
        format === "excel" ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" :
        format === "pptx"  ? "application/vnd.openxmlformats-officedocument.presentationml.presentation" :
                             "text/html";
      const blob = new Blob([buffer], { type: mimeType });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      const cd   = res.headers.get("Content-Disposition") ?? "";
      const match = cd.match(/filename="([^"]+)"/);
      const defaultName =
        format === "pdf"   ? "ukip_report.pdf"  :
        format === "excel" ? "ukip_report.xlsx" :
        format === "pptx"  ? "ukip_report.pptx" :
                             "ukip_report.html";
      a.href     = url;
      a.download = match ? match[1] : defaultName;
      a.click();
      URL.revokeObjectURL(url);
      toast(tr("page.reports.toast.downloaded", "Report downloaded"), "success");
    } catch {
      toast(tr("page.reports.toast.generate_error", "Failed to generate report"), "error");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumbs={[
          { label: t('page.reports.breadcrumb_home'), href: "/" },
          { label: t('page.reports.breadcrumb_analytics'), href: "/analytics" },
          { label: t('page.reports.title') },
        ]}
        title={t('page.reports.title')}
        description={t('page.reports.description')}
        actions={
          <button
            onClick={handleGenerate}
            disabled={generating || selected.size === 0}
            className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {generating ? (
              <>
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {t('page.reports.generating')}
              </>
            ) : (
              <>
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
                {t('page.reports.generate_button')}
              </>
            )}
          </button>
        }
      />

      <PilotFlowCard
        currentStep="brief"
        tone="emerald"
        title={t("page.reports.guided.title")}
        body={preset === "pilot-brief"
          ? t("page.reports.guided.brief")
          : t("page.reports.guided.default")}
        primaryCta={preset === "pilot-brief"
          ? {
              href: "/analytics/dashboard",
              label: t("page.reports.guided.cta_dashboard"),
            }
          : {
              href: presetHref,
              label: t("page.reports.guided.cta_preset"),
            }}
        secondaryCta={{
          href: "/",
          label: t("page.reports.guided.cta_explorer"),
        }}
      />

      <div className={`rounded-2xl border px-5 py-4 ${pilotExitSummary.tone}`}>
        <div className="grid gap-3 lg:grid-cols-[1.15fr_0.85fr]">
          <div>
            <p className="text-sm font-semibold">{pilotExitSummary.title}</p>
            <p className="mt-1 text-xs opacity-80">{pilotExitSummary.body}</p>
          </div>
          <div className="rounded-xl bg-white/70 px-4 py-3 text-xs shadow-sm dark:bg-gray-950/30">
            <p className="font-semibold">{tr("page.reports.exit_summary.audience", "Primary audience")}</p>
            <p className="mt-1 opacity-80">{activeStakeholder.label}</p>
            <p className="mt-3 font-semibold">{tr("page.reports.exit_summary.format", "Output")}</p>
            <p className="mt-1 opacity-80">{format.toUpperCase()} · {selected.size} {tr("page.reports.exit_summary.sections", "sections selected")}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        {reportOverviewCards.map((card) => (
          <div
            key={card.title}
            className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900"
          >
            <p className="text-sm font-semibold text-gray-900 dark:text-white">
              {card.title}
            </p>
            <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">
              {card.body}
            </p>
          </div>
        ))}
      </div>

      {preset === "pilot-brief" && (
        <div className="rounded-2xl border border-blue-200 bg-gradient-to-r from-blue-50 to-indigo-50 p-5 shadow-sm dark:border-blue-500/20 dark:from-blue-500/5 dark:to-indigo-500/5">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-sm font-semibold text-blue-900 dark:text-blue-200">
                {t("page.reports.pilot_preset_loaded")}
              </p>
              <p className="mt-1 text-sm text-blue-700 dark:text-blue-300">
                {importedRows
                  ? `${Number(importedRows).toLocaleString()} ${t("page.reports.imported_entities")}`
                  : t("page.reports.this_dataset")}{" "}
                {t("page.reports.pilot_preset_hint.before_domain")}{" "}
                <span className="font-semibold">{presetDomain ?? activeDomainId}</span>{" "}
                {t("page.reports.pilot_preset_hint.after_domain")}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {[
                  t("page.reports.preset_badge.baseline"),
                  t("page.reports.preset_badge.coverage"),
                  t("page.reports.preset_badge.actions"),
                  t("page.reports.preset_badge.benchmark"),
                  t("page.reports.preset_badge.concentration"),
                  t("page.reports.preset_badge.concepts"),
                ].map((item) => (
                  <span
                    key={item}
                    className="rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-blue-700 shadow-sm dark:bg-gray-900/80 dark:text-blue-300"
                  >
                    {item}
                  </span>
                ))}
              </div>
            </div>
            <div className="rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-blue-700 dark:bg-gray-900/80 dark:text-blue-300">
              {t("page.reports.summary.output")}: {format.toUpperCase()}
            </div>
          </div>
        </div>
      )}

      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 shadow-sm dark:border-emerald-900/40 dark:bg-emerald-950/20">
        <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_auto]">
          <div className="grid gap-2 sm:grid-cols-2">
            {briefChecklist.map((item) => (
              <div
                key={item.key}
                className="flex items-center gap-2 rounded-xl bg-white/80 px-3 py-2 text-sm text-emerald-900 shadow-sm dark:bg-gray-900/80 dark:text-emerald-100"
              >
                <span className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-xs font-bold ${
                  item.done
                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                    : "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300"
                }`}>
                  {item.done ? "✓" : "!"}
                </span>
                <span>{item.label}</span>
              </div>
            ))}
          </div>
          <div className="rounded-xl bg-white/80 px-4 py-3 text-sm text-emerald-900 shadow-sm dark:bg-gray-900/80 dark:text-emerald-100">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700 dark:text-emerald-300">
              {t("page.reports.brief_ready.eyebrow")}
            </p>
            <p className="mt-1 font-semibold">
              {briefReady
                ? t("page.reports.brief_ready.yes")
                : t("page.reports.brief_ready.no")}
            </p>
            <p className="mt-1 text-xs text-emerald-800 dark:text-emerald-200">
              {briefReady
                ? t("page.reports.brief_ready.yes_hint")
                : t("page.reports.brief_ready.no_hint")}
            </p>
          </div>
        </div>
      </div>

      {/* Templates panel */}
      <div className="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900">
        <button
          onClick={() => { setShowTemplates((v) => !v); if (!showTemplates) loadTemplates(); }}
          className="flex w-full items-center justify-between px-5 py-4 text-left"
        >
          <div className="flex items-center gap-2">
            <span className="text-base">📐</span>
            <div>
              <span className="text-sm font-semibold text-gray-900 dark:text-white">{t('page.reports.templates_panel_title')}</span>
              <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{t("page.reports.templates_panel_help")}</p>
            </div>
            {templates.length > 0 && (
              <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-500/20 dark:text-blue-300">
                {templates.length}
              </span>
            )}
          </div>
          <svg
            className={`h-4 w-4 text-gray-400 transition-transform ${showTemplates ? "rotate-180" : ""}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {showTemplates && (
          <div className="border-t border-gray-100 px-5 pb-5 pt-4 dark:border-gray-800">
            {loadingTemplates ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-20 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
                ))}
              </div>
            ) : templates.length === 0 ? (
              <p className="text-sm text-gray-400 dark:text-gray-500">{t('page.reports.no_templates')}</p>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {templates.map((tpl) => (
                  <button
                    key={tpl.id}
                    onClick={() => applyTemplate(tpl)}
                    className="flex flex-col items-start rounded-xl border border-gray-200 bg-gray-50 p-4 text-left transition-all hover:border-blue-300 hover:bg-blue-50 dark:border-gray-700 dark:bg-gray-800 dark:hover:border-blue-500/40 dark:hover:bg-blue-500/10"
                  >
                    <div className="flex w-full items-center justify-between gap-2">
                      <span className="text-sm font-medium text-gray-900 dark:text-white">{tpl.name}</span>
                      {tpl.is_builtin && (
                        <span className="shrink-0 rounded-full bg-gray-200 px-1.5 py-0.5 text-xs text-gray-500 dark:bg-gray-700 dark:text-gray-400">
                          {t("page.reports.builtin_badge")}
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400 line-clamp-2">{tpl.description}</p>
                    <span className="mt-2 rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-500/20 dark:text-blue-300">
                      {t("page.reports.template_sections_count", { count: tpl.sections.length })}
                    </span>
                  </button>
                ))}
              </div>
            )}

            {/* Save as template */}
            {selected.size > 0 && (
              <div className="mt-4 flex items-center gap-2 border-t border-gray-100 pt-4 dark:border-gray-800">
                <input
                  type="text"
                  value={newTemplateName}
                  onChange={(e) => setNewTemplateName(e.target.value)}
                  placeholder={t("page.reports.template_name_placeholder")}
                  className="flex-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:placeholder-gray-500"
                />
                <button
                  onClick={saveAsTemplate}
                  disabled={savingTemplate || !newTemplateName.trim()}
                  className="inline-flex items-center gap-1 rounded-lg border border-blue-300 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50 dark:border-blue-500/40 dark:bg-blue-500/10 dark:text-blue-300"
                >
                  {savingTemplate ? t('page.reports.template_saving') : t('page.reports.template_save_button')}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        {/* Section picker */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
              {t('page.reports.sections_title')}
              <span className="ml-2 text-xs font-normal text-gray-400">
                {t("page.reports.sections_selected_summary", { selected: selected.size, total: sections.length })}
              </span>
            </h2>
            <div className="flex gap-2">
              <button onClick={selectAll} className="text-xs text-blue-600 hover:underline dark:text-blue-400">{t('page.reports.select_all_button')}</button>
              <span className="text-gray-300 dark:text-gray-700">·</span>
              <button onClick={clearAll} className="text-xs text-gray-500 hover:underline dark:text-gray-400">{t('page.reports.select_none_button')}</button>
            </div>
          </div>

          {loadingSections ? (
            <div className="flex justify-center py-16">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {sections.map((sec) => {
                const isOn = selected.has(sec.id);
                return (
                  <button
                    key={sec.id}
                    onClick={() => toggleSection(sec.id)}
                    className={`group flex items-start gap-4 rounded-2xl border p-5 text-left transition-all ${
                      isOn
                        ? "border-blue-300 bg-blue-50 dark:border-blue-500/40 dark:bg-blue-500/10"
                        : "border-gray-200 bg-white hover:border-gray-300 dark:border-gray-700 dark:bg-gray-900 dark:hover:border-gray-600"
                    }`}
                  >
                    {/* Checkbox */}
                    <div className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border-2 transition-colors ${
                      isOn
                        ? "border-blue-600 bg-blue-600"
                        : "border-gray-300 bg-white dark:border-gray-600 dark:bg-gray-800"
                    }`}>
                      {isOn && (
                        <svg className="h-3 w-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-base">{SECTION_ICONS[sec.id] ?? "📋"}</span>
                        <span className={`text-sm font-medium ${isOn ? "text-blue-700 dark:text-blue-300" : "text-gray-900 dark:text-white"}`}>
                          {sec.label}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        {sectionDescriptions[sec.id] ?? ""}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Configuration panel */}
        <div className="space-y-4">
          {/* Report title */}
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
            <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">{t('page.reports.config_title')}</h3>
            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">
                  {t('page.reports.title_label')}
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder={t("page.reports.title_placeholder", { domain: activeDomainId || "default" })}
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:placeholder-gray-500"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">
                  {t('page.reports.domain_label')}
                </label>
                <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-700 dark:bg-gray-800">
                  <span className="text-sm text-gray-700 dark:text-gray-300">{activeDomainId || "default"}</span>
                  <Badge variant="info" size="sm">{t('page.reports.domain_active_badge')}</Badge>
                </div>
                <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">{t('page.reports.domain_help')}</p>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">
                  {t("page.reports.benchmark_profile_label")}
                </label>
                <select
                  value={selectedBenchmarkProfile}
                  onChange={(e) => setSelectedBenchmarkProfile(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                >
                  {benchmarkProfiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                  {t("page.reports.benchmark_profile_help")}
                </p>
                <div className="mt-3 rounded-xl border border-violet-200 bg-violet-50 px-3 py-3 text-xs text-violet-900 dark:border-violet-900/40 dark:bg-violet-950/30 dark:text-violet-100">
                  <p className="font-semibold">
                    {t("page.reports.benchmark_profile_active")}
                  </p>
                  <p className="mt-1">{benchmarkProfileNarrative}</p>
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">
                  {t("page.reports.stakeholder.label")}
                </label>
                <select
                  value={selectedStakeholderProfile}
                  onChange={(e) => setSelectedStakeholderProfile(e.target.value as StakeholderProfile)}
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                >
                  {stakeholderOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                  {t("page.reports.stakeholder.help")}
                </p>
                <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-3 text-xs text-emerald-900 dark:border-emerald-900/40 dark:bg-emerald-950/30 dark:text-emerald-100">
                  <p className="font-semibold">
                    {activeStakeholder.label}
                  </p>
                  <p className="mt-1">{activeStakeholder.desc}</p>
                  {!presetStakeholderProfile && rememberedPersonaLabel && (
                    <p className="mt-2 text-[11px] text-emerald-800 dark:text-emerald-200">
                      {t("page.reports.stakeholder.recommended_from_persona", { persona: rememberedPersonaLabel })}
                    </p>
                  )}
                </div>
                <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-200">
                  <p className="font-semibold text-slate-900 dark:text-slate-100">
                    {t("page.reports.stakeholder.reading_title")}
                  </p>
                  <ul className="mt-2 space-y-1.5 pl-4">
                    {stakeholderReadingPoints.map((point) => (
                      <li key={point} className="list-disc leading-5">
                        {point}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-3 text-[11px] text-slate-600 dark:text-slate-300">
                    <span className="font-semibold">{t("page.reports.stakeholder.goal_label")}</span>{" "}
                    {stakeholderNarrativeGoal}
                  </p>
                </div>
              </div>
              <div className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-3 text-xs text-sky-900 dark:border-sky-900/40 dark:bg-sky-950/30 dark:text-sky-100">
                <p className="font-semibold">
                  {t("page.reports.summary.title")}
                </p>
                <div className="mt-3 space-y-2">
                  {configSummary.map((item) => (
                    <div
                      key={item.label}
                      className="rounded-lg bg-white/80 px-3 py-2 shadow-sm dark:bg-gray-900/70"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
                          {item.label}
                        </span>
                        <span className="text-sm font-semibold text-sky-950 dark:text-sky-50">
                          {item.value}
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] leading-5 text-sky-800 dark:text-sky-200">
                        {item.detail}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Preview of what's included */}
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
            <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">{t('page.reports.included_sections_title')}</h3>
            {selected.size === 0 ? (
              <p className="text-xs text-gray-400 dark:text-gray-500">{t('page.reports.no_sections_selected')}</p>
            ) : (
              <ol className="space-y-2">
                {sections
                  .filter((s) => selected.has(s.id))
                  .map((s, i) => (
                    <li key={s.id} className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-600 dark:bg-blue-500/20 dark:text-blue-400">
                        {i + 1}
                      </span>
                      {SECTION_ICONS[s.id]} {s.label}
                    </li>
                  ))}
              </ol>
            )}
          </div>

          {/* Format selector */}
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
            <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">{t('page.reports.format_title')}</h3>
            <div className="space-y-2">
              {formatOptions.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setFormat(opt.value)}
                  className={`flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all ${
                    format === opt.value
                      ? "border-blue-400 bg-blue-50 dark:border-blue-500/50 dark:bg-blue-500/10"
                      : "border-gray-200 bg-white hover:border-gray-300 dark:border-gray-700 dark:bg-gray-800"
                  }`}
                >
                  <span className="text-lg">{opt.icon}</span>
                  <div className="min-w-0 flex-1">
                    <p className={`text-sm font-medium ${format === opt.value ? "text-blue-700 dark:text-blue-300" : "text-gray-900 dark:text-white"}`}>
                      {opt.label}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">{opt.desc}</p>
                  </div>
                  {format === opt.value && (
                    <svg className="h-4 w-4 shrink-0 text-blue-600 dark:text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
