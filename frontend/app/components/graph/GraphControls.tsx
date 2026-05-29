"use client";

import { communityColor } from "./palette";

interface GraphControlsProps {
  search: string;
  onSearch: (value: string) => void;
  minWeight: number;
  onMinWeight: (value: number) => void;
  communities: number[];
  communityId: number | null;
  onCommunity: (value: number | null) => void;
  onResetView?: () => void;
}

/**
 * Top-bar controls for the coauthorship graph: live search, min-weight slider,
 * community filter chips, and a reset-view action. Pure controlled component —
 * all state lives in the parent page.
 */
export function GraphControls({
  search,
  onSearch,
  minWeight,
  onMinWeight,
  communities,
  communityId,
  onCommunity,
  onResetView,
}: GraphControlsProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-900">
      <div className="relative">
        <input
          type="search"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Search authors…"
          aria-label="Search authors"
          className="w-56 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-100"
        />
      </div>

      <div className="flex items-center gap-2">
        <label htmlFor="min-weight" className="text-sm text-gray-600 dark:text-gray-400">
          Min weight
        </label>
        <input
          id="min-weight"
          type="range"
          min={1}
          max={10}
          value={minWeight}
          onChange={(e) => onMinWeight(Number(e.target.value))}
          className="w-28"
          aria-label="Minimum edge weight"
        />
        <span className="rounded bg-gray-100 px-2 py-0.5 text-sm font-mono dark:bg-gray-800">
          {minWeight}
        </span>
      </div>

      {communities.length > 1 && (
        <div className="flex items-center gap-1" role="group" aria-label="Filter by community">
          <button
            type="button"
            onClick={() => onCommunity(null)}
            className={`rounded-full px-2.5 py-1 text-xs font-medium transition ${
              communityId === null
                ? "bg-gray-900 text-white dark:bg-white dark:text-gray-900"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300"
            }`}
          >
            All
          </button>
          {communities.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => onCommunity(c)}
              aria-pressed={communityId === c}
              className="flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition"
              style={{
                background: communityId === c ? communityColor(c) : "transparent",
                color: communityId === c ? "white" : undefined,
                border: `1px solid ${communityColor(c)}`,
              }}
            >
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: communityColor(c) }}
              />
              C{c}
            </button>
          ))}
        </div>
      )}

      {onResetView && (
        <button
          type="button"
          onClick={onResetView}
          className="ml-auto rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          Reset view
        </button>
      )}
    </div>
  );
}

export default GraphControls;
