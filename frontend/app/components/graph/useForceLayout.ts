"use client";

import { useEffect, useMemo, useState } from "react";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationNodeDatum,
} from "d3-force";
import type { GraphEdge, GraphNode } from "../../types/graph";

export interface PositionedNode extends SimulationNodeDatum, GraphNode {
  radius: number;
}

export interface PositionedEdge {
  source: PositionedNode;
  target: PositionedNode;
  weight: number;
}

interface ForceLayoutResult {
  nodes: PositionedNode[];
  edges: PositionedEdge[];
  /** True once the simulation has cooled enough to be stable-looking. */
  stable: boolean;
  /** Re-run the simulation from a fresh state. */
  restart: () => void;
}

/**
 * Runs a d3-force simulation against the given nodes + edges and returns
 * positioned nodes whose `(x, y)` are stable inside the [0, width] × [0, height]
 * viewBox. Re-runs whenever the dataset or dimensions change.
 *
 * Cost: O(N + E) per tick, ~300 ticks to settle. For N<200 (UKIP coauthor
 * graphs at limit=100) this takes ~80ms once, then is essentially free until
 * the data changes.
 */
export function useForceLayout(
  rawNodes: GraphNode[],
  rawEdges: GraphEdge[],
  width: number,
  height: number,
): ForceLayoutResult {
  // Compute initial node positions and edge references freshly whenever the
  // shape of the data changes. The simulation mutates `x/y` on each node
  // in place; `version` is bumped per tick so React re-renders.
  const [version, setVersion] = useState(0);
  const [stable, setStable] = useState(false);

  // Rebuild positioned arrays whenever the source data identity changes.
  const { positionedNodes, positionedEdges } = useMemo(() => {
    const map = new Map<string, PositionedNode>();
    const nodes = rawNodes.map<PositionedNode>((n) => {
      // Radius reflects publication count (GraphDB look); fall back to degree.
      const scalar = n.total_publications ?? n.degree;
      const radius = Math.min(28, 6 + Math.sqrt(Math.max(0, scalar)) * 2);
      // Seed positions in a circle around the center so the simulation
      // doesn't start from (0,0) and collapse on itself.
      const angle =
        (Array.from(map.keys()).length / Math.max(1, rawNodes.length)) *
        Math.PI *
        2;
      const r = Math.min(width, height) * 0.35;
      const node: PositionedNode = {
        ...n,
        radius,
        x: width / 2 + Math.cos(angle) * r,
        y: height / 2 + Math.sin(angle) * r,
      };
      map.set(n.id, node);
      return node;
    });
    const edges = rawEdges
      .map<PositionedEdge | null>((e) => {
        const source = map.get(e.source);
        const target = map.get(e.target);
        if (!source || !target) return null;
        return { source, target, weight: e.weight };
      })
      .filter((e): e is PositionedEdge => e !== null);
    return { positionedNodes: nodes, positionedEdges: edges };
  }, [rawNodes, rawEdges, width, height]);

  useEffect(() => {
    let cancelled = false;
    const rafRef = { current: 0 };

    if (positionedNodes.length === 0) {
      // Defer the setState so we don't call it synchronously in the effect.
      rafRef.current = requestAnimationFrame(() => {
        if (!cancelled) setStable(true);
      });
      return () => {
        cancelled = true;
        cancelAnimationFrame(rafRef.current);
      };
    }

    const maxWeight = Math.max(1, ...positionedEdges.map((e) => e.weight));
    const sim = forceSimulation<PositionedNode>(positionedNodes)
      .force(
        "link",
        forceLink<PositionedNode, PositionedEdge>(positionedEdges)
          .id((d) => d.id)
          .distance((e) => 50 + 80 * (1 - e.weight / maxWeight))
          .strength(0.4),
      )
      .force("charge", forceManyBody().strength(-180).distanceMax(420))
      .force("center", forceCenter(width / 2, height / 2).strength(0.06))
      .force(
        "collide",
        forceCollide<PositionedNode>((d) => d.radius + 4).iterations(2),
      )
      .alphaDecay(0.04)
      .stop();

    // Reset stability from inside the rAF loop (i.e., outside the effect body).
    let ticks = 0;
    const maxTicks = 320;
    const step = () => {
      if (cancelled) return;
      if (ticks === 0) setStable(false);
      sim.tick();
      ticks += 1;
      setVersion((v) => v + 1);
      if (ticks < maxTicks && sim.alpha() > 0.012) {
        rafRef.current = requestAnimationFrame(step);
      } else {
        setStable(true);
      }
    };
    rafRef.current = requestAnimationFrame(step);

    return () => {
      cancelled = true;
      cancelAnimationFrame(rafRef.current);
      sim.stop();
    };
  }, [positionedNodes, positionedEdges, width, height]);

  // Touch `version` so React re-renders as positions update; the array
  // identities themselves don't change between ticks.
  void version;

  return {
    nodes: positionedNodes,
    edges: positionedEdges,
    stable,
    restart: () => setVersion((v) => v + 1),
  };
}
