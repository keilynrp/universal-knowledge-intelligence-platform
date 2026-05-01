import type { ReactNode } from "react";

type DeltaDirection = "up" | "down" | "neutral";

interface DeltaBadgeProps {
  value: ReactNode;
  direction?: DeltaDirection;
  children?: ReactNode;
  className?: string;
}

const toneClass: Record<DeltaDirection, string> = {
  up: "bg-emerald-100 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-200",
  down: "bg-rose-100 text-rose-700 dark:bg-rose-400/15 dark:text-rose-200",
  neutral: "bg-slate-100 text-slate-600 dark:bg-white/10 dark:text-[var(--ukip-muted)]",
};

function TrendIcon({ direction }: { direction: DeltaDirection }) {
  if (direction === "neutral") {
    return <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" aria-hidden="true" />;
  }

  return (
    <svg
      className={direction === "down" ? "h-3 w-3 rotate-90" : "h-3 w-3"}
      fill="none"
      viewBox="0 0 16 16"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 10.5 6.5 7l2.25 2.25L13 5m0 0v4m0-4H9" />
    </svg>
  );
}

export default function DeltaBadge({ value, direction = "up", children, className = "" }: DeltaBadgeProps) {
  return (
    <span className={`inline-flex min-w-0 items-center gap-2 text-xs text-slate-500 dark:text-[var(--ukip-muted)] ${className}`}>
      <span className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-1 font-mono text-[11px] font-bold leading-none ${toneClass[direction]}`}>
        <TrendIcon direction={direction} />
        {value}
      </span>
      {children ? <span className="min-w-0 truncate font-medium">{children}</span> : null}
    </span>
  );
}
