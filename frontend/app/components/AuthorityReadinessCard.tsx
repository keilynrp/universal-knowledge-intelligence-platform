"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import ProvBadge from "./ProvBadge";

interface FamilyCounts {
  extracted: number;
  resolved: number;
  review_required: number;
  rejected: number;
  failed: number;
  stale: number;
}

interface ReadinessData {
  dataset_id: string;
  state: string;
  families: Record<string, FamilyCounts>;
}

interface AuthorityReadinessCardProps {
  datasetId: string;
  className?: string;
}

const STATE_STYLES: Record<string, { label: string; color: string }> = {
  not_started: { label: "Not started", color: "text-gray-400" },
  source_candidates_ready: { label: "Source candidates ready", color: "text-cyan-600 dark:text-cyan-400" },
  enrichment_candidates_ready: { label: "Enrichment candidates ready", color: "text-cyan-600 dark:text-cyan-400" },
  review_required: { label: "Review required", color: "text-amber-600 dark:text-amber-400" },
  partially_resolved: { label: "Partially resolved", color: "text-amber-600 dark:text-amber-400" },
  resolved: { label: "Resolved", color: "text-emerald-600 dark:text-emerald-400" },
  stale: { label: "Stale", color: "text-red-600 dark:text-red-400" },
  failed: { label: "Failed", color: "text-red-600 dark:text-red-400" },
};

const FAMILY_ICONS: Record<string, string> = {
  person: "👤",
  institution: "🏛",
  identifier: "🔗",
  place: "📍",
  venue: "📖",
  concept: "💡",
};

export default function AuthorityReadinessCard({
  datasetId,
  className = "",
}: AuthorityReadinessCardProps) {
  const [data, setData] = useState<ReadinessData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await apiFetch(`/governance/authority-readiness/${datasetId}`);
        if (res.ok) setData(await res.json());
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [datasetId]);

  if (loading) {
    return (
      <div className={`rounded-lg border border-gray-200 dark:border-gray-700 p-4 ${className}`}>
        <div className="animate-pulse h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-3" />
        <div className="animate-pulse h-3 bg-gray-100 dark:bg-gray-800 rounded w-2/3" />
      </div>
    );
  }

  if (!data) return null;

  const stateConfig = STATE_STYLES[data.state] || STATE_STYLES.not_started;
  const families = Object.entries(data.families);

  return (
    <div
      className={`rounded-lg border border-gray-200 dark:border-gray-700 p-4 bg-white dark:bg-gray-800/50 ${className}`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <ProvBadge layer="authority" size="md" />
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Authority Readiness
          </h3>
        </div>
        <span className={`text-xs font-medium ${stateConfig.color}`}>
          {stateConfig.label}
        </span>
      </div>

      {families.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {families.map(([family, counts]) => {
            const total = counts.extracted + counts.resolved;
            const resolvedPct =
              total > 0 ? Math.round((counts.resolved / total) * 100) : 0;

            return (
              <div
                key={family}
                className="rounded border border-gray-100 dark:border-gray-700 p-2 bg-gray-50 dark:bg-gray-800/30"
              >
                <div className="flex items-center gap-1 mb-1">
                  <span className="text-sm">{FAMILY_ICONS[family] || "📦"}</span>
                  <span className="text-xs font-medium text-gray-600 dark:text-gray-400 capitalize">
                    {family}
                  </span>
                </div>
                <div className="text-lg font-bold text-gray-800 dark:text-gray-200 tabular-nums">
                  {resolvedPct}%
                </div>
                <div className="flex gap-2 text-[10px] text-gray-400">
                  <span>{counts.extracted} ext</span>
                  <span>{counts.resolved} res</span>
                  {counts.review_required > 0 && (
                    <span className="text-amber-500">{counts.review_required} rev</span>
                  )}
                  {counts.stale > 0 && (
                    <span className="text-red-500">{counts.stale} stale</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
