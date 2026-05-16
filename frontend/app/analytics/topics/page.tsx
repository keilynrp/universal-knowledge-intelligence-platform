"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useDomain } from "../../contexts/DomainContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { apiFetch } from "@/lib/api";
import { SkeletonList, ErrorBanner, EmptyState as UiEmptyState } from "../../components/ui";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Topic {
  concept: string;
  count: number;
  pct: number;
}

interface TopicsResult {
  domain_id: string;
  total_enriched: number;
  topics: Topic[];
}

interface CooccPair {
  concept_a: string;
  concept_b: string;
  count: number;
  pmi: number;
}

interface CooccResult {
  domain_id: string;
  total_enriched: number;
  pairs: CooccPair[];
}

interface ClusterMember {
  concept: string;
  count: number;
}

interface Cluster {
  id: number;
  seed: string;
  size: number;
  members: ClusterMember[];
}

interface ClustersResult {
  domain_id: string;
  n_clusters: number;
  clusters: Cluster[];
}

interface Correlation {
  field_a: string;
  field_b: string;
  cramers_v: number;
  strength: "weak" | "moderate" | "strong";
}

interface CorrelationResult {
  domain_id: string;
  n_entities: number;
  fields_analyzed: number;
  correlations: Correlation[];
}

// ─── Palette ──────────────────────────────────────────────────────────────────

const CLUSTER_COLORS = [
  "bg-blue-500", "bg-violet-500", "bg-amber-500",
  "bg-emerald-500", "bg-rose-500", "bg-cyan-500",
  "bg-orange-500", "bg-lime-500", "bg-pink-500", "bg-teal-500",
];

