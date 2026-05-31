# Researchers Reskin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reskin `frontend/app/analytics/researchers/page.tsx` to the "VANTAGE ANALYTICS" reference aesthetic (mono micro-labels, `rounded-xl`/`ring-1`/`shadow-xs`, lighter font weights) by extracting it into focused presentational components — with zero changes to data/endpoints/types.

**Architecture:** The 573-line `page.tsx` is split into a thin orchestrator plus 6 files under `app/analytics/researchers/components/`. Types and pure helpers move to `researchersTypes.ts` / `researchersUtils.ts`. All data logic (`loadTopic`, `useAssistantContextRegistration`, error handling) stays in `page.tsx` unchanged. Styling moves from chunky `font-black`/`rounded-3xl` to disciplined `font-semibold`/`rounded-xl ring-1 ring-slate-950/5 shadow-xs` with `font-mono` uppercase micro-labels. Dark mode preserved via `dark:` variants.

**Tech Stack:** Next.js 16 + React 19, Tailwind v4 (Geist Sans/Mono), Vitest + React Testing Library.

---

## Reskin token reference (use consistently)

| Role | Class string |
|------|--------------|
| Panel container | `rounded-xl bg-white p-5 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10` |
| Micro-label (eyebrow) | `text-[10px] font-mono uppercase tracking-wider text-slate-400` |
| Sub-card | `rounded-lg bg-slate-50 p-3 dark:bg-white/5` |
| Big number | `text-2xl font-bold tabular-nums text-slate-950 dark:text-white` |
| Section title | `text-lg font-bold tracking-tight text-slate-950 dark:text-white` |
| Primary button | `h-11 rounded-xl bg-blue-600 px-6 text-sm font-semibold text-white transition hover:bg-blue-700 focus:ring-4 focus:ring-blue-100 disabled:opacity-60 dark:focus:ring-blue-500/20` |
| Chip (neutral) | `rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700 dark:bg-white/10 dark:text-slate-200` |

Existing helpers `scoreTone()` and `barColor()` are reused verbatim (they already handle dark mode).

---

## File Structure

- Create: `frontend/app/analytics/researchers/researchersTypes.ts` — all `type` declarations + `DRIVER_LABELS`.
- Create: `frontend/app/analytics/researchers/researchersUtils.ts` — `scoreTone`, `barColor`, `externalHref`, `buildQuery`.
- Create: `frontend/app/analytics/researchers/components/ResearcherCard.tsx`
- Create: `frontend/app/analytics/researchers/components/TopicGraph.tsx`
- Create: `frontend/app/analytics/researchers/components/ExecutivePanel.tsx`
- Create: `frontend/app/analytics/researchers/components/KpiStrip.tsx`
- Create: `frontend/app/analytics/researchers/components/FilterPanel.tsx`
- Create: `frontend/app/analytics/researchers/components/CalibrationBar.tsx`
- Modify: `frontend/app/analytics/researchers/page.tsx` — becomes orchestrator (~150 lines).
- Create: `frontend/__tests__/ResearchersKpiStrip.test.tsx`
- Create: `frontend/__tests__/ResearchersCard.test.tsx`

> Note: this is a visual reskin. For pure component *moves* (TopicGraph), tests are not added. For the two presentational components whose props→DOM mapping is worth locking (`KpiStrip`, `ResearcherCard`), we write a render test first (TDD).

---

## Task 1: Extract types and utils (no behavior change)

**Files:**
- Create: `frontend/app/analytics/researchers/researchersTypes.ts`
- Create: `frontend/app/analytics/researchers/researchersUtils.ts`

- [ ] **Step 1: Create `researchersTypes.ts`** with the type block currently at `page.tsx:13-117` plus `DRIVER_LABELS`:

