"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useDomain } from "../../contexts/DomainContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { useAuth } from "../../contexts/AuthContext";
import { apiFetch } from "@/lib/api";
import { SkeletonList, ErrorBanner, EmptyState as UiEmptyState } from "../../components/ui";

// Lazy-load NetworkGraph so d3-force (~25 KB gz) only ships to this page.
const NetworkGraph = dynamic(
  () => import("../../components/graph/NetworkGraph").then((m) => m.NetworkGraph),
  { ssr: false, loading: () => <div className="h-[520px] animate-pulse rounded-lg bg-slate-100 dark:bg-slate-900" /> },
);

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
  const { user } = useAuth();
  const isAdmin = user?.role === "admin" || user?.role === "super_admin";
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<NetworkResult | null>(null);
  const [minWeight, setMinWeight] = useState(1);
  const [backfillState, setBackfillState] = useState<{
    running: boolean;
    result: { mode: string; scanned: number; with_authors: number; edges_generated: number } | null;
    error: string | null;
  }>({ running: false, result: null, error: null });

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

  const runBackfill = useCallback(async () => {
    setBackfillState({ running: true, result: null, error: null });
    try {
      const r = await apiFetch("/admin/data-fixes/coauthor-edges", {
        method: "POST",
        body: JSON.stringify({ dry_run: false }),
      });
      if (!r.ok) {
        // Surface the FastAPI `detail` so the admin can see the real cause.
        let detail = `${r.status}`;
        try {
          const body = await r.json();
          if (typeof body?.detail === "string") detail = body.detail;
        } catch {
          /* not JSON */
        }
        throw new Error(`Backfill failed: ${detail}`);
      }
      const result = await r.json();
      setBackfillState({ running: false, result, error: null });
      // Refresh the network with new data
      fetchNetwork(activeDomainId, minWeight);
    } catch (err) {
      setBackfillState({
        running: false,
        result: null,
        error: err instanceof Error ? err.message : "Backfill failed",
      });
    }
  }, [activeDomainId, minWeight, fetchNetwork]);

  const communityCount = data ? new Set(data.nodes.map((n) => n.community_id)).size : 0;

  const [selected, setSelected] = useState<string | null>(null);
  const selectedNode = useMemo(
    () => (data && selected ? data.nodes.find((n) => n.id === selected) || null : null),
    [data, selected],
  );
  const neighborEdges = useMemo(
    () =>
      data && selected
        ? data.edges
            .filter((e) => e.source === selected || e.target === selected)
            .slice(0, 12)
        : [],
    [data, selected],
  );

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
      <div className="flex flex-wrap items-center gap-4">
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

        {isAdmin && (
          <div className="ml-auto flex items-center gap-3">
            {backfillState.result && (
              <span className="text-xs text-emerald-700 dark:text-emerald-300">
                {t("page.coauthorship.backfill_done") || "Backfill done"}:{" "}
                <span className="font-mono">
                  {backfillState.result.with_authors}
                </span>{" "}
                {t("page.coauthorship.backfill_entities") || "entities"}
              </span>
            )}
            {backfillState.error && (
              <span className="text-xs text-rose-700 dark:text-rose-300">
                {backfillState.error}
              </span>
            )}
            <button
              type="button"
              onClick={runBackfill}
              disabled={backfillState.running}
              className="rounded-md border border-violet-300 bg-violet-50 px-3 py-1.5 text-xs font-medium text-violet-700 hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-violet-800 dark:bg-violet-900/30 dark:text-violet-200 dark:hover:bg-violet-900/50"
              title={
                t("page.coauthorship.backfill_tooltip") ||
                "Materialize co-author edges for entities that were enriched before the extraction hook landed."
              }
            >
              {backfillState.running
                ? t("page.coauthorship.backfill_running") || "Running…"
                : t("page.coauthorship.backfill_button") || "Backfill co-author edges"}
            </button>
          </div>
        )}
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
            <div className="grid gap-4 lg:grid-cols-3">
              {/* Force-directed graph */}
              <div className="col-span-1 rounded-xl border border-gray-200 bg-white p-3 lg:col-span-2 dark:border-gray-800 dark:bg-gray-900">
                <NetworkGraph
                  nodes={data.nodes}
                  edges={data.edges}
                  selected={selected}
                  onNodeClick={setSelected}
                />
              </div>

              {/* Inspection panel */}
              <div className="col-span-1 rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
                {!selectedNode && (
                  <div className="flex h-full min-h-[420px] flex-col items-center justify-center p-6 text-center">
                    <div className="text-4xl">🕸️</div>
                    <p className="mt-3 text-sm font-medium text-gray-700 dark:text-gray-200">
                      {t("page.coauthorship.pick_node") || "Pick an author"}
                    </p>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      {t("page.coauthorship.pick_hint") ||
                        "Click a node in the graph to inspect their collaborators."}
                    </p>
                  </div>
                )}

                {selectedNode && (() => {
                  const colorIdx = selectedNode.community_id % COMMUNITY_COLORS.length;
                  return (
                    <div className="flex h-full min-h-[420px] flex-col">
                      <div className="flex items-start justify-between border-b border-gray-100 px-5 py-4 dark:border-gray-800">
                        <div>
                          <div className="flex items-center gap-2">
                            <span
                              className={`inline-block h-2.5 w-2.5 rounded-full ${COMMUNITY_COLORS[colorIdx]}`}
                            />
                            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                              {selectedNode.label}
                            </h3>
                          </div>
                          <p className={`mt-0.5 text-xs ${COMMUNITY_TEXT_COLORS[colorIdx]}`}>
                            {t("page.coauthorship.community")} C{selectedNode.community_id}
                          </p>
                        </div>
                        <button
                          onClick={() => setSelected(null)}
                          className="rounded-full p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                          aria-label="Close"
                        >
                          ✕
                        </button>
                      </div>

                      <div className="grid grid-cols-2 gap-3 px-5 py-4">
                        <div>
                          <p className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
                            {t("page.coauthorship.degree")}
                          </p>
                          <p className="mt-1 text-xl font-semibold tabular-nums text-gray-900 dark:text-white">
                            {selectedNode.degree}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
                            Centrality
                          </p>
                          <p className="mt-1 text-xl font-semibold tabular-nums text-gray-900 dark:text-white">
                            {selectedNode.centrality.toFixed(3)}
                          </p>
                        </div>
                      </div>

                      <div className="flex-1 overflow-y-auto px-5 pb-5">
                        <p className="mb-2 text-[11px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
                          {t("page.coauthorship.top_collaborators")}
                        </p>
                        {neighborEdges.length === 0 ? (
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            {t("page.coauthorship.no_collaborators") || "No collaborators in current view."}
                          </p>
                        ) : (
                          <ul className="space-y-1">
                            {neighborEdges.map((edge, i) => {
                              const other =
                                edge.source === selectedNode.id ? edge.target : edge.source;
                              return (
                                <li
                                  key={`${edge.source}-${edge.target}-${i}`}
                                  className="flex items-center justify-between rounded px-2 py-1.5 text-sm text-gray-800 hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-gray-800/40"
                                >
                                  <button
                                    type="button"
                                    onClick={() => setSelected(other)}
                                    className="truncate text-left hover:underline"
                                  >
                                    {other}
                                  </button>
                                  <span className="ml-2 shrink-0 rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-medium text-violet-700 dark:bg-violet-900/30 dark:text-violet-300">
                                    {edge.weight}
                                  </span>
                                </li>
                              );
                            })}
                          </ul>
                        )}
                      </div>
                    </div>
                  );
                })()}
              </div>

              {/* Top-collaborators table (full width below the graph) */}
              <div className="col-span-1 rounded-xl border border-gray-200 bg-white lg:col-span-3 dark:border-gray-800 dark:bg-gray-900">
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
                    const isSel = selected === node.id;
                    return (
                      <button
                        key={node.id}
                        type="button"
                        onClick={() => setSelected(node.id)}
                        className={`grid w-full grid-cols-[1fr_4rem_4rem_5rem] items-center gap-2 px-4 py-2.5 text-left transition ${
                          isSel
                            ? "bg-blue-50 dark:bg-blue-900/20"
                            : "hover:bg-gray-50 dark:hover:bg-gray-800/40"
                        }`}
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
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
