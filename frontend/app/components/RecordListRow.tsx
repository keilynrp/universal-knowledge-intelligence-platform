"use client";

import type { ReactNode } from "react";

type RecordListTone = "verified" | "review" | "rejected" | "pending" | "enriched" | "default";

interface RecordListRowProps {
  title: ReactNode;
  metaLine?: ReactNode;
  statusBadge?: ReactNode;
  owner?: ReactNode;
  authorityScore?: ReactNode;
  qualityScore?: ReactNode;
  selected?: boolean;
  selectable?: boolean;
  tone?: RecordListTone;
  onSelect?: () => void;
  onClick?: () => void;
}

const toneClasses: Record<RecordListTone, string> = {
  verified: "border-l-emerald-500",
  enriched: "border-l-emerald-500",
  review: "border-l-amber-400",
  pending: "border-l-violet-500",
  rejected: "border-l-rose-500",
  default: "border-l-slate-300",
};

export default function RecordListRow({
  title,
  metaLine,
  statusBadge,
  owner,
  authorityScore,
  qualityScore,
  selected = false,
  selectable = false,
  tone = "default",
  onSelect,
  onClick,
}: RecordListRowProps) {
  return (
    <article
      onClick={onClick}
      className={`group grid min-h-[4rem] gap-3 rounded-2xl border border-l-4 border-slate-200 bg-white px-4 py-3 shadow-sm transition hover:-translate-y-0.5 hover:border-violet-200 hover:shadow-md dark:border-white/10 dark:bg-[var(--ukip-panel)] ${toneClasses[tone]} ${onClick ? "cursor-pointer" : ""}`}
    >
      <div className="grid items-center gap-3 md:grid-cols-[auto_minmax(0,1fr)_auto_auto_auto]">
        <div className="flex items-center gap-3">
          {selectable ? (
            <input
              type="checkbox"
              className="ukip-selection-control"
              checked={selected}
              onClick={(event) => event.stopPropagation()}
              onChange={onSelect}
              aria-label="Seleccionar registro"
            />
          ) : (
            <span className="h-4 w-4 rounded-full border border-violet-400" aria-hidden="true" />
          )}
        </div>

        <div className="min-w-0">
          <h3 className="truncate text-sm font-bold text-slate-950 dark:text-[var(--ukip-text-strong)]">
            {title}
          </h3>
          {metaLine ? (
            <div className="mt-1 truncate font-mono text-xs text-slate-500 dark:text-[var(--ukip-muted)]">
              {metaLine}
            </div>
          ) : null}
        </div>

        <div className="flex items-center gap-3 font-mono text-xs text-slate-600 dark:text-[var(--ukip-muted)]">
          {authorityScore ? <span>A {authorityScore}</span> : null}
          {qualityScore ? <span>Q {qualityScore}</span> : null}
        </div>

        <div className="flex justify-start md:justify-center">
          {statusBadge}
        </div>

        <div className="min-w-0 text-sm text-slate-600 dark:text-[var(--ukip-muted)] md:min-w-[7rem]">
          <span className="block truncate">{owner}</span>
        </div>
      </div>
    </article>
  );
}
