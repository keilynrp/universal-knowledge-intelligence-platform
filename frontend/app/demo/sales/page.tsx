"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { EntityConcept } from "../../components/ui";

interface SalesDeckData {
  generated_at: string;
  kpis: {
    total_entities: number;
    enriched_count: number;
    enrichment_pct: number;
    avg_quality_pct: number;
    domains_count: number;
  };
  domain_breakdown: { domain: string; count: number }[];
  value_props: { icon: string; title: string; desc: string }[];
}

function AnimatedNumber({ value, suffix = "" }: { value: number; suffix?: string }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let start = 0;
    const step = value / 40;
    const timer = setInterval(() => {
      start += step;
      if (start >= value) { setDisplay(value); clearInterval(timer); }
      else setDisplay(Math.floor(start));
    }, 25);
    return () => clearInterval(timer);
  }, [value]);
  return <span>{display.toLocaleString()}{suffix}</span>;
}

export default function SalesDeckPage() {
  const [data, setData] = useState<SalesDeckData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/exports/sales-deck/data")
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(setData)
      .catch(() => setError("Could not load platform data."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex h-64 items-center justify-center">
      <svg className="h-8 w-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
    </div>
  );
  if (error || !data) return <p className="p-8 text-red-500">{error ?? "No data"}</p>;

  const { kpis, domain_breakdown, value_props } = data;

  return (
    <div className="space-y-10 pb-16">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-blue-700 via-indigo-700 to-violet-700 px-10 py-16 text-white shadow-2xl">
        <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-white/5" />
        <div className="absolute -bottom-10 -left-10 h-48 w-48 rounded-full bg-white/5" />
        <div className="relative">
          <div className="mb-3 inline-flex rounded-full bg-white/15 px-4 py-1.5 text-sm font-medium">
            Executive Sales Deck — Live Data
          </div>
          <h1 className="text-4xl font-extrabold leading-tight">Universal Knowledge<br />Intelligence Platform</h1>
          <p className="mt-4 max-w-2xl text-lg text-white/80 leading-relaxed">
            Enterprise-grade master data management, AI enrichment, and analytics — from raw spreadsheets to strategic intelligence in minutes.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="/exports/sales-deck"
              target="_blank"
              className="inline-flex items-center gap-2 rounded-xl bg-white px-5 py-2.5 text-sm font-semibold text-blue-700 shadow hover:bg-blue-50"
            >
              🖨 Export to PDF
            </a>
            <Link
              href="/"
              className="inline-flex items-center gap-2 rounded-xl border border-white/30 bg-white/10 px-5 py-2.5 text-sm font-semibold text-white hover:bg-white/20"
            >
              → Live Platform
            </Link>
          </div>
        </div>
      </div>

      {/* KPI grid */}
      <div>
        <h2 className="mb-5 text-xl font-bold text-gray-900 dark:text-white">Platform at a Glance</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            { id: "entities", label: <EntityConcept>Entities Managed</EntityConcept>, value: kpis.total_entities, suffix: "" },
            { id: "enrichment", label: "Auto-Enriched", value: kpis.enrichment_pct, suffix: "%" },
            { id: "quality", label: "Avg Quality Score", value: kpis.avg_quality_pct, suffix: "%" },
            { id: "domains", label: "Active Domains", value: kpis.domains_count, suffix: "" },
          ].map(({ id, label, value, suffix }) => (
            <div key={id} className="rounded-2xl border border-gray-100 bg-white p-6 text-center shadow-sm dark:border-gray-800 dark:bg-gray-900">
              <div className="text-4xl font-extrabold text-blue-600 dark:text-blue-400">
                <AnimatedNumber value={value} suffix={suffix} />
              </div>
              <div className="mt-2 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">{label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Value Props */}
      <div>
        <h2 className="mb-5 text-xl font-bold text-gray-900 dark:text-white">Why UKIP?</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {value_props.map((vp) => (
            <div key={vp.title} className="rounded-2xl border border-blue-100 bg-blue-50/50 p-6 dark:border-blue-900/30 dark:bg-blue-950/20">
              <div className="mb-3 text-3xl">{vp.icon}</div>
              <div className="mb-2 text-base font-bold text-blue-800 dark:text-blue-300">{vp.title}</div>
              <div className="text-sm leading-relaxed text-gray-600 dark:text-gray-400">{vp.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Workflow Timeline */}
      <div>
        <h2 className="mb-5 text-xl font-bold text-gray-900 dark:text-white">Typical Workflow — With UKIP</h2>
        <div className="relative rounded-2xl border border-gray-100 bg-white p-8 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <div className="flex items-center justify-between gap-2">
            {[
              { step: "1", title: "Import", time: "2 min", color: "bg-blue-600" },
              { step: "→", title: "", time: "", color: "" },
              { step: "2", title: "Auto-Enrich", time: "30 min (auto)", color: "bg-indigo-600" },
              { step: "→", title: "", time: "", color: "" },
              { step: "3", title: "Analyze", time: "5 min", color: "bg-violet-600" },
              { step: "→", title: "", time: "", color: "" },
              { step: "4", title: "Project", time: "2 min", color: "bg-purple-600" },
              { step: "→", title: "", time: "", color: "" },
              { step: "5", title: "Export", time: "1 min", color: "bg-pink-600" },
            ].map((s, i) =>
              s.title ? (
                <div key={i} className="flex flex-col items-center text-center flex-1">
                  <div className={`${s.color} flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold text-white shadow`}>{s.step}</div>
                  <div className="mt-2 text-sm font-semibold text-gray-800 dark:text-gray-200">{s.title}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{s.time}</div>
                </div>
              ) : (
                <div key={i} className="text-gray-300 dark:text-gray-600 text-xl font-light flex-shrink-0">→</div>
              )
            )}
          </div>
          <p className="mt-6 text-center text-sm text-gray-500 dark:text-gray-400">
            Total: ~40 minutes vs. 3 months of manual work
          </p>
        </div>
      </div>

      {/* Domain Breakdown */}
      {domain_breakdown.length > 0 && (
        <div>
          <h2 className="mb-5 text-xl font-bold text-gray-900 dark:text-white">Domain Breakdown</h2>
          <div className="overflow-hidden rounded-2xl border border-gray-100 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-100 dark:border-gray-800">
                <tr>
                  <th className="px-6 py-3.5 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Domain</th>
                  <th className="px-6 py-3.5 text-right text-xs font-semibold uppercase tracking-wider text-gray-500">
                    <EntityConcept>Entities</EntityConcept>
                  </th>
                  <th className="px-6 py-3.5 text-right text-xs font-semibold uppercase tracking-wider text-gray-500">Share</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                {domain_breakdown.map((d) => {
                  const total = domain_breakdown.reduce((s, x) => s + x.count, 0);
                  const pct = total > 0 ? Math.round(d.count / total * 100) : 0;
                  return (
                    <tr key={d.domain} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="px-6 py-3.5 font-medium text-gray-900 dark:text-white">{d.domain}</td>
                      <td className="px-6 py-3.5 text-right tabular-nums text-gray-700 dark:text-gray-300">{d.count.toLocaleString()}</td>
                      <td className="px-6 py-3.5 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-20 h-1.5 rounded-full bg-gray-100 dark:bg-gray-700">
                            <div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${pct}%` }} />
                          </div>
                          <span className="text-xs tabular-nums text-gray-500">{pct}%</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Capabilities checklist */}
      <div>
        <h2 className="mb-5 text-xl font-bold text-gray-900 dark:text-white">82 Sprints Delivered — Full Capability Map</h2>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {[
            "Multi-domain entity management",
            "AI enrichment (OpenAlex, Wikidata, VIAF, ORCID, DBpedia)",
            "OLAP Cube Explorer (DuckDB)",
            "Natural Language Query (NLQ via LLM)",
            "Executive Dashboard + KPIs",
            "Topic Modeling & Correlation Analysis",
            "Data Harmonization Pipeline",
            "Authority Control & Disambiguation",
            "Knowledge Graph Export (GraphML / Cytoscape / JSON-LD)",
            "Scheduled Reports by email (PDF / Excel / HTML)",
            "Alert Channels (Slack / Teams / Discord / webhook)",
            "Public API Keys (175+ endpoints, OpenAPI docs)",
            "Custom Dashboard Builder (drag-and-drop widgets)",
            "Semantic RAG + Context Engineering Layer",
            "Audit Log + RBAC (4 roles) + Account Lockout",
            "LLM-Assisted Column Mapping on Import",
            "Logo & White-Label Branding",
            "Collaborative Annotations + Threading",
          ].map((cap) => (
            <div key={cap} className="flex items-start gap-2 rounded-xl border border-gray-100 bg-gray-50 px-4 py-3 text-sm dark:border-gray-800 dark:bg-gray-800/40">
              <span className="mt-0.5 text-blue-600">✓</span>
              <span className="text-gray-700 dark:text-gray-300">{cap}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
