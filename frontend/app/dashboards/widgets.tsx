/**
 * Sprint 80 — Custom Dashboard: individual widget renderers.
 * Each widget fetches its own data and renders independently.
 */
"use client";

import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "../lib/dateFormat";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Treemap,
} from "recharts";

export interface WidgetConfig {
  id:     string;
  type:   string;
  title?: string;
  cols:   number;
  config: Record<string, unknown>;
}

function resolveWidgetDomain(config: Record<string, unknown>): string {
  const configured = config.domain_id ?? config.domain;
  return typeof configured === "string" && configured.trim() ? configured : "default";
}

// ── Shared shell ──────────────────────────────────────────────────────────────

function WidgetShell({
  title, children, loading, error,
}: {
  title: string;
  children: React.ReactNode;
  loading?: boolean;
  error?: string | null;
}) {
  return (
    <div className="flex h-full flex-col">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
        {title}
      </p>
      {loading ? (
        <div className="flex flex-1 items-center justify-center">
          <svg className="h-6 w-6 animate-spin text-gray-300 dark:text-gray-600" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
      ) : error ? (
        <p className="text-xs text-red-500">{error}</p>
      ) : (
        <div className="flex-1 min-h-0">{children}</div>
      )}
    </div>
  );
}

// ── Entity KPI ────────────────────────────────────────────────────────────────

