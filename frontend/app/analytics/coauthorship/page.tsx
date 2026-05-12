"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useDomain } from "../../contexts/DomainContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { apiFetch } from "@/lib/api";
import { SkeletonList, ErrorBanner, EmptyState as UiEmptyState } from "../../components/ui";

// ── Types ────────────────────────────────────────────────────────────────────

interface NetworkNode {
  id: string;
  label: string;
  degree: number;
  centrality: number;
  community_id: number;
  total_publications: number;
}

interface NetworkEdge {
  source: string;
  target: string;
  weight: number;
}

interface NetworkResult {
  domain_id: string;
  nodes: NetworkNode[];
  edges: NetworkEdge[];
}

// ── Community colors ─────────────────────────────────────────────────────────

const COMMUNITY_COLORS = [
  "bg-blue-500", "bg-violet-500", "bg-amber-500",
  "bg-emerald-500", "bg-rose-500", "bg-cyan-500",
  "bg-orange-500", "bg-lime-500", "bg-pink-500", "bg-teal-500",
];

const COMMUNITY_TEXT_COLORS = [
  "text-blue-600 dark:text-blue-400",
  "text-violet-600 dark:text-violet-400",
  "text-amber-600 dark:text-amber-400",
  "text-emerald-600 dark:text-emerald-400",
  "text-rose-600 dark:text-rose-400",
  "text-cyan-600 dark:text-cyan-400",
  "text-orange-600 dark:text-orange-400",
  "text-lime-600 dark:text-lime-400",
  "text-pink-600 dark:text-pink-400",
  "text-teal-600 dark:text-teal-400",
];

// ── Page ─────────────────────────────────────────────────────────────────────

export default function CoauthorshipPage() {
  const { activeDomainId } = useDomain();
  const { t } = useLanguage();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<NetworkResult | null>(null);
  const [minWeight, setMinWeight] = useState(1);

  const fetchNetwork = useCallback(async (domainId: string, mw: number) => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch(`/analyzers/coauthorship/${domainId}?min_weight=${mw}&limit=100`);
      if (!r.ok) throw new Error(`Server responded with ${r.status}`);
      setData(await r.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("page.coauthorship.error_load"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchNetwork(activeDomainId, minWeight);
  }, [activeDomainId, minWeight, fetchNetwork]);

  const communityCount = data ? new Set(data.nodes.map((n) => n.community_id)).size : 0;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            {t("page.coauthorship.title")}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("page.coauthorship.subtitle")}
          </p>
        </div>
        <Link
          href="/analytics"
          className="text-sm text-blue-600 hover:underline dark:text-blue-400"
        >
          &larr; {t("nav.analytics")}
        </Link>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4">
        <label className="text-sm text-gray-600 dark:text-gray-400">
          {t("page.coauthorship.min_weight")}:
        </label>
        <input
          type="range"
          min={1}
          max={10}
          value={minWeight}
          onChange={(e) => setMinWeight(Number(e.target.value))}
          className="w-32"
        />
        <span className="rounded bg-gray-100 px-2 py-0.5 text-sm font-mono dark:bg-gray-800">
          {minWeight}
        </span>
      </div>

      {loading && (
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900 overflow-hidden">
          <SkeletonList rows={10} />
        </div>
      )}

      {!loading && error && (
        <ErrorBanner
          message={t("page.coauthorship.error_load")}
          detail={error}
          onRetry={() => fetchNetwork(activeDomainId, minWeight)}
        />
      )}

      {!loading && !error && data && (
        <>
          {/* KPI row */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: t("page.coauthorship.nodes"), value: data.nodes.length },
              { label: t("page.coauthorship.edges"), value: data.edges.length },
              { label: t("page.coauthorship.communities"), value: communityCount },
            ].map((kpi) => (
              <div
                key={kpi.label}
                className="rounded-xl border border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-900"
              >
                <p className="text-xs text-gray-500 dark:text-gray-400">{kpi.label}</p>
                <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{kpi.value}</p>
              </div>
            ))}
          </div>

          {data.nodes.length === 0 ? (
            <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
              <UiEmptyState
                icon="users"
                color="violet"
                title={t("page.coauthorship.empty_title")}
                description={t("page.coauthorship.empty_description")}
                size="compact"
              />
            </div>
          ) : (
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Node table — top collaborators by centrality */}
              <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
                <div className="border-b border-gray-200 px-4 py-3 dark:border-gray-800">
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {t("page.coauthorship.top_collaborators")}
                  </h3>
                </div>
                <div className="grid grid-cols-[1fr_4rem_4rem_5rem] items-center gap-2 border-b border-gray-100 px-4 py-2 text-xs font-medium uppercase tracking-wide text-gray-400 dark:border-gray-800">
                  <span>Author</span>
                  <span className="text-right">{t("page.coauthorship.degree")}</span>
                  <span className="text-right">{t("page.coauthorship.community")}</span>
                  <span className="text-right">Centrality</span>
                </div>
                <div className="divide-y divide-gray-100 dark:divide-gray-800 max-h-96 overflow-y-auto">
                  {data.nodes.map((node) => {
                    const colorIdx = node.community_id % COMMUNITY_COLORS.length;
                    return (
                      <div
                        key={node.id}
                        className="grid grid-cols-[1fr_4rem_4rem_5rem] items-center gap-2 px-4 py-2.5"
                      >
                        <div className="flex items-center gap-2 truncate">
                          <span className={`inline-block h-2.5 w-2.5 rounded-full ${COMMUNITY_COLORS[colorIdx]}`} />
                          <span className="truncate text-sm text-gray-800 dark:text-gray-200">
                            {node.label}
                          </span>
                        </div>
                        <span className="text-right text-sm tabular-nums font-medium text-gray-700 dark:text-gray-300">
                          {node.degree}
                        </span>
                        <span className={`text-right text-sm tabular-nums font-medium ${COMMUNITY_TEXT_COLORS[colorIdx]}`}>
                          C{node.community_id}
                        </span>
                        <span className="text-right text-xs tabular-nums font-mono text-gray-500 dark:text-gray-400">
                          {node.centrality.toFixed(3)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Edge table — strongest collaborations */}
              <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
                <div className="border-b border-gray-200 px-4 py-3 dark:border-gray-800">
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {t("page.coauthorship.edges")} (top by {t("page.coauthorship.weight")})
                  </h3>
                </div>
                <div className="divide-y divide-gray-100 dark:divide-gray-800 max-h-96 overflow-y-auto">
                  {data.edges.slice(0, 50).map((edge, i) => (
                    <div key={`${edge.source}-${edge.target}-${i}`} className="flex items-center gap-3 px-4 py-2.5">
                      <span className="truncate text-sm text-gray-800 dark:text-gray-200">
                        {edge.source}
                      </span>
                      <span className="text-gray-300 dark:text-gray-600">&harr;</span>
                      <span className="truncate text-sm text-gray-800 dark:text-gray-200">
                        {edge.target}
                      </span>
                      <span className="ml-auto shrink-0 rounded bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-700 dark:bg-violet-900/30 dark:text-violet-300">
                        {edge.weight}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