```typescript
export type ScoreDrivers = {
  topic_match: number;
  publication_signal: number;
  citation_signal: number;
  recency_signal: number;
  authority_signal: number;
  quality_signal: number;
};

export type ResearcherEvidence = {
  entity_id: number;
  title: string | null;
  secondary_label: string | null;
  citations: number;
};

export type Researcher = {
  name: string;
  orcid: string | null;
  openalex_id: string | null;
  records_count: number;
  citation_count: number;
  topic_score: number;
  drivers: ScoreDrivers;
  evidence: ResearcherEvidence[];
};

export type TopicFilters = {
  source: string | null;
  year_from: number | null;
  year_to: number | null;
  country: string | null;
  institution: string | null;
  min_citations: number;
};

export type ExecutiveSummary = {
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

export type ResearchersPayload = {
  domain_id: string;
  topic: string;
  filters: TopicFilters;
  records_analyzed: number;
  researcher_count: number;
  researchers: Researcher[];
  executive_summary: ExecutiveSummary;
};

export type GraphNode = {
  id: string;
  type: "topic" | "researcher";
  label: string;
  score: number;
  records_count?: number;
  citation_count?: number;
};

export type GraphEdge = {
  source: string;
  target: string;
  type: "works_on_topic" | "coauthor_with";
  weight: number;
};

export type GraphPayload = {
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

export type PositionedNode = GraphNode & { x: number; y: number };

export type FilterForm = {
  source: string;
  yearFrom: string;
  yearTo: string;
  country: string;
  institution: string;
  minCitations: string;
};

export const DRIVER_LABELS: Array<{ key: keyof ScoreDrivers; label: string }> = [
  { key: "topic_match", label: "Tema" },
  { key: "publication_signal", label: "Produccion" },
  { key: "citation_signal", label: "Citas" },
  { key: "recency_signal", label: "Recencia" },
  { key: "authority_signal", label: "Autoridad" },
  { key: "quality_signal", label: "Calidad" },
];

export const EMPTY_FILTERS: FilterForm = {
  source: "",
  yearFrom: "",
  yearTo: "",
  country: "",
  institution: "",
  minCitations: "",
};
```

- [ ] **Step 2: Create `researchersUtils.ts`** with the helpers from `page.tsx:119-148`:

```typescript
import type { FilterForm } from "./researchersTypes";

export function scoreTone(score: number) {
  if (score >= 70) return "text-emerald-700 bg-emerald-50 ring-emerald-200 dark:text-emerald-200 dark:bg-emerald-400/10 dark:ring-emerald-400/20";
  if (score >= 40) return "text-amber-700 bg-amber-50 ring-amber-200 dark:text-amber-200 dark:bg-amber-400/10 dark:ring-amber-400/20";
  return "text-red-700 bg-red-50 ring-red-200 dark:text-red-200 dark:bg-red-400/10 dark:ring-red-400/20";
}

export function barColor(score: number) {
  if (score >= 70) return "bg-emerald-500";
  if (score >= 40) return "bg-amber-500";
  return "bg-red-500";
}

export function externalHref(id: string | null) {
  if (!id) return null;
  if (id.startsWith("http")) return id;
  if (id.startsWith("0000-")) return `https://orcid.org/${id}`;
  return id;
}

