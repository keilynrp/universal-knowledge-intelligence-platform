"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { useDomain } from "../../contexts/DomainContext";
import { useLanguage } from "../../contexts/LanguageContext";

// ── Types ─────────────────────────────────────────────────────────────────────

interface GNode { id: number; label: string; community: number; pagerank: number; degree: number; }
interface GLink { source: number; target: number; type: string; }
interface GraphData {
  nodes: GNode[];
  links: GLink[];
  edge_types: string[];
  total_communities: number;
  filters?: { import_batch_id?: number | null; provider?: string | null; domain?: string | null; portal?: string | null };
  stats: { visible_nodes: number; visible_edges: number; top_pagerank_leader: string | null; top_pagerank_score: number; };
}
interface PathResult { found: boolean; length?: number; relations?: string[]; steps?: Array<{ entity_id: number; primary_label: string | null }>; }
interface KeywordSignal {
  keyword: string;
  classification: string;
  support_count: number;
  external_support: number;
  opportunity_score: number;
  source_fields: string[];
}

// ── Constants ─────────────────────────────────────────────────────────────────

const COMMUNITY_COLORS = ["#8b5cf6","#06b6d4","#10b981","#f59e0b","#f43f5e","#3b82f6","#84cc16","#ec4899","#a78bfa","#22d3ee"];
const EDGE_TYPE_COLORS: Record<string, string> = { cites: "#8b5cf6", "authored-by": "#06b6d4", "belongs-to": "#10b981", "related-to": "#f59e0b" };

function edgeColor(type: string) {
  return EDGE_TYPE_COLORS[type] ?? "#94a3b8";
}

// ── Force Graph Canvas ────────────────────────────────────────────────────────

interface ForceGraphProps { nodes: GNode[]; links: GLink[]; highlightIds?: Set<number>; }

