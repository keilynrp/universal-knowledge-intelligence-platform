"use client";

import { useState, useEffect, useCallback, type ReactNode } from "react";
import { useLanguage } from "../../contexts/LanguageContext";
import { EntityConcept, PageHeader } from "../../components/ui";
import { apiFetch } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface DomainKPIs {
  total_entities: number;
  enriched_count: number;
  enrichment_pct: number;
  avg_citations: number;
  total_concepts: number;
}

interface TypeDist { type: string; count: number; }
interface YearEntry { year: number; count: number; }
interface TopEntity { id: number; entity_name: string; citation_count: number; source: string | null; }
interface TopConcept { concept: string; count: number; }

interface DomainSnapshot {
  domain_id: string;
  kpis: DomainKPIs;
  type_distribution: TypeDist[];
  entities_by_year: YearEntry[];
  top_concepts: TopConcept[];
  top_entities: TopEntity[];
}

interface CompareResult {
  domains: DomainSnapshot[];
}

// ── Colour palette per column ─────────────────────────────────────────────────
const COLORS = [
  { bg: "bg-blue-50 dark:bg-blue-500/5",   ring: "ring-blue-200 dark:ring-blue-800",  text: "text-blue-700 dark:text-blue-300",  bar: "bg-blue-500"   },
  { bg: "bg-violet-50 dark:bg-violet-500/5", ring: "ring-violet-200 dark:ring-violet-800", text: "text-violet-700 dark:text-violet-300", bar: "bg-violet-500" },
  { bg: "bg-emerald-50 dark:bg-emerald-500/5", ring: "ring-emerald-200 dark:ring-emerald-800", text: "text-emerald-700 dark:text-emerald-300", bar: "bg-emerald-500" },
  { bg: "bg-amber-50 dark:bg-amber-500/5", ring: "ring-amber-200 dark:ring-amber-800", text: "text-amber-700 dark:text-amber-300", bar: "bg-amber-500" },
];

const DOMAIN_PRESETS = ["default", "science", "healthcare", "all"];

