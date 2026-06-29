"use client";

import { type ReactElement, useState, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useAuth } from "../../contexts/AuthContext";
import {
  Button,
  ErrorBanner,
  SkeletonCard,
  PageHeader,
  useToast,
} from "../../components/ui";
import { JournalsRankingTable, type JournalRow } from "./JournalsRankingTable";
import { JournalsCharts } from "./JournalsCharts";

// ── Types ──────────────────────────────────────────────────────────────────────

interface JournalStats {
  apc_distribution: { currency: string | null; count: number; min: number | null; max: number | null; median: number | null }[];
  open_access_share: { in_doaj: number; total: number; pct: number };
  nif_by_field: { nif_field: string | null; journal_count: number; mean_nif: number }[];
}

// ── Constants ──────────────────────────────────────────────────────────────────

const ADMIN_ROLES = new Set(["admin", "super_admin"]);
const DEFAULT_SORT = "nif";
const DEFAULT_ORDER: "asc" | "desc" = "desc";
const NIF_BAYES_READY_SIGNAL = "nif_bayes_ready";

// ── Page ──────────────────────────────────────────────────────────────────────

export default function JournalsDashboardPage(): ReactElement {
  const { user } = useAuth();
  const isAdmin = user ? ADMIN_ROLES.has(user.role) : false;
  const { toast } = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [journals, setJournals] = useState<JournalRow[]>([]);
  const [stats, setStats] = useState<JournalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recomputing, setRecomputing] = useState(false);

  const sortBy = searchParams.get("sort_by") ?? DEFAULT_SORT;
  const order = (searchParams.get("order") ?? DEFAULT_ORDER) as "asc" | "desc";
  const metricSignal = searchParams.get("metric_signal");
  const showNifBayesReadyOnly = metricSignal === NIF_BAYES_READY_SIGNAL;

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const listParams = new URLSearchParams({ sort_by: sortBy, order });
      if (showNifBayesReadyOnly) {
        listParams.set("metric_signal", NIF_BAYES_READY_SIGNAL);
      }
      const [listRes, statsRes] = await Promise.all([
        apiFetch(`/journals?${listParams.toString()}`),
        apiFetch("/journals/stats"),
      ]);
      if (!listRes.ok) throw new Error(`HTTP ${listRes.status}`);
      if (!statsRes.ok) throw new Error(`HTTP ${statsRes.status}`);
      const listData: JournalRow[] = await listRes.json();
      const statsData: JournalStats = await statsRes.json();
      setJournals(listData);
      setStats(statsData);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load journals");
    } finally {
      setLoading(false);
    }
  }, [sortBy, order, showNifBayesReadyOnly]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  function handleSort(column: string): void {
    const params = new URLSearchParams(searchParams.toString());
    if (column === sortBy) {
      params.set("order", order === "asc" ? "desc" : "asc");
    } else {
      params.set("sort_by", column);
      params.set("order", "desc");
    }
    router.push(`?${params.toString()}`);
  }

  function handleMetricSignalToggle(): void {
    const params = new URLSearchParams(searchParams.toString());
    if (showNifBayesReadyOnly) {
      params.delete("metric_signal");
    } else {
      params.set("metric_signal", NIF_BAYES_READY_SIGNAL);
    }
    router.push(`?${params.toString()}`);
  }

  async function handleRecompute(): Promise<void> {
    setRecomputing(true);
    try {
      const res = await apiFetch("/journals/normalize", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: { updated: number } = await res.json();
      toast(`NIF recomputed for ${data.updated} journal(s)`, "success");
      void fetchData();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Recompute failed", "error");
    } finally {
      setRecomputing(false);
    }
  }

  return (
    <main className="min-h-screen px-5 py-7 text-[var(--ukip-text)] sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1240px] space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <PageHeader
            title="Journals"
            description="Ranked journal metrics: NIF, citedness, h-index and APC."
          />
          {isAdmin && (
            <Button
              variant="primary"
              size="md"
              onClick={() => { void handleRecompute(); }}
              disabled={recomputing}
            >
              {recomputing ? "Recomputing…" : "Recompute NIF"}
            </Button>
          )}
        </div>

        {error && <ErrorBanner message={error} onRetry={fetchData} variant="card" />}

        {loading ? (
          <div className="space-y-4">
            <SkeletonCard />
            <SkeletonCard />
          </div>
        ) : (
          <div className="space-y-6">
            <JournalsCharts stats={stats} />
            <section className="rounded-2xl border border-[var(--ukip-border)] bg-[var(--ukip-surface)] px-4 py-3">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--ukip-muted)]">
                    Facets
                  </h2>
                  <p className="mt-1 text-sm text-[var(--ukip-muted)]">
                    Filter journals by available metric signals.
                  </p>
                </div>
                <Button
                  variant={showNifBayesReadyOnly ? "primary" : "secondary"}
                  size="sm"
                  onClick={handleMetricSignalToggle}
                  aria-pressed={showNifBayesReadyOnly}
                >
                  NIF + Bayes
                </Button>
              </div>
            </section>
            <JournalsRankingTable
              journals={journals}
              sortBy={sortBy}
              order={order}
              onSort={handleSort}
            />
          </div>
        )}
      </div>
    </main>
  );
}
