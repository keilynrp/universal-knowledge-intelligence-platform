import type { HTMLAttributes } from "react";

type SurfaceTone = "base" | "raised" | "muted";

interface SurfaceProps extends HTMLAttributes<HTMLDivElement> {
  tone?: SurfaceTone;
}

const tones: Record<SurfaceTone, string> = {
  base: "border-[var(--ukip-border)] bg-[var(--ukip-panel)]",
  raised: "border-violet-400/25 bg-[var(--ukip-panel-strong)] shadow-[var(--ukip-shadow-soft)]",
  muted: "border-[var(--ukip-border)] bg-[var(--ukip-panel)]",
};

export default function Surface({ tone = "base", className = "", ...props }: SurfaceProps) {
  return (
    <div
      className={`rounded-[var(--ukip-radius-lg)] border backdrop-blur ${tones[tone]} ${className}`}
      {...props}
    />
  );
}
