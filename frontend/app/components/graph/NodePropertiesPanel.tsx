"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { communityColor } from "./palette";

interface AuthorDetail {
  author_id: number;
  display_name: string;
  orcid: string | null;
  aliases: string[];
  metrics: {
    degree: number;
    centrality: number;
    community_id: number | null;
    publication_count: number;
  };
  publications: { entity_id: number; title: string; year: number | null }[];
  collaborators: { author_id: number; name: string | null; weight: number }[];
}

interface NodePropertiesPanelProps {
  domainId: string;
  authorId: string | null;
  onClose: () => void;
  onSelectCollaborator?: (authorId: string) => void;
}

/**
 * GraphDB/Neo4j-style properties side panel. Fetches the selected author's
 * detail and renders identity header, metric grid, aliases, collaborators, and
 * publications. Empty when no node is selected.
 */
export function NodePropertiesPanel({
  domainId,
  authorId,
  onClose,
  onSelectCollaborator,
}: NodePropertiesPanelProps) {
  const [detail, setDetail] = useState<AuthorDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authorId) {
      setDetail(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiFetch(`/analyzers/coauthorship/${domainId}/author/${authorId}`)
      .then(async (r) => {
        if (!r.ok) throw new Error(`Server responded with ${r.status}`);
        const body = (await r.json()) as AuthorDetail;
        if (!cancelled) setDetail(body);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load author");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [domainId, authorId]);

  if (!authorId) {
    return (
      <div
        className="flex h-full min-h-[420px] flex-col items-center justify-center p-6 text-center"
        data-testid="node-panel-empty"
      >
        <div className="text-4xl">🕸️</div>
        <p className="mt-3 text-sm font-medium text-gray-700 dark:text-gray-200">Pick an author</p>
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Click a node in the graph to inspect their collaborators and publications.
        </p>
      </div>
    );
  }

  const color = detail ? communityColor(detail.metrics.community_id ?? 0) : "oklch(60% 0 0)";

  return (
    <div
      className="flex h-full min-h-[420px] flex-col"
      aria-live="polite"
      data-testid="node-panel"
    >
      <div className="flex items-start justify-between border-b border-gray-100 px-5 py-4 dark:border-gray-800">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span
              className="inline-block h-3 w-3 shrink-0 rounded-full"
              style={{ background: color }}
            />
            <h3 className="truncate text-base font-semibold text-gray-900 dark:text-white">
              {detail?.display_name ?? "…"}
            </h3>
          </div>
          {detail?.orcid && (
            <a
              href={`https://orcid.org/${detail.orcid}`}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 inline-flex items-center gap-1 rounded bg-lime-100 px-1.5 py-0.5 text-[10px] font-medium text-lime-700 hover:underline dark:bg-lime-900/30 dark:text-lime-300"
            >
              ORCID {detail.orcid}
            </a>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
          aria-label="Close panel"
        >
          ✕
        </button>
      </div>

      {loading && (
        <div className="flex-1 animate-pulse space-y-3 p-5">
          <div className="h-16 rounded bg-gray-100 dark:bg-gray-800" />
          <div className="h-24 rounded bg-gray-100 dark:bg-gray-800" />
          <div className="h-24 rounded bg-gray-100 dark:bg-gray-800" />
        </div>
      )}

      {!loading && error && (
        <p className="p-5 text-sm text-rose-600 dark:text-rose-400">{error}</p>
      )}

      {!loading && !error && detail && (
        <div className="flex-1 overflow-y-auto">
          <div className="grid grid-cols-2 gap-3 px-5 py-4">
            <Metric label="Publications" value={detail.metrics.publication_count} />
            <Metric label="Degree" value={detail.metrics.degree} />
            <Metric label="Centrality" value={detail.metrics.centrality.toFixed(3)} />
            <Metric
              label="Community"
              value={detail.metrics.community_id != null ? `C${detail.metrics.community_id}` : "—"}
            />
          </div>

          {detail.aliases.length > 1 && (
            <details className="px-5 pb-3">
              <summary className="cursor-pointer text-[11px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
                Aliases ({detail.aliases.length})
              </summary>
              <ul className="mt-2 flex flex-wrap gap-1">
                {detail.aliases.map((a) => (
                  <li
                    key={a}
                    className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                  >
                    {a}
                  </li>
                ))}
              </ul>
            </details>
          )}

          <Section title={`Top collaborators (${detail.collaborators.length})`}>
            {detail.collaborators.length === 0 ? (
              <p className="text-xs text-gray-500 dark:text-gray-400">No collaborators in scope.</p>
            ) : (
              <ul className="space-y-1">
                {detail.collaborators.map((c) => (
                  <li
                    key={c.author_id}
                    className="flex items-center justify-between rounded px-2 py-1.5 text-sm text-gray-800 hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-gray-800/40"
                  >
                    <button
                      type="button"
                      onClick={() => onSelectCollaborator?.(String(c.author_id))}
                      className="truncate text-left hover:underline"
                    >
                      {c.name ?? `Author ${c.author_id}`}
                    </button>
                    <span className="ml-2 shrink-0 rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-medium text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
                      {c.weight}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title={`Publications (${detail.publications.length})`}>
            {detail.publications.length === 0 ? (
              <p className="text-xs text-gray-500 dark:text-gray-400">No publications in scope.</p>
            ) : (
              <ul className="space-y-1">
                {detail.publications.map((p) => (
                  <li key={p.entity_id} className="flex items-baseline justify-between gap-2 px-2 py-1 text-sm">
                    <span className="truncate text-gray-800 dark:text-gray-200">{p.title}</span>
                    {p.year != null && (
                      <span className="shrink-0 font-mono text-[11px] text-gray-500 dark:text-gray-400">
                        {p.year}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-gray-400">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-gray-900 dark:text-white">{value}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="px-5 pb-5">
      <p className="mb-2 text-[11px] uppercase tracking-wider text-gray-500 dark:text-gray-400">{title}</p>
      {children}
    </div>
  );
}

export default NodePropertiesPanel;