function getDomainPresetLabel(t: (key: string, params?: Record<string, string | number>) => string, domainId: string) {
  return t(`page.compare.domain_preset.${domainId}`);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function KPICard({ label, values, formatter = String }: {
  label: ReactNode;
  values: (string | number)[];
  formatter?: (v: string | number) => string;
}) {
  const winner = values.reduce<number>((best, v, i) =>
    Number(v) > Number(values[best] ?? 0) ? i : best, 0);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">{label}</p>
      <div className="flex gap-3">
        {values.map((v, i) => (
          <div key={i} className={`flex-1 rounded-lg px-3 py-2 text-center ${COLORS[i].bg} ${i === winner && values.filter(x => Number(x) > 0).length > 1 ? "ring-1 " + COLORS[i].ring : ""}`}>
            <p className={`text-xl font-bold ${COLORS[i].text}`}>{formatter(v)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function MiniBar({ label, count, max, color }: { label: string; count: number; max: number; color: string }) {
  const pct = max > 0 ? Math.round(count / max * 100) : 0;
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-28 truncate text-gray-600 dark:text-gray-400 text-xs">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-gray-100 dark:bg-gray-800">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right text-xs text-gray-500">{count}</span>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function DomainComparePage() {
  const { t } = useLanguage();
  const [selectedDomains, setSelectedDomains] = useState<string[]>(["default", "science"]);
  const [customA, setCustomA] = useState("");
  const [customB, setCustomB] = useState("");
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (ids: string[]) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/dashboard/compare?domains=${ids.join(",")}`);
      if (!res.ok) throw new Error(t("page.compare.error_status", { status: res.status }));
      setResult(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : t("page.compare.error_load"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { load(selectedDomains); }, [load, selectedDomains]);

  function addCustomDomain() {
    const a = customA.trim();
    const b = customB.trim();
    const ids = [a || "default", b || "science"].filter(Boolean);
    setSelectedDomains(ids.slice(0, 4));
    setCustomA("");
    setCustomB("");
  }

  const snapshots = result?.domains ?? [];
  const domainLabels = snapshots.map(s => s.domain_id);

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumbs={[
          { label: t("nav.home"), href: "/" },
          { label: t("nav.analytics"), href: "/analytics" },
          { label: t("page.compare.title") },
        ]}
        title={t("page.compare.title")}
        description={t("page.compare.description")}
      />

      {/* Domain selector */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">{t("page.compare.compare_domains")}</h3>
        <div className="flex flex-wrap gap-2 mb-4">
          {DOMAIN_PRESETS.map((d) => (
            <button
              key={d}
              onClick={() => {
                const next = selectedDomains.includes(d)
                  ? selectedDomains.filter(x => x !== d)
                  : [...selectedDomains, d].slice(0, 4);
                if (next.length >= 2) setSelectedDomains(next);
              }}
              className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
                selectedDomains.includes(d)
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              }`}
            >
              {getDomainPresetLabel(t, d)}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text" placeholder={t("page.compare.custom_domain_a")} value={customA}
            onChange={e => setCustomA(e.target.value)}
            className="h-9 flex-1 rounded-lg border border-gray-200 bg-white px-3 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white"
          />
          <input
            type="text" placeholder={t("page.compare.custom_domain_b")} value={customB}
            onChange={e => setCustomB(e.target.value)}
            className="h-9 flex-1 rounded-lg border border-gray-200 bg-white px-3 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white"
          />
          <button
            onClick={addCustomDomain}
            className="h-9 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700"
          >
            {t("page.compare.compare_button")}
          </button>
        </div>
      </div>

      {/* Domain colour legend */}
      {snapshots.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {domainLabels.map((label, i) => (
            <div key={label} className={`flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ring-1 ${COLORS[i].bg} ${COLORS[i].ring} ${COLORS[i].text}`}>
              <span className={`h-2 w-2 rounded-full ${COLORS[i].bar}`} />
              {label}
            </div>
          ))}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-16">
          <svg className="h-8 w-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-500/5 dark:text-red-400">
          {error}
        </div>
      )}

      {!loading && snapshots.length > 0 && (
        <>
          {/* KPI grid */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">{t("page.compare.key_metrics")}</h3>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <KPICard
                label={<EntityConcept>{t("page.compare.total_entities")}</EntityConcept>}
                values={snapshots.map(s => s.kpis.total_entities)}
                formatter={v => Number(v).toLocaleString()}
              />
              <KPICard
                label={t("page.compare.enriched_records")}
                values={snapshots.map(s => s.kpis.enriched_count)}
                formatter={v => Number(v).toLocaleString()}
              />
              <KPICard
                label={t("page.compare.enrichment_pct")}
                values={snapshots.map(s => s.kpis.enrichment_pct)}
                formatter={v => `${v}%`}
              />
              <KPICard
                label={t("page.compare.avg_citations")}
                values={snapshots.map(s => s.kpis.avg_citations)}
                formatter={v => String(v)}
              />
              <KPICard
                label={t("page.compare.unique_concepts")}
                values={snapshots.map(s => s.kpis.total_concepts)}
                formatter={v => Number(v).toLocaleString()}
              />
            </div>
          </div>

          {/* Per-domain detail columns */}
          <div className={`grid gap-4 ${snapshots.length === 2 ? "grid-cols-2" : snapshots.length === 3 ? "grid-cols-3" : "grid-cols-2 xl:grid-cols-4"}`}>
            {snapshots.map((snap, idx) => {
              const clr = COLORS[idx];
              const maxType = Math.max(...snap.type_distribution.map(t => t.count), 1);
              const maxConcept = Math.max(...snap.top_concepts.map(c => c.count), 1);

              return (
                <div key={snap.domain_id} className={`space-y-4 rounded-2xl p-4 ring-1 ${clr.bg} ${clr.ring}`}>
                  <h3 className={`text-sm font-bold uppercase tracking-wide ${clr.text}`}>
                    {snap.domain_id}
                  </h3>

                  {/* Entity types */}
                  {snap.type_distribution.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold text-gray-500 dark:text-gray-400">
                        <EntityConcept>{t("page.compare.entity_types")}</EntityConcept>
                      </p>

                      <div className="space-y-1.5">
                        {snap.type_distribution.slice(0, 6).map(t => (
                          <MiniBar key={t.type} label={t.type} count={t.count} max={maxType} color={clr.bar} />
                        ))}
                        {snap.type_distribution.length === 0 && (
                          <p className="text-xs text-gray-400">{t("common.no_data")}</p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Top concepts */}
                  {snap.top_concepts.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold text-gray-500 dark:text-gray-400">{t("page.compare.top_concepts")}</p>
                      <div className="space-y-1.5">
                        {snap.top_concepts.slice(0, 8).map(c => (
                          <MiniBar key={c.concept} label={c.concept} count={c.count} max={maxConcept} color={clr.bar} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Timeline sparkline (text) */}
                  {snap.entities_by_year.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold text-gray-500 dark:text-gray-400">{t("page.compare.activity_timeline")}</p>
                      <div className="flex flex-wrap gap-1">
                        {snap.entities_by_year.slice(-6).map(e => (
                          <div key={e.year} className="text-center">
                            <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">{e.count}</div>
                            <div className="text-xs text-gray-400">{e.year}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Top entities */}
                  {snap.top_entities.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold text-gray-500 dark:text-gray-400">{t("page.compare.top_by_citations")}</p>
                      <div className="space-y-1">
                        {snap.top_entities.slice(0, 4).map(e => (
                          <a key={e.id} href={`/entities/${e.id}`}
                            className="block truncate text-xs text-gray-600 hover:text-blue-600 dark:text-gray-400 dark:hover:text-blue-400">
                            {e.entity_name || t("page.compare.entity_fallback", { id: e.id })}
                            <span className="ml-1 text-gray-400">({e.citation_count})</span>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}

                  {snap.kpis.total_entities === 0 && (
                    <p className="text-center text-sm text-gray-400 py-4">{t("page.compare.no_data_domain")}</p>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
