"use client";

import { type ReactElement } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import Panel from "../../components/ui/Panel";
import SectionHeader from "../../components/ui/SectionHeader";
import Metric from "../../components/ui/Metric";
import EmptyState from "../../components/ui/EmptyState";
import { JournalProvenanceBadge } from "../../components/JournalProvenanceBadge";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ApcBucket {
  currency: string | null;
  count: number;
  min: number | null;
  max: number | null;
  median: number | null;
}

interface NifByField {
  nif_field: string | null;
  journal_count: number;
  mean_nif: number;
}

interface JournalStats {
  apc_distribution: ApcBucket[];
  open_access_share: { in_doaj: number; total: number; pct: number };
  nif_by_field: NifByField[];
}

export interface JournalsChartsProps {
  stats: JournalStats | null;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function JournalsCharts({ stats }: JournalsChartsProps): ReactElement {
  if (stats === null) {
    return (
      <EmptyState
        icon="chart"
        title="No data available"
        description="Journal statistics are not yet available. Enrich journal records to see APC and NIF distributions."
        size="card"
      />
    );
  }

  const { apc_distribution, open_access_share, nif_by_field } = stats;

  const nifChartData = nif_by_field.map((row) => ({
    name: row.nif_field ?? "Unknown",
    mean_nif: Number(row.mean_nif.toFixed(3)),
    journal_count: row.journal_count,
  }));

  const apcChartData = apc_distribution.map((bucket) => ({
    name: bucket.currency ?? "N/A",
    median: bucket.median ?? 0,
    count: bucket.count,
  }));

  return (
    <div className="space-y-6">
      {/* Open-access share metric — plain DOM text so it is testable */}
      <Metric
        label="Open Access (DOAJ)"
        value={`${open_access_share.pct.toFixed(1)}%`}
        description={`${open_access_share.in_doaj} of ${open_access_share.total} journals indexed in DOAJ`}
        tone="emerald"
      />

      {/* NIF by discipline chart */}
      <Panel>
        <div className="p-5">
          <SectionHeader
            eyebrow="Impact"
            title={
              <span className="flex flex-wrap items-center gap-2">
                NIF by discipline
                <JournalProvenanceBadge />
              </span>
            }
            description="Mean normalized impact factor (open proxy — not Clarivate JIF)"
          />
          <div className="mt-5 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={nifChartData}
                margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="var(--ukip-border)" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 11, fill: "var(--ukip-muted)" }}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "var(--ukip-muted)" }}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--ukip-panel)",
                    border: "1px solid var(--ukip-border)",
                    borderRadius: "8px",
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="mean_nif" fill="var(--ukip-violet)" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </Panel>

      {/* APC distribution chart */}
      <Panel>
        <div className="p-5">
          <SectionHeader
            eyebrow="Cost"
            title="APC distribution by currency"
            description="Median Article Processing Charge per currency (source: OpenAlex + DOAJ)"
          />
          <div className="mt-5 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={apcChartData}
                margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="var(--ukip-border)" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 11, fill: "var(--ukip-muted)" }}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "var(--ukip-muted)" }}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--ukip-panel)",
                    border: "1px solid var(--ukip-border)",
                    borderRadius: "8px",
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="median" fill="var(--ukip-cyan)" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          {apc_distribution.map((bucket) =>
            bucket.min != null && bucket.max != null ? (
              <p
                key={bucket.currency ?? "N/A"}
                className="mt-1 text-xs text-[var(--ukip-muted)]"
              >
                {bucket.currency ?? "N/A"}: range {bucket.min.toLocaleString("en-US")}–
                {bucket.max.toLocaleString("en-US")} (n={bucket.count})
              </p>
            ) : null
          )}
        </div>
      </Panel>
    </div>
  );
}
