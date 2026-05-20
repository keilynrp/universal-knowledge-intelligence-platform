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
    "cites":       "#6366f1",   // indigo
    "authored-by": "#10b981",   // emerald
    "belongs-to":  "#f59e0b",   // amber
    "published-in": "#06b6d4",  // cyan
    "has-concept": "#ec4899",   // pink
    "identified-by": "#64748b", // slate
    "coauthor-with": "#14b8a6", // teal
    "keyword-co-occurs-with": "#f97316", // orange
    "same-as": "#0f172a", // slate strong
    "equivalent-to": "#a855f7", // purple
    "external-signal-for": "#059669", // emerald
    "semantic-neighbor": "#2563eb", // blue
    "derived-keyword": "#c026d3", // fuchsia
    "emerging-from": "#d97706", // amber
    "related-to":  "#8b5cf6",   // violet
};

const RELATION_LABEL_COLORS: Record<string, string> = {
    "cites":       "#818cf8",
    "authored-by": "#34d399",
    "belongs-to":  "#fbbf24",
    "published-in": "#22d3ee",
    "has-concept": "#f472b6",
    "identified-by": "#94a3b8",
    "coauthor-with": "#2dd4bf",
    "keyword-co-occurs-with": "#fb923c",
    "same-as": "#334155",
    "equivalent-to": "#c084fc",
    "external-signal-for": "#10b981",
    "semantic-neighbor": "#60a5fa",
    "derived-keyword": "#e879f9",
    "emerging-from": "#f59e0b",
    "related-to":  "#a78bfa",
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
            </div>

            {/* SVG Canvas */}
            <div className="relative overflow-hidden rounded-xl border border-gray-100 bg-gray-50 dark:border-gray-800 dark:bg-gray-900/50">
                <svg
                    ref={svgRef}
                    viewBox={`0 0 ${W} ${H}`}
                    className="w-full"
                    style={{ height: `${H}px` }}
                >
                    <defs>
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
                        const fill = isCenter
                            ? "#4f46e5"
                            : isHovered
                            ? "#818cf8"
                            : "#e0e7ff";
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
                                <circle r={r} fill={fill} stroke={stroke} strokeWidth={isCenter ? 2.5 : 1.5} />
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
