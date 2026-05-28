"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { CountryDatum, MapProjection } from "../../types/geo";
import { flagEmoji } from "../../analytics/geographic/countryMeta";
import { useWorldGeographies } from "./useWorldGeographies";

const LABEL_TOP_N = 15;

/**
 * Reusable choropleth world map for UKIP.
 *
 * Renders:
 * - true country polygons (lazy-loaded from world-atlas)
 * - configurable projection
 * - choropleth fill based on `data` + `colorScale`
 * - manual zoom (+/− buttons, mouse wheel) and drag-to-pan with grab cursor
 * - selection-driven auto-zoom that composes with manual zoom
 *
 * Higher-level overlays (markers, tooltips, legends) are passed via
 * `overlayChildren` so consumers can layer their own visuals while reusing
 * the geometry and interactions.
 */
export interface WorldMapProps {
  data: CountryDatum[];
  selected?: string | null;
  onCountryClick?: (code: string) => void;
  onCountryHover?: (info: { code: string; x: number; y: number } | null) => void;
  projection?: MapProjection;
  /** SVG viewBox dimensions. Defaults to 1000×500 (equirectangular). */
  width?: number;
  height?: number;
  /** Fill color resolver. Receives the datum (or null for unmatched countries). */
  colorFor?: (datum: CountryDatum | null) => string;
  /** Slot for overlays in the projected coordinate system (inside the zoom <g>). */
  overlayChildren?: ReactNode;
  /** Slot for overlays in screen coordinates (outside the SVG). */
  screenOverlay?: ReactNode;
  /** Labels for accessibility / i18n. */
  labels?: {
    zoomIn?: string;
    zoomOut?: string;
    zoomReset?: string;
  };
  className?: string;
}

const DEFAULT_W = 1000;
const DEFAULT_H = 500;
const SELECTION_ZOOM = 3;
const ZOOM_MIN = 1;
const ZOOM_MAX = 8;
const ZOOM_STEP = 1.4;

const DEFAULT_COLOR = (datum: CountryDatum | null) => {
  if (!datum) return "rgba(148, 163, 184, 0.18)"; // slate-400/18
  const v = Math.min(1, Math.sqrt(datum.entity_count) / 20);
  // Interpolate blue-50 → blue-700
  const r = Math.round(239 - v * 210);
  const g = Math.round(246 - v * 173);
  const b = Math.round(255 - v * 80);
  return `rgb(${r}, ${g}, ${b})`;
};

