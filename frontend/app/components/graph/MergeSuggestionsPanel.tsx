"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface MergeSuggestion {
  id: number;
  author_a_id: number;
  author_a_name: string | null;
  author_b_id: number;
  author_b_name: string | null;
  reason: string | null;
  status: string;
  created_at: string | null;
}

interface MergeSuggestionsPanelProps {
  isAdmin: boolean;
  /** Called after a confirm/reject so the parent can refresh the graph. */
  onResolved?: () => void;
}

/**
 * Admin-only review queue for ambiguous author identities (e.g. "J. Smith" vs
 * "John Smith"). Confirm merges them; reject keeps them distinct. Hidden for
 * non-admins and when the queue is empty.
 */
export function MergeSuggestionsPanel({ isAdmin, onResolved }: MergeSuggestionsPanelProps) {
  const [items, setItems] = useState<MergeSuggestion[]>([]);
  const [open, setOpen] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!isAdmin) return;
    try {
      const r = await apiFetch("/coauthorship/merge-suggestions?status=pending");
      if (!r.ok) throw new Error(`Server responded with ${r.status}`);
      setItems((await r.json()) as MergeSuggestion[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load suggestions");
    }
  }, [isAdmin]);

  useEffect(() => {
    void load();
  }, [load]);

  const act = useCallback(
    async (id: number, action: "confirm" | "reject") => {
      setBusyId(id);
      setError(null);
      try {
        const r = await apiFetch(`/coauthorship/merge-suggestions/${id}/${action}`, {
          method: "POST",
        });
        if (!r.ok) throw new Error(`Server responded with ${r.status}`);
        setItems((prev) => prev.filter((s) => s.id !== id));
        onResolved?.();
      } catch (err) {
        setError(err instanceof Error ? err.message : `Failed to ${action}`);
      } finally {
        setBusyId(null);
      }
    },
    [onResolved],
  );

  if (!isAdmin || (items.length === 0 && !error)) return null;

  return (
    <div
      className="rounded-xl border border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30"
      data-testid="merge-suggestions"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
        aria-expanded={open}
      >
        <span className="flex items-center gap-2 text-sm font-medium text-amber-800 dark:text-amber-200">
          <span aria-hidden>⚠️</span>
          {items.length} ambiguous author{items.length === 1 ? "" : "s"} to review
        </span>
        <span className="text-amber-600 dark:text-amber-400">{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <div className="space-y-2 px-4 pb-4">
          {error && <p className="text-xs text-rose-600 dark:text-rose-400">{error}</p>}
          {items.map((s) => (
            <div
              key={s.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-200 bg-white px-3 py-2 dark:border-amber-900 dark:bg-gray-900"
            >
              <div className="min-w-0 text-sm">
                <span className="font-medium text-gray-900 dark:text-white">
                  {s.author_a_name ?? `Author ${s.author_a_id}`}
                </span>
                <span className="mx-2 text-gray-400">↔</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {s.author_b_name ?? `Author ${s.author_b_id}`}
                </span>
                {s.reason && (
                  <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">({s.reason})</span>
                )}
              </div>
              <div className="flex shrink-0 gap-2">
                <button
                  type="button"
                  disabled={busyId === s.id}
                  onClick={() => act(s.id, "confirm")}
                  className="rounded-md bg-emerald-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                >
                  Merge
                </button>
                <button
                  type="button"
                  disabled={busyId === s.id}
                  onClick={() => act(s.id, "reject")}
                  className="rounded-md border border-gray-300 px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                >
                  Keep separate
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default MergeSuggestionsPanel;
