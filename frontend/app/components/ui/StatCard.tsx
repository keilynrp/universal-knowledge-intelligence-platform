"use client";

import type { ReactNode } from "react";
import DeltaBadge from "./DeltaBadge";

interface StatCardProps {
  icon: React.ReactNode;
  iconColor?: "blue" | "emerald" | "amber" | "violet" | "red" | "gray";
  label: ReactNode;
  value: string | number;
  trend?: {
    value: string;
    direction: "up" | "down" | "neutral";
    positive?: boolean;
  };
  subtitle?: string;
}

const ICON_COLORS: Record<string, { bg: string; text: string }> = {
  blue:    { bg: "bg-cyan-500/10",    text: "text-cyan-300" },
  emerald: { bg: "bg-emerald-500/10", text: "text-emerald-300" },
  amber:   { bg: "bg-amber-500/10",  text: "text-amber-300" },
  violet:  { bg: "bg-violet-500/10", text: "text-violet-300" },
  red:     { bg: "bg-red-500/10",      text: "text-red-300" },
  gray:    { bg: "bg-white/5",      text: "text-[var(--ukip-muted)]" },
};

export default function StatCard({ icon, iconColor = "blue", label, value, trend, subtitle }: StatCardProps) {
  const colors = ICON_COLORS[iconColor] || ICON_COLORS.blue;
  const trendDirection = trend?.direction === "neutral" ? "neutral" : trend?.positive === false ? "down" : "up";

  return (
    <div className="ukip-panel-soft p-5">
      <div className="flex items-center justify-between">
        <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${colors.bg}`}>
          <span className={colors.text}>{icon}</span>
        </div>
        {trend && (
          <DeltaBadge value={trend.value} direction={trendDirection} />
        )}
      </div>
      <div className="mt-4">
        <p className="text-2xl font-semibold text-[var(--ukip-text-strong)]">{value}</p>
        <p className="mt-1 text-sm font-medium text-[var(--ukip-muted)]">{label}</p>
        {subtitle && (
          <p className="mt-0.5 text-xs text-[var(--ukip-muted-soft)]">{subtitle}</p>
        )}
      </div>
    </div>
  );
}
