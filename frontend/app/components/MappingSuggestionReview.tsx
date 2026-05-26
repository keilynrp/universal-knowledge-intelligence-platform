"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import ConfidenceIndicator from "./ConfidenceIndicator";
import AIDisclosureBadge from "./AIDisclosureBadge";

interface MappingSuggestion {
  id: number;
  source_field: string;
  canonical_target: string;
  confidence: number;
  status: string;
  evidence_samples: string[];
  rationale: string;
  semantic_concept?: string | null;
  identifier_scheme?: string | null;
  evidence?: string[];
  requires_review?: boolean;
}

interface MappingSuggestionReviewProps {
  statusFilter?: string;
  onUpdate?: () => void;
}

export default function MappingSuggestionReview({
  statusFilter,
  onUpdate,
}: MappingSuggestionReviewProps) {
  const [suggestions, setSuggestions] = useState<MappingSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [rejectRationale, setRejectRationale] = useState("");
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const fetchSuggestions = useCallback(async () => {
    setLoading(true);
    try {
      const url = statusFilter
        ? `/mapping-suggestions?status=${statusFilter}`
        : "/mapping-suggestions";
      const res = await apiFetch(url);
      if (res.ok) {
        setSuggestions(await res.json());
      }
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchSuggestions();
  }, [fetchSuggestions]);

  async function handleAccept(id: number) {
    setActionLoading(id);
    try {
      const res = await apiFetch(`/mapping-suggestions/${id}/accept`, {
        method: "POST",
      });
      if (res.ok) {
        await fetchSuggestions();
        onUpdate?.();
      }
    } finally {
      setActionLoading(null);
    }
  }

  async function handleReject(id: number) {
    if (!rejectRationale.trim()) return;
    setActionLoading(id);
    try {
      const res = await apiFetch(`/mapping-suggestions/${id}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rationale: rejectRationale }),
      });
      if (res.ok) {
        setRejectingId(null);
        setRejectRationale("");
        await fetchSuggestions();
        onUpdate?.();
      }
    } finally {
      setActionLoading(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-gray-400">
        Loading suggestions...
      </div>
    );
  }

  if (!suggestions.length) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-gray-400 dark:text-gray-500">
        No mapping suggestions to review.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {suggestions.map((s) => (
        <div
          key={s.id}
          className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 bg-white dark:bg-gray-800/50"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <code className="text-sm font-mono text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded">
                  {s.source_field}
                </code>
                <span className="text-gray-400">→</span>
                <code className="text-sm font-mono text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 px-1.5 py-0.5 rounded">
                  {s.canonical_target}
                </code>
              </div>

              <div className="flex items-center gap-2 mt-2">
                <ConfidenceIndicator score={s.confidence} size="sm" />
                <AIDisclosureBadge type="assisted" size="sm" />
                <span className="text-[10px] uppercase tracking-wider font-medium text-gray-400">
                  {s.status.replace("_", " ")}
                </span>
                {s.requires_review && (
                  <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
                    Review
                  </span>
                )}
              </div>

              {(s.semantic_concept || s.identifier_scheme || (s.evidence?.length ?? 0) > 0) && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {s.semantic_concept && (
                    <span className="rounded bg-sky-50 px-1.5 py-0.5 text-xs text-sky-700 dark:bg-sky-500/10 dark:text-sky-300">
                      {s.semantic_concept}
                    </span>
                  )}
                  {s.identifier_scheme && (
                    <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-xs text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300">
                      {s.identifier_scheme}
                    </span>
                  )}
                  {s.evidence?.map((item) => (
                    <span
                      key={item}
                      className="rounded bg-gray-50 px-1.5 py-0.5 text-xs text-gray-600 dark:bg-gray-700/50 dark:text-gray-300"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              )}

              {s.evidence_samples.length > 0 && (
                <div className="mt-2">
                  <span className="text-[10px] uppercase tracking-wider text-gray-400">
                    Samples:
                  </span>
                  <div className="flex gap-1 mt-0.5 flex-wrap">
                    {s.evidence_samples.map((sample, i) => (
                      <span
                        key={i}
                        className="text-xs bg-gray-50 dark:bg-gray-700/50 text-gray-600 dark:text-gray-400 px-1.5 py-0.5 rounded"
                      >
                        {sample}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {s.rationale && (
                <p className="mt-1 text-xs text-gray-500 italic">
                  {s.rationale}
                </p>
              )}
            </div>

            {(s.status === "review_required" || s.status === "auto_acceptable") && (
              <div className="flex flex-col gap-1.5 shrink-0">
                <button
                  onClick={() => handleAccept(s.id)}
                  disabled={actionLoading === s.id}
                  className="rounded px-3 py-1 text-xs font-semibold bg-emerald-100 text-emerald-700 hover:bg-emerald-200 disabled:opacity-50 dark:bg-emerald-500/10 dark:text-emerald-400 dark:hover:bg-emerald-500/20 transition"
                >
                  Accept
                </button>
                <button
                  onClick={() => setRejectingId(s.id)}
                  disabled={actionLoading === s.id}
                  className="rounded px-3 py-1 text-xs font-semibold bg-red-100 text-red-700 hover:bg-red-200 disabled:opacity-50 dark:bg-red-500/10 dark:text-red-400 dark:hover:bg-red-500/20 transition"
                >
                  Reject
                </button>
              </div>
            )}
          </div>

          {rejectingId === s.id && (
            <div className="mt-3 flex gap-2">
              <input
                type="text"
                value={rejectRationale}
                onChange={(e) => setRejectRationale(e.target.value)}
                placeholder="Rationale for rejection..."
                className="flex-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-2 py-1 text-xs text-gray-700 dark:text-gray-300 placeholder-gray-400"
              />
              <button
                onClick={() => handleReject(s.id)}
                disabled={!rejectRationale.trim() || actionLoading === s.id}
                className="rounded px-3 py-1 text-xs font-semibold bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 transition"
              >
                Confirm
              </button>
              <button
                onClick={() => {
                  setRejectingId(null);
                  setRejectRationale("");
                }}
                className="rounded px-3 py-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
