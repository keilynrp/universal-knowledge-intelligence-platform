"use client";

import { DeltaTable } from "./ContextPanels";
import type { DiffResult, Session } from "./contextTypes";
import { formatDateTime } from "../lib/dateFormat";
import { EntityConcept } from "../components/ui";

export function DiffTab({
  sortedSessions,
  diffA,
  diffB,
  diffResult,
  diffLoading,
  diffError,
  diffInsights,
  loadingDiffInsights,
  insightsError,
  onDiffAChange,
  onDiffBChange,
  onRunDiff,
  onFetchDiffInsights,
}: {
  sortedSessions: Session[];
  diffA: number | "";
  diffB: number | "";
  diffResult: DiffResult | null;
  diffLoading: boolean;
  diffError: string | null;
  diffInsights: string | null;
  loadingDiffInsights: boolean;
  insightsError: string | null;
  onDiffAChange: (value: number | "") => void;
  onDiffBChange: (value: number | "") => void;
  onRunDiff: () => void;
  onFetchDiffInsights: () => void;
}) {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-900 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">
            Snapshot A (older)
          </label>
          <select
            value={diffA}
            onChange={(e) => onDiffAChange(Number(e.target.value) || "")}
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          >
            <option value="">Select session...</option>
            {sortedSessions.map((session) => (
              <option key={session.id} value={session.id}>
                {session.label || `Snapshot #${session.id}`} - {session.domain_id}
              </option>
            ))}
          </select>
        </div>
        <div className="hidden items-center text-gray-400 sm:flex">-&gt;</div>
        <div className="flex-1">
          <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">
            Snapshot B (newer)
          </label>
          <select
            value={diffB}
            onChange={(e) => onDiffBChange(Number(e.target.value) || "")}
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          >
            <option value="">Select session...</option>
            {sortedSessions.map((session) => (
              <option key={session.id} value={session.id}>
                {session.label || `Snapshot #${session.id}`} - {session.domain_id}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={onRunDiff}
          disabled={!diffA || !diffB || diffLoading}
          className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-6 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
        >
          {diffLoading ? "Comparing..." : "Compare"}
        </button>
      </div>

      {diffError && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          {diffError}
        </div>
      )}

      {diffResult && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onFetchDiffInsights}
              disabled={loadingDiffInsights}
              className="inline-flex items-center gap-2 rounded-xl border border-violet-300 bg-violet-50 px-4 py-2 text-sm font-medium text-violet-700 hover:bg-violet-100 disabled:opacity-50 dark:border-violet-700 dark:bg-violet-500/10 dark:text-violet-300"
            >
              {loadingDiffInsights ? "Analyzing..." : "AI Analysis of Changes"}
            </button>
            {insightsError && (
              <span className="text-xs text-amber-600 dark:text-amber-400">{insightsError}</span>
            )}
          </div>

          {diffInsights && (
            <div className="rounded-2xl border border-violet-200 bg-violet-50 p-5 dark:border-violet-800 dark:bg-violet-500/5">
              <p className="mb-2 text-xs font-semibold text-violet-700 dark:text-violet-300">AI Analysis</p>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-violet-900 dark:text-violet-200">
                {diffInsights}
              </p>
            </div>
          )}

          <div className="flex flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
            <span>
              A: <strong>{diffResult.snapshot_a_domain}</strong> ·{" "}
              {formatDateTime(diffResult.snapshot_a_generated)}
            </span>
            <span className="mx-2">-&gt;</span>
            <span>
              B: <strong>{diffResult.snapshot_b_domain}</strong> ·{" "}
              {formatDateTime(diffResult.snapshot_b_generated)}
            </span>
          </div>

          <DeltaTable
            title={<EntityConcept>Entity Stats</EntityConcept>}
            rows={Object.entries(diffResult.entity_stats).map(([key, value]) => ({ label: key, ...value }))}
          />
          <DeltaTable
            title="Data Gaps"
            rows={Object.entries(diffResult.gaps).map(([key, value]) => ({ label: key, ...value }))}
          />
          {diffResult.top_topics.filter((topic) => topic.change !== 0).length > 0 && (
            <DeltaTable
              title="Concept Changes"
              rows={diffResult.top_topics
                .filter((topic) => topic.change !== 0)
                .sort((a, b) => Math.abs(b.change) - Math.abs(a.change))
                .map((topic) => ({
                  label: topic.concept,
                  before: topic.before,
                  after: topic.after,
                  change: topic.change,
                }))}
            />
          )}
        </div>
      )}

      {!diffResult && !diffLoading && !diffError && (
        <div className="flex flex-col items-center py-16 text-center">
          <span className="text-4xl">⚖️</span>
          <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
            Select two sessions and click Compare to see the delta.
          </p>
        </div>
      )}
    </div>
  );
}
