import type { HTMLAttributes } from "react";

type SignalTone = "violet" | "cyan" | "emerald" | "amber" | "danger" | "neutral";

interface SignalBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: SignalTone;
}

const tones: Record<SignalTone, string> = {
  violet: "border-violet-400/20 bg-violet-500/15 text-violet-200",
  cyan: "border-cyan-400/20 bg-cyan-500/15 text-cyan-200",
  emerald: "border-emerald-400/20 bg-emerald-500/15 text-emerald-200",
  amber: "border-amber-400/20 bg-amber-500/15 text-amber-200",
  danger: "border-red-400/20 bg-red-500/15 text-red-200",
  neutral: "border-[var(--ukip-border)] bg-[var(--ukip-panel-strong)] text-[var(--ukip-muted)]",
};

export default function SignalBadge({ tone = "neutral", className = "", ...props }: SignalBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold leading-none ${tones[tone]} ${className}`}
      {...props}
    />
  );
}

