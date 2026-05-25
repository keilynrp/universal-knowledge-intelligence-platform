"use client";

/**
 * ConfidenceIndicator — Visual treatment for confidence levels.
 * Maps score to high/medium/low/unknown/review-required with semantic colors.
 */

export type ConfidenceLevel = "high" | "medium" | "low" | "unknown" | "review_required";

interface ConfidenceIndicatorProps {
  score: number;
  requiresReview?: boolean;
  showScore?: boolean;
  size?: "sm" | "md";
  className?: string;
}

interface LevelConfig {
  level: ConfidenceLevel;
  label: string;
  dot: string;
  text: string;
  bg: string;
}

function getLevel(score: number, requiresReview: boolean): LevelConfig {
  if (requiresReview) {
    return {
      level: "review_required",
      label: "Review required",
      dot: "bg-amber-500",
      text: "text-amber-700 dark:text-amber-400",
      bg: "bg-amber-50 dark:bg-amber-500/10",
    };
  }
  if (score >= 0.8) {
    return {
      level: "high",
      label: "High",
      dot: "bg-emerald-500",
      text: "text-emerald-700 dark:text-emerald-400",
      bg: "bg-emerald-50 dark:bg-emerald-500/10",
    };
  }
  if (score >= 0.5) {
    return {
      level: "medium",
      label: "Medium",
      dot: "bg-amber-500",
      text: "text-amber-700 dark:text-amber-400",
      bg: "bg-amber-50 dark:bg-amber-500/10",
    };
  }
  if (score >= 0.2) {
    return {
      level: "low",
      label: "Low",
      dot: "bg-red-500",
      text: "text-red-700 dark:text-red-400",
      bg: "bg-red-50 dark:bg-red-500/10",
    };
  }
  return {
    level: "unknown",
    label: "Unknown",
    dot: "bg-gray-400",
    text: "text-gray-500 dark:text-gray-400",
    bg: "bg-gray-50 dark:bg-gray-700/50",
  };
}

export default function ConfidenceIndicator({
  score,
  requiresReview = false,
  showScore = true,
  size = "sm",
  className = "",
}: ConfidenceIndicatorProps) {
  const config = getLevel(score, requiresReview);

  const sizeClasses =
    size === "sm"
      ? "px-1.5 py-0.5 text-[10px] gap-1"
      : "px-2 py-1 text-xs gap-1.5";

  const dotSize = size === "sm" ? "h-1.5 w-1.5" : "h-2 w-2";

  return (
    <span
      className={`inline-flex items-center font-medium rounded ${config.bg} ${config.text} ${sizeClasses} ${className}`}
      title={`Confidence: ${(score * 100).toFixed(0)}% — ${config.label}`}
    >
      <span className={`inline-block rounded-full ${config.dot} ${dotSize}`} aria-hidden="true" />
      {config.label}
      {showScore && <span className="opacity-70">({(score * 100).toFixed(0)}%)</span>}
    </span>
  );
}
