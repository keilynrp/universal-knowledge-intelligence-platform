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