function ForceGraph({ nodes, links, highlightIds }: ForceGraphProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const stateRef = useRef<{ running: boolean; nodes: (GNode & { x: number; y: number; vx: number; vy: number })[]; links: { s: number; t: number; type: string }[]; transform: { x: number; y: number; k: number }; drag: { active: boolean; lastX: number; lastY: number } }>({ running: false, nodes: [], links: [], transform: { x: 0, y: 0, k: 1 }, drag: { active: false, lastX: 0, lastY: 0 } });
  const [hovered, setHovered] = useState<GNode | null>(null);
  const hoverPos = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || nodes.length === 0) return;

    const w = container.clientWidth || 600;
    const h = container.clientHeight || 500;
    canvas.width = w;
    canvas.height = h;

    const state = stateRef.current;
    state.running = true;
    state.transform = { x: 0, y: 0, k: 1 };

    const nodeMap = new Map<number, typeof state.nodes[0]>();
    state.nodes = nodes.map(n => {
      const sn = { ...n, x: w / 2 + (Math.random() - 0.5) * 200, y: h / 2 + (Math.random() - 0.5) * 200, vx: 0, vy: 0 };
      nodeMap.set(n.id, sn);
      return sn;
    });
    state.links = links.filter(l => nodeMap.has(l.source) && nodeMap.has(l.target))
      .map(l => ({ s: l.source, t: l.target, type: l.type }));

    let iter = 0;

    function tick() {
      if (!state.running) return;
      const ns = state.nodes;
      const alpha = iter < 150 ? 1 - iter / 200 : 0.02;
      iter++;

      // Center gravity
      for (const n of ns) {
        n.vx += (w / 2 - n.x) * 0.002 * alpha;
        n.vy += (h / 2 - n.y) * 0.002 * alpha;
      }

      // Repulsion
      for (let i = 0; i < ns.length; i++) {
        for (let j = i + 1; j < ns.length; j++) {
          const dx = ns[j].x - ns[i].x;
          const dy = ns[j].y - ns[i].y;
          const d2 = dx * dx + dy * dy + 1;
          const f = (-400 / d2) * alpha;
          ns[i].vx += f * dx; ns[i].vy += f * dy;
          ns[j].vx -= f * dx; ns[j].vy -= f * dy;
        }
      }

      // Spring forces
      for (const lk of state.links) {
        const a = nodeMap.get(lk.s)!;
        const b = nodeMap.get(lk.t)!;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) + 0.01;
        const f = (dist - 90) * 0.04 * alpha;
        a.vx += f * dx / dist; a.vy += f * dy / dist;
        b.vx -= f * dx / dist; b.vy -= f * dy / dist;
      }

      for (const n of ns) {
        n.vx *= 0.75; n.vy *= 0.75;
        n.x += n.vx; n.y += n.vy;
      }

      render();
      requestAnimationFrame(tick);
    }

    function render() {
      const ctx = canvas!.getContext("2d");
      if (!ctx) return;
      ctx.clearRect(0, 0, w, h);

      // Grid background
      ctx.save();
      ctx.strokeStyle = "rgba(148,163,184,0.08)";
      ctx.lineWidth = 1;
      const step = 40;
      for (let x = 0; x < w; x += step) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
      for (let y = 0; y < h; y += step) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
      ctx.restore();

      ctx.save();
      ctx.translate(state.transform.x, state.transform.y);
      ctx.scale(state.transform.k, state.transform.k);

      // Edges
      for (const lk of state.links) {
        const a = nodeMap.get(lk.s)!;
        const b = nodeMap.get(lk.t)!;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = edgeColor(lk.type) + "55";
        ctx.lineWidth = 1 / state.transform.k;
        ctx.stroke();
      }

      // Nodes
      for (const n of state.nodes) {
        const color = COMMUNITY_COLORS[n.community % COMMUNITY_COLORS.length];
        const r = Math.max(4, 4 + Math.log(n.degree + 1) * 1.5);
        const isHighlighted = highlightIds?.has(n.id);
        ctx.beginPath();
        ctx.arc(n.x, n.y, isHighlighted ? r + 3 : r, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.globalAlpha = isHighlighted ? 1 : (highlightIds && highlightIds.size > 0 ? 0.4 : 0.85);
        ctx.fill();
        ctx.globalAlpha = 1;
        if (isHighlighted) {
          ctx.strokeStyle = "#fff";
          ctx.lineWidth = 2 / state.transform.k;
          ctx.stroke();
        }
      }

      ctx.restore();
    }

    tick();
    return () => { state.running = false; };
  }, [nodes, links, highlightIds]);

  // Zoom
  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const state = stateRef.current;
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    state.transform.k = Math.min(4, Math.max(0.2, state.transform.k * factor));
  }, []);

  // Pan
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    stateRef.current.drag = { active: true, lastX: e.clientX, lastY: e.clientY };
  }, []);
  const onMouseMove = useCallback((e: React.MouseEvent) => {
    hoverPos.current = { x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY };
    const state = stateRef.current;
    if (state.drag.active) {
      state.transform.x += e.clientX - state.drag.lastX;
      state.transform.y += e.clientY - state.drag.lastY;
      state.drag.lastX = e.clientX;
      state.drag.lastY = e.clientY;
    }
    // Hover detection
    const mx = (hoverPos.current.x - state.transform.x) / state.transform.k;
    const my = (hoverPos.current.y - state.transform.y) / state.transform.k;
    const hit = state.nodes.find(n => {
      const r = Math.max(4, 4 + Math.log(n.degree + 1) * 1.5) + 4;
      return (n.x - mx) ** 2 + (n.y - my) ** 2 < r * r;
    });
    setHovered(hit ?? null);
  }, []);
  const onMouseUp = useCallback(() => { stateRef.current.drag.active = false; }, []);

  return (
    <div ref={containerRef} className="relative h-full w-full cursor-grab active:cursor-grabbing" onWheel={onWheel} onMouseDown={onMouseDown} onMouseMove={onMouseMove} onMouseUp={onMouseUp} onMouseLeave={onMouseUp}>
      <canvas ref={canvasRef} className="h-full w-full" />
      {hovered && (
        <div className="pointer-events-none absolute left-3 top-3 rounded-lg border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-3 py-2 shadow-lg">
          <p className="text-xs font-semibold text-[var(--ukip-text-strong)]">{hovered.label}</p>
          <p className="mt-0.5 text-[11px] text-[var(--ukip-muted)]">C{hovered.community + 1} · PageRank {hovered.pagerank.toFixed(3)} · Degree {hovered.degree}</p>
        </div>
      )}
      {/* Zoom controls */}
      <div className="absolute bottom-3 left-3 flex flex-col gap-1">
        {[["＋", 1.2], ["－", 0.8]].map(([label, f]) => (
          <button key={label as string} onClick={() => { stateRef.current.transform.k = Math.min(4, Math.max(0.2, stateRef.current.transform.k * (f as number))); }}
            className="flex h-7 w-7 items-center justify-center rounded-md border border-[var(--ukip-border)] bg-[var(--ukip-panel)] text-sm text-[var(--ukip-muted)] hover:text-[var(--ukip-text-strong)]">
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function GraphExplorerPage() {
  const { t } = useLanguage();
  const { activeDomainId, activeDomain } = useDomain();
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Path finder
  const [showPath, setShowPath] = useState(false);
  const [fromId, setFromId] = useState("");
  const [toId, setToId] = useState("");
  const [pathResult, setPathResult] = useState<PathResult | null>(null);
  const [loadingPath, setLoadingPath] = useState(false);
  const [pathError, setPathError] = useState<string | null>(null);
  const [highlightIds, setHighlightIds] = useState<Set<number>>(new Set());

  // Export
  const [exporting, setExporting] = useState(false);
  const [materializing, setMaterializing] = useState(false);
  const [materializeMessage, setMaterializeMessage] = useState<string | null>(null);
  const [keywordSignals, setKeywordSignals] = useState<KeywordSignal[]>([]);
  const [loadingSignals, setLoadingSignals] = useState(false);

  const activeGraphDomain = activeDomainId && activeDomainId !== "all" ? activeDomainId : null;
  const activeGraphScopeLabel = activeGraphDomain ? (activeDomain?.name || activeGraphDomain) : "Todos los dominios";

  const buildScopedQuery = useCallback((base?: Record<string, string>) => {
    const query = new URLSearchParams(base);
    if (typeof window !== "undefined") {
      const current = new URLSearchParams(window.location.search);
      ["import_batch_id", "provider", "portal", "portal_slug"].forEach((key) => {
        const value = current.get(key);
        if (value) query.set(key, value);
      });
      const urlDomain = current.get("domain");
      if (!activeGraphDomain && urlDomain && urlDomain !== "all") query.set("domain", urlDomain);
    }
    if (activeGraphDomain) query.set("domain", activeGraphDomain);
    else query.delete("domain");
    return query;
  }, [activeGraphDomain]);

  useEffect(() => {
    const query = buildScopedQuery({ limit: "500" });

    setLoading(true);
    setError(null);
    setData(null);
    setPathResult(null);
    setPathError(null);
    setHighlightIds(new Set());
    apiFetch(`/graph/visualization?${query.toString()}`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(setData)
      .catch(e => setError(`Failed to load graph (${e})`))
      .finally(() => setLoading(false));
  }, [buildScopedQuery]);

  const fetchKeywordSignals = useCallback(async () => {
    setLoadingSignals(true);
    try {
      const domain = activeGraphDomain || "all";
      const response = await apiFetch(`/analytics/keywords/${encodeURIComponent(domain)}/signals?limit=8`);
      if (response.ok) {
        const payload = await response.json();
        setKeywordSignals(payload.signals ?? []);
      } else {
        setKeywordSignals([]);
      }
    } catch {
      setKeywordSignals([]);
    } finally {
      setLoadingSignals(false);
    }
  }, [activeGraphDomain]);

  useEffect(() => {
    void fetchKeywordSignals();
  }, [fetchKeywordSignals]);

  async function findPath() {
    if (!fromId || !toId) return;
    setLoadingPath(true); setPathResult(null); setPathError(null); setHighlightIds(new Set());
    try {
      const query = buildScopedQuery({ from_id: fromId, to_id: toId });
      const r = await apiFetch(`/graph/path?${query.toString()}`);
      const result: PathResult = await r.json();
      setPathResult(result);
      if (result.found && result.steps) setHighlightIds(new Set(result.steps.map(s => s.entity_id)));
    } catch { setPathError(t("page.graph.network_error")); }
    finally { setLoadingPath(false); }
  }

  async function handleExport() {
    setExporting(true);
    try {
      const query = buildScopedQuery({ format: "graphml" });
      const r = await apiFetch(`/export/graph?${query.toString()}`);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const suffix = activeGraphDomain ? `_${activeGraphDomain}` : "";
      const a = document.createElement("a"); a.href = url; a.download = `ukip_graph${suffix}.graphml`; a.click();
      URL.revokeObjectURL(url);
    } finally { setExporting(false); }
  }

  async function handleMaterialize() {
    setMaterializing(true);
    setMaterializeMessage(null);
    try {
      const query = buildScopedQuery({ limit: "50" });
      const r = await apiFetch(`/graph/materialize?${query.toString()}`, { method: "POST" });
      const payload = r.ok ? await r.json() : null;
      const created = payload?.totals?.relationships_created ?? 0;
      const batches = payload?.totals?.batches ?? 0;
      setMaterializeMessage(created > 0 ? `${created} relaciones generadas en ${batches} batches.` : `Sin relaciones nuevas en ${batches} batches.`);
      const refreshQuery = buildScopedQuery({ limit: "500" });
      const refreshed = await apiFetch(`/graph/visualization?${refreshQuery.toString()}`);
      if (refreshed.ok) setData(await refreshed.json());
      await fetchKeywordSignals();
    } catch {
      setMaterializeMessage("No se pudo generar el grafo para este contexto.");
    } finally {
      setMaterializing(false);
    }
  }

  const stats = data?.stats;
  const activeFilters = data?.filters ? Object.entries(data.filters).filter(([, value]) => value !== null && value !== undefined && value !== "") : [];
  const edgeTypeLabels: Record<string, string> = {
    cites: t("page.graph.edge_cites") || "Cita",
    "authored-by": t("page.graph.edge_authored") || "Autoría",
    "belongs-to": t("page.graph.edge_belongs") || "Afiliación",
    "published-in": "Publicación",
    "has-concept": "Concepto",
    "identified-by": "Identificador",
    "coauthor-with": "Coautoría",
    "related-to": t("page.graph.edge_related") || "Relacionado",
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col overflow-hidden bg-[var(--ukip-bg)]">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-6 py-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-[var(--ukip-muted)]">
            <span>Intelligence</span><span>/</span><span className="text-[var(--ukip-text-strong)]">{t("page.graph.title") || "Grafo"}</span>
          </div>
          <h1 className="mt-1 text-2xl font-bold text-[var(--ukip-text-strong)]">{t("page.graph.explorer_title") || "Graph Explorer"}</h1>
          <p className="mt-0.5 text-sm text-[var(--ukip-muted)]">{t("page.graph.explorer_description") || "Grafo de conocimiento interactivo con comunidades Leiden y PageRank."}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {[["RENDER", "Canvas 2D"], ["LAYOUT", "Force-directed"], ["NODES", stats ? `${stats.visible_nodes}` : "—"], ["EDGES", stats ? `${stats.visible_edges}` : "—"]].map(([k, v]) => (
              <span key={k} className="rounded-md border border-[var(--ukip-border)] bg-[var(--ukip-panel-strong)] px-2 py-0.5 text-[11px] font-mono text-[var(--ukip-muted)]">
                <span className="mr-1 text-[var(--ukip-muted-soft)]">{k}</span>{v}
              </span>
            ))}
            {activeFilters.map(([key, value]) => (
              <span key={key} className="rounded-md border border-[var(--ukip-primary-soft)] bg-[var(--ukip-primary-soft)] px-2 py-0.5 text-[11px] font-mono text-[var(--ukip-primary-strong)]">
                <span className="mr-1 uppercase opacity-70">{key}</span>{String(value)}
              </span>
            ))}
            <span className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-mono text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300">
              <span className="mr-1 uppercase opacity-70">scope</span>{activeGraphScopeLabel}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleMaterialize} disabled={materializing}
            className="flex items-center gap-2 rounded-xl bg-[var(--ukip-primary)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4.5 12a7.5 7.5 0 0112.728-5.364M19.5 12a7.5 7.5 0 01-12.728 5.364M16.5 6.75h1.5V5.25M7.5 17.25H6v1.5" /></svg>
            {materializing ? "Generando..." : "Generar grafo"}
          </button>
          <button onClick={() => { setShowPath(p => !p); setPathResult(null); setHighlightIds(new Set()); }}
            className="flex items-center gap-2 rounded-xl bg-[var(--ukip-primary-soft)] px-4 py-2 text-sm font-semibold text-[var(--ukip-primary-strong)] transition hover:opacity-90">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" /></svg>
            Path Finder
          </button>
          <button onClick={handleExport} disabled={exporting}
            className="flex items-center gap-2 rounded-xl border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-4 py-2 text-sm font-semibold text-[var(--ukip-text-strong)] transition hover:bg-[var(--ukip-panel-strong)] disabled:opacity-50">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>
            {exporting ? "Exportando..." : "Exportar"}
          </button>
        </div>
      </div>
      {materializeMessage && (
        <div className="shrink-0 border-b border-[var(--ukip-border)] bg-[var(--ukip-primary-soft)] px-6 py-2 text-xs font-semibold text-[var(--ukip-primary-strong)]">
          {materializeMessage}
        </div>
      )}

      {/* KPI Row */}
      {stats && (
        <div className="grid shrink-0 grid-cols-4 divide-x divide-[var(--ukip-border)] border-b border-[var(--ukip-border)] bg-[var(--ukip-panel)]">
          {[
            { label: t("page.graph.total_nodes") || "Nodos visibles", value: stats.visible_nodes.toLocaleString(), sub: `filtrados por comunidad`, icon: "M12 18a6 6 0 100-12 6 6 0 000 12z" },
            { label: t("page.graph.total_edges") || "Aristas tipadas", value: stats.visible_edges.toLocaleString(), sub: data?.edge_types.join(" · ") || "", icon: "M5 12h14M12 5l7 7-7 7" },
            { label: "PageRank líder", value: stats.top_pagerank_score.toFixed(2), sub: stats.top_pagerank_leader || "—", icon: "M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" },
            { label: "Comunidades", value: data ? `${data.total_communities}/${data.total_communities}` : "—", sub: "Leiden", icon: "M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6z" },
          ].map(kpi => (
            <div key={kpi.label} className="px-6 py-4">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-[var(--ukip-muted)]">{kpi.label}</p>
                <svg className="h-4 w-4 text-[var(--ukip-muted-soft)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={kpi.icon} /></svg>
              </div>
              <p className="mt-2 text-3xl font-bold tabular-nums text-[var(--ukip-text-strong)]">{kpi.value}</p>
              <p className="mt-1 truncate text-[11px] text-[var(--ukip-muted-soft)]">{kpi.sub}</p>
            </div>
          ))}
        </div>
      )}

      {/* Path Finder Panel */}
      {showPath && (
        <div className="shrink-0 border-b border-[var(--ukip-border)] bg-[var(--ukip-surface)] px-6 py-3">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-[var(--ukip-muted)]">{t("page.graph.from_entity_id") || "Desde (ID)"}</label>
              <input type="number" min={1} value={fromId} onChange={e => setFromId(e.target.value)} placeholder="1"
                className="w-28 rounded-lg border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-3 py-1.5 text-sm text-[var(--ukip-text-strong)] outline-none focus:border-[var(--ukip-primary)]" />
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-[var(--ukip-muted)]">{t("page.graph.to_entity_id") || "Hasta (ID)"}</label>
              <input type="number" min={1} value={toId} onChange={e => setToId(e.target.value)} placeholder="5"
                className="w-28 rounded-lg border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-3 py-1.5 text-sm text-[var(--ukip-text-strong)] outline-none focus:border-[var(--ukip-primary)]" />
            </div>
            <button onClick={findPath} disabled={loadingPath || !fromId || !toId}
              className="rounded-lg bg-[var(--ukip-primary)] px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-50">
              {loadingPath ? "Buscando..." : t("page.graph.find_path") || "Encontrar ruta"}
            </button>
            {pathResult && !pathResult.found && <span className="text-xs text-amber-500">Sin ruta directa</span>}
            {pathResult?.found && pathResult.steps && (
              <div className="flex flex-wrap items-center gap-1">
                {pathResult.steps.map((s, i) => (
                  <span key={s.entity_id} className="flex items-center gap-1">
                    <span className="rounded-md bg-[var(--ukip-primary-soft)] px-2 py-0.5 text-xs font-medium text-[var(--ukip-primary-strong)]">{s.primary_label ?? `#${s.entity_id}`}</span>
                    {i < (pathResult.steps?.length ?? 0) - 1 && <svg className="h-3 w-3 text-[var(--ukip-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>}
                  </span>
                ))}
              </div>
            )}
            {pathError && <span className="text-xs text-red-500">{pathError}</span>}
          </div>
        </div>
      )}

      {/* Main content */}
      <div className="flex min-h-0 flex-1">
        {/* Graph canvas */}
        <div className="relative min-h-0 flex-1 border-r border-[var(--ukip-border)] bg-[var(--ukip-bg)]">
          {loading && (
            <div className="flex h-full items-center justify-center">
              <svg className="h-8 w-8 animate-spin text-[var(--ukip-primary)]" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            </div>
          )}
          {error && <div className="flex h-full items-center justify-center p-8 text-sm text-red-500">{error}</div>}
          {!loading && !error && data && data.nodes.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-[var(--ukip-muted)]">
              <svg className="h-12 w-12 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.5 16.875h3.375m0 0h3.375m-3.375 0V13.5m0 3.375v3.375M6 10.5h2.25a2.25 2.25 0 002.25-2.25V6a2.25 2.25 0 00-2.25-2.25H6A2.25 2.25 0 003.75 6v2.25A2.25 2.25 0 006 10.5z" /></svg>
              <p className="text-sm">{t("page.graph.no_relationships") || "Sin relaciones. Añade relaciones entre entidades para visualizar el grafo."}</p>
              <p className="max-w-md text-center text-xs text-[var(--ukip-muted-soft)]">Este contexto puede tener entidades enriquecidas pero aún no relaciones materializadas. Usa “Generar grafo” para reconstruir nodos y aristas desde autores, conceptos, DOI y venues.</p>
              <button onClick={handleMaterialize} disabled={materializing}
                className="rounded-xl bg-[var(--ukip-primary)] px-4 py-2 text-xs font-bold text-white disabled:opacity-50">
                {materializing ? "Generando..." : "Generar grafo para este contexto"}
              </button>
            </div>
          )}
          {!loading && !error && data && data.nodes.length > 0 && (
            <ForceGraph nodes={data.nodes} links={data.links} highlightIds={highlightIds.size > 0 ? highlightIds : undefined} />
          )}
        </div>

        {/* Right info panel */}
        <div className="flex w-64 shrink-0 flex-col gap-4 overflow-y-auto bg-[var(--ukip-panel)] p-4">
          <div>
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--ukip-muted-soft)]">Señales semánticas</p>
              <button onClick={() => void fetchKeywordSignals()} className="text-[11px] font-semibold text-[var(--ukip-primary-strong)] hover:underline">
                {loadingSignals ? "..." : "Refrescar"}
              </button>
            </div>
            {keywordSignals.length === 0 ? (
              <div className="rounded-lg border border-[var(--ukip-border)] px-3 py-2 text-xs text-[var(--ukip-muted)]">
                Sin señales todavía. Genera el grafo o ejecuta enrichment para poblar keywords long-tail y soporte externo.
              </div>
            ) : (
              <div className="space-y-1.5">
                {keywordSignals.slice(0, 6).map((signal) => (
                  <div key={signal.keyword} className="rounded-lg border border-[var(--ukip-border)] px-3 py-2">
                    <div className="flex items-start justify-between gap-2">
                      <p className="min-w-0 flex-1 truncate text-xs font-semibold text-[var(--ukip-text-strong)]">{signal.keyword}</p>
                      <span className="shrink-0 rounded bg-[var(--ukip-primary-soft)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--ukip-primary-strong)]">
                        {Math.round(signal.opportunity_score)}
                      </span>
                    </div>
                    <p className="mt-1 text-[11px] text-[var(--ukip-muted)]">
                      {signal.classification} · {signal.support_count} registros
                      {signal.external_support ? ` · ${signal.external_support} externas` : ""}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Edge types */}
          {data && data.edge_types.length > 0 && (
            <div>
              <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--ukip-muted-soft)]">Tipos de arista</p>
              <div className="space-y-1.5">
                {data.edge_types.map(t => (
                  <div key={t} className="flex items-center justify-between rounded-lg border border-[var(--ukip-border)] px-3 py-2">
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: edgeColor(t) }} />
                      <span className="text-xs font-medium text-[var(--ukip-text-strong)]">{t}</span>
                    </div>
                    <span className="text-[11px] text-[var(--ukip-muted)]">{edgeTypeLabels[t] ?? t}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Communities */}
          {data && data.total_communities > 0 && (
            <div>
              <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--ukip-muted-soft)]">Comunidades (Leiden)</p>
              <div className="flex flex-wrap gap-1.5">
                {Array.from({ length: data.total_communities }, (_, i) => (
                  <span key={i} className="flex items-center gap-1.5 rounded-full border border-[var(--ukip-border)] px-2.5 py-1 text-xs font-semibold text-[var(--ukip-text-strong)]">
                    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: COMMUNITY_COLORS[i % COMMUNITY_COLORS.length] }} />
                    C{i + 1}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Top PageRank */}
          {data && data.nodes.length > 0 && (
            <div>
              <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--ukip-muted-soft)]">Top PageRank</p>
              <div className="space-y-1">
                {[...data.nodes].sort((a, b) => b.pagerank - a.pagerank).slice(0, 8).map((n, i) => (
                  <div key={n.id} className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-[var(--ukip-panel-strong)]">
                    <span className="w-4 text-[11px] tabular-nums text-[var(--ukip-muted-soft)]">{i + 1}</span>
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: COMMUNITY_COLORS[n.community % COMMUNITY_COLORS.length] }} />
                    <span className="min-w-0 flex-1 truncate text-xs text-[var(--ukip-text-strong)]">{n.label}</span>
                    <span className="shrink-0 text-[11px] tabular-nums text-[var(--ukip-muted)]">{n.pagerank.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
