"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { EntityConcept } from "../../components/ui";

// ── Standalone embed page — no auth, no sidebar ────────────────────────────
// Rendered at /embed/{token} — consumer sites can iframe this URL directly.

type WidgetType = "entity_stats" | "top_concepts" | "recent_entities" | "quality_score";

interface WidgetPayload {
  widget_type: WidgetType;
  name: string;
  data: Record<string, unknown>;
  fetched_at: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Render helpers ─────────────────────────────────────────────────────────

function EntityStatsView({ data }: { data: Record<string, unknown> }) {
  const total = data.total as number;
  const enriched = data.enriched as number;
  const rate = data.enrichment_rate as number;
  const byDomain = (data.by_domain as Array<{ domain: string; count: number }>) || [];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg bg-blue-50 border border-blue-100 p-3 text-center">
          <p className="text-2xl font-bold text-blue-700">{total ?? 0}</p>
          <p className="mt-1 text-xs text-blue-500">
            <EntityConcept>Total Entities</EntityConcept>
          </p>
        </div>
        <div className="rounded-lg bg-emerald-50 border border-emerald-100 p-3 text-center">
          <p className="text-2xl font-bold text-emerald-700">{enriched ?? 0}</p>
          <p className="text-xs text-emerald-500 mt-1">Enriched</p>
        </div>
        <div className="rounded-lg bg-violet-50 border border-violet-100 p-3 text-center">
          <p className="text-2xl font-bold text-violet-700">{rate ?? 0}%</p>
          <p className="text-xs text-violet-500 mt-1">Enrichment Rate</p>
        </div>
      </div>
      {byDomain.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 mb-2">By Domain</p>
          <div className="space-y-1.5">
            {byDomain.slice(0, 5).map((d) => {
              const pct = total > 0 ? Math.round((d.count / total) * 100) : 0;
              return (
                <div key={d.domain} className="flex items-center gap-2">
                  <span className="text-xs text-slate-600 w-20 truncate">{d.domain}</span>
                  <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-violet-400 rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-xs text-slate-500 w-8 text-right">{d.count}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function TopConceptsView({ data }: { data: Record<string, unknown> }) {
  const concepts = (data.concepts as Array<{ concept: string; count: number }>) || [];
  const max = concepts[0]?.count || 1;

  return (
    <div className="space-y-1.5">
      {concepts.slice(0, 10).map((c) => (
        <div key={c.concept} className="flex items-center gap-2">
          <span className="text-xs text-slate-700 w-28 truncate" title={c.concept}>{c.concept}</span>
          <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full bg-violet-400 rounded-full" style={{ width: `${(c.count / max) * 100}%` }} />
          </div>
          <span className="text-xs text-slate-500 w-6 text-right">{c.count}</span>
        </div>
      ))}
    </div>
  );
}

function RecentEntitiesView({ data }: { data: Record<string, unknown> }) {
  const entities = (data.entities as Array<{ id: number; primary_label: string; domain: string; enrichment_status: string }>) || [];

  const statusColor: Record<string, string> = {
    completed: "text-emerald-600",
    pending: "text-amber-600",
    failed: "text-rose-600",
    none: "text-slate-400",
  };

  return (
    <div className="space-y-2">
      {entities.map((e) => (
        <div key={e.id} className="flex items-center justify-between text-sm">
          <span className="text-slate-800 truncate flex-1">{e.primary_label}</span>
          <span className="text-xs text-slate-400 mx-2">{e.domain}</span>
          <span className={`text-xs font-medium ${statusColor[e.enrichment_status] || "text-slate-500"}`}>
            {e.enrichment_status}
          </span>
        </div>
      ))}
    </div>
  );
}

function QualityScoreView({ data }: { data: Record<string, unknown> }) {
  const avg = data.average as number | null;
  const dist = (data.distribution as Array<{ bucket: string; count: number }>) || [];
  const maxCount = Math.max(...dist.map((d) => d.count), 1);

  const bucketColor: Record<string, string> = {
    "0-25": "bg-rose-400", "26-50": "bg-amber-400", "51-75": "bg-blue-400", "76-100": "bg-emerald-400",
  };

  return (
    <div className="space-y-4">
      <div className="text-center">
        <p className="text-4xl font-bold text-slate-900">{avg !== null ? Math.round(avg * 100) : "—"}</p>
        <p className="text-sm text-slate-400 mt-1">Average Quality Score</p>
      </div>
      <div className="space-y-1.5">
        {dist.map((d) => (
          <div key={d.bucket} className="flex items-center gap-2">
            <span className="text-xs text-slate-600 w-12">{d.bucket}</span>
            <div className="flex-1 h-3 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${bucketColor[d.bucket] || "bg-slate-400"}`}
                style={{ width: `${(d.count / maxCount) * 100}%` }}
              />
            </div>
            <span className="text-xs text-slate-500 w-6 text-right">{d.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

const VIEWS: Record<WidgetType, React.ComponentType<{ data: Record<string, unknown> }>> = {
  entity_stats: EntityStatsView,
  top_concepts: TopConceptsView,
  recent_entities: RecentEntitiesView,
  quality_score: QualityScoreView,
};

// ── Main embed page ────────────────────────────────────────────────────────

export default function EmbedPage() {
  const params = useParams();
  const token = params?.token as string;
  const [payload, setPayload] = useState<WidgetPayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/embed/${token}/data`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        return r.json();
      })
      .then(setPayload)
      .catch((e: Error) => setError(e.message));
  }, [token]);

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50">
        <div className="text-center text-slate-500">
          <p className="text-4xl mb-2">⚠️</p>
          <p className="text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (!payload) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-white">
        <div className="h-6 w-6 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const View = VIEWS[payload.widget_type];

  return (
    <div className="min-h-screen bg-white p-4 font-sans">
      <div className="max-w-sm mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-800 truncate">{payload.name}</h2>
          <span className="text-xs text-slate-400">
            {new Date(payload.fetched_at).toLocaleTimeString()}
          </span>
        </div>

        {/* Widget content */}
        {View ? <View data={payload.data} /> : (
          <pre className="text-xs font-mono text-slate-600 whitespace-pre-wrap">
            {JSON.stringify(payload.data, null, 2)}
          </pre>
        )}

        {/* Footer */}
        <p className="mt-4 text-center text-xs text-slate-300">
          Powered by UKIP
        </p>
      </div>
    </div>
  );
}
