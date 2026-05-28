// Shared geographic types — consumed by WorldMap and any UKIP module
// that needs to render or interact with country-level data.

export interface CountryDatum {
  /** ISO 3166-1 alpha-2 (e.g., "US", "CN") */
  country_code: string;
  country_name: string;
  entity_count: number;
  citation_sum: number;
  percentage: number;
}

export interface WorldMapHoverInfo {
  code: string;
  x: number;
  y: number;
}

/** Projection name accepted by WorldMap. */
export type MapProjection = "equirectangular" | "mercator" | "naturalEarth1";