export function WorldMap({
  data,
  selected,
  onCountryClick,
  onCountryHover,
  projection = "equirectangular",
  width = DEFAULT_W,
  height = DEFAULT_H,
  colorFor = DEFAULT_COLOR,
  overlayChildren,
  screenOverlay,
  labels,
  className,
}: WorldMapProps) {
  const { countries, loaded } = useWorldGeographies(width, height, projection);

  // ── data lookup
  const byCode = useMemo(() => {
    const m = new Map<string, CountryDatum>();
    for (const d of data) m.set(d.country_code, d);
    return m;
  }, [data]);

  // Top-N countries that should always get a flag label on the map.
  const labelCodes = useMemo(() => {
    const top = [...data]
      .filter((d) => d.country_code !== "OTHER")
      .sort((a, b) => b.entity_count - a.entity_count)
      .slice(0, LABEL_TOP_N)
      .map((d) => d.country_code);
    return new Set(top);
  }, [data]);

  // ── zoom + pan state
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ tx: 0, ty: 0 });
  const [manualOverride, setManualOverride] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<{
    startX: number;
    startY: number;
    startTx: number;
    startTy: number;
    moved: boolean;
  } | null>(null);
  // Set on pointerup when the gesture WAS a drag (moved > threshold). Cleared
  // on the next microtask, after the trailing click event has been suppressed.
  const justDraggedRef = useRef<boolean>(false);

  // ── selection-based centroid (when manual override is off)
  const selectionTransform = useMemo(() => {
    if (manualOverride) return null;
    if (!selected) return null;
    const country = countries.find((c) => c.iso === selected);
    if (!country) return null;
    // Approximate centroid via path bounding box midpoint — d3 geoPath could
    // also compute it precisely, but we already have the `d` string and bbox
    // requires DOM measurement. So we re-derive from existing data lookup.
    const m = country.d.match(/M\s*([-0-9.]+)[ ,]+([-0-9.]+)/);
    if (!m) return null;
    const x = parseFloat(m[1]);
    const y = parseFloat(m[2]);
    return {
      tx: width / 2 - x * SELECTION_ZOOM,
      ty: height / 2 - y * SELECTION_ZOOM,
      scale: SELECTION_ZOOM,
    };
  }, [manualOverride, selected, countries, width, height]);

  const transform = useMemo(() => {
    if (manualOverride) return `translate(${pan.tx} ${pan.ty}) scale(${zoom})`;
    if (selectionTransform) {
      return `translate(${selectionTransform.tx} ${selectionTransform.ty}) scale(${selectionTransform.scale})`;
    }
    return "translate(0 0) scale(1)";
  }, [manualOverride, pan.tx, pan.ty, zoom, selectionTransform]);

  const effectiveZoom = manualOverride
    ? zoom
    : selectionTransform
      ? selectionTransform.scale
      : 1;

  // ── zoom handlers
  const clamp = (z: number) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));
  const zoomBy = useCallback((factor: number) => {
    setZoom((prev) => {
      const next = clamp(prev * factor);
      if (next === ZOOM_MIN) {
        setManualOverride(false);
        setPan({ tx: 0, ty: 0 });
        return 1;
      }
      setManualOverride(true);
      return next;
    });
  }, []);
  const handleZoomIn = useCallback(() => zoomBy(ZOOM_STEP), [zoomBy]);
  const handleZoomOut = useCallback(() => zoomBy(1 / ZOOM_STEP), [zoomBy]);
  const handleZoomReset = useCallback(() => {
    setZoom(1);
    setPan({ tx: 0, ty: 0 });
    setManualOverride(false);
  }, []);

  const handleWheel = useCallback(
    (e: React.WheelEvent<SVGSVGElement>) => {
      e.preventDefault();
      zoomBy(e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP);
    },
    [zoomBy],
  );

  // ── drag-to-pan
  //
  // IMPORTANT: do NOT call preventDefault or setPointerCapture on pointerdown.
  // Both would cancel the subsequent `click` event on country <path>s and
  // break selection. We only "promote" the gesture to a real drag after the
  // pointer has moved past the 3px threshold inside pointermove.
  const handlePointerDown = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      const target = e.target as Element;
      if (target.closest("[data-marker]")) return;
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

  const handlePointerMove = useCallback((e: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    const svg = svgRef.current;
    if (!drag || !svg) return;
    const dx = e.clientX - drag.startX;
    const dy = e.clientY - drag.startY;
    if (!drag.moved && Math.abs(dx) + Math.abs(dy) < 3) return;
    if (!drag.moved) {
      drag.moved = true;
      setIsPanning(true);
      setManualOverride(true);
      // NOW it is a real drag — capture so we still get pointermove/up
      // even if the pointer leaves the SVG.
      try {
        svg.setPointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
    }
    e.preventDefault();
    const rect = svg.getBoundingClientRect();
    const sx = rect.width > 0 ? DEFAULT_W / rect.width : 1;
    const sy = rect.height > 0 ? DEFAULT_H / rect.height : 1;
    setPan({
      tx: drag.startTx + dx * sx,
      ty: drag.startTy + dy * sy,
    });
  }, []);

  const handlePointerUp = useCallback((e: React.PointerEvent<SVGSVGElement>) => {
    const wasDragging = !!dragRef.current?.moved;
    if (wasDragging) {
      try {
        svgRef.current?.releasePointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
      justDraggedRef.current = true;
      // Click event fires AFTER pointerup synchronously, so a microtask is
      // enough to outlive that click without affecting later clicks.
      queueMicrotask(() => {
        justDraggedRef.current = false;
      });
    }
    dragRef.current = null;
    setIsPanning(false);
  }, []);

  return (
    <div className={`relative ${className ?? "h-[420px]"}`}>
      {/* Zoom controls */}
      <div
        data-testid="map-zoom-controls"
        className="absolute right-3 top-3 z-10 flex flex-col gap-1 rounded-lg border border-gray-200 bg-white/90 p-1 shadow-sm backdrop-blur-sm dark:border-gray-700 dark:bg-gray-900/90"
      >
        <button
          type="button"
          onClick={handleZoomIn}
          disabled={effectiveZoom >= ZOOM_MAX}
          aria-label={labels?.zoomIn ?? "Zoom in"}
          title={labels?.zoomIn ?? "Zoom in"}
          className="flex h-7 w-7 items-center justify-center rounded text-base font-bold text-gray-700 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          +
        </button>
        <div
          aria-label="zoom level"
          className="select-none text-center text-[9px] font-mono text-gray-500 dark:text-gray-400"
        >
          {effectiveZoom.toFixed(1)}×
        </div>
        <button
          type="button"
          onClick={handleZoomOut}
          disabled={effectiveZoom <= ZOOM_MIN}
          aria-label={labels?.zoomOut ?? "Zoom out"}
          title={labels?.zoomOut ?? "Zoom out"}
          className="flex h-7 w-7 items-center justify-center rounded text-base font-bold text-gray-700 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          −
        </button>
        {(manualOverride || selected) && (
          <button
            type="button"
            onClick={handleZoomReset}
            aria-label={labels?.zoomReset ?? "Reset zoom"}
            title={labels?.zoomReset ?? "Reset zoom"}
            className="flex h-7 w-7 items-center justify-center rounded text-xs font-semibold text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-800"
          >
            ⟲
          </button>
        )}
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        className={`h-full w-full select-none touch-none ${
          isPanning ? "cursor-grabbing" : "cursor-grab"
        }`}
        preserveAspectRatio="xMidYMid meet"
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <g
          style={{
            transition: isPanning
              ? "none"
              : "transform 700ms cubic-bezier(0.22,1,0.36,1)",
          }}
          transform={transform}
        >
          {/* Background ocean */}
          <rect width={width} height={height} fill="rgba(59,130,246,0.04)" />

          {/* Country polygons */}
          {loaded &&
            countries.map((c) => {
              const datum = c.iso ? byCode.get(c.iso) ?? null : null;
              const isSel = !!c.iso && selected === c.iso;
              return (
                <path
                  key={`${c.iso || c.name}-${c.d.length}`}
                  data-iso={c.iso || undefined}
                  data-name={c.name}
                  d={c.d}
                  fill={isSel ? "rgb(37, 99, 235)" : colorFor(datum)}
                  fillOpacity={isSel ? 0.9 : 1}
                  stroke="rgba(15, 23, 42, 0.35)"
                  strokeWidth={isSel ? 1.2 : 0.4}
                  className={c.iso ? "cursor-pointer" : ""}
                  onClick={() => {
                    if (!justDraggedRef.current && c.iso && onCountryClick) {
                      onCountryClick(c.iso);
                    }
                  }}
                  onMouseEnter={(e) => {
                    if (c.iso && onCountryHover) {
                      // Get pointer position in viewBox coordinates.
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
                      onCountryHover({ code: c.iso, x, y });
                    }
                  }}
                  onMouseLeave={() => onCountryHover?.(null)}
                />
              );
            })}

          {/* Flag labels — for top-N countries plus the selected one. */}
          {loaded &&
            countries.map((c) => {
              if (!c.iso || c.iso === "OTHER") return null;
              const isSel = selected === c.iso;
              if (!isSel && !labelCodes.has(c.iso)) return null;
              if (!Number.isFinite(c.cx) || !Number.isFinite(c.cy)) return null;
              // Counter-scale text so it stays legible while zoomed in.
              const scaleInv = 1 / Math.max(zoom, 1);
              return (
                <g
                  key={`label-${c.iso}`}
                  transform={`translate(${c.cx} ${c.cy}) scale(${scaleInv})`}
                  pointerEvents="none"
                >
                  <text
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize={isSel ? 14 : 11}
                    fontWeight={isSel ? 700 : 600}
                    className="fill-slate-900 dark:fill-slate-100"
                    paintOrder="stroke"
                    stroke="rgba(255,255,255,0.85)"
                    strokeWidth={3}
                    strokeLinejoin="round"
                  >
                    {flagEmoji(c.iso)} {c.iso}
                  </text>
                </g>
              );
            })}

          {!loaded && (
            <text
              x={width / 2}
              y={height / 2}
              textAnchor="middle"
              className="fill-slate-500 text-xs"
            >
              Loading map…
            </text>
          )}

          {overlayChildren}
        </g>
      </svg>

      {screenOverlay}
    </div>
  );
}

export default WorldMap;
