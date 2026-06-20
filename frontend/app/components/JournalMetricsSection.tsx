"use client";

import { useEffect, useState } from "react";
import type { ReactElement } from "react";
import { apiFetch } from "@/lib/api";
import { JournalProvenanceBadge, formatApc } from "./JournalProvenanceBadge";
import { SkeletonCard } from "./ui/Skeleton";
import Badge from "./ui/Badge";
import Metric from "./ui/Metric";

interface JournalMetricResponse {
  issn_l: string;
  display_name: string | null;
  source_id: string | null;
  two_yr_mean_citedness: number | null;
  h_index: number | null;
  normalized_impact_factor: number | null;
  nif_field: string | null;
  apc_usd: number | null;
  apc_currency: string | null;
  apc_source: string | null;
  is_in_doaj: boolean | null;
  if_metric_kind: string | null;
  nif_updated_at: string | null;
  works_count: number | null;
}

type FetchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "found"; data: JournalMetricResponse }
  | { status: "not_found" }
  | { status: "error" };

export interface JournalMetricsSectionProps {
  issnL: string | null;
}

export function JournalMetricsSection({ issnL }: JournalMetricsSectionProps): ReactElement | null {
  const [state, setState] = useState<FetchState>({ status: "idle" });

  useEffect(() => {
    if (!issnL) return;

    // No synchronous setState here: the initial "idle" state already renders the
    // loading skeleton (see render below), so resetting to "loading" up-front would
    // just trigger an extra cascading render (flagged by react-hooks lint).
    let cancelled = false;

    apiFetch(`/journals/${encodeURIComponent(issnL)}`)
      .then(async (res) => {
        if (cancelled) return;
        if (res.ok) {
          const data = (await res.json()) as JournalMetricResponse;
          setState({ status: "found", data });
        } else if (res.status === 404) {
          setState({ status: "not_found" });
        } else {
          setState({ status: "error" });
        }
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error" });
      });

    return () => {
      cancelled = true;
    };
  }, [issnL]);

  if (!issnL) return null;

  if (state.status === "idle" || state.status === "loading") {
    return (
      <section aria-label="Journal metrics loading">
        <SkeletonCard lines={3} />
      </section>
    );
  }

  if (state.status === "not_found") {
    return (
      <section aria-label="Journal metrics">
        <p className="text-xs text-[var(--ukip-muted)] italic">
          Journal metrics not yet available for this ISSN.
        </p>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section aria-label="Journal metrics">
        <p className="text-xs text-[var(--ukip-muted)] italic">
          Unable to load journal metrics.
        </p>
      </section>
    );
  }

  const { data } = state;

  return (
    <section aria-label="Journal metrics">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-[var(--ukip-text-strong)]">
          {data.display_name ?? issnL}
        </h3>
        {data.nif_field && (
          <Badge variant="info" size="sm">
            {data.nif_field}
          </Badge>
        )}
        {data.is_in_doaj && (
          <Badge variant="success" size="sm">
            Open Access
          </Badge>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {data.normalized_impact_factor != null && (
          <Metric
            label={
              <span className="flex items-center gap-1.5">
                NIF <JournalProvenanceBadge />
              </span>
            }
            value={data.normalized_impact_factor.toFixed(2)}
            description="Field-normalized impact factor"
            tone="violet"
          />
        )}

        {data.two_yr_mean_citedness != null && (
          <Metric
            label="2-yr Mean Citedness"
            value={data.two_yr_mean_citedness.toFixed(1)}
            description="OpenAlex 2-year mean"
            tone="cyan"
          />
        )}

        {data.h_index != null && (
          <Metric
            label="h-index"
            value={data.h_index}
            description="Journal h-index"
            tone="emerald"
          />
        )}

        {data.apc_usd != null && (
          <Metric
            label="APC"
            value={formatApc(data.apc_usd, data.apc_currency)}
            description={data.apc_source ?? "Article Processing Charge"}
            tone="amber"
          />
        )}
      </div>

      {data.works_count != null && data.works_count > 0 && (
        <p className="mt-3 text-xs text-[var(--ukip-muted)]">
          {data.works_count} works in your catalog
        </p>
      )}
    </section>
  );
}
