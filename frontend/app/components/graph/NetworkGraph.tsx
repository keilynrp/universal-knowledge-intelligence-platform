"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { GraphEdge, GraphNode } from "../../types/graph";
import { useForceLayout, type PositionedNode } from "./useForceLayout";

/**
 * Reusable force-directed network visualisation for UKIP analytics.
 *
 * Features:
 * - d3-force layout (memoized, only re-runs when nodes/edges identity changes)
 * - drag-to-pan on the background, drag-to-reposition on a node
 * - mouse-wheel zoom + +/− buttons + reset
 * - click → selection; hover → tooltip
 * - configurable color resolver (defaults to a 10-community palette)
 *
 * Future modules (citations, concept maps, researcher graphs) can reuse this
 * via the same data contract.
 */
export interface NetworkGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selected?: string | null;
  onNodeClick?: (id: string) => void;
  onNodeHover?: (info: { id: string; x: number; y: number } | null) => void;
  width?: number;
  height?: number;
  /** Custom color resolver. Default: indexed community palette. */
  colorForNode?: (node: GraphNode) => string;
  /** Optional overlay (e.g. legend) rendered above the SVG. */
  screenOverlay?: ReactNode;
  labels?: {
    zoomIn?: string;
    zoomOut?: string;
    zoomReset?: string;
  };
  className?: string;
}

const DEFAULT_W = 1000;
const DEFAULT_H = 600;
const ZOOM_MIN = 0.4;
const ZOOM_MAX = 6;
const ZOOM_STEP = 1.4;
const LABEL_TOP_N = 10;

// 10-color community palette (matches the table chip colors)
const COMMUNITY_PALETTE = [
  "#3b82f6", "#8b5cf6", "#f59e0b", "#10b981", "#f43f5e",
  "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#14b8a6",
];

const DEFAULT_COLOR = (node: GraphNode) =>
  COMMUNITY_PALETTE[node.community_id % COMMUNITY_PALETTE.length];

