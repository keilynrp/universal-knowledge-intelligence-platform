import type { HTMLAttributes } from "react";

type PanelVariant = "default" | "soft" | "cognitive";

interface PanelProps extends HTMLAttributes<HTMLDivElement> {
  variant?: PanelVariant;
}

const variants: Record<PanelVariant, string> = {
  default: "ukip-panel",
  soft: "ukip-panel-soft",
  cognitive: "ukip-gradient-panel",
};

export default function Panel({ variant = "default", className = "", ...props }: PanelProps) {
  return <div className={`${variants[variant]} ${className}`} {...props} />;
}

