// Shared community color palette for the coauthorship graph (GraphDB/Neo4j look).
// OKLCH gives perceptually-even hues with consistent lightness/chroma, so no
// single community visually dominates. Indexed by community_id % length.

export const COMMUNITY_OKLCH = [
  "oklch(62% 0.20 264)", // indigo
  "oklch(64% 0.20 305)", // violet
  "oklch(72% 0.17 75)",  // amber
  "oklch(66% 0.17 155)", // emerald
  "oklch(63% 0.22 18)",  // rose
  "oklch(68% 0.15 220)", // cyan
  "oklch(67% 0.19 45)",  // orange
  "oklch(70% 0.18 130)", // lime
  "oklch(65% 0.20 348)", // pink
  "oklch(66% 0.14 190)", // teal
] as const;

export function communityColor(communityId: number): string {
  const idx = ((communityId % COMMUNITY_OKLCH.length) + COMMUNITY_OKLCH.length) % COMMUNITY_OKLCH.length;
  return COMMUNITY_OKLCH[idx];
}

/** Node radius from publication count: gentle sqrt growth, clamped. */
export function nodeRadius(publicationCount: number): number {
  return Math.min(28, Math.sqrt(Math.max(0, publicationCount)) * 2 + 6);
}