export function NetworkGraph({
  nodes: rawNodes,
  edges: rawEdges,
  selected,
  onNodeClick,
  onNodeHover,
  width = DEFAULT_W,
  height = DEFAULT_H,
  colorForNode = DEFAULT_COLOR,
  screenOverlay,
  labels,
  className,
}: NetworkGraphProps) {
  const { nodes, edges, stable } = useForceLayout(rawNodes, rawEdges, width, height);

  const maxWeight = useMemo(
    () => Math.max(1, ...rawEdges.map((e) => e.weight)),
    [rawEdges],
  );

  const labelIds = useMemo(() => {
    const top = [...rawNodes]
      .sort((a, b) => b.centrality - a.centrality)
      .slice(0, LABEL_TOP_N)
      .map((n) => n.id);
    return new Set(top);
  }, [rawNodes]);

  // ── zoom + pan state
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ tx: 0, ty: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<{
    startX: number;
    startY: number;
    startTx: number;
    startTy: number;
    moved: boolean;
  } | null>(null);
  const nodeDragRef = useRef<{ node: PositionedNode } | null>(null);
  const justDraggedRef = useRef(false);

  const clamp = (z: number) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));
  const zoomBy = useCallback((factor: number) => {
    setZoom((prev) => {
      const next = clamp(prev * factor);
      if (next === 1 && Math.abs(pan.tx) < 1 && Math.abs(pan.ty) < 1) {
        setPan({ tx: 0, ty: 0 });
      }
      return next;
    });
  }, [pan.tx, pan.ty]);
  const handleZoomIn = useCallback(() => zoomBy(ZOOM_STEP), [zoomBy]);
  const handleZoomOut = useCallback(() => zoomBy(1 / ZOOM_STEP), [zoomBy]);
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

  // ── background pan
  const handlePointerDown = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      const target = e.target as Element;
      // Node drags are handled by the node's own pointerdown.
      if (target.closest("[data-node]")) return;
      if (e.button !== 0) return;
      dragRef.current = {
        startX: e.clientX,
        startY: e.clientY,
        startTx: pan.tx,
        startTy: pan.ty,
        moved: false,
      };
    },
    [pan.tx, pan.ty],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      const svg = svgRef.current;
      if (!svg) return;
      // Node drag in progress?
      const nd = nodeDragRef.current;
      if (nd) {
        const rect = svg.getBoundingClientRect();
        const sx = rect.width > 0 ? width / rect.width : 1;
        const sy = rect.height > 0 ? height / rect.height : 1;
        // Map client px → graph coords accounting for current pan/zoom.
        const gx = ((e.clientX - rect.left) * sx - pan.tx) / zoom;
        const gy = ((e.clientY - rect.top) * sy - pan.ty) / zoom;
        // Pin the node by setting fx/fy (d3-force convention).
        nd.node.fx = gx;
        nd.node.fy = gy;
        // Mutate visible coords too so the SVG re-render reflects the drag
        // even while the simulation has settled.
        nd.node.x = gx;
        nd.node.y = gy;
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
      const rect = svg.getBoundingClientRect();
      const sx = rect.width > 0 ? width / rect.width : 1;
      const sy = rect.height > 0 ? height / rect.height : 1;
      setPan({
        tx: drag.startTx + dx * sx,
        ty: drag.startTy + dy * sy,
      });
    },
    [pan.tx, pan.ty, zoom, width, height],
  );

  const handlePointerUp = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      const nd = nodeDragRef.current;
      if (nd) {
        nodeDragRef.current = null;
        // Release the pin so the simulation can pick it up again.
        nd.node.fx = null;
        nd.node.fy = null;
      }
      const wasDragging = !!dragRef.current?.moved;
      if (wasDragging) {
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
    },
    [],
  );

  // ── per-node drag start
  const onNodePointerDown = useCallback(
    (e: React.PointerEvent<SVGCircleElement>, node: PositionedNode) => {
      e.stopPropagation();
      if (e.button !== 0) return;
      nodeDragRef.current = { node };
    },
    [],
  );

  const transform = `translate(${pan.tx} ${pan.ty}) scale(${zoom})`;

  return (
    <div className={`relative ${className ?? "h-[520px]"}`}>
      <div
        data-testid="graph-zoom-controls"
        className="absolute right-3 top-3 z-10 flex flex-col gap-1 rounded-lg border border-gray-200 bg-white/90 p-1 shadow-sm backdrop-blur-sm dark:border-gray-700 dark:bg-gray-900/90"
      >
        <button
          type="button"
          onClick={handleZoomIn}
          disabled={zoom >= ZOOM_MAX}
          aria-label={labels?.zoomIn ?? "Zoom in"}
          className="flex h-7 w-7 items-center justify-center rounded text-base font-bold text-gray-700 hover:bg-gray-100 disabled:opacity-40 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          +
        </button>
        <div className="select-none text-center text-[9px] font-mono text-gray-500 dark:text-gray-400">
          {zoom.toFixed(1)}×
        </div>
        <button
          type="button"
          onClick={handleZoomOut}
          disabled={zoom <= ZOOM_MIN}
          aria-label={labels?.zoomOut ?? "Zoom out"}
          className="flex h-7 w-7 items-center justify-center rounded text-base font-bold text-gray-700 hover:bg-gray-100 disabled:opacity-40 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          −
        </button>
        {(zoom !== 1 || pan.tx !== 0 || pan.ty !== 0) && (
          <button
            type="button"
            onClick={handleZoomReset}
            aria-label={labels?.zoomReset ?? "Reset zoom"}
            className="flex h-7 w-7 items-center justify-center rounded text-xs font-semibold text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-800"
          >
            ⟲
          </button>
        )}
      </div>

      {!stable && nodes.length > 0 && (
        <div className="absolute left-3 top-3 z-10 rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-mono text-gray-500 shadow-sm backdrop-blur-sm dark:bg-gray-900/80 dark:text-gray-400">
          relaxing…
        </div>
      )}

      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        className={`h-full w-full select-none touch-none rounded-lg border border-gray-100 bg-slate-50 dark:border-gray-800 dark:bg-slate-950 ${
          isPanning ? "cursor-grabbing" : "cursor-grab"
        }`}
        preserveAspectRatio="xMidYMid meet"
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <g transform={transform}>
          {/* Edges */}
          {edges.map((e, i) => {
            const sx = e.source.x ?? 0;
            const sy = e.source.y ?? 0;
            const tx = e.target.x ?? 0;
            const ty = e.target.y ?? 0;
            const w = Math.max(0.6, (e.weight / maxWeight) * 3);
            const isSel =
              selected != null &&
              (e.source.id === selected || e.target.id === selected);
            return (
              <line
                key={`e-${i}`}
                x1={sx}
                y1={sy}
                x2={tx}
                y2={ty}
                stroke={isSel ? "rgba(37, 99, 235, 0.8)" : "rgba(100, 116, 139, 0.35)"}
                strokeWidth={isSel ? w + 0.6 : w}
              />
            );
          })}

          {/* Nodes */}
          {nodes.map((n) => {
            const isSel = selected === n.id;
            const fill = colorForNode(n);
            return (
              <g
                key={n.id}
                data-node={n.id}
                transform={`translate(${n.x ?? 0} ${n.y ?? 0})`}
              >
                {isSel && (
                  <circle
                    r={n.radius + 5}
                    fill="none"
                    stroke="#2563eb"
                    strokeWidth={2}
                  />
                )}
                <circle
                  r={n.radius}
                  fill={fill}
                  fillOpacity={isSel ? 1 : 0.85}
                  stroke="#fff"
                  strokeWidth={1.2}
                  className="cursor-pointer"
                  onPointerDown={(e) => onNodePointerDown(e, n)}
                  onClick={() => {
                    if (justDraggedRef.current) return;
                    if (nodeDragRef.current) return;
                    if (onNodeClick) onNodeClick(n.id);
                  }}
                  onMouseEnter={(e) => {
                    if (!onNodeHover) return;
                    const svg = svgRef.current;
                    if (!svg) return;
                    const rect = svg.getBoundingClientRect();
                    const x =
                      rect.width > 0
                        ? ((e.clientX - rect.left) / rect.width) * width
                        : 0;
                    const y =
                      rect.height > 0
                        ? ((e.clientY - rect.top) / rect.height) * height
                        : 0;
                    onNodeHover({ id: n.id, x, y });
                  }}
                  onMouseLeave={() => onNodeHover?.(null)}
                />
                {(isSel || labelIds.has(n.id)) && (
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
                    {n.label.length > 28
                      ? `${n.label.slice(0, 28)}…`
                      : n.label}
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
