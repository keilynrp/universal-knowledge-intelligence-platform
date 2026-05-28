"use client";

import { useEffect, useMemo, useState } from "react";
import { geoEquirectangular, geoMercator, geoNaturalEarth1, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import type { MapProjection } from "../../types/geo";
import { ISO_NUM_TO_ALPHA2 } from "./isoNumericToAlpha2";

/**
 * Lazy-fetched + memoized projection of the Natural Earth countries atlas.
 *
 * The atlas (~80 KB gz) is imported via the `world-atlas` npm package and
 * webpack splits it into its own chunk, so it only ships to pages that
 * import this hook (or anything that imports WorldMap).
 *
 * Re-projection only happens when `width`, `height`, or `projection` changes,
 * not on every render of the parent.
 */
export interface ProjectedCountry {
  iso: string;          // ISO alpha-2 (or "" if unmapped)
  name: string;         // English display name from atlas properties
  d: string;            // SVG path "d" attribute
  /** Projected centroid in SVG (viewBox) coordinates — for label placement. */
  cx: number;
  cy: number;
}

interface WorldGeographiesResult {
  countries: ProjectedCountry[];
  loaded: boolean;
  error: string | null;
}

function projector(name: MapProjection) {
  switch (name) {
    case "mercator":
      return geoMercator();
    case "naturalEarth1":
      return geoNaturalEarth1();
    case "equirectangular":
    default:
      return geoEquirectangular();
  }
}

export function useWorldGeographies(
  width: number,
  height: number,
  projection: MapProjection = "equirectangular",
): WorldGeographiesResult {
  const [topology, setTopology] = useState<unknown | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Lazy chunk — only loaded when this hook is reached.
        const atlas = await import(
          /* webpackChunkName: "world-atlas-110m" */ "world-atlas/countries-110m.json"
        );
        if (!cancelled) setTopology(atlas.default ?? atlas);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load atlas");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const countries = useMemo<ProjectedCountry[]>(() => {
    if (!topology) return [];
    // topojson-client typing is permissive; cast through unknown.
    const t = topology as Parameters<typeof feature>[0];
    const fc = feature(t, t.objects.countries) as FeatureCollection<
      Geometry,
      { name?: string }
    >;
    const proj = projector(projection).fitSize([width, height], fc);
    const pathGen = geoPath(proj);

    const result: ProjectedCountry[] = [];
    for (const f of fc.features as Feature<Geometry, { name?: string }>[]) {
      const numericId = String(f.id ?? "");
      const iso = ISO_NUM_TO_ALPHA2[numericId] ?? "";
      const d = pathGen(f) ?? "";
      if (!d) continue;
      const [cx, cy] = pathGen.centroid(f);
      result.push({
        iso,
        name: f.properties?.name ?? iso ?? "Unknown",
        d,
        cx: Number.isFinite(cx) ? cx : 0,
        cy: Number.isFinite(cy) ? cy : 0,
      });
    }
    return result;
  }, [topology, width, height, projection]);

  return { countries, loaded: !!topology, error };
}
