"use client";

import { useState, useEffect, useCallback } from "react";
import { PageHeader, Badge } from "../components/ui";
import { apiFetch } from "../../lib/api";
import { useDomain } from "../contexts/DomainContext";
import { useToast } from "../components/ui";
import { useLanguage } from "../contexts/LanguageContext";

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

const SECTION_ICONS: Record<string, string> = {
  entity_stats:         "📊",
  enrichment_coverage:  "🔬",
  top_brands:           "🏷️",
  topic_clusters:       "🧩",
  harmonization_log:    "⚙️",
};

const SECTION_DESCRIPTIONS: Record<string, string> = {
  entity_stats:         "Total entities, validation status breakdown, distribution chart",
  enrichment_coverage:  "Coverage %, average citations, top enriched entities",
  top_brands:           "Top 15 primary labels or classifications by entity count",
  topic_clusters:       "Most frequent concepts from enrichment data",
  harmonization_log:    "Last 10 harmonization steps with status",
};

// ── Format types ──────────────────────────────────────────────────────────────

type ExportFormat = "html" | "pdf" | "excel" | "pptx";

const FORMAT_OPTIONS: { value: ExportFormat; label: string; desc: string; icon: string }[] = [
  { value: "html",  label: "HTML",       desc: "Preview in browser, Ctrl+P to print",               icon: "🌐" },
  { value: "pdf",   label: "PDF",        desc: "Professional branded PDF download",                  icon: "📄" },
  { value: "excel", label: "Excel",      desc: "Multi-sheet workbook with KPIs, entities & concepts", icon: "📊" },
  { value: "pptx",  label: "PowerPoint", desc: "Branded slide deck for presentations",               icon: "📑" },
];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const { activeDomainId } = useDomain();
  const { toast } = useToast();
  const { t } = useLanguage();

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
    toast(`Template "${tpl.name}" applied`, "success");
  };

  const saveAsTemplate = async () => {
    if (!newTemplateName.trim()) {
      toast("Enter a template name", "warning");
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
        toast("Template saved", "success");
      } else {
        const err = await res.text();
        toast(`Failed: ${err}`, "error");
      }
    } finally {
      setSavingTemplate(false);
    }
  };

  const toggleSection = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const selectAll = () => setSelected(new Set(sections.map((s) => s.id)));
  const clearAll  = () => setSelected(new Set());

  const handleGenerate = async () => {
    if (selected.size === 0) {
      toast("Select at least one section", "warning");
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
        }),
      });
      if (!res.ok) {
        const err = await res.text();
        toast(`Generation failed: ${err}`, "error");
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
      toast("Report downloaded", "success");
    } catch {
      toast("Failed to generate report", "error");
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

      {/* Templates panel */}
      <div className="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900">
        <button
          onClick={() => { setShowTemplates((v) => !v); if (!showTemplates) loadTemplates(); }}
          className="flex w-full items-center justify-between px-5 py-4 text-left"
        >
          <div className="flex items-center gap-2">
            <span className="text-base">📐</span>
            <span className="text-sm font-semibold text-gray-900 dark:text-white">{t('page.reports.templates_panel_title')}</span>
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
                          built-in
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400 line-clamp-2">{tpl.description}</p>
                    <span className="mt-2 rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-500/20 dark:text-blue-300">
                      {tpl.sections.length} section{tpl.sections.length !== 1 ? "s" : ""}
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
                  placeholder="New template name…"
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
                {selected.size} of {sections.length} {t('page.reports.sections_selected_count')}
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
                        {SECTION_DESCRIPTIONS[sec.id] ?? ""}
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
                  placeholder={`UKIP Report — ${activeDomainId || "default"}`}
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
              {FORMAT_OPTIONS.map((opt) => (
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
