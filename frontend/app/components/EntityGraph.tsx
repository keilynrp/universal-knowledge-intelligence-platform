"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

interface GraphNode {
    id: number;
    label: string;
    entity_type: string | null;
    domain: string | null;
    is_center: boolean;
}

interface GraphEdge {
    id: number;
    source: number;
    target: number;
    relation_type: string;
    weight: number;
}

interface GraphData {
    center_id: number;
    depth: number;
    nodes: GraphNode[];
    edges: GraphEdge[];
}

interface GraphMetrics {
    entity_id: number;
    primary_label: string;
    degree: {
        in_degree: number;
        out_degree: number;
        total_degree: number;
    };
    pagerank: {
        score: number;
        rank: number | null;
        total_nodes: number;
    };
    component: {
        component_id: number | null;
        size: number;
    };
}

interface GraphDiagnostics {
    status: "ready" | "materializable" | "needs_enrichment" | "insufficient_metadata";
    action: string;
    can_materialize: boolean;
    relationship_count: number;
    import_batch_id: number | null;
    signals: {
        concept_count: number;
        author_count: number;
        has_identifier: boolean;
        has_venue: boolean;
        enrichment_status: string | null;
    };
    missing: string[];
}

interface Position { x: number; y: number; }

const RELATION_COLORS: Record<string, string> = {
    "cites":       "#3B4CC0",   // blue-violet
    "authored-by": "#008B8B",   // teal
    "belongs-to":  "#7A7A00",   // olive
    "published-in": "#6A5ACD",  // slate blue
    "has-concept": "#8E5A2A",   // umber
    "identified-by": "#64748b", // slate
    "coauthor-with": "#1B9E77", // green
    "keyword-co-occurs-with": "#A6761D", // ochre
    "same-as": "#0f172a", // slate strong
    "equivalent-to": "#984EA3", // purple
    "external-signal-for": "#009E73", // bluish green
    "semantic-neighbor": "#0072B2", // blue
    "derived-keyword": "#D55E00", // vermillion
    "emerging-from": "#CC79A7", // reddish purple
    "related-to":  "#7E57C2",   // violet
};

const RELATION_LABEL_COLORS: Record<string, string> = {
    "cites":       "#6C78D8",
    "authored-by": "#20A6A6",
    "belongs-to":  "#999933",
    "published-in": "#8173D1",
    "has-concept": "#A87345",
    "identified-by": "#94a3b8",
    "coauthor-with": "#35B18B",
    "keyword-co-occurs-with": "#C08A36",
    "same-as": "#334155",
    "equivalent-to": "#B36DBA",
    "external-signal-for": "#22B98D",
    "semantic-neighbor": "#2490D0",
    "derived-keyword": "#E47734",
    "emerging-from": "#D995BD",
    "related-to":  "#9B7AD8",
};

function usePositions(nodes: GraphNode[], width: number, height: number): Record<number, Position> {
    const cx = width / 2;
    const cy = height / 2;
    const radius = Math.min(width, height) * 0.35;

    const positions: Record<number, Position> = {};
    const center = nodes.find((n) => n.is_center);
    const others = nodes.filter((n) => !n.is_center);

    if (center) positions[center.id] = { x: cx, y: cy };

    others.forEach((node, i) => {
        const angle = (2 * Math.PI * i) / others.length - Math.PI / 2;
        positions[node.id] = {
            x: cx + radius * Math.cos(angle),
            y: cy + radius * Math.sin(angle),
        };
    });

    return positions;
}

