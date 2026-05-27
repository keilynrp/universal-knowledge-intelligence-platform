"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { apiFetch } from "@/lib/api";

import { ErrorBanner, PageHeader } from "../../components/ui";
import { useAssistantContextRegistration } from "../../contexts/AssistantContext";
import { useDomain } from "../../contexts/DomainContext";

type ScoreDrivers = {
  topic_match: number;
  publication_signal: number;
  citation_signal: number;
  recency_signal: number;
  authority_signal: number;
  quality_signal: number;
};

type ResearcherEvidence = {
  entity_id: number;
  title: string | null;
  secondary_label: string | null;
  citations: number;
};

type Researcher = {
  name: string;
  orcid: string | null;
  openalex_id: string | null;
  records_count: number;
  citation_count: number;
  topic_score: number;
  drivers: ScoreDrivers;
  evidence: ResearcherEvidence[];
};

type ResearchersPayload = {
  domain_id: string;
  topic: string;
  filters: TopicFilters;
  records_analyzed: number;
  researcher_count: number;
  researchers: Researcher[];
  executive_summary: ExecutiveSummary;
};

type GraphNode = {
  id: string;
  type: "topic" | "researcher";
  label: string;
  score: number;
  records_count?: number;
  citation_count?: number;
};

type GraphEdge = {
  source: string;
  target: string;
  type: "works_on_topic" | "coauthor_with";
  weight: number;
};

type GraphPayload = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  summary: {
    researcher_count: number;
    relationship_count: number;
    records_analyzed: number;
    top_researcher: Researcher | null;
    executive_summary: ExecutiveSummary;
  };
};

type PositionedNode = GraphNode & { x: number; y: number };

type TopicFilters = {
  source: string | null;
  year_from: number | null;
  year_to: number | null;
  country: string | null;
  institution: string | null;
  min_citations: number;
};

type ExecutiveSummary = {
  topic: string;
  confidence: number;
  coverage_score: number;
  network_density_score: number | null;
  high_confidence_researchers: number;
  total_citations: number;
  top_researcher: Researcher | null;
  headline: string;
  stakeholder_value: string;
};

type FilterForm = {
  source: string;
  yearFrom: string;
  yearTo: string;
  country: string;
  institution: string;
  minCitations: string;
};

const DRIVER_LABELS: Array<{ key: keyof ScoreDrivers; label: string }> = [
  { key: "topic_match", label: "Tema" },
  { key: "publication_signal", label: "Produccion" },
  { key: "citation_signal", label: "Citas" },
  { key: "recency_signal", label: "Recencia" },
  { key: "authority_signal", label: "Autoridad" },
  { key: "quality_signal", label: "Calidad" },
];

function scoreTone(score: number) {
  if (score >= 70) return "text-emerald-700 bg-emerald-50 ring-emerald-200 dark:text-emerald-200 dark:bg-emerald-400/10 dark:ring-emerald-400/20";
  if (score >= 40) return "text-amber-700 bg-amber-50 ring-amber-200 dark:text-amber-200 dark:bg-amber-400/10 dark:ring-amber-400/20";
  return "text-red-700 bg-red-50 ring-red-200 dark:text-red-200 dark:bg-red-400/10 dark:ring-red-400/20";
}

function barColor(score: number) {
  if (score >= 70) return "bg-emerald-500";
  if (score >= 40) return "bg-amber-500";
  return "bg-red-500";
}

function externalHref(id: string | null) {
  if (!id) return null;
  if (id.startsWith("http")) return id;
  if (id.startsWith("0000-")) return `https://orcid.org/${id}`;
  return id;
}

function buildQuery(topic: string, domainId: string, filters: FilterForm, limit: string, minWeight?: string) {
  const params = new URLSearchParams({ topic, domain_id: domainId, limit });
  if (minWeight) params.set("min_weight", minWeight);
  if (filters.source.trim()) params.set("source", filters.source.trim());
  if (filters.yearFrom.trim()) params.set("year_from", filters.yearFrom.trim());
  if (filters.yearTo.trim()) params.set("year_to", filters.yearTo.trim());
  if (filters.country.trim()) params.set("country", filters.country.trim());
  if (filters.institution.trim()) params.set("institution", filters.institution.trim());
  if (filters.minCitations.trim()) params.set("min_citations", filters.minCitations.trim());
  return params;
}