const STRENGTH_COLORS: Record<string, string> = {
  strong:   "bg-red-500",
  moderate: "bg-amber-400",
  weak:     "bg-blue-400",
};
const STRENGTH_TEXT: Record<string, string> = {
  strong:   "text-red-700 dark:text-red-300",
  moderate: "text-amber-700 dark:text-amber-300",
  weak:     "text-blue-700 dark:text-blue-300",
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function PctBar({ value, max, color = "bg-blue-500" }: { value: number; max: number; color?: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="h-2 w-full rounded-full bg-gray-100 dark:bg-gray-800">
      <div
        className={`h-2 rounded-full transition-all ${color}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function PMIBadge({ pmi }: { pmi: number }) {
  const { t } = useLanguage();
  const color =
    pmi > 1 ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300" :
    pmi > 0 ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" :
               "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400";
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-mono font-medium ${color}`}>
      {t("page.topics.pmi", { value: pmi.toFixed(2) })}
    </span>
  );
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────

const TABS = [
  { key: "topics",       labelKey: "page.topics.tab.top_concepts" },
  { key: "cooccurrence", labelKey: "page.topics.tab.cooccurrence" },
  { key: "clusters",     labelKey: "page.topics.tab.clusters" },
  { key: "correlation",  labelKey: "page.topics.tab.correlation" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function TopicsPage() {
  const { activeDomainId } = useDomain();
  const { t } = useLanguage();
  const [tab, setTab] = useState<TabKey>("topics");
  const [loading, setLoading] = useState(false);
  const [tabError, setTabError] = useState<string | null>(null);

  const [topicsData,      setTopicsData]      = useState<TopicsResult | null>(null);
  const [cooccData,       setCooccData]        = useState<CooccResult | null>(null);
  const [clustersData,    setClustersData]     = useState<ClustersResult | null>(null);
  const [correlationData, setCorrelationData]  = useState<CorrelationResult | null>(null);

  const fetchTab = useCallback(async (tabKey: TabKey, domainId: string) => {
    setLoading(true);
    setTabError(null);
    try {
      if (tabKey === "topics") {
        const r = await apiFetch(`/analyzers/topics/${domainId}?top_n=30`);
        if (!r.ok) throw new Error(`Server responded with ${r.status}`);
        const data = await r.json();
        if (!data.topics) data.topics = [];
        setTopicsData(data);
      } else if (tabKey === "cooccurrence") {
        const r = await apiFetch(`/analyzers/cooccurrence/${domainId}?top_n=20`);
        if (!r.ok) throw new Error(`Server responded with ${r.status}`);
        const data = await r.json();
        if (!data.pairs) data.pairs = [];
        setCooccData(data);
      } else if (tabKey === "clusters") {
        const r = await apiFetch(`/analyzers/clusters/${domainId}?n_clusters=6`);
        if (!r.ok) throw new Error(`Server responded with ${r.status}`);
        const data = await r.json();
        if (!data.clusters) data.clusters = [];
        setClustersData(data);
      } else if (tabKey === "correlation") {
        const r = await apiFetch(`/analyzers/correlation/${domainId}?top_n=20`);
        if (!r.ok) throw new Error(`Server responded with ${r.status}`);
        const data = await r.json();
        if (!data.correlations) data.correlations = [];
        setCorrelationData(data);
      }
    } catch (err) {
      setTabError(err instanceof Error ? err.message : t("page.topics.analysis_failed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchTab(tab, activeDomainId);
  }, [tab, activeDomainId, fetchTab]);

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            {t("page.topics.title")}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("page.topics.subtitle")}
          </p>
        </div>
        <Link
          href="/analytics"
          className="text-sm text-blue-600 hover:underline dark:text-blue-400"
        >
          ← {t("nav.analytics")}
        </Link>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-800">
        <nav className="-mb-px flex gap-1">
          {TABS.map((tabOption) => (
            <button
              key={tabOption.key}
              onClick={() => setTab(tabOption.key)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === tabOption.key
                  ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                  : "border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              }`}
            >
              {t(tabOption.labelKey)}
            </button>
          ))}
        </nav>
      </div>

      {/* Loading skeleton */}
      {loading && (
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900 overflow-hidden">
          <SkeletonList rows={10} />
        </div>
      )}

      {/* Error state */}
      {!loading && tabError && (
        <ErrorBanner
          message={t("page.topics.error_load")}
          detail={tabError}
          onRetry={() => fetchTab(tab, activeDomainId)}
        />
      )}

      {/* ── Tab: Top Concepts ────────────────────────────────────────────────── */}
      {!loading && !tabError && tab === "topics" && topicsData && topicsData.topics && (
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
          <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-800">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {topicsData.topics.length} {t("page.topics.concepts_label")}{" "}
              {t("page.topics.across")}{" "}
              <strong>{topicsData.total_enriched}</strong> {t("page.topics.enriched_entities")}
            </span>
          </div>
          {topicsData.topics.length === 0 ? (
            <UiEmptyState icon="sparkles" color="blue" title={t("page.topics.empty_concepts_title")} description={t("page.topics.empty_concepts_description")} size="compact" />
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              {topicsData.topics.map((t, i) => {
                const maxCount = topicsData.topics[0]?.count ?? 1;
                return (
                  <div key={t.concept} className="flex items-center gap-4 px-4 py-3">
                    <span className="w-6 text-right text-xs font-mono text-gray-400">
                      {i + 1}
                    </span>
                    <span className="w-48 truncate text-sm font-medium text-gray-800 dark:text-gray-200">
                      {t.concept}
                    </span>
                    <div className="flex-1">
                      <PctBar value={t.count} max={maxCount} color="bg-blue-500" />
                    </div>
                    <span className="w-10 text-right text-sm tabular-nums text-gray-700 dark:text-gray-300">
                      {t.count}
                    </span>
                    <span className="w-14 text-right text-xs text-gray-400">
                      {t.pct.toFixed(1)}%
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Co-occurrence ───────────────────────────────────────────────── */}
      {!loading && !tabError && tab === "cooccurrence" && cooccData && cooccData.pairs && (
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
          <div className="border-b border-gray-200 px-4 py-3 dark:border-gray-800">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {cooccData.pairs.length} {t("page.topics.pairs_label")} {t("page.topics.from")}{" "}
              <strong>{cooccData.total_enriched}</strong> {t("page.topics.enriched_entities")}
            </span>
          </div>
          {cooccData.pairs.length === 0 ? (
            <UiEmptyState icon="sparkles" color="violet" title={t("page.topics.empty_pairs_title")} description={t("page.topics.empty_pairs_description")} size="compact" />
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              {cooccData.pairs.map((p, i) => {
                const maxCount = cooccData.pairs[0]?.count ?? 1;
                return (
                  <div key={`${p.concept_a}-${p.concept_b}`} className="flex items-center gap-4 px-4 py-3">
                    <span className="w-6 text-right text-xs font-mono text-gray-400">
                      {i + 1}
                    </span>
                    <div className="flex w-72 flex-wrap items-center gap-1.5">
                      <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                        {p.concept_a}
                      </span>
                      <span className="text-gray-300 dark:text-gray-600">+</span>
                      <span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-700 dark:bg-violet-900/30 dark:text-violet-300">
                        {p.concept_b}
                      </span>
                    </div>
                    <div className="flex-1">
                      <PctBar value={p.count} max={maxCount} color="bg-violet-500" />
                    </div>
                    <span className="w-10 text-right text-sm tabular-nums text-gray-700 dark:text-gray-300">
                      {p.count}
                    </span>
                    <PMIBadge pmi={p.pmi} />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Topic Clusters ──────────────────────────────────────────────── */}
      {!loading && !tabError && tab === "clusters" && clustersData && clustersData.clusters && (
        <div>
          {clustersData.clusters.length === 0 ? (
            <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
              <UiEmptyState icon="sparkles" color="amber" title={t("page.topics.empty_clusters_title")} description={t("page.topics.empty_clusters_description")} size="compact" />
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {clustersData.clusters.map((cluster) => {
                const color = CLUSTER_COLORS[cluster.id % CLUSTER_COLORS.length];
                return (
                  <div
                    key={cluster.id}
                    className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900"
                  >
                    {/* Cluster header */}
                    <div className={`flex items-center gap-2 rounded-t-xl px-4 py-3 ${color} bg-opacity-10 dark:bg-opacity-20`}>
                      <div className={`h-3 w-3 rounded-full ${color}`} />
                      <span className="font-semibold text-gray-800 dark:text-white">
                        {cluster.seed}
                      </span>
                      <span className="ml-auto rounded-full bg-white/60 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-900/60 dark:text-gray-400">
                        {t("page.topics.terms_label", { count: cluster.size })}
                      </span>
                    </div>
                    {/* Members */}
                    <ul className="divide-y divide-gray-100 dark:divide-gray-800">
                      {cluster.members.slice(0, 8).map((m) => (
                        <li key={m.concept} className="flex items-center justify-between px-4 py-2">
                          <span className="text-sm text-gray-700 dark:text-gray-300">
                            {m.concept}
                          </span>
                          <span className="text-xs tabular-nums text-gray-400">{m.count}</span>
                        </li>
                      ))}
                      {cluster.members.length > 8 && (
                        <li className="px-4 py-2 text-xs text-gray-400">
                          {t("page.topics.more_members", { count: cluster.members.length - 8 })}
                        </li>
                      )}
                    </ul>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Field Correlation ───────────────────────────────────────────── */}
      {!loading && !tabError && tab === "correlation" && correlationData && correlationData.correlations && (
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
          <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-800">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {correlationData.fields_analyzed} {t("page.topics.fields_analyzed")} {t("page.topics.across")}{" "}
              <strong>{correlationData.n_entities}</strong> {t("page.topics.entities")}
            </span>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1">
                <span className="inline-block h-2 w-4 rounded bg-red-500" /> {t("page.topics.strong_threshold")}
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-2 w-4 rounded bg-amber-400" /> {t("page.topics.moderate_threshold")}
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-2 w-4 rounded bg-blue-400" /> {t("page.topics.weak_label")}
              </span>
            </div>
          </div>
          {correlationData.correlations.length === 0 ? (
            <UiEmptyState icon="chart" color="slate" title={t("page.topics.empty_correlation_title")} description={t("page.topics.empty_correlation_description")} size="compact" />
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              {correlationData.correlations.map((c, i) => (
                <div key={`${c.field_a}-${c.field_b}`} className="flex items-center gap-4 px-4 py-3">
                  <span className="w-6 text-right text-xs font-mono text-gray-400">{i + 1}</span>
                  <div className="flex w-64 flex-wrap items-center gap-1.5">
                    <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                      {c.field_a}
                    </code>
                    <span className="text-gray-400">↔</span>
                    <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                      {c.field_b}
                    </code>
                  </div>
                  <div className="flex-1">
                    <div className="h-2 w-full rounded-full bg-gray-100 dark:bg-gray-800">
                      <div
                        className={`h-2 rounded-full transition-all ${STRENGTH_COLORS[c.strength]}`}
                        style={{ width: `${Math.round(c.cramers_v * 100)}%` }}
                      />
                    </div>
                  </div>
                  <span className="w-12 text-right text-sm tabular-nums font-medium text-gray-800 dark:text-gray-200">
                    {c.cramers_v.toFixed(3)}
                  </span>
                  <span className={`w-16 text-right text-xs font-medium capitalize ${STRENGTH_TEXT[c.strength]}`}>
                    {t(`page.topics.strength.${c.strength}`)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

