"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { apiFetch } from "@/lib/api";

import { ErrorBanner, PageHeader } from "../../components/ui";
import { useAssistantContextRegistration } from "../../contexts/AssistantContext";
import { useDomain } from "../../contexts/DomainContext";

import CalibrationBar from "./components/CalibrationBar";
import ExecutivePanel from "./components/ExecutivePanel";
import FilterPanel from "./components/FilterPanel";
import KpiStrip from "./components/KpiStrip";
import ResearcherCard from "./components/ResearcherCard";
import TopicGraph from "./components/TopicGraph";
import { EMPTY_FILTERS } from "./researchersTypes";
import type { FilterForm, GraphPayload, ResearchersPayload } from "./researchersTypes";
import { buildQuery } from "./researchersUtils";

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
  const [filters, setFilters] = useState<FilterForm>(EMPTY_FILTERS);
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

  function handleFilterChange(key: keyof FilterForm, value: string) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function handleReset() {
    setFilters(EMPTY_FILTERS);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumbs={[{ label: "Home", href: "/" }, { label: "Analytics", href: "/analytics" }, { label: "Investigadores por tema" }]}
        title="Investigadores por tema"
        description="Identifica investigadores, evidencia y relaciones de coautoria a partir de los datos ingeridos y enriquecidos."
      />

      <FilterPanel
        topicInput={topicInput}
        filters={filters}
        loading={loading}
        onTopicChange={setTopicInput}
        onFilterChange={handleFilterChange}
        onSubmit={submit}
        onReset={handleReset}
      />

      {error && <ErrorBanner message={error} onRetry={() => void loadTopic(activeTopic, filters)} variant="card" />}

      <KpiStrip
        topic={activeTopic}
        researcherCount={data?.researcher_count ?? 0}
        totalCitations={executiveSummary?.total_citations ?? 0}
        networkDensity={executiveSummary?.network_density_score ?? 0}
        confidence={executiveSummary?.confidence ?? 0}
        topResearcherName={topResearcher?.name ?? "Sin datos"}
      />

      <ExecutivePanel summary={executiveSummary} />

      <TopicGraph graph={graph} />

      <CalibrationBar feedback={feedback} onFeedback={setFeedback} />

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-bold tracking-tight text-slate-950 dark:text-white">Ranking ponderado</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Score combinado por coincidencia tematica, produccion, citas, recencia, autoridad y calidad de enriquecimiento.
          </p>
        </div>
        {loading && !data ? (
          <div className="rounded-xl bg-white p-8 text-center text-sm text-slate-500 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:text-slate-400 dark:ring-white/10">Calculando investigadores...</div>
        ) : data && data.researchers.length > 0 ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {data.researchers.map((researcher, index) => (
              <ResearcherCard key={researcher.orcid || researcher.openalex_id || researcher.name} researcher={researcher} rank={index + 1} />
            ))}
          </div>
        ) : (
          <div className="rounded-xl bg-white p-8 text-center text-sm text-slate-500 ring-1 ring-dashed ring-slate-200 dark:bg-slate-950 dark:text-slate-400 dark:ring-white/10">
            No hay investigadores detectados para este tema con la ingesta actual.
          </div>
        )}
      </section>
    </div>
  );
}