function ExecutiveMetricCard({ summary }: { summary: ExecutiveSummary | null }) {
  const confidence = summary?.confidence ?? 0;
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-slate-950">
      <div className="grid gap-5 lg:grid-cols-[220px_1fr]">
        <div className={`rounded-3xl p-5 ring-1 ${scoreTone(confidence)}`}>
          <p className="text-xs font-black uppercase tracking-[0.14em]">Metrica ejecutiva</p>
          <p className="mt-3 text-5xl font-black tabular-nums">{confidence}</p>
          <p className="mt-1 text-sm font-bold">confianza del mapa</p>
        </div>
        <div className="min-w-0">
          <h2 className="text-xl font-black tracking-normal text-slate-950 dark:text-white">
            {summary?.headline ?? "Ejecuta una busqueda para generar el mapa ejecutivo."}
          </h2>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            {summary?.stakeholder_value ?? "La metrica resume cobertura, autoridad, citas, evidencia y densidad de red para briefs y conversaciones ejecutivas."}
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-4">
            {[
              { label: "Cobertura", value: summary?.coverage_score ?? 0 },
              { label: "Alta confianza", value: summary?.high_confidence_researchers ?? 0 },
              { label: "Citas", value: summary?.total_citations ?? 0 },
              { label: "Densidad red", value: summary?.network_density_score ?? 0 },
            ].map((metric) => (
              <div key={metric.label} className="rounded-2xl bg-slate-50 p-3 dark:bg-white/5">
                <p className="text-xs font-bold text-slate-500">{metric.label}</p>
                <p className="mt-1 text-2xl font-black text-slate-950 dark:text-white">{metric.value}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function TopicGraph({ graph }: { graph: GraphPayload | null }) {
  const { nodes, edges, nodeMap } = useMemo(() => {
    if (!graph || graph.nodes.length === 0) return { nodes: [] as PositionedNode[], edges: [] as GraphEdge[], nodeMap: new Map<string, PositionedNode>() };
    const topic = graph.nodes.find((node) => node.type === "topic") ?? graph.nodes[0];
    const researchers = graph.nodes.filter((node) => node.type === "researcher").slice(0, 18);
    const center = { ...topic, x: 360, y: 220 };
    const radiusX = researchers.length > 8 ? 250 : 210;
    const radiusY = researchers.length > 8 ? 145 : 120;
    const positioned: PositionedNode[] = [
      center,
      ...researchers.map((node, index) => {
        const angle = (Math.PI * 2 * index) / Math.max(researchers.length, 1) - Math.PI / 2;
        return {
          ...node,
          x: 360 + Math.cos(angle) * radiusX,
          y: 220 + Math.sin(angle) * radiusY,
        };
      }),
    ];
    const map = new Map(positioned.map((node) => [node.id, node]));
    return {
      nodes: positioned,
      edges: graph.edges.filter((edge) => map.has(edge.source) && map.has(edge.target)).slice(0, 40),
      nodeMap: map,
    };
  }, [graph]);

  if (!graph || nodes.length === 0) {
    return (
      <div className="flex min-h-[360px] items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white text-sm text-slate-500 dark:border-white/10 dark:bg-slate-950 dark:text-slate-400">
        Ejecuta una busqueda para construir la red del tema.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-slate-950">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-black tracking-normal text-slate-950 dark:text-white">Red de investigadores</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {graph.summary.researcher_count} investigadores · {graph.summary.relationship_count} relaciones
          </p>
        </div>
        <div className="flex gap-2 text-xs font-bold">
          <span className="rounded-full bg-violet-50 px-3 py-1 text-violet-700 ring-1 ring-violet-200 dark:bg-violet-400/10 dark:text-violet-200 dark:ring-violet-400/20">tema</span>
          <span className="rounded-full bg-blue-50 px-3 py-1 text-blue-700 ring-1 ring-blue-200 dark:bg-blue-400/10 dark:text-blue-200 dark:ring-blue-400/20">autor</span>
          <span className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-700 ring-1 ring-emerald-200 dark:bg-emerald-400/10 dark:text-emerald-200 dark:ring-emerald-400/20">coautoria</span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <svg viewBox="0 0 720 440" className="h-[420px] min-w-[720px] rounded-xl bg-slate-50 dark:bg-slate-900" role="img" aria-label="Grafo de investigadores por tema">
          {edges.map((edge) => {
            const source = nodeMap.get(edge.source);
            const target = nodeMap.get(edge.target);
            if (!source || !target) return null;
            const isCoauthor = edge.type === "coauthor_with";
            return (
              <line
                key={`${edge.source}-${edge.target}-${edge.type}`}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke={isCoauthor ? "#10b981" : "#8b5cf6"}
                strokeOpacity={isCoauthor ? 0.42 : 0.28}
                strokeWidth={Math.min(8, 1.5 + edge.weight)}
              />
            );
          })}
          {nodes.map((node) => {
            const isTopic = node.type === "topic";
            const radius = isTopic ? 34 : Math.max(18, Math.min(30, 16 + node.score / 8));
            return (
              <g key={node.id}>
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={radius}
                  fill={isTopic ? "#7c3aed" : "#2563eb"}
                  opacity={isTopic ? 0.95 : 0.9}
                />
                <circle cx={node.x} cy={node.y} r={radius + 5} fill="none" stroke={isTopic ? "#c4b5fd" : "#bfdbfe"} strokeOpacity={0.7} />
                <text x={node.x} y={node.y + radius + 18} textAnchor="middle" className="fill-slate-700 text-[12px] font-bold dark:fill-slate-200">
                  {node.label.length > 24 ? `${node.label.slice(0, 22)}...` : node.label}
                </text>
                <text x={node.x} y={node.y + 4} textAnchor="middle" className="fill-white text-[12px] font-black">
                  {isTopic ? "T" : node.score}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

function ResearcherCard({ researcher, rank }: { researcher: Researcher; rank: number }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-slate-950">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-sm font-black text-blue-700 ring-1 ring-blue-100 dark:bg-blue-400/10 dark:text-blue-200 dark:ring-blue-400/20">
              {rank}
            </span>
            <div className="min-w-0">
              <h3 className="truncate text-base font-black tracking-normal text-slate-950 dark:text-white">{researcher.name}</h3>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Investigador identificado</p>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2 text-xs font-bold">
            {researcher.orcid && (
              <a href={externalHref(researcher.orcid) ?? "#"} target="_blank" rel="noreferrer" className="rounded-full bg-slate-100 px-3 py-1 text-slate-700 hover:text-blue-700 dark:bg-white/10 dark:text-slate-200">
                ORCID {researcher.orcid}
              </a>
            )}
            {researcher.openalex_id && (
              <a href={externalHref(researcher.openalex_id) ?? "#"} target="_blank" rel="noreferrer" className="rounded-full bg-slate-100 px-3 py-1 text-slate-700 hover:text-blue-700 dark:bg-white/10 dark:text-slate-200">
                OpenAlex
              </a>
            )}
          </div>
        </div>
        <div className={`rounded-2xl px-4 py-3 text-center ring-1 ${scoreTone(researcher.topic_score)}`}>
          <p className="text-3xl font-black tabular-nums">{researcher.topic_score}</p>
          <p className="text-[11px] font-bold uppercase tracking-[0.14em]">score</p>
        </div>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-3">
        <div className="rounded-xl bg-slate-50 p-3 dark:bg-white/5">
          <p className="text-xs text-slate-500">Registros</p>
          <p className="text-xl font-black text-slate-950 dark:text-white">{researcher.records_count}</p>
        </div>
        <div className="rounded-xl bg-slate-50 p-3 dark:bg-white/5">
          <p className="text-xs text-slate-500">Citas</p>
          <p className="text-xl font-black text-slate-950 dark:text-white">{researcher.citation_count}</p>
        </div>
        <div className="rounded-xl bg-slate-50 p-3 dark:bg-white/5">
          <p className="text-xs text-slate-500">Evidencias</p>
          <p className="text-xl font-black text-slate-950 dark:text-white">{researcher.evidence.length}</p>
        </div>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {DRIVER_LABELS.map(({ key, label }) => (
          <div key={key}>
            <div className="mb-1 flex justify-between text-xs font-bold text-slate-500">
              <span>{label}</span>
              <span>{researcher.drivers[key]}%</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100 dark:bg-white/10">
              <div className={`h-full rounded-full ${barColor(researcher.drivers[key])}`} style={{ width: `${researcher.drivers[key]}%` }} />
            </div>
          </div>
        ))}
      </div>
      {researcher.evidence.length > 0 && (
        <div className="mt-5 space-y-2">
          <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">Evidencia</p>
          {researcher.evidence.map((item) => (
            <Link
              key={item.entity_id}
              href={`/entities/${item.entity_id}`}
              className="block rounded-xl border border-slate-100 px-3 py-2 text-sm text-slate-700 transition hover:border-blue-200 hover:bg-blue-50 dark:border-white/10 dark:text-slate-200 dark:hover:bg-blue-400/10"
            >
              <span className="font-semibold">{item.title || `Registro ${item.entity_id}`}</span>
              <span className="ml-2 text-xs text-slate-400">{item.citations} citas</span>
            </Link>
          ))}
        </div>
      )}
    </article>
  );
}

export default function ResearchersByTopicPage() {
  const searchParams = useSearchParams();
  const { activeDomainId } = useDomain();
  const initialTopic = searchParams.get("topic") || searchParams.get("signal") || "open science";
  const [topicInput, setTopicInput] = useState(initialTopic);
  const [activeTopic, setActiveTopic] = useState(initialTopic);
  const [data, setData] = useState<ResearchersPayload | null>(null);
  const [graph, setGraph] = useState<GraphPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterForm>({
    source: "",
    yearFrom: "",
    yearTo: "",
    country: "",
    institution: "",
    minCitations: "",
  });
  const filtersRef = useRef(filters);
  const [feedback, setFeedback] = useState<"useful" | "review" | null>(null);

  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);

  const loadTopic = useCallback(async (topic: string, nextFilters: FilterForm) => {
    const trimmed = topic.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    setFeedback(null);
    try {
      const domainId = activeDomainId || "default";
      const params = buildQuery(trimmed, domainId, nextFilters, "25");
      const graphParams = buildQuery(trimmed, domainId, nextFilters, "50", "1");
      const [researchersResponse, graphResponse] = await Promise.all([
        apiFetch(`/analytics/researchers-by-topic?${params.toString()}`),
        apiFetch(`/analytics/topic-researcher-graph?${graphParams.toString()}`),
      ]);
      if (!researchersResponse.ok) throw new Error("No se pudo cargar el ranking de investigadores.");
      if (!graphResponse.ok) throw new Error("No se pudo cargar la red de investigadores.");
      setData(await researchersResponse.json() as ResearchersPayload);
      setGraph(await graphResponse.json() as GraphPayload);
      setActiveTopic(trimmed);
    } catch (err) {
      setData(null);
      setGraph(null);
      setError(err instanceof Error ? err.message : "No se pudo analizar el tema.");
    } finally {
      setLoading(false);
    }
  }, [activeDomainId]);

  useEffect(() => {
    void loadTopic(initialTopic, filtersRef.current);
  }, [activeDomainId, initialTopic, loadTopic]);

  const topResearcher = data?.researchers[0] ?? null;
  const executiveSummary = graph?.summary.executive_summary ?? data?.executive_summary ?? null;

  useAssistantContextRegistration({
    route: "/analytics/researchers",
    domainId: activeDomainId || "default",
    moduleLabel: "Investigadores por tema",
    totalEntities: data?.records_analyzed ?? null,
    readinessPct: data?.researcher_count ? Math.min(100, data.researcher_count * 10) : null,
    leadingGap: data?.researcher_count ? null : "Sin investigadores detectados para el tema consultado",
    recommendedActions: [
      `Listar investigadores que trabajan en ${activeTopic}`,
      `Explorar red de coautoria para ${activeTopic}`,
      `Usar confianza ejecutiva ${executiveSummary?.confidence ?? 0} como senal para briefing`,
    ],
    actionLinks: [
      { id: "topic-researchers-ranking", label: "Ver ranking del tema", href: `/analytics/researchers?topic=${encodeURIComponent(activeTopic)}`, kind: "navigate" },
      { id: "topic-researchers-graph", label: "Abrir grafo general", href: `/analytics/graph?signal=${encodeURIComponent(activeTopic)}&domain=${encodeURIComponent(activeDomainId || "default")}`, kind: "navigate" },
      { id: "topic-researchers-rag", label: "Preguntar al RAG", href: `/rag?q=${encodeURIComponent(`Que investigadores trabajan en ${activeTopic}?`)}`, kind: "navigate" },
    ],
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void loadTopic(topicInput, filters);
  }

  return (
    <div className="space-y-8">
      <PageHeader
        breadcrumbs={[{ label: "Home", href: "/" }, { label: "Analytics", href: "/analytics" }, { label: "Investigadores por tema" }]}
        title="Investigadores por tema"
        description="Identifica investigadores, evidencia y relaciones de coautoria a partir de los datos ingeridos y enriquecidos."
      />

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-slate-950">
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
            <label className="sr-only" htmlFor="topic-search">Tema a analizar</label>
            <input
              id="topic-search"
              value={topicInput}
              onChange={(event) => setTopicInput(event.target.value)}
              className="h-12 rounded-2xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-900 outline-none ring-blue-500/20 transition focus:border-blue-400 focus:ring-4 dark:border-white/10 dark:bg-slate-900 dark:text-white"
              placeholder="Ej. open science, quantum materials, knowledge graphs"
            />
            <button
              type="submit"
              disabled={loading || topicInput.trim().length === 0}
              className="h-12 rounded-2xl bg-blue-600 px-6 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Analizando..." : "Analizar tema"}
            </button>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
            {[
              { key: "source", label: "Fuente", placeholder: "openalex" },
              { key: "yearFrom", label: "Desde", placeholder: "2020" },
              { key: "yearTo", label: "Hasta", placeholder: "2026" },
              { key: "country", label: "Pais", placeholder: "China" },
              { key: "institution", label: "Institucion", placeholder: "University" },
              { key: "minCitations", label: "Min. citas", placeholder: "10" },
            ].map((field) => (
              <label key={field.key} className="block">
                <span className="text-xs font-black uppercase tracking-[0.12em] text-slate-400">{field.label}</span>
                <input
                  value={filters[field.key as keyof FilterForm]}
                  onChange={(event) => setFilters((current) => ({ ...current, [field.key]: event.target.value }))}
                  className="mt-1 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-900 outline-none ring-blue-500/20 transition focus:border-blue-400 focus:ring-4 dark:border-white/10 dark:bg-slate-900 dark:text-white"
                  placeholder={field.placeholder}
                />
              </label>
            ))}
          </div>
        </form>
      </section>

      {error && <ErrorBanner message={error} onRetry={() => void loadTopic(activeTopic, filters)} variant="card" />}

      <ExecutiveMetricCard summary={executiveSummary} />

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-slate-950">
          <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">Tema</p>
          <p className="mt-2 text-2xl font-black tracking-normal text-slate-950 dark:text-white">{activeTopic}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-slate-950">
          <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">Investigadores</p>
          <p className="mt-2 text-2xl font-black tracking-normal text-slate-950 dark:text-white">{data?.researcher_count ?? 0}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-slate-950">
          <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">Mejor evidencia</p>
          <p className="mt-2 truncate text-2xl font-black tracking-normal text-slate-950 dark:text-white">{topResearcher?.name ?? "Sin datos"}</p>
        </div>
      </section>

      <TopicGraph graph={graph} />

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-slate-950">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-black tracking-normal text-slate-950 dark:text-white">Calibracion stakeholder</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Marca si el mapa parece accionable. Esta senal nos ayuda a ajustar el scoring cuando validemos con usuarios reales.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setFeedback("useful")}
              className={`rounded-xl px-4 py-2 text-sm font-black ring-1 transition ${feedback === "useful" ? "bg-emerald-600 text-white ring-emerald-600" : "bg-emerald-50 text-emerald-700 ring-emerald-200 hover:bg-emerald-100 dark:bg-emerald-400/10 dark:text-emerald-200 dark:ring-emerald-400/20"}`}
            >
              Util
            </button>
            <button
              type="button"
              onClick={() => setFeedback("review")}
              className={`rounded-xl px-4 py-2 text-sm font-black ring-1 transition ${feedback === "review" ? "bg-amber-600 text-white ring-amber-600" : "bg-amber-50 text-amber-700 ring-amber-200 hover:bg-amber-100 dark:bg-amber-400/10 dark:text-amber-200 dark:ring-amber-400/20"}`}
            >
              Revisar
            </button>
          </div>
        </div>
        {feedback && (
          <p className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600 dark:bg-white/5 dark:text-slate-300">
            Feedback registrado localmente para este corte: {feedback === "useful" ? "mapa util" : "requiere revision"}.
          </p>
        )}
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-black tracking-normal text-slate-950 dark:text-white">Ranking ponderado</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Score combinado por coincidencia tematica, produccion, citas, recencia, autoridad y calidad de enriquecimiento.
          </p>
        </div>
        {loading && !data ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500 dark:border-white/10 dark:bg-slate-950">Calculando investigadores...</div>
        ) : data && data.researchers.length > 0 ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {data.researchers.map((researcher, index) => (
              <ResearcherCard key={researcher.orcid || researcher.openalex_id || researcher.name} researcher={researcher} rank={index + 1} />
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-center text-sm text-slate-500 dark:border-white/10 dark:bg-slate-950">
            No hay investigadores detectados para este tema con la ingesta actual.
          </div>
        )}
      </section>
    </div>
  );
}
