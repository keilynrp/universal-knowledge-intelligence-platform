"use client";

import type { ReactNode } from "react";

type MetaItem = {
  label: string;
  value: ReactNode;
  minWidthClassName?: string;
};

interface RecordResultCardProps {
  title: ReactNode;
  idTag?: ReactNode;
  secondaryLine?: ReactNode;
  statusRow?: ReactNode;
  primaryMeta?: MetaItem[];
  secondaryMeta?: MetaItem[];
  actions?: ReactNode;
  tileLabel: ReactNode;
  leadingSlot?: ReactNode;
  statusTone?: "verified" | "review" | "rejected" | "pending" | "enriched" | "default";
  onClick?: () => void;
}

function MetaRow({ items }: { items: MetaItem[] }) {
  if (items.length === 0) return null;

  return (
    <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-slate-100 pt-4 dark:border-white/10">
      {items.map((item) => (
        <div key={item.label} className="min-w-0">
          <p className="truncate text-[9px] font-bold uppercase tracking-[0.16em] text-slate-500 dark:text-[var(--ukip-muted)]">
            {item.label}
          </p>
          <div className="mt-1 truncate text-xs font-bold leading-5 text-slate-950 dark:text-[var(--ukip-text-strong)]">{item.value}</div>
        </div>
      ))}
    </div>
  );
}

export default function RecordResultCard({
  title,
  idTag,
  secondaryLine,
  statusRow,
  primaryMeta = [],
  secondaryMeta = [],
  actions,
  tileLabel,
  leadingSlot,
  statusTone = "default",
  onClick,
}: RecordResultCardProps) {
  const toneClass = {
    verified: "border-l-emerald-500 hover:border-l-emerald-500",
    enriched: "border-l-emerald-500 hover:border-l-emerald-500",
    review: "border-l-amber-400 hover:border-l-amber-400",
    pending: "border-l-violet-400 hover:border-l-violet-400",
    rejected: "border-l-rose-500 hover:border-l-rose-500",
    default: "border-l-slate-300 hover:border-l-violet-400",
  }[statusTone];

  const tileToneClass = {
    verified: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-200",
    enriched: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-200",
    review: "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200",
    pending: "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-500/20 dark:bg-violet-500/10 dark:text-violet-200",
    rejected: "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-200",
    default: "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-500/20 dark:bg-violet-500/10 dark:text-violet-200",
  }[statusTone];

  return (
    <article
      className={`${onClick ? "cursor-pointer" : ""} h-full transition`}
      onClick={onClick}
    >
      <div className={`h-full rounded-2xl border border-l-4 border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-violet-200 hover:shadow-md dark:border-white/10 dark:bg-[var(--ukip-panel)] dark:hover:border-violet-400/30 ${toneClass}`}>
        <div className="flex h-full flex-col">
          <div className="flex items-start gap-2">
            <div className="pt-0.5">{leadingSlot}</div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className={`rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.16em] ${tileToneClass}`}>
                  {tileLabel}
                </span>
                {idTag}
              </div>
              <p className="mt-3 line-clamp-2 text-sm font-bold leading-5 text-slate-950 dark:text-[var(--ukip-text-strong)]">
                {title}
              </p>
              {secondaryLine ? (
                <div className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[11px] text-slate-500 dark:text-[var(--ukip-muted)]">
                  {secondaryLine}
                </div>
              ) : null}
            </div>
          </div>

          {statusRow ? <div className="mt-3 flex flex-wrap gap-1.5">{statusRow}</div> : null}
          <MetaRow items={[...primaryMeta, ...secondaryMeta].slice(0, 4)} />

          {actions ? (
            <div className="mt-auto flex flex-row flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3 dark:border-white/10">
              {actions}
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}
