"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useDomain } from "../../contexts/DomainContext";
import { apiFetch } from "@/lib/api";

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
  const color =
    pmi > 1 ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300" :
    pmi > 0 ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" :
               "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400";
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-mono font-medium ${color}`}>
      PMI {pmi.toFixed(2)}
    </span>
  );
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────

const TABS = [
  { key: "topics",       label: "Top Concepts" },
  { key: "cooccurrence", label: "Co-occurrence" },
  { key: "clusters",     label: "Topic Clusters" },
  { key: "correlation",  label: "Field Correlation" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function TopicsPage() {
  const { activeDomainId } = useDomain();
  const [tab, setTab] = useState<TabKey>("topics");
  const [loading, setLoading] = useState(false);

  const [topicsData,      setTopicsData]      = useState<TopicsResult | null>(null);
  const [cooccData,       setCooccData]        = useState<CooccResult | null>(null);
  const [clustersData,    setClustersData]     = useState<ClustersResult | null>(null);
  const [correlationData, setCorrelationData]  = useState<CorrelationResult | null>(null);

  const fetchTab = useCallback(async (t: TabKey, domainId: string) => {
    setLoading(true);
    try {
      if (t === "topics") {
        const d = await apiFetch(`/analyzers/topics/${domainId}?top_n=30`);
        setTopicsData(d);
      } else if (t === "cooccurrence") {
        const d = await apiFetch(`/analyzers/cooccurrence/${domainId}?top_n=20`);
        setCooccData(d);
      } else if (t === "clusters") {
        const d = await apiFetch(`/analyzers/clusters/${domainId}?n_clusters=6`);
        setClustersData(d);
      } else if (t === "correlation") {
        const d = await apiFetch(`/analyzers/correlation/${domainId}?top_n=20`);
        setCorrelationData(d);
      }
    } catch (err) {
      console.error("Topic analysis error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTab(tab, activeDomainId);
  }, [tab, activeDomainId, fetchTab]);

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Topic Modeling
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Concept frequency, co-occurrence, and correlation analysis from enrichment data
          </p>
        </div>
        <Link
          href="/analytics"
          className="text-sm text-blue-600 hover:underline dark:text-blue-400"
        >
          ← Analytics
        </Link>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-800">
        <nav className="-mb-px flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === t.key
                  ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                  : "border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Loading overlay */}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
        </div>
      )}

      {/* ── Tab: Top Concepts ────────────────────────────────────────────────── */}
      {!loading && tab === "topics" && topicsData && (
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
          <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-800">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {topicsData.topics.length} concepts across{" "}
              <strong>{topicsData.total_enriched}</strong> enriched entities
            </span>
          </div>
          {topicsData.topics.length === 0 ? (
            <EmptyState message="No enriched concepts found. Run the enrichment pipeline first." />
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
      {!loading && tab === "cooccurrence" && cooccData && (
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
          <div className="border-b border-gray-200 px-4 py-3 dark:border-gray-800">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {cooccData.pairs.length} concept pairs from{" "}
              <strong>{cooccData.total_enriched}</strong> enriched entities
            </span>
          </div>
          {cooccData.pairs.length === 0 ? (
            <EmptyState message="No co-occurrences found. Entities need at least 2 concepts each." />
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
      {!loading && tab === "clusters" && clustersData && (
        <div>
          {clustersData.clusters.length === 0 ? (
            <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
              <EmptyState message="No concept clusters found. Enrich entities to populate topics." />
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
                        {cluster.size} terms
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
                          +{cluster.members.length - 8} more
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
      {!loading && tab === "correlation" && correlationData && (
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
          <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-800">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {correlationData.fields_analyzed} fields analyzed across{" "}
              <strong>{correlationData.n_entities}</strong> entities
            </span>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1">
                <span className="inline-block h-2 w-4 rounded bg-red-500" /> strong ≥ 0.5
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-2 w-4 rounded bg-amber-400" /> moderate ≥ 0.2
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-2 w-4 rounded bg-blue-400" /> weak
              </span>
            </div>
          </div>
          {correlationData.correlations.length === 0 ? (
            <EmptyState message="No significant correlations found (Cramér's V < 0.05 for all pairs)." />
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
                    {c.strength}
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

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-16 text-center">
      <svg className="h-12 w-12 text-gray-300 dark:text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m1.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
        />
      </svg>
      <p className="max-w-sm text-sm text-gray-500 dark:text-gray-400">{message}</p>
    </div>
  );
}
