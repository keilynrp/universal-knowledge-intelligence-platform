"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { GraphEdge, GraphNode } from "../../types/graph";
import { useForceLayout, type PositionedNode } from "./useForceLayout";
import { communityColor } from "./palette";

/**
 * GraphDB/Neo4j-style force-directed network for UKIP coauthorship.
 *
 * - d3-force layout (memoized; reduced-motion settles instantly)
 * - cubic-Bézier edges, thickness log(weight+1)·1.5, weight labels when zoomed
 * - nodes colored by community (OKLCH palette), radius by publication count
 * - hover highlights neighbors + dims the rest
 * - click selects; arrow keys cycle a focused node's neighbors
 * - drag-to-pan background, drag-to-reposition nodes, wheel + button zoom
 */
export interface NetworkGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selected?: string | null;
  onNodeClick?: (id: string) => void;
  width?: number;
  height?: number;
  screenOverlay?: ReactNode;
  className?: string;
}

const DEFAULT_W = 1000;
const DEFAULT_H = 600;
const ZOOM_MIN = 0.4;
const ZOOM_MAX = 6;
const ZOOM_STEP = 1.4;
const LABEL_TOP_N = 12;
const WEIGHT_LABEL_ZOOM = 0.7;

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function NetworkGraph({
  nodes: rawNodes,
  edges: rawEdges,
  selected,
  onNodeClick,
  width = DEFAULT_W,
  height = DEFAULT_H,
  screenOverlay,
  className,
}: NetworkGraphProps) {
  const { nodes, edges, stable } = useForceLayout(rawNodes, rawEdges, width, height);

  // Adjacency for hover-dim + keyboard neighbor cycling.
  const neighbors = useMemo(() => {
    const map = new Map<string, string[]>();
    const add = (a: string, b: string) => {
      const list = map.get(a);
      if (list) list.push(b);
      else map.set(a, [b]);
    };
    for (const e of rawEdges) {
      add(e.source, e.target);
      add(e.target, e.source);
    }
    return map;
  }, [rawEdges]);

  const maxWeight = useMemo(() => Math.max(1, ...rawEdges.map((e) => e.weight)), [rawEdges]);

  const labelIds = useMemo(() => {
    const top = [...rawNodes]
      .sort((a, b) => b.centrality - a.centrality)
      .slice(0, LABEL_TOP_N)
      .map((n) => n.id);
    return new Set(top);
  }, [rawNodes]);

  const [hovered, setHovered] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ tx: 0, ty: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<{ startX: number; startY: number; startTx: number; startTy: number; moved: boolean } | null>(null);
  const nodeDragRef = useRef<{ node: PositionedNode } | null>(null);
  const justDraggedRef = useRef(false);

  const clamp = (z: number) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));
  const zoomBy = useCallback((factor: number) => setZoom((p) => clamp(p * factor)), []);
  const handleZoomReset = useCallback(() => {
    setZoom(1);
    setPan({ tx: 0, ty: 0 });
  }, []);

  const handleWheel = useCallback(
    (e: React.WheelEvent<SVGSVGElement>) => {
      e.preventDefault();
      zoomBy(e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP);
    },
    [zoomBy],
  );

  const handlePointerDown = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      if ((e.target as Element).closest("[data-node]")) return;
      if (e.button !== 0) return;
      dragRef.current = { startX: e.clientX, startY: e.clientY, startTx: pan.tx, startTy: pan.ty, moved: false };
    },
    [pan.tx, pan.ty],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      const sx = rect.width > 0 ? width / rect.width : 1;
      const sy = rect.height > 0 ? height / rect.height : 1;
      const nd = nodeDragRef.current;
      if (nd) {
        nd.node.fx = nd.node.x = ((e.clientX - rect.left) * sx - pan.tx) / zoom;
        nd.node.fy = nd.node.y = ((e.clientY - rect.top) * sy - pan.ty) / zoom;
        return;
      }
      const drag = dragRef.current;
      if (!drag) return;
      const dx = e.clientX - drag.startX;
      const dy = e.clientY - drag.startY;
      if (!drag.moved && Math.abs(dx) + Math.abs(dy) < 3) return;
      if (!drag.moved) {
        drag.moved = true;
        setIsPanning(true);
        try {
          svg.setPointerCapture(e.pointerId);
        } catch {
          /* ignore */
        }
      }
      e.preventDefault();
      setPan({ tx: drag.startTx + dx * sx, ty: drag.startTy + dy * sy });
    },
    [pan.tx, pan.ty, zoom, width, height],
  );

  const handlePointerUp = useCallback((e: React.PointerEvent<SVGSVGElement>) => {
    const nd = nodeDragRef.current;
    if (nd) {
      nodeDragRef.current = null;
      nd.node.fx = null;
      nd.node.fy = null;
    }
    if (dragRef.current?.moved) {
      try {
        svgRef.current?.releasePointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
      justDraggedRef.current = true;
      queueMicrotask(() => {
        justDraggedRef.current = false;
      });
    }
    dragRef.current = null;
    setIsPanning(false);
  }, []);

  const onNodePointerDown = useCallback((e: React.PointerEvent<SVGCircleElement>, node: PositionedNode) => {
    e.stopPropagation();
    if (e.button !== 0) return;
    nodeDragRef.current = { node };
  }, []);

  // Keyboard: arrow keys move selection to the next/previous neighbor.
  const onNodeKeyDown = useCallback(
    (e: React.KeyboardEvent<SVGCircleElement>, nodeId: string) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onNodeClick?.(nodeId);
        return;
      }
      const nbrs = neighbors.get(nodeId);
      if (!nbrs || nbrs.length === 0) return;
      if (["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(e.key)) {
        e.preventDefault();
        const anchor = selected && nbrs.includes(selected) ? selected : nbrs[0];
        const idx = nbrs.indexOf(anchor);
        const delta = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1;
        const next = nbrs[(idx + delta + nbrs.length) % nbrs.length];
        onNodeClick?.(next);
      }
    },
    [neighbors, selected, onNodeClick],
  );

  const transform = `translate(${pan.tx} ${pan.ty}) scale(${zoom})`;
  const focusId = hovered ?? selected ?? null;
  const focusNeighbors = focusId ? new Set([focusId, ...(neighbors.get(focusId) ?? [])]) : null;

  const isDimmed = (id: string) => focusNeighbors != null && !focusNeighbors.has(id);

  return (
    <div className={`relative ${className ?? "h-[560px]"}`}>
      <div
        data-testid="graph-zoom-controls"
        className="absolute right-3 top-3 z-10 flex flex-col gap-1 rounded-lg border border-gray-200 bg-white/90 p-1 shadow-sm backdrop-blur-sm dark:border-gray-700 dark:bg-gray-900/90"
      >
        <button type="button" onClick={() => zoomBy(ZOOM_STEP)} disabled={zoom >= ZOOM_MAX}
          aria-label="Zoom in"
          className="flex h-7 w-7 items-center justify-center rounded text-base font-bold text-gray-700 hover:bg-gray-100 disabled:opacity-40 dark:text-gray-200 dark:hover:bg-gray-800">+</button>
        <div className="select-none text-center text-[9px] font-mono text-gray-500 dark:text-gray-400">{zoom.toFixed(1)}×</div>
        <button type="button" onClick={() => zoomBy(1 / ZOOM_STEP)} disabled={zoom <= ZOOM_MIN}
          aria-label="Zoom out"
          className="flex h-7 w-7 items-center justify-center rounded text-base font-bold text-gray-700 hover:bg-gray-100 disabled:opacity-40 dark:text-gray-200 dark:hover:bg-gray-800">−</button>
        {(zoom !== 1 || pan.tx !== 0 || pan.ty !== 0) && (
          <button type="button" onClick={handleZoomReset} aria-label="Reset zoom"
            className="flex h-7 w-7 items-center justify-center rounded text-xs font-semibold text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-800">⟲</button>
        )}
      </div>

      {!stable && nodes.length > 0 && !prefersReducedMotion() && (
        <div className="absolute left-3 top-3 z-10 rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-mono text-gray-500 shadow-sm backdrop-blur-sm dark:bg-gray-900/80 dark:text-gray-400">
          relaxing…
        </div>
      )}

      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        className={`h-full w-full touch-none rounded-lg border border-gray-100 bg-slate-50 dark:border-gray-800 dark:bg-slate-950 ${isPanning ? "cursor-grabbing" : "cursor-grab"}`}
        preserveAspectRatio="xMidYMid meet"
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <g transform={transform}>
          {edges.map((e, i) => {
            const sx = e.source.x ?? 0;
            const sy = e.source.y ?? 0;
            const tx = e.target.x ?? 0;
            const ty = e.target.y ?? 0;
            // Control point: perpendicular offset at the midpoint -> gentle arc.
            const mx = (sx + tx) / 2;
            const my = (sy + ty) / 2;
            const dx = tx - sx;
            const dy = ty - sy;
            const len = Math.hypot(dx, dy) || 1;
            const off = Math.min(40, len * 0.12);
            const cx = mx + (-dy / len) * off;
            const cy = my + (dx / len) * off;
            const w = Math.log(e.weight + 1) * 1.5 + 0.4;
            const dim = isDimmed(e.source.id) || isDimmed(e.target.id);
            const showLabel = zoom > WEIGHT_LABEL_ZOOM && e.weight >= maxWeight * 0.4;
            return (
              <g key={`e-${i}`} opacity={dim ? 0.08 : 1}>
                <path
                  d={`M ${sx} ${sy} Q ${cx} ${cy} ${tx} ${ty}`}
                  fill="none"
                  stroke="oklch(60% 0.02 260)"
                  strokeOpacity={0.45}
                  strokeWidth={w}
                />
                {showLabel && (
                  <text x={cx} y={cy} textAnchor="middle" fontSize={9}
                    className="pointer-events-none fill-slate-500 dark:fill-slate-400"
                    paintOrder="stroke" stroke="rgba(255,255,255,0.8)" strokeWidth={2.5} strokeLinejoin="round">
                    {e.weight}
                  </text>
                )}
              </g>
            );
          })}

          {nodes.map((n) => {
            const isSel = selected === n.id;
            const dim = isDimmed(n.id);
            const fill = communityColor(n.community_id);
            return (
              <g key={n.id} data-node={n.id} transform={`translate(${n.x ?? 0} ${n.y ?? 0})`} opacity={dim ? 0.22 : 1}>
                {isSel && <circle r={n.radius + 5} fill="none" stroke="oklch(55% 0.20 264)" strokeWidth={2} />}
                <circle
                  r={n.radius}
                  fill={fill}
                  fillOpacity={isSel ? 1 : 0.9}
                  stroke="#fff"
                  strokeWidth={1.2}
                  tabIndex={0}
                  role="button"
                  aria-label={n.label}
                  className="cursor-pointer outline-none focus-visible:stroke-indigo-600"
                  onPointerDown={(e) => onNodePointerDown(e, n)}
                  onClick={() => {
                    if (justDraggedRef.current || nodeDragRef.current) return;
                    onNodeClick?.(n.id);
                  }}
                  onKeyDown={(e) => onNodeKeyDown(e, n.id)}
                  onMouseEnter={() => setHovered(n.id)}
                  onMouseLeave={() => setHovered(null)}
                  onFocus={() => setHovered(n.id)}
                  onBlur={() => setHovered(null)}
                />
                {(isSel || hovered === n.id || labelIds.has(n.id)) && (
                  <text
                    y={-n.radius - 4}
                    textAnchor="middle"
                    fontSize={isSel ? 12 : 10}
                    fontWeight={isSel ? 700 : 500}
                    className="pointer-events-none fill-slate-800 dark:fill-slate-100"
                    paintOrder="stroke"
                    stroke="rgba(255,255,255,0.85)"
                    strokeWidth={3}
                    strokeLinejoin="round"
                  >
                    {n.label.length > 28 ? `${n.label.slice(0, 28)}…` : n.label}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {screenOverlay}
    </div>
  );
}

export default NetworkGraph;
