"use client";

/**
 * ProvBadge — Provenance layer badge.
 * Visually distinguishes source / enrichment / canonical / authority data.
 */

export type ProvenanceLayer = "source" | "enrichment" | "canonical" | "authority";

interface ProvBadgeProps {
  layer: ProvenanceLayer;
  size?: "sm" | "md";
  className?: string;
}

const LAYER_CONFIG: Record<
  ProvenanceLayer,
  { label: string; icon: string; bg: string; text: string; border: string }
> = {
  source: {
    label: "Source",
    icon: "↑",
    bg: "bg-gray-100 dark:bg-gray-700/50",
    text: "text-gray-600 dark:text-gray-400",
    border: "border-gray-300 dark:border-gray-600",
  },
  enrichment: {
    label: "Enriched",
    icon: "✦",
    bg: "bg-cyan-50 dark:bg-cyan-500/10",
    text: "text-cyan-700 dark:text-cyan-400",
    border: "border-cyan-300 dark:border-cyan-500/30",
  },
  canonical: {
    label: "Canonical",
    icon: "✓",
    bg: "bg-emerald-50 dark:bg-emerald-500/10",
    text: "text-emerald-700 dark:text-emerald-400",
    border: "border-emerald-300 dark:border-emerald-500/30",
  },
  authority: {
    label: "Authority",
    icon: "⛊",
    bg: "bg-violet-50 dark:bg-violet-500/10",
    text: "text-violet-700 dark:text-violet-400",
    border: "border-violet-300 dark:border-violet-500/30",
  },
};

export default function ProvBadge({ layer, size = "sm", className = "" }: ProvBadgeProps) {
  const config = LAYER_CONFIG[layer];
  if (!config) return null;

  const sizeClasses =
    size === "sm"
      ? "px-1.5 py-0.5 text-[10px] gap-1"
      : "px-2 py-1 text-xs gap-1.5";

  return (
    <span
      className={`inline-flex items-center font-medium rounded border ${config.bg} ${config.text} ${config.border} ${sizeClasses} ${className}`}
      title={`${config.label} layer`}
    >
      <span aria-hidden="true">{config.icon}</span>
      {config.label}
    </span>
  );
}