export function EntityKpiWidget({ config }: { config: WidgetConfig }) {
  const [data, setData] = useState<Record<string, number> | null>(null);
  const [loading, setLoading] = useState(true);
  const domain = resolveWidgetDomain(config.config);

  useEffect(() => {
    apiFetch(`/stats?domain_id=${domain}`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [domain]);

  const kpis = data
    ? [
        { label: "Total Entities",    value: data.total_entities ?? 0,    color: "text-blue-600 dark:text-blue-400" },
        { label: "Enriched",          value: `${data.enrichment_pct ?? 0}%`, color: "text-green-600 dark:text-green-400" },
        { label: "Avg Quality",       value: `${(data.avg_quality ?? 0).toFixed(0)}`,  color: "text-violet-600 dark:text-violet-400" },
      ]
    : [];

  return (
    <WidgetShell title={config.title || "Entity KPIs"} loading={loading}>
      <div className="grid grid-cols-3 gap-3 h-full items-center">
        {kpis.map((k) => (
          <div key={k.label} className="rounded-lg bg-gray-50 dark:bg-gray-800/60 p-3 text-center">
            <p className={`text-2xl font-bold ${k.color}`}>{k.value}</p>
            <p className="mt-0.5 text-[10px] text-gray-500 dark:text-gray-400">{k.label}</p>
          </div>
        ))}
      </div>
    </WidgetShell>
  );
}

// ── Enrichment Coverage ───────────────────────────────────────────────────────

const PIE_COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444"];

export function EnrichmentCoverageWidget({ config }: { config: WidgetConfig }) {
  const [data, setData] = useState<{ name: string; value: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const domain = resolveWidgetDomain(config.config);

  useEffect(() => {
    apiFetch(`/stats?domain_id=${domain}`)
      .then((r) => r.json())
      .then((d) => {
        const total = d.total_entities ?? 0;
        const enriched = Math.round((d.enrichment_pct ?? 0) / 100 * total);
        setData([
          { name: "Enriched",    value: enriched },
          { name: "Unenriched",  value: total - enriched },
        ]);
      })
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [domain]);

  return (
    <WidgetShell title={config.title || "Enrichment Coverage"} loading={loading}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey="value" cx="50%" cy="50%" innerRadius="40%" outerRadius="70%">
            {data.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
          </Pie>
          <Tooltip formatter={(v) => [Number(v) || 0, ""]} />
        </PieChart>
      </ResponsiveContainer>
    </WidgetShell>
  );
}

// ── Top Entities ──────────────────────────────────────────────────────────────

export function TopEntitiesWidget({ config }: { config: WidgetConfig }) {
  const [rows, setRows] = useState<{ id: number; name: string; quality_score: number | null; enrichment_status: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const domain = resolveWidgetDomain(config.config);

  useEffect(() => {
    apiFetch(`/entities?domain_id=${domain}&limit=8&sort=quality_score&order=desc`)
      .then((r) => r.json())
      .then((d) => setRows(Array.isArray(d) ? d : d.items ?? []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [domain]);

  return (
    <WidgetShell title={config.title || "Top Entities"} loading={loading}>
      <div className="overflow-auto h-full">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-800">
              <th className="py-1 text-left font-medium text-gray-500 dark:text-gray-400">Name</th>
              <th className="py-1 text-right font-medium text-gray-500 dark:text-gray-400">Quality</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-gray-50 dark:border-gray-800/50">
                <td className="py-1 text-gray-800 dark:text-gray-200 truncate max-w-[180px]">{r.name}</td>
                <td className="py-1 text-right font-mono text-gray-600 dark:text-gray-400">
                  {r.quality_score != null ? r.quality_score.toFixed(0) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </WidgetShell>
  );
}

// ── Top Facets ────────────────────────────────────────────────────────────────

export function TopBrandsWidget({ config }: { config: WidgetConfig }) {
  const [data, setData] = useState<{ name: string; count: number }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/secondary-labels?limit=8")
      .then((r) => r.json())
      .then((d) => setData(Array.isArray(d) ? d.slice(0, 8) : []))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <WidgetShell title={config.title || "Top Secondary Labels"} loading={loading}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 0, right: 8, top: 0, bottom: 0 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 10 }} />
          <Tooltip />
          <Bar dataKey="count" fill="#6366f1" radius={[0, 3, 3, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </WidgetShell>
  );
}

// ── Semantic Co-occurrence Map ────────────────────────────────────────────────

interface CooccurrencePair {
  concept_a: string;
  concept_b: string;
  count: number;
  pmi: number;
  semantic_score?: number;
}

interface CooccurrenceTile extends Record<string, unknown> {
  name: string;
  value: number;
  count: number;
  pmi: number;
  semanticScore: number;
}

function CooccurrenceTileContent(props: Record<string, unknown>) {
  const x = Number(props.x ?? 0);
  const y = Number(props.y ?? 0);
  const width = Number(props.width ?? 0);
  const height = Number(props.height ?? 0);
  const name = String(props.name ?? "");
  const pmi = Number(props.pmi ?? 0);
  const count = Number(props.count ?? 0);
  const intensity = Math.max(0.18, Math.min(0.92, 0.22 + Math.max(pmi, 0) / 6));
  const fill = `rgba(124, 58, 237, ${intensity})`;
  const canShowText = width > 92 && height > 42;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={Math.max(width - 3, 0)}
        height={Math.max(height - 3, 0)}
        rx={7}
        ry={7}
        fill={fill}
        stroke="rgba(255,255,255,0.78)"
        strokeWidth={1}
      />
      {canShowText && (
        <>
          <text x={x + 8} y={y + 16} fill="#fff" fontSize={10} fontWeight={700}>
            {name.length > 30 ? `${name.slice(0, 27)}...` : name}
          </text>
          <text x={x + 8} y={y + 32} fill="rgba(255,255,255,0.82)" fontSize={9}>
            {count}x · PMI {pmi.toFixed(2)}
          </text>
        </>
      )}
    </g>
  );
}

export function ConceptCloudWidget({ config }: { config: WidgetConfig }) {
  const [pairs, setPairs] = useState<CooccurrencePair[]>([]);
  const [normalizedCount, setNormalizedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const domain = resolveWidgetDomain(config.config);

  useEffect(() => {
    apiFetch(`/analyzers/cooccurrence/${domain}?top_n=18&normalize_similar=true&min_similarity=0.88`)
      .then((r) => r.json())
      .then((d) => {
        setPairs(Array.isArray(d) ? [] : d.pairs ?? []);
        setNormalizedCount(Array.isArray(d) ? 0 : d.normalization?.merged_terms?.length ?? 0);
      })
      .catch(() => {
        setPairs([]);
        setNormalizedCount(0);
      })
      .finally(() => setLoading(false));
  }, [domain]);

  if (loading) return <WidgetShell title={config.title || "Coocurrencia temática"} loading>{null}</WidgetShell>;

  const tiles: CooccurrenceTile[] = pairs.map((pair) => ({
    name: `${pair.concept_a} + ${pair.concept_b}`,
    value: Math.max(pair.count, 1),
    count: pair.count,
    pmi: pair.pmi,
    semanticScore: pair.semantic_score ?? pair.count * Math.max(pair.pmi, 0),
  }));

  return (
    <WidgetShell title={config.title || "Coocurrencia temática"}>
      <div className="flex h-full flex-col gap-2">
        <div className="flex items-center justify-between text-[10px] text-gray-500 dark:text-gray-400">
          <span>{pairs.length} pares depurados</span>
          <span>Jaro-Winkler · Levenshtein{normalizedCount ? ` · ${normalizedCount} merges` : ""}</span>
        </div>
        {tiles.length === 0 ? (
          <p className="flex h-full items-center justify-center text-xs text-gray-400">
            No hay coocurrencias suficientes. Enriquece entidades con al menos 2 keywords.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <Treemap
              data={tiles}
              dataKey="value"
              aspectRatio={4 / 3}
              stroke="#fff"
              content={<CooccurrenceTileContent />}
            >
              <Tooltip
                formatter={(value, name, item) => {
                  const payload = item.payload as CooccurrenceTile;
                  return [`${value} coocurrencias · PMI ${payload.pmi.toFixed(2)}`, payload.name];
                }}
              />
            </Treemap>
          </ResponsiveContainer>
        )}
      </div>
    </WidgetShell>
  );
}

// ── Recent Activity ───────────────────────────────────────────────────────────

export function RecentActivityWidget({ config }: { config: WidgetConfig }) {
  const [items, setItems] = useState<{ id: number; action: string; username: string; created_at: string }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/audit-log?limit=8")
      .then((r) => r.json())
      .then((d) => setItems(Array.isArray(d) ? d : d.items ?? []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <WidgetShell title={config.title || "Recent Activity"} loading={loading}>
      <div className="space-y-1.5 overflow-auto h-full">
        {items.map((item) => (
          <div key={item.id} className="flex items-start gap-2">
            <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
            <div className="min-w-0">
              <p className="truncate text-[11px] text-gray-700 dark:text-gray-300">{item.action}</p>
              <p className="text-[10px] text-gray-400">
                {item.username} · {formatDateTime(item.created_at, undefined, { hour: "2-digit", minute: "2-digit" })}
              </p>
            </div>
          </div>
        ))}
        {items.length === 0 && <p className="text-xs text-gray-400">No recent activity.</p>}
      </div>
    </WidgetShell>
  );
}

// ── Quality Histogram ─────────────────────────────────────────────────────────

export function QualityHistogramWidget({ config }: { config: WidgetConfig }) {
  const [data, setData] = useState<{ range: string; count: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const domain = resolveWidgetDomain(config.config);

  useEffect(() => {
    apiFetch(`/entities?domain_id=${domain}&limit=500`)
      .then((r) => r.json())
      .then((d) => {
        const entities = Array.isArray(d) ? d : d.items ?? [];
        const buckets = [0, 0, 0, 0, 0]; // 0-19, 20-39, 40-59, 60-79, 80-100
        entities.forEach((e: { quality_score: number | null }) => {
          const s = e.quality_score ?? 0;
          const b = Math.min(Math.floor(s / 20), 4);
          buckets[b]++;
        });
        setData([
          { range: "0–19",  count: buckets[0] },
          { range: "20–39", count: buckets[1] },
          { range: "40–59", count: buckets[2] },
          { range: "60–79", count: buckets[3] },
          { range: "80–100", count: buckets[4] },
        ]);
      })
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [domain]);

  return (
    <WidgetShell title={config.title || "Quality Distribution"} loading={loading}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
          <XAxis dataKey="range" tick={{ fontSize: 9 }} />
          <YAxis tick={{ fontSize: 9 }} />
          <Tooltip />
          <Bar dataKey="count" fill="#10b981" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </WidgetShell>
  );
}

// ── OLAP Snapshot ─────────────────────────────────────────────────────────────

export function OlapSnapshotWidget({ config }: { config: WidgetConfig }) {
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [cols, setCols] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const domain = resolveWidgetDomain(config.config);
  const groupBy = useMemo(() => {
    const configured = config.config.group_by;
    return Array.isArray(configured) ? configured as string[] : [];
  }, [config.config.group_by]);
  const groupByKey = groupBy.join(",");

  useEffect(() => {
    if (!groupBy.length) {
      return;
    }
    apiFetch("/cube/query", {
      method: "POST",
      body: JSON.stringify({ domain_id: domain, group_by: groupBy, filters: {}, limit: 8 }),
    })
      .then((r) => r.json())
      .then((d) => {
        setRows(d.rows ?? []);
        setCols(d.columns ?? []);
        })
        .catch(() => setError("Failed to load OLAP data."))
        .finally(() => setLoading(false));
  }, [domain, groupBy, groupByKey]);

  const widgetError = !groupBy.length
    ? "Configure a group_by dimension in widget settings."
    : error;
  const widgetLoading = groupBy.length ? loading : false;

  return (
    <WidgetShell title={config.title || "OLAP Snapshot"} loading={widgetLoading} error={widgetError}>
      <div className="overflow-auto h-full">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-800">
              {cols.map((c) => (
                <th key={c} className="py-1 text-left font-medium text-gray-500 dark:text-gray-400">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-b border-gray-50 dark:border-gray-800/50">
                {cols.map((c) => (
                  <td key={c} className="py-1 text-gray-700 dark:text-gray-300">
                    {String(row[c] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </WidgetShell>
  );
}

// ── Widget registry ───────────────────────────────────────────────────────────

export const WIDGET_REGISTRY: Record<string, React.FC<{ config: WidgetConfig }>> = {
  entity_kpi:           EntityKpiWidget,
  enrichment_coverage:  EnrichmentCoverageWidget,
  top_entities:         TopEntitiesWidget,
  top_brands:           TopBrandsWidget,
  top_secondary_labels: TopBrandsWidget,
  concept_cloud:        ConceptCloudWidget,
  recent_activity:      RecentActivityWidget,
  quality_histogram:    QualityHistogramWidget,
  olap_snapshot:        OlapSnapshotWidget,
};
