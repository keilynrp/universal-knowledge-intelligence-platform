"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
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
  records_analyzed: number;
  researcher_count: number;
  researchers: Researcher[];
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
  };
};

type PositionedNode = GraphNode & { x: number; y: number };

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

  const loadTopic = useCallback(async (topic: string) => {
    const trimmed = topic.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ topic: trimmed, domain_id: activeDomainId || "default", limit: "25" });
      const graphParams = new URLSearchParams({ topic: trimmed, domain_id: activeDomainId || "default", limit: "50", min_weight: "1" });
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
    void loadTopic(initialTopic);
  }, [initialTopic, loadTopic]);

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
    ],
    actionLinks: [
      { id: "topic-researchers-ranking", label: "Ver ranking del tema", href: `/analytics/researchers?topic=${encodeURIComponent(activeTopic)}`, kind: "navigate" },
      { id: "topic-researchers-graph", label: "Abrir grafo general", href: `/analytics/graph?signal=${encodeURIComponent(activeTopic)}&domain=${encodeURIComponent(activeDomainId || "default")}`, kind: "navigate" },
      { id: "topic-researchers-rag", label: "Preguntar al RAG", href: `/rag?q=${encodeURIComponent(`Que investigadores trabajan en ${activeTopic}?`)}`, kind: "navigate" },
    ],
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void loadTopic(topicInput);
  }

  const topResearcher = data?.researchers[0] ?? null;

  return (
    <div className="space-y-8">
      <PageHeader
        breadcrumbs={[{ label: "Home", href: "/" }, { label: "Analytics", href: "/analytics" }, { label: "Investigadores por tema" }]}
        title="Investigadores por tema"
        description="Identifica investigadores, evidencia y relaciones de coautoria a partir de los datos ingeridos y enriquecidos."
      />

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-slate-950">
        <form onSubmit={submit} className="grid gap-3 lg:grid-cols-[1fr_auto]">
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
        </form>
      </section>

      {error && <ErrorBanner message={error} onRetry={() => void loadTopic(activeTopic)} variant="card" />}

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
