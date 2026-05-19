"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useDomain } from "../../contexts/DomainContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { useAuth } from "../../contexts/AuthContext";
import { apiFetch } from "@/lib/api";
import { useToast } from "../../components/ui/Toast";

// ── Types ────────────────────────────────────────────────────────────────────

interface ConceptNode {
  id: number;
  name: string;
  level: number;
  entity_count: number;
  openalex_id: string;
  children: ConceptNode[];
}

interface TreeResponse {
  nodes: ConceptNode[];
  materialized_at: string | null;
}

// ── Tree Node Component ─────────────────────────────────────────────────────

function TreeNode({
  node,
  defaultExpanded,
  onClickConcept,
  t,
}: {
  node: ConceptNode;
  defaultExpanded: boolean;
  onClickConcept: (name: string) => void;
  t: (key: string) => string;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const hasChildren = node.children.length > 0;

  return (
    <div className="ml-2">
      <div className="group flex items-center gap-1.5 rounded-md px-2 py-1 transition-colors hover:bg-[var(--ukip-panel)]">
        {/* Expand/collapse toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          className={`flex h-5 w-5 shrink-0 items-center justify-center rounded text-xs transition-transform ${
            hasChildren
              ? "text-[var(--ukip-muted)] hover:text-[var(--ukip-text-strong)]"
              : "invisible"
          }`}
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          <svg
            className={`h-3.5 w-3.5 transition-transform duration-200 ${expanded ? "rotate-90" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>

        {/* Node name — clickable to filter entities */}
        <button
          onClick={() => onClickConcept(node.name)}
          className="truncate text-sm font-medium text-[var(--ukip-text)] hover:text-[var(--ukip-accent)] hover:underline"
          title={`${node.name} — ${t("concepts.level")} ${node.level}`}
        >
          {node.name}
        </button>

        {/* Entity count badge */}
        {node.entity_count > 0 && (
          <span className="ml-auto shrink-0 rounded-full bg-[var(--ukip-panel-strong)] px-2 py-0.5 text-[11px] font-semibold text-[var(--ukip-muted)]">
            {node.entity_count}
          </span>
        )}

        {/* Level indicator */}
        <span className="shrink-0 text-[10px] text-[var(--ukip-muted)] opacity-0 group-hover:opacity-100">
          L{node.level}
        </span>
      </div>

      {/* Children */}
      {expanded && hasChildren && (
        <div className="border-l border-[var(--ukip-border)] ml-2.5">
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              defaultExpanded={child.level < 2}
              onClickConcept={onClickConcept}
              t={t}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Sunburst Component ──────────────────────────────────────────────────────

function flattenForSunburst(nodes: ConceptNode[]): { name: string; level: number; count: number; parent: string }[] {
  const items: { name: string; level: number; count: number; parent: string }[] = [];

  function walk(node: ConceptNode, parentName: string) {
    items.push({
      name: node.name,
      level: node.level,
      count: Math.max(node.entity_count, 1),
      parent: parentName,
    });
    for (const child of node.children) {
      walk(child, node.name);
    }
  }

  for (const root of nodes) {
    walk(root, "");
  }
  return items;
}

const LEVEL_COLORS = [
  "var(--ukip-accent, #6366f1)",
  "#8b5cf6",
  "#a78bfa",
  "#c4b5fd",
  "#ddd6fe",
  "#ede9fe",
];

function SunburstView({
  nodes,
  onClickConcept,
  t,
}: {
  nodes: ConceptNode[];
  onClickConcept: (name: string) => void;
  t: (key: string) => string;
}) {
  const items = useMemo(() => flattenForSunburst(nodes), [nodes]);
  const [hovered, setHovered] = useState<string | null>(null);

  if (items.length === 0) return null;

  // Group by level for ring layout
  const byLevel: Record<number, typeof items> = {};
  for (const item of items) {
    (byLevel[item.level] ??= []).push(item);
  }
  const levels = Object.keys(byLevel).map(Number).sort();
  const maxLevel = Math.max(...levels);

  const size = 400;
  const cx = size / 2;
  const cy = size / 2;
  const minR = 40;
  const maxR = size / 2 - 10;
  const ringWidth = (maxR - minR) / (maxLevel + 1);

  return (
    <div className="flex flex-col items-center gap-4">
      <svg viewBox={`0 0 ${size} ${size}`} className="h-[400px] w-[400px]">
        {levels.map((level) => {
          const ring = byLevel[level];
          const totalCount = ring.reduce((s, r) => s + r.count, 0);
          let startAngle = 0;

          return ring.map((item) => {
            const sweep = (item.count / totalCount) * 360;
            const endAngle = startAngle + sweep;
            const innerR = minR + level * ringWidth;
            const outerR = innerR + ringWidth - 2;

            const a1 = ((startAngle - 90) * Math.PI) / 180;
            const a2 = ((endAngle - 90) * Math.PI) / 180;

            const x1 = cx + innerR * Math.cos(a1);
            const y1 = cy + innerR * Math.sin(a1);
            const x2 = cx + outerR * Math.cos(a1);
            const y2 = cy + outerR * Math.sin(a1);
            const x3 = cx + outerR * Math.cos(a2);
            const y3 = cy + outerR * Math.sin(a2);
            const x4 = cx + innerR * Math.cos(a2);
            const y4 = cy + innerR * Math.sin(a2);

            const large = sweep > 180 ? 1 : 0;

            const d = [
              `M ${x1} ${y1}`,
              `L ${x2} ${y2}`,
              `A ${outerR} ${outerR} 0 ${large} 1 ${x3} ${y3}`,
              `L ${x4} ${y4}`,
              `A ${innerR} ${innerR} 0 ${large} 0 ${x1} ${y1}`,
              "Z",
            ].join(" ");

            startAngle = endAngle;

            const isHovered = hovered === item.name;

            return (
              <path
                key={`${level}-${item.name}`}
                d={d}
                fill={LEVEL_COLORS[Math.min(level, LEVEL_COLORS.length - 1)]}
                stroke="var(--ukip-bg, #fff)"
                strokeWidth={1.5}
                opacity={isHovered ? 1 : 0.85}
                className="cursor-pointer transition-opacity duration-150"
                onMouseEnter={() => setHovered(item.name)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => onClickConcept(item.name)}
              >
                <title>
                  {item.name} — {t("concepts.level")} {item.level}, {item.count} {t("concepts.entities_count")}
                  {item.parent ? ` (${t("concepts.parent")}: ${item.parent})` : ` (${t("concepts.root")})`}
                </title>
              </path>
            );
          });
        })}
      </svg>

      {/* Hover legend */}
      {hovered && (
        <div className="rounded-lg border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-4 py-2 text-sm">
          <span className="font-semibold text-[var(--ukip-text-strong)]">{hovered}</span>
          {(() => {
            const item = items.find((i) => i.name === hovered);
            if (!item) return null;
            return (
              <span className="ml-2 text-[var(--ukip-muted)]">
                {t("concepts.level")} {item.level} &middot; {item.count} {t("concepts.entities_count")}
                {item.parent ? ` &middot; ${t("concepts.parent")}: ${item.parent}` : ""}
              </span>
            );
          })()}
        </div>
      )}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ConceptHierarchyPage() {
  const { activeDomain } = useDomain();
  const { t } = useLanguage();
  const { user } = useAuth();
  const { toast } = useToast();
  const router = useRouter();

  const [tree, setTree] = useState<TreeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [materializing, setMaterializing] = useState(false);
  const [view, setView] = useState<"tree" | "sunburst">("tree");

  const domainId = activeDomain?.id ?? "default";
  const isAdmin = user?.role === "super_admin" || user?.role === "admin";

  const fetchTree = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await apiFetch(`/analytics/concepts/${domainId}/tree`);
      if (resp.ok) {
        setTree(await resp.json());
      }
    } catch {
      /* network error */
    } finally {
      setLoading(false);
    }
  }, [domainId]);

  useEffect(() => {
    fetchTree();
  }, [fetchTree]);

  const handleMaterialize = async () => {
    setMaterializing(true);
    try {
      const resp = await apiFetch(`/analytics/concepts/${domainId}/materialize`, {
        method: "POST",
      });
      if (resp.ok) {
        toast(t("concepts.refresh_success"), "success");
        await fetchTree();
      } else {
        toast(t("concepts.refresh_error"), "error");
      }
    } catch {
      toast(t("concepts.refresh_error"), "error");
    } finally {
      setMaterializing(false);
    }
  };

  const handleClickConcept = (conceptName: string) => {
    router.push(`/entities?concept=${encodeURIComponent(conceptName)}`);
  };

  const isEmpty = !tree || tree.nodes.length === 0;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--ukip-text-strong)]">
            {t("concepts.title")}
          </h1>
          <p className="mt-1 text-sm text-[var(--ukip-muted)]">
            {t("concepts.subtitle")}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* View toggle */}
          {!isEmpty && (
            <div className="flex rounded-lg border border-[var(--ukip-border)] bg-[var(--ukip-panel)]">
              <button
                onClick={() => setView("tree")}
                className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                  view === "tree"
                    ? "bg-[var(--ukip-accent)] text-white rounded-l-lg"
                    : "text-[var(--ukip-muted)] hover:text-[var(--ukip-text)]"
                }`}
              >
                {t("concepts.tree_view")}
              </button>
              <button
                onClick={() => setView("sunburst")}
                className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                  view === "sunburst"
                    ? "bg-[var(--ukip-accent)] text-white rounded-r-lg"
                    : "text-[var(--ukip-muted)] hover:text-[var(--ukip-text)]"
                }`}
              >
                {t("concepts.sunburst_view")}
              </button>
            </div>
          )}

          {/* Admin refresh button */}
          {isAdmin && (
            <button
              onClick={handleMaterialize}
              disabled={materializing}
              className="rounded-lg bg-[var(--ukip-accent)] px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {materializing ? t("concepts.refreshing") : t("concepts.refresh")}
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-8 animate-pulse rounded-md bg-[var(--ukip-panel)]" />
          ))}
        </div>
      ) : isEmpty ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--ukip-border)] bg-[var(--ukip-panel)] py-16">
          <svg className="mb-4 h-12 w-12 text-[var(--ukip-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.25 6.75h12M8.25 12h12M8.25 17.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
          </svg>
          <h3 className="text-lg font-semibold text-[var(--ukip-text-strong)]">
            {t("concepts.empty_title")}
          </h3>
          <p className="mt-1 max-w-sm text-center text-sm text-[var(--ukip-muted)]">
            {t("concepts.empty_description")}
          </p>
          {isAdmin && (
            <button
              onClick={handleMaterialize}
              disabled={materializing}
              className="mt-6 rounded-lg bg-[var(--ukip-accent)] px-5 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {materializing ? t("concepts.refreshing") : t("concepts.refresh")}
            </button>
          )}
        </div>
      ) : view === "tree" ? (
        <div className="rounded-xl border border-[var(--ukip-border)] bg-[var(--ukip-bg)] p-4">
          {tree!.nodes.map((node) => (
            <TreeNode
              key={node.id}
              node={node}
              defaultExpanded={node.level < 2}
              onClickConcept={handleClickConcept}
              t={t}
            />
          ))}
          {tree!.materialized_at && (
            <p className="mt-4 text-xs text-[var(--ukip-muted)]">
              Last materialized: {new Date(tree!.materialized_at).toLocaleString()}
            </p>
          )}
        </div>
      ) : (
        <div className="rounded-xl border border-[var(--ukip-border)] bg-[var(--ukip-bg)] p-6">
          <SunburstView
            nodes={tree!.nodes}
            onClickConcept={handleClickConcept}
            t={t}
          />
          {tree!.materialized_at && (
            <p className="mt-4 text-center text-xs text-[var(--ukip-muted)]">
              Last materialized: {new Date(tree!.materialized_at).toLocaleString()}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