export default function EntityGraph({ entityId }: { entityId: number }) {
    const [graph, setGraph] = useState<GraphData | null>(null);
    const [depth, setDepth] = useState<1 | 2>(1);
    const [zoom, setZoom] = useState(1);
    const [hovered, setHovered] = useState<number | null>(null);
    const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string } | null>(null);
    const [metrics, setMetrics] = useState<GraphMetrics | null>(null);
    const [diagnostics, setDiagnostics] = useState<GraphDiagnostics | null>(null);
    const [resolvedKey, setResolvedKey] = useState<string | null>(null);
    const [materializing, setMaterializing] = useState(false);
    const [materializeMessage, setMaterializeMessage] = useState<string | null>(null);
    const svgRef = useRef<SVGSVGElement>(null);

    const W = 600;
    const H = 420;
    const viewW = W / zoom;
    const viewH = H / zoom;
    const viewX = (W - viewW) / 2;
    const viewY = (H - viewH) / 2;

    const requestKey = `${entityId}:${depth}`;
    const loading = resolvedKey !== requestKey;

    useEffect(() => {
        let active = true;
        Promise.all([
            apiFetch(`/entities/${entityId}/graph?depth=${depth}`)
                .then((r) => r.ok ? r.json() : null)
                .catch(() => null),
            apiFetch(`/entities/${entityId}/graph/metrics`)
                .then((r) => r.ok ? r.json() : null)
                .catch(() => null),
            apiFetch(`/entities/${entityId}/graph/diagnostics`)
                .then((r) => r.ok ? r.json() : null)
                .catch(() => null),
        ]).then(([graphData, metricsData, diagnosticsData]) => {
            if (!active) {
                return;
            }
            setGraph(graphData);
            setMetrics(metricsData);
            setDiagnostics(diagnosticsData);
            setResolvedKey(requestKey);
        });

        return () => {
            active = false;
        };
    }, [entityId, depth, requestKey]);

    const positions = usePositions(graph?.nodes ?? [], W, H);

    async function materializeForEntity() {
        setMaterializing(true);
        setMaterializeMessage(null);
        try {
            const response = await apiFetch(`/graph/materialize?entity_id=${entityId}`, { method: "POST" });
            const payload = response.ok ? await response.json() : null;
            const created = payload?.totals?.relationships_created ?? 0;
            setMaterializeMessage(created > 0 ? `Generated ${created} relationships.` : "No new relationships were generated.");
            setResolvedKey(null);
        } catch {
            setMaterializeMessage("Could not generate relationships.");
        } finally {
            setMaterializing(false);
        }
    }

    if (loading) {
        return (
            <div className="flex h-64 items-center justify-center">
                <svg className="h-6 w-6 animate-spin text-indigo-500" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
            </div>
        );
    }

    if (!graph || graph.edges.length === 0) {
        return (
            <div className="space-y-4 rounded-2xl border border-dashed border-slate-200 bg-white p-5 text-center dark:border-white/10 dark:bg-slate-950/40">
                <svg className="mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                <div>
                    <p className="text-sm font-bold text-slate-700 dark:text-slate-200">No hay relaciones activas para este registro</p>
                    <p className="mx-auto mt-1 max-w-xl text-xs leading-5 text-slate-500 dark:text-slate-400">
                        {diagnostics?.action || "Genera relaciones desde enrichment o crea una conexión manual para activar métricas del grafo."}
                    </p>
                </div>
                {diagnostics && (
                    <div className="mx-auto grid max-w-2xl grid-cols-2 gap-2 text-left sm:grid-cols-4">
                        {[
                            ["Conceptos", diagnostics.signals.concept_count],
                            ["Autores", diagnostics.signals.author_count],
                            ["Identificador", diagnostics.signals.has_identifier ? "sí" : "no"],
                            ["Venue", diagnostics.signals.has_venue ? "sí" : "no"],
                        ].map(([label, value]) => (
                            <div key={label} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2 dark:border-white/10 dark:bg-white/5">
                                <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">{label}</p>
                                <p className="mt-1 text-sm font-black text-slate-800 dark:text-white">{value}</p>
                            </div>
                        ))}
                    </div>
                )}
                <div className="flex flex-wrap justify-center gap-2">
                    <button
                        onClick={materializeForEntity}
                        disabled={materializing || !diagnostics?.can_materialize}
                        className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {materializing ? "Generando..." : "Generar relaciones"}
                    </button>
                    <Link href="/analytics/graph" className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-600 transition hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-200">
                        Ver grafo global
                    </Link>
                </div>
                {materializeMessage && <p className="text-xs font-semibold text-slate-500">{materializeMessage}</p>}
            </div>
        );
    }

    return (
        <div className="space-y-3">
            {/* Controls */}
            <div className="flex items-center gap-3">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Depth:</span>
                {([1, 2] as const).map((d) => (
                    <button
                        key={d}
                        onClick={() => setDepth(d)}
                        className={`rounded-lg border px-3 py-1 text-xs font-semibold transition-colors ${
                            depth === d
                                ? "border-indigo-300 bg-indigo-50 text-indigo-700 dark:border-indigo-500/40 dark:bg-indigo-500/10 dark:text-indigo-300"
                                : "border-gray-200 bg-white text-gray-500 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
                        }`}
                    >
                        {d}-hop
                    </button>
                ))}
                <span className="ml-auto text-xs text-gray-400 dark:text-gray-500">
                    {graph.nodes.length} nodes · {graph.edges.length} edges
                </span>
                <div className="flex items-center gap-1 rounded-lg border border-gray-200 bg-white p-1 dark:border-gray-700 dark:bg-gray-800">
                    <button
                        onClick={() => setZoom((value) => Math.max(0.7, Number((value - 0.2).toFixed(1))))}
                        className="flex h-7 w-7 items-center justify-center rounded-md text-sm font-bold text-gray-500 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
                        title="Zoom out"
                    >
                        −
                    </button>
                    <span className="w-12 text-center text-[11px] font-semibold text-gray-500 dark:text-gray-300">{Math.round(zoom * 100)}%</span>
                    <button
                        onClick={() => setZoom((value) => Math.min(2.4, Number((value + 0.2).toFixed(1))))}
                        className="flex h-7 w-7 items-center justify-center rounded-md text-sm font-bold text-gray-500 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
                        title="Zoom in"
                    >
                        +
                    </button>
                    <button
                        onClick={() => setZoom(1)}
                        className="rounded-md px-2 py-1 text-[11px] font-semibold text-gray-500 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
                    >
                        Reset
                    </button>
                </div>
            </div>

            {/* SVG Canvas */}
            <div className="relative overflow-hidden rounded-xl border border-gray-100 bg-gray-50 dark:border-gray-800 dark:bg-gray-900/50">
                <svg
                    ref={svgRef}
                    viewBox={`${viewX} ${viewY} ${viewW} ${viewH}`}
                    className="w-full"
                    style={{ height: `${H}px` }}
                >
                    <defs>
                        <filter id="node-soft-shadow" x="-50%" y="-50%" width="200%" height="200%">
                            <feDropShadow dx="0" dy="3" stdDeviation="3" floodColor="#0f172a" floodOpacity="0.18" />
                        </filter>
                        {Object.entries(RELATION_COLORS).map(([type, color]) => (
                            <marker
                                key={type}
                                id={`arrow-${type.replace(/[^a-z]/g, "-")}`}
                                markerWidth="8"
                                markerHeight="8"
                                refX="6"
                                refY="3"
                                orient="auto"
                            >
                                <path d="M0,0 L0,6 L8,3 z" fill={color} />
                            </marker>
                        ))}
                        {graph.nodes.map((node) => {
                            const isCenter = node.is_center;
                            const base = isCenter ? "#4f46e5" : hovered === node.id ? "#818cf8" : "#c7d2fe";
                            const light = isCenter ? "#a5b4fc" : hovered === node.id ? "#c7d2fe" : "#eef2ff";
                            const dark = isCenter ? "#312e81" : hovered === node.id ? "#4f46e5" : "#818cf8";
                            return (
                                <radialGradient key={node.id} id={`node-sphere-${node.id}`} cx="35%" cy="28%" r="72%">
                                    <stop offset="0%" stopColor="#ffffff" stopOpacity="0.92" />
                                    <stop offset="22%" stopColor={light} />
                                    <stop offset="58%" stopColor={base} />
                                    <stop offset="100%" stopColor={dark} />
                                </radialGradient>
                            );
                        })}
                    </defs>

                    {/* Edges */}
                    {graph.edges.map((edge) => {
                        const src = positions[edge.source];
                        const tgt = positions[edge.target];
                        if (!src || !tgt) return null;
                        const color = RELATION_COLORS[edge.relation_type] ?? "#94a3b8";
                        const markerId = `arrow-${edge.relation_type.replace(/[^a-z]/g, "-")}`;
                        const mx = (src.x + tgt.x) / 2;
                        const my = (src.y + tgt.y) / 2;

                        // Shorten line to not overlap node circles (r=22)
                        const dx = tgt.x - src.x;
                        const dy = tgt.y - src.y;
                        const len = Math.sqrt(dx * dx + dy * dy) || 1;
                        const x1 = src.x + (dx / len) * 24;
                        const y1 = src.y + (dy / len) * 24;
                        const x2 = tgt.x - (dx / len) * 28;
                        const y2 = tgt.y - (dy / len) * 28;

                        return (
                            <g key={edge.id}>
                                <line
                                    x1={x1} y1={y1} x2={x2} y2={y2}
                                    stroke={color}
                                    strokeWidth={edge.weight > 1 ? Math.min(edge.weight, 4) : 1.5}
                                    strokeOpacity={0.7}
                                    markerEnd={`url(#${markerId})`}
                                />
                                <text
                                    x={mx} y={my - 5}
                                    textAnchor="middle"
                                    fontSize="9"
                                    fill={RELATION_LABEL_COLORS[edge.relation_type] ?? "#94a3b8"}
                                    className="pointer-events-none select-none"
                                >
                                    {edge.relation_type}
                                </text>
                            </g>
                        );
                    })}

                    {/* Nodes */}
                    {graph.nodes.map((node) => {
                        const pos = positions[node.id];
                        if (!pos) return null;
                        const isCenter = node.is_center;
                        const isHovered = hovered === node.id;
                        const r = isCenter ? 28 : 22;
                        const textFill = isCenter || isHovered ? "#fff" : "#3730a3";
                        const stroke = isCenter ? "#3730a3" : isHovered ? "#6366f1" : "#c7d2fe";

                        return (
                            <g
                                key={node.id}
                                transform={`translate(${pos.x},${pos.y})`}
                                style={{ cursor: isCenter ? "default" : "pointer" }}
                                onMouseEnter={(e) => {
                                    setHovered(node.id);
                                    const svgRect = svgRef.current?.getBoundingClientRect();
                                    if (svgRect) {
                                        const scaleX = W / svgRect.width;
                                        const scaleY = H / svgRect.height;
                                        setTooltip({
                                            x: (e.clientX - svgRect.left) * scaleX,
                                            y: (e.clientY - svgRect.top) * scaleY - 40,
                                            text: `${node.label}${node.entity_type ? ` · ${node.entity_type}` : ""}`,
                                        });
                                    }
                                }}
                                onMouseLeave={() => { setHovered(null); setTooltip(null); }}
                            >
                                <circle r={r + (isHovered ? 4 : 0)} fill={isHovered ? "#4f46e5" : "#6366f1"} opacity={isHovered ? 0.16 : 0.08} />
                                <circle r={r} fill={`url(#node-sphere-${node.id})`} stroke={stroke} strokeWidth={isCenter ? 2.5 : 1.5} filter="url(#node-soft-shadow)" />
                                <circle cx={-r * 0.34} cy={-r * 0.38} r={Math.max(3, r * 0.2)} fill="#fff" opacity={isCenter || isHovered ? 0.55 : 0.42} />
                                <text
                                    textAnchor="middle"
                                    dy="0.35em"
                                    fontSize={isCenter ? "10" : "9"}
                                    fontWeight={isCenter ? "700" : "500"}
                                    fill={textFill}
                                    className="pointer-events-none select-none"
                                >
                                    {node.label.length > 10 ? node.label.slice(0, 9) + "\u2026" : node.label}
                                </text>
                                {!isCenter && (
                                    <foreignObject x={-r} y={r + 2} width={r * 2} height={16}>
                                        <Link
                                            href={`/entities/${node.id}`}
                                            className="block truncate text-center text-[9px] text-indigo-600 hover:underline dark:text-indigo-400"
                                        >
                                            #{node.id}
                                        </Link>
                                    </foreignObject>
                                )}
                            </g>
                        );
                    })}

                    {/* Tooltip */}
                    {tooltip && (
                        <g>
                            <rect
                                x={tooltip.x - 70} y={tooltip.y - 14}
                                width={140} height={22}
                                rx={4} fill="#1e1b4b" opacity={0.9}
                            />
                            <text
                                x={tooltip.x} y={tooltip.y + 2}
                                textAnchor="middle" fontSize="10" fill="#e0e7ff"
                                className="pointer-events-none select-none"
                            >
                                {tooltip.text.length > 30 ? tooltip.text.slice(0, 29) + "\u2026" : tooltip.text}
                            </text>
                        </g>
                    )}
                </svg>
            </div>

            {/* Legend */}
            <div className="flex flex-wrap gap-3 px-1">
                {Object.entries(RELATION_COLORS).map(([type, color]) => (
                    <div key={type} className="flex items-center gap-1.5">
                        <div className="h-2 w-5 rounded-full" style={{ backgroundColor: color }} />
                        <span className="text-[10px] text-gray-500 dark:text-gray-400">{type}</span>
                    </div>
                ))}
            </div>

            {/* Metrics strip */}
            {metrics && (
                <div className="mt-2 grid grid-cols-3 divide-x divide-gray-100 rounded-xl border border-gray-100 bg-gray-50 dark:divide-gray-800 dark:border-gray-800 dark:bg-gray-900/40">
                    <div className="px-4 py-3">
                        <p className="text-[10px] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
                            Degree
                        </p>
                        <p className="mt-0.5 text-sm font-semibold text-gray-900 dark:text-white">
                            ↓ {metrics.degree.in_degree} / ↑ {metrics.degree.out_degree}
                        </p>
                    </div>
                    <div className="px-4 py-3">
                        <p className="text-[10px] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
                            PageRank
                        </p>
                        <p className="mt-0.5 text-sm font-semibold text-gray-900 dark:text-white">
                            {metrics.pagerank.score.toFixed(4)}
                            {metrics.pagerank.rank != null && (
                                <span className="ml-1.5 text-xs font-normal text-gray-500 dark:text-gray-400">
                                    #{metrics.pagerank.rank} of {metrics.pagerank.total_nodes}
                                </span>
                            )}
                        </p>
                    </div>
                    <div className="px-4 py-3">
                        <p className="text-[10px] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
                            Component
                        </p>
                        <p className="mt-0.5 text-sm font-semibold text-gray-900 dark:text-white">
                            {metrics.component.component_id != null
                                ? `Component ${metrics.component.component_id} · ${metrics.component.size} nodes`
                                : "—"}
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}