export function buildQuery(topic: string, domainId: string, filters: FilterForm, limit: string, minWeight?: string) {
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
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (no new errors introduced; files compile in isolation).

- [ ] **Step 4: Commit**

```bash
git add frontend/app/analytics/researchers/researchersTypes.ts frontend/app/analytics/researchers/researchersUtils.ts
git commit -m "refactor(researchers): extract types and utils"
```

---

## Task 2: ResearcherCard component (TDD)

**Files:**
- Test: `frontend/__tests__/ResearchersCard.test.tsx`
- Create: `frontend/app/analytics/researchers/components/ResearcherCard.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

import ResearcherCard from "../app/analytics/researchers/components/ResearcherCard";
import type { Researcher } from "../app/analytics/researchers/researchersTypes";

const researcher: Researcher = {
  name: "Brian A. Nosek",
  orcid: "0000-0001-2345-6789",
  openalex_id: null,
  records_count: 12,
  citation_count: 340,
  topic_score: 82,
  drivers: {
    topic_match: 90, publication_signal: 70, citation_signal: 85,
    recency_signal: 60, authority_signal: 75, quality_signal: 65,
  },
  evidence: [{ entity_id: 1, title: "Open Science", secondary_label: null, citations: 120 }],
};

describe("ResearcherCard", () => {
  it("renders rank, name, score and core metrics", () => {
    render(<ResearcherCard researcher={researcher} rank={1} />);
    expect(screen.getByText("Brian A. Nosek")).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();   // records
    expect(screen.getByText("340")).toBeInTheDocument();  // citations
    expect(screen.getByText(/ORCID/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run __tests__/ResearchersCard.test.tsx`
Expected: FAIL (cannot resolve `components/ResearcherCard`).

- [ ] **Step 3: Create `ResearcherCard.tsx`** (extracted from `page.tsx:284-360`, reskinned):

```tsx
import Link from "next/link";

import type { Researcher } from "../researchersTypes";
import { DRIVER_LABELS } from "../researchersTypes";
import { barColor, externalHref, scoreTone } from "../researchersUtils";

export default function ResearcherCard({ researcher, rank }: { researcher: Researcher; rank: number }) {
  return (
    <article className="rounded-xl bg-white p-5 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 font-mono text-sm font-bold text-blue-700 ring-1 ring-blue-100 dark:bg-blue-400/10 dark:text-blue-200 dark:ring-blue-400/20">
              {rank}
            </span>
            <div className="min-w-0">
              <h3 className="truncate text-base font-bold tracking-tight text-slate-950 dark:text-white">{researcher.name}</h3>
              <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Investigador identificado</p>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2 text-xs font-medium">
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
        <div className={`rounded-lg px-4 py-3 text-center ring-1 ${scoreTone(researcher.topic_score)}`}>
          <p className="text-3xl font-bold tabular-nums">{researcher.topic_score}</p>
          <p className="text-[10px] font-mono uppercase tracking-wider">score</p>
        </div>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-3">
        {[
          { label: "Registros", value: researcher.records_count },
          { label: "Citas", value: researcher.citation_count },
          { label: "Evidencias", value: researcher.evidence.length },
        ].map((m) => (
          <div key={m.label} className="rounded-lg bg-slate-50 p-3 dark:bg-white/5">
            <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{m.label}</p>
            <p className="mt-1 text-xl font-bold tabular-nums text-slate-950 dark:text-white">{m.value}</p>
          </div>
        ))}
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {DRIVER_LABELS.map(({ key, label }) => (
          <div key={key}>
            <div className="mb-1 flex justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>{label}</span>
              <span className="tabular-nums text-slate-500">{researcher.drivers[key]}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-slate-100 dark:bg-white/10">
              <div className={`h-full rounded-full ${barColor(researcher.drivers[key])}`} style={{ width: `${researcher.drivers[key]}%` }} />
            </div>
          </div>
        ))}
      </div>
      {researcher.evidence.length > 0 && (
        <div className="mt-5 space-y-2">
          <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Evidencia</p>
          {researcher.evidence.map((item) => (
            <Link
              key={item.entity_id}
              href={`/entities/${item.entity_id}`}
              className="block rounded-lg px-3 py-2 text-sm text-slate-700 ring-1 ring-slate-100 transition hover:bg-blue-50 hover:ring-blue-200 dark:text-slate-200 dark:ring-white/10 dark:hover:bg-blue-400/10"
            >
              <span className="font-medium">{item.title || `Registro ${item.entity_id}`}</span>
              <span className="ml-2 text-xs text-slate-400">{item.citations} citas</span>
            </Link>
          ))}
        </div>
      )}
    </article>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run __tests__/ResearchersCard.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/analytics/researchers/components/ResearcherCard.tsx frontend/__tests__/ResearchersCard.test.tsx
git commit -m "feat(researchers): reskinned ResearcherCard component"
```

---

## Task 3: TopicGraph component (move + restyle, no test)

**Files:**
- Create: `frontend/app/analytics/researchers/components/TopicGraph.tsx`

- [ ] **Step 1: Create `TopicGraph.tsx`** — move the component from `page.tsx:186-282` verbatim, then apply only these container/typography restyles (keep all SVG layout math, colors, and `useMemo` logic identical):
  - Outer container: `rounded-xl bg-white p-4 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10`
  - Empty-state container: replace `rounded-2xl border border-dashed border-slate-200 ... shadow-sm` with `rounded-xl ring-1 ring-dashed ring-slate-200 dark:ring-white/10` (keep min-height and text).
  - Title: `text-lg font-bold tracking-tight text-slate-950 dark:text-white` (was `font-black`).
  - Subtitle stays `text-sm text-slate-500 dark:text-slate-400`.
  - Legend chips: add `font-mono` to the existing chip spans; keep their color rings.
  - Imports at top: `import { useMemo } from "react";` and `import type { GraphEdge, GraphPayload, PositionedNode } from "../researchersTypes";`

```tsx
"use client";

import { useMemo } from "react";

import type { GraphEdge, GraphPayload, PositionedNode } from "../researchersTypes";

export default function TopicGraph({ graph }: { graph: GraphPayload | null }) {
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
        return { ...node, x: 360 + Math.cos(angle) * radiusX, y: 220 + Math.sin(angle) * radiusY };
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
      <div className="flex min-h-[360px] items-center justify-center rounded-xl bg-white text-sm text-slate-500 ring-1 ring-dashed ring-slate-200 dark:bg-slate-950 dark:text-slate-400 dark:ring-white/10">
        Ejecuta una busqueda para construir la red del tema.
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-white p-4 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold tracking-tight text-slate-950 dark:text-white">Red de investigadores</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {graph.summary.researcher_count} investigadores · {graph.summary.relationship_count} relaciones
          </p>
        </div>
        <div className="flex gap-2 font-mono text-[10px] font-medium uppercase tracking-wider">
          <span className="rounded-full bg-violet-50 px-3 py-1 text-violet-700 ring-1 ring-violet-200 dark:bg-violet-400/10 dark:text-violet-200 dark:ring-violet-400/20">tema</span>
          <span className="rounded-full bg-blue-50 px-3 py-1 text-blue-700 ring-1 ring-blue-200 dark:bg-blue-400/10 dark:text-blue-200 dark:ring-blue-400/20">autor</span>
          <span className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-700 ring-1 ring-emerald-200 dark:bg-emerald-400/10 dark:text-emerald-200 dark:ring-emerald-400/20">coautoria</span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <svg viewBox="0 0 720 440" className="h-[420px] min-w-[720px] rounded-lg bg-slate-50 dark:bg-slate-900" role="img" aria-label="Grafo de investigadores por tema">
          {edges.map((edge) => {
            const source = nodeMap.get(edge.source);
            const target = nodeMap.get(edge.target);
            if (!source || !target) return null;
            const isCoauthor = edge.type === "coauthor_with";
            return (
              <line
                key={`${edge.source}-${edge.target}-${edge.type}`}
                x1={source.x} y1={source.y} x2={target.x} y2={target.y}
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
                <circle cx={node.x} cy={node.y} r={radius} fill={isTopic ? "#7c3aed" : "#2563eb"} opacity={isTopic ? 0.95 : 0.9} />
                <circle cx={node.x} cy={node.y} r={radius + 5} fill="none" stroke={isTopic ? "#c4b5fd" : "#bfdbfe"} strokeOpacity={0.7} />
                <text x={node.x} y={node.y + radius + 18} textAnchor="middle" className="fill-slate-700 text-[12px] font-bold dark:fill-slate-200">
                  {node.label.length > 24 ? `${node.label.slice(0, 22)}...` : node.label}
                </text>
                <text x={node.x} y={node.y + 4} textAnchor="middle" className="fill-white text-[12px] font-bold">
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
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/analytics/researchers/components/TopicGraph.tsx
git commit -m "refactor(researchers): extract and restyle TopicGraph"
```

---

## Task 4: ExecutivePanel component (extract + reskin)

**Files:**
- Create: `frontend/app/analytics/researchers/components/ExecutivePanel.tsx`

- [ ] **Step 1: Create `ExecutivePanel.tsx`** (extracted from `ExecutiveMetricCard` `page.tsx:150-184`, reskinned). Keep the same data fields and the `scoreTone(confidence)` accent:

```tsx
import type { ExecutiveSummary } from "../researchersTypes";
import { scoreTone } from "../researchersUtils";

export default function ExecutivePanel({ summary }: { summary: ExecutiveSummary | null }) {
  const confidence = summary?.confidence ?? 0;
  const metrics = [
    { label: "Cobertura", value: summary?.coverage_score ?? 0 },
    { label: "Alta confianza", value: summary?.high_confidence_researchers ?? 0 },
    { label: "Citas", value: summary?.total_citations ?? 0 },
    { label: "Densidad red", value: summary?.network_density_score ?? 0 },
  ];
  return (
    <section className="rounded-xl bg-white p-5 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
      <div className="grid gap-5 lg:grid-cols-[220px_1fr]">
        <div className={`rounded-xl p-5 ring-1 ${scoreTone(confidence)}`}>
          <p className="text-[10px] font-mono uppercase tracking-wider">Metrica ejecutiva</p>
          <p className="mt-3 text-5xl font-bold tabular-nums">{confidence}</p>
          <p className="mt-1 text-sm font-medium">confianza del mapa</p>
        </div>
        <div className="min-w-0">
          <h2 className="text-xl font-bold tracking-tight text-slate-950 dark:text-white">
            {summary?.headline ?? "Ejecuta una busqueda para generar el mapa ejecutivo."}
          </h2>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            {summary?.stakeholder_value ?? "La metrica resume cobertura, autoridad, citas, evidencia y densidad de red para briefs y conversaciones ejecutivas."}
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-4">
            {metrics.map((metric) => (
              <div key={metric.label} className="rounded-lg bg-slate-50 p-3 dark:bg-white/5">
                <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{metric.label}</p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-slate-950 dark:text-white">{metric.value}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/analytics/researchers/components/ExecutivePanel.tsx
git commit -m "feat(researchers): reskinned ExecutivePanel"
```

---

## Task 5: KpiStrip component (TDD)

**Files:**
- Test: `frontend/__tests__/ResearchersKpiStrip.test.tsx`
- Create: `frontend/app/analytics/researchers/components/KpiStrip.tsx`

This replaces the old 3-card row (`page.tsx:500-513`) with a compact 5-KPI strip. It is purely presentational — all values are passed in as props (no data logic).

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

import KpiStrip from "../app/analytics/researchers/components/KpiStrip";

describe("KpiStrip", () => {
  it("renders all KPI labels and values", () => {
    render(
      <KpiStrip
        topic="open science"
        researcherCount={7}
        totalCitations={1200}
        networkDensity={42}
        confidence={88}
        topResearcherName="Brian A. Nosek"
      />,
    );
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("1200")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("88")).toBeInTheDocument();
    expect(screen.getByText("Brian A. Nosek")).toBeInTheDocument();
    expect(screen.getByText(/Investigadores/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run __tests__/ResearchersKpiStrip.test.tsx`
Expected: FAIL (cannot resolve `components/KpiStrip`).

- [ ] **Step 3: Create `KpiStrip.tsx`**:

```tsx
interface KpiStripProps {
  topic: string;
  researcherCount: number;
  totalCitations: number;
  networkDensity: number;
  confidence: number;
  topResearcherName: string;
}

export default function KpiStrip({
  topic,
  researcherCount,
  totalCitations,
  networkDensity,
  confidence,
  topResearcherName,
}: KpiStripProps) {
  const items: Array<{ label: string; value: string | number; truncate?: boolean }> = [
    { label: "Tema", value: topic, truncate: true },
    { label: "Investigadores", value: researcherCount },
    { label: "Citas totales", value: totalCitations },
    { label: "Densidad red", value: networkDensity },
    { label: "Nivel de confianza", value: confidence },
    { label: "Mejor evidencia", value: topResearcherName, truncate: true },
  ];
  return (
    <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      {items.map((item) => (
        <div key={item.label} className="rounded-xl bg-white p-4 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
          <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{item.label}</p>
          <p className={`mt-2 text-2xl font-bold tabular-nums text-slate-950 dark:text-white ${item.truncate ? "truncate" : ""}`}>
            {item.value}
          </p>
        </div>
      ))}
    </section>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run __tests__/ResearchersKpiStrip.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/analytics/researchers/components/KpiStrip.tsx frontend/__tests__/ResearchersKpiStrip.test.tsx
git commit -m "feat(researchers): add reskinned KpiStrip"
```

---

## Task 6: FilterPanel component (extract + reskin + reset button)

**Files:**
- Create: `frontend/app/analytics/researchers/components/FilterPanel.tsx`

This extracts the search form (`page.tsx:454-494`) and adds a "Reiniciar filtros" button (UI-only: calls `onReset`). It is controlled — receives `topicInput`, `filters`, and change/submit callbacks from the page.

- [ ] **Step 1: Create `FilterPanel.tsx`**:

```tsx
import type { FormEvent } from "react";

import type { FilterForm } from "../researchersTypes";

interface FilterPanelProps {
  topicInput: string;
  filters: FilterForm;
  loading: boolean;
  onTopicChange: (value: string) => void;
  onFilterChange: (key: keyof FilterForm, value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onReset: () => void;
}

const FILTER_FIELDS: Array<{ key: keyof FilterForm; label: string; placeholder: string }> = [
  { key: "source", label: "Fuente", placeholder: "openalex" },
  { key: "yearFrom", label: "Desde", placeholder: "2020" },
  { key: "yearTo", label: "Hasta", placeholder: "2026" },
  { key: "country", label: "Pais", placeholder: "China" },
  { key: "institution", label: "Institucion", placeholder: "University" },
  { key: "minCitations", label: "Min. citas", placeholder: "10" },
];

export default function FilterPanel({
  topicInput, filters, loading, onTopicChange, onFilterChange, onSubmit, onReset,
}: FilterPanelProps) {
  return (
    <section className="rounded-xl bg-white p-5 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Filtros de busqueda cientifica</p>
        <button
          type="button"
          onClick={onReset}
          className="rounded-lg px-3 py-1 text-xs font-medium text-slate-500 ring-1 ring-slate-200 transition hover:bg-slate-50 hover:text-slate-700 dark:text-slate-400 dark:ring-white/10 dark:hover:bg-white/5"
        >
          Reiniciar filtros
        </button>
      </div>
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
          <label className="sr-only" htmlFor="topic-search">Tema a analizar</label>
          <input
            id="topic-search"
            value={topicInput}
            onChange={(event) => onTopicChange(event.target.value)}
            className="h-11 rounded-xl bg-white px-4 text-sm font-medium text-slate-900 outline-none ring-1 ring-slate-200 transition focus:ring-4 focus:ring-blue-100 dark:bg-slate-900 dark:text-white dark:ring-white/10 dark:focus:ring-blue-500/20"
            placeholder="Buscar por tema: open science, quantum materials, knowledge graphs"
          />
          <button
            type="submit"
            disabled={loading || topicInput.trim().length === 0}
            className="h-11 rounded-xl bg-blue-600 px-6 text-sm font-semibold text-white transition hover:bg-blue-700 focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60 dark:focus:ring-blue-500/20"
          >
            {loading ? "Analizando..." : "Analizar tema"}
          </button>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          {FILTER_FIELDS.map((field) => (
            <label key={field.key} className="block">
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{field.label}</span>
              <input
                value={filters[field.key]}
                onChange={(event) => onFilterChange(field.key, event.target.value)}
                className="mt-1 h-10 w-full rounded-lg bg-white px-3 text-sm font-medium text-slate-900 outline-none ring-1 ring-slate-200 transition focus:ring-4 focus:ring-blue-100 dark:bg-slate-900 dark:text-white dark:ring-white/10 dark:focus:ring-blue-500/20"
                placeholder={field.placeholder}
              />
            </label>
          ))}
        </div>
      </form>
    </section>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/analytics/researchers/components/FilterPanel.tsx
git commit -m "feat(researchers): reskinned FilterPanel with reset"
```

---

## Task 7: CalibrationBar component (extract + reskin)

**Files:**
- Create: `frontend/app/analytics/researchers/components/CalibrationBar.tsx`

Extracts the feedback section (`page.tsx:517-547`). Controlled via `feedback` + `onFeedback`.

- [ ] **Step 1: Create `CalibrationBar.tsx`**:

```tsx
type Feedback = "useful" | "review" | null;

interface CalibrationBarProps {
  feedback: Feedback;
  onFeedback: (value: "useful" | "review") => void;
}

export default function CalibrationBar({ feedback, onFeedback }: CalibrationBarProps) {
  return (
    <section className="rounded-xl bg-white p-5 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold tracking-tight text-slate-950 dark:text-white">Calibracion stakeholder</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Marca si el mapa parece accionable. Esta senal nos ayuda a ajustar el scoring cuando validemos con usuarios reales.
          </p>
        </div>
        <div className="flex gap-2 font-mono text-xs font-medium uppercase tracking-wider">
          <button
            type="button"
            onClick={() => onFeedback("useful")}
            className={`rounded-lg px-4 py-2 ring-1 transition ${feedback === "useful" ? "bg-emerald-600 text-white ring-emerald-600" : "bg-emerald-50 text-emerald-700 ring-emerald-200 hover:bg-emerald-100 dark:bg-emerald-400/10 dark:text-emerald-200 dark:ring-emerald-400/20"}`}
          >
            Util
          </button>
          <button
            type="button"
            onClick={() => onFeedback("review")}
            className={`rounded-lg px-4 py-2 ring-1 transition ${feedback === "review" ? "bg-amber-600 text-white ring-amber-600" : "bg-amber-50 text-amber-700 ring-amber-200 hover:bg-amber-100 dark:bg-amber-400/10 dark:text-amber-200 dark:ring-amber-400/20"}`}
          >
            Revisar
          </button>
        </div>
      </div>
      {feedback && (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm font-medium text-slate-600 dark:bg-white/5 dark:text-slate-300">
          Feedback registrado localmente para este corte: {feedback === "useful" ? "mapa util" : "requiere revision"}.
        </p>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/analytics/researchers/components/CalibrationBar.tsx
git commit -m "feat(researchers): reskinned CalibrationBar"
```

---

## Task 8: Reassemble page.tsx orchestrator

**Files:**
- Modify: `frontend/app/analytics/researchers/page.tsx` (replace entire file)

The page keeps ALL existing data logic unchanged (`loadTopic`, `useEffect`, `useAssistantContextRegistration`, error handling). It imports the new components, removes the inlined type/helper/component definitions (now in the extracted files), wires the `onReset` handler (`setFilters(EMPTY_FILTERS)`), and renders sections in the new order: PageHeader → FilterPanel → ErrorBanner → KpiStrip → ExecutivePanel → TopicGraph → CalibrationBar → Ranking.

- [ ] **Step 1: Replace `page.tsx`** with:

```tsx
"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
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
```

> Note: `useMemo` import is dropped from `page.tsx` (it moved into `TopicGraph`). Ensure no unused-import lint error remains.

- [ ] **Step 2: Typecheck + full frontend test run**

Run: `cd frontend && npx tsc --noEmit && npx vitest run __tests__/ResearchersCard.test.tsx __tests__/ResearchersKpiStrip.test.tsx`
Expected: PASS (no type errors; both new tests green).

- [ ] **Step 3: Lint the touched files**

Run: `cd frontend && npx eslint app/analytics/researchers`
Expected: no errors (fix any unused-import warnings, e.g. stray `useMemo`/`Link`).

- [ ] **Step 4: Commit**

```bash
git add frontend/app/analytics/researchers/page.tsx
git commit -m "feat(researchers): reassemble page with reskinned components"
```

---

## Task 9: Visual verification (preview, light + dark, responsive)

**Files:** none (verification only)

- [ ] **Step 1: Start the dev server**

Use the preview tooling (`preview_start`) against the frontend dev server. If the backend is required for data, the page must still render its shell, filters, and empty/error states without it — verify those first.

- [ ] **Step 2: Verify light mode @ 1440px**

Navigate to `/analytics/researchers`. Confirm: FilterPanel with reset button, KPI strip (6 cards), ExecutivePanel, TopicGraph (or empty state), CalibrationBar, Ranking grid. Check no console errors (`preview_console_logs`). Take a screenshot (`preview_screenshot`).

- [ ] **Step 3: Verify dark mode**

Toggle theme to dark (set `localStorage.app_theme = "dark"` then reload, or use the app's theme toggle). Confirm every panel uses the `dark:` surfaces (slate-950 bg, white/10 rings) with no white flashes. Screenshot.

- [ ] **Step 4: Verify responsive @ 768 and 375**

`preview_resize` to 768 then 375. Confirm KPI strip reflows (6→3→2→1), filters stack, no horizontal overflow (the graph stays in its own `overflow-x-auto`). Screenshot each.

- [ ] **Step 5: Functional smoke (if backend available)**

Type a topic, submit, confirm KPIs/graph/ranking populate; click "Reiniciar filtros" and confirm the 6 filter inputs clear; click Util/Revisar and confirm the calibration confirmation line appears.

- [ ] **Step 6: Final confirmation**

Confirm no file under `app/analytics/researchers/` exceeds ~400 lines (`page.tsx` should be ~150). Report results with screenshots. No commit needed unless fixes were made during verification.

---

## Done criteria

- All 6 components + types + utils extracted; `page.tsx` is a ~150-line orchestrator.
- Reskin tokens applied consistently (mono micro-labels, `rounded-xl`/`ring-1`/`shadow-xs`, `font-semibold`/`font-bold`, `tabular-nums`).
- Dark mode intact across all sections.
- `npx tsc --noEmit` clean; `npx vitest run` (new tests) green; `npx eslint app/analytics/researchers` clean.
- No changes to endpoints, schemas, data shapes, or `loadTopic`/assistant logic.
