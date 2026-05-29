// Shared graph types — reusable across UKIP analytics modules
// (coauthorship, citations, concept maps, etc.)

export interface GraphNode {
  id: string;
  label: string;
  /** Number of neighbors. */
  degree: number;
  /** Normalized degree centrality [0,1]. */
  centrality: number;
  /** Cluster / community membership index. */
  community_id: number;
  /** Publication count — drives node radius in the coauthorship graph. */
  total_publications?: number;
  /** Optional secondary scalar (publication count, citation impact, …). */
  weight?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  /** Edge strength — drives line thickness in the visualisation. */
  weight: number;
}

export interface GraphHoverInfo {
  id: string;
  x: number;
  y: number;
}
