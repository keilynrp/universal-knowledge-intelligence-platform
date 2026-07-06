"use client";

import type { ReactNode } from "react";

type MetaItem = {
  label: string;
  value: ReactNode;
  minWidthClassName?: string;
};

interface RecordResultCardProps {
  title: ReactNode;
  secondaryLine?: ReactNode;
  statusRow?: ReactNode;
  primaryMeta?: MetaItem[];
  secondaryMeta?: MetaItem[];
  actions?: ReactNode;
  leadingSlot?: ReactNode;
  statusTone?: "verified" | "review" | "rejected" | "pending" | "enriched" | "default";
  onClick?: () => void;
}

function MetaRow({ items }: { items: MetaItem[] }) {
  if (items.length === 0) return null;

  return (
    <div className="mt-4 grid grid-cols-1 gap-x-4 gap-y-3 border-t border-slate-100 pt-4 sm:grid-cols-2 dark:border-white/10">
      {items.map((item) => (
        <div key={item.label} className={`min-w-0 ${item.minWidthClassName ?? ""}`}>
          <p className="truncate text-[9px] font-bold uppercase tracking-[0.16em] text-slate-500 dark:text-[var(--ukip-muted)]">
            {item.label}
          </p>
          <div className="mt-1 min-w-0 break-words text-xs font-bold leading-5 text-slate-950 [overflow-wrap:anywhere] dark:text-[var(--ukip-text-strong)]">{item.value}</div>
        </div>
      ))}
    </div>
  );
}

export default function RecordResultCard({
  title,
  secondaryLine,
  statusRow,
  primaryMeta = [],
  secondaryMeta = [],
  actions,
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

  return (
    <article
      className={`${onClick ? "cursor-pointer" : ""} h-full transition`}
      onClick={onClick}
    >
      <div className={`h-full rounded-2xl border border-l-4 border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-violet-200 hover:shadow-md dark:border-white/10 dark:bg-[var(--ukip-panel)] dark:hover:border-violet-400/30 ${toneClass}`}>
        <div className="grid h-full grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[1.25rem_minmax(0,1fr)]">
          <div className="pt-1">{leadingSlot}</div>
          <div className="flex min-w-0 flex-col">
            <div className="min-w-0">
              <p className="line-clamp-2 text-sm font-bold leading-5 text-slate-950 dark:text-[var(--ukip-text-strong)]">
                {title}
              </p>
              {secondaryLine ? (
                <div className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[11px] text-slate-500 dark:text-[var(--ukip-muted)]">
                  {secondaryLine}
                </div>
              ) : null}
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
      </div>
    </article>
  );
}
