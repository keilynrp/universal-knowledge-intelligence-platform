"use client";

import type { Snapshot } from "./contextTypes";
import type { ReactNode } from "react";
import { EntityConcept } from "../components/ui";

export function SnapshotCards({ snap }: { snap: Snapshot }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-5 dark:border-blue-800 dark:bg-blue-900/10">
          <p className="text-xs font-medium text-blue-600 dark:text-blue-400">
            <EntityConcept>Total Entities</EntityConcept>
          </p>
          <p className="mt-1 text-3xl font-bold text-blue-700 dark:text-blue-300">
            {snap.entity_stats.total.toLocaleString()}
          </p>
          <p className="mt-1 text-xs text-blue-600 dark:text-blue-400">
            {snap.entity_stats.pct_enriched}% enriched
          </p>
        </div>
        <div className="rounded-xl border border-red-200 bg-red-50 p-5 dark:border-red-800 dark:bg-red-900/10">
          <p className="text-xs font-medium text-red-600 dark:text-red-400">Data Gaps</p>
          <p className="mt-1 text-3xl font-bold text-red-700 dark:text-red-300">{snap.gaps.critical}</p>
          <p className="mt-1 text-xs text-red-600 dark:text-red-400">
            critical · {snap.gaps.warning} warnings
          </p>
        </div>
        <div className="rounded-xl border border-violet-200 bg-violet-50 p-5 dark:border-violet-800 dark:bg-violet-900/10">
          <p className="text-xs font-medium text-violet-600 dark:text-violet-400">Schema</p>
          <p className="mt-1 truncate text-base font-bold text-violet-700 dark:text-violet-300">
            {snap.schema?.name || snap.domain_id}
          </p>
          <p className="mt-1 text-xs text-violet-600 dark:text-violet-400">
            {snap.schema?.attributes?.length ?? 0} attributes
          </p>
        </div>
      </div>
      {snap.top_topics.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-900">
          <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Top Concepts</h3>
          <div className="flex flex-wrap gap-2">
            {snap.top_topics.map((topic) => (
              <span
                key={topic.concept}
                className="inline-flex items-center gap-1 rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs dark:border-gray-700 dark:bg-gray-800"
              >
                <span className="font-medium text-gray-700 dark:text-gray-300">{topic.concept}</span>
                <span className="text-gray-400 dark:text-gray-500">{topic.count}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function DeltaTable({
  title,
  rows,
}: {
  title: ReactNode;
  rows: Array<{ label: string; before: number; after: number; change: number }>;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900">
      <p className="border-b border-gray-200 px-5 py-3 text-sm font-semibold text-gray-900 dark:border-gray-700 dark:text-white">
        {title}
      </p>
      <table className="w-full text-sm">
        <thead className="bg-gray-50 dark:bg-gray-800">
          <tr>
            <th className="px-5 py-2 text-left text-xs font-medium text-gray-500">Metric</th>
            <th className="px-5 py-2 text-right text-xs font-medium text-gray-500">Before</th>
            <th className="px-5 py-2 text-right text-xs font-medium text-gray-500">After</th>
            <th className="px-5 py-2 text-right text-xs font-medium text-gray-500">Change</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-t border-gray-100 dark:border-gray-800">
              <td className="px-5 py-2 font-medium capitalize text-gray-800 dark:text-gray-200">
                {row.label.replace(/_/g, " ")}
              </td>
              <td className="px-5 py-2 text-right text-gray-500">{row.before}</td>
              <td className="px-5 py-2 text-right text-gray-700 dark:text-gray-300">{row.after}</td>
              <td
                className={`px-5 py-2 text-right font-semibold ${
                  row.change > 0 ? "text-green-600" : row.change < 0 ? "text-red-500" : "text-gray-400"
                }`}
              >
                {row.change > 0 ? "+" : ""}
                {row.change}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
