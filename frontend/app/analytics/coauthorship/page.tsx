"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useDomain } from "../../contexts/DomainContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { useAuth } from "../../contexts/AuthContext";
import { apiFetch } from "@/lib/api";
import { SkeletonList, ErrorBanner, EmptyState as UiEmptyState } from "../../components/ui";
import { GraphControls } from "../../components/graph/GraphControls";
import { NodePropertiesPanel } from "../../components/graph/NodePropertiesPanel";
import { MergeSuggestionsPanel } from "../../components/graph/MergeSuggestionsPanel";

const NetworkGraph = dynamic(
  () => import("../../components/graph/NetworkGraph").then((m) => m.NetworkGraph),
  { ssr: false, loading: () => <div className="h-[560px] animate-pulse rounded-lg bg-slate-100 dark:bg-slate-900" /> },
);

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
  computed_at?: string | null;
  stale?: boolean;
  coverage_pct?: number;
}

function relativeTime(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  return hrs < 24 ? `${hrs} h ago` : `${Math.round(hrs / 24)} d ago`;
}

export default function CoauthorshipPage() {
  const { activeDomainId } = useDomain();
  const { t } = useLanguage();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin" || user?.role === "super_admin";

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<NetworkResult | null>(null);
  const [minWeight, setMinWeight] = useState(1);
  const [communityId, setCommunityId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  // Debounce search so typing doesn't refetch per keystroke.
  useEffect(() => {
    const h = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(h);
  }, [search]);

  const fetchNetwork = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ min_weight: String(minWeight), limit: "150" });
      if (communityId !== null) params.set("community_id", String(communityId));
      if (debouncedSearch.trim()) params.set("search", debouncedSearch.trim());
      const r = await apiFetch(`/analyzers/coauthorship/${activeDomainId}?${params.toString()}`);
      if (!r.ok) throw new Error(`Server responded with ${r.status}`);
      setData((await r.json()) as NetworkResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("page.coauthorship.error_load"));
    } finally {
      setLoading(false);
    }
  }, [activeDomainId, minWeight, communityId, debouncedSearch, t]);

  useEffect(() => {
    void fetchNetwork();
  }, [fetchNetwork, reloadKey]);

  // Keep selection valid as data changes.
  useEffect(() => {
    if (!data || data.nodes.length === 0) {
      setSelected(null);
      return;
    }
    setSelected((cur) => (cur && data.nodes.some((n) => n.id === cur) ? cur : null));
  }, [data]);

  const communities = useMemo(
    () => (data ? Array.from(new Set(data.nodes.map((n) => n.community_id))).sort((a, b) => a - b) : []),
    [data],
  );
  const communityCount = communities.length;
  const updatedLabel = relativeTime(data?.computed_at);

  return (
    <div className="space-y-5 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            {t("page.coauthorship.title")}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("page.coauthorship.subtitle")}
          </p>
        </div>
        <Link href="/analytics" className="text-sm text-blue-600 hover:underline dark:text-blue-400">
          &larr; {t("nav.analytics")}
        </Link>
      </div>

      <MergeSuggestionsPanel isAdmin={isAdmin} onResolved={() => setReloadKey((k) => k + 1)} />

      <GraphControls
        search={search}
        onSearch={setSearch}
        minWeight={minWeight}
        onMinWeight={setMinWeight}
        communities={communities}
        communityId={communityId}
        onCommunity={setCommunityId}
        onResetView={() => {
          setMinWeight(1);
          setCommunityId(null);
          setSearch("");
        }}
      />

      {(data?.stale || (data?.coverage_pct != null && data.coverage_pct < 100) || updatedLabel) && (
        <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
          {data?.stale && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" /> Recomputing…
            </span>
          )}
          {updatedLabel && !data?.stale && <span>Updated {updatedLabel}</span>}
          {data?.coverage_pct != null && data.coverage_pct < 100 && (
            <span>Coverage {data.coverage_pct.toFixed(0)}%</span>
          )}
        </div>
      )}

      {loading && (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
          <SkeletonList rows={10} />
        </div>
      )}

      {!loading && error && (
        <ErrorBanner
          message={t("page.coauthorship.error_load")}
          detail={error}
          onRetry={() => setReloadKey((k) => k + 1)}
        />
      )}

      {!loading && !error && data && (
        <>
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: t("page.coauthorship.nodes"), value: data.nodes.length },
              { label: t("page.coauthorship.edges"), value: data.edges.length },
              { label: t("page.coauthorship.communities"), value: communityCount },
              { label: "Coverage", value: `${(data.coverage_pct ?? 0).toFixed(0)}%` },
            ].map((kpi) => (
              <div key={kpi.label} className="rounded-xl border border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-900">
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
            <div className="grid gap-4 lg:grid-cols-3">
              <div className="col-span-1 rounded-xl border border-gray-200 bg-white p-3 lg:col-span-2 dark:border-gray-800 dark:bg-gray-900">
                <NetworkGraph
                  nodes={data.nodes}
                  edges={data.edges}
                  selected={selected}
                  onNodeClick={setSelected}
                />
              </div>
              <div className="col-span-1 rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
                <NodePropertiesPanel
                  domainId={activeDomainId}
                  authorId={selected}
                  onClose={() => setSelected(null)}
                  onSelectCollaborator={setSelected}
                />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
