"use client";

interface StatCardProps {
  icon: React.ReactNode;
  iconColor?: "blue" | "emerald" | "amber" | "violet" | "red" | "gray";
  label: string;
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

const TREND_COLORS = {
  positive: "bg-emerald-500/10 text-emerald-300",
  negative: "bg-red-500/10 text-red-300",
  neutral:  "bg-[var(--ukip-panel-strong)] text-[var(--ukip-muted)]",
};

export default function StatCard({ icon, iconColor = "blue", label, value, trend, subtitle }: StatCardProps) {
  const colors = ICON_COLORS[iconColor] || ICON_COLORS.blue;

  const trendColorKey = trend
    ? trend.direction === "neutral"
      ? "neutral"
      : trend.positive !== false
        ? "positive"
        : "negative"
    : null;

  return (
    <div className="ukip-panel-soft p-5">
      <div className="flex items-center justify-between">
        <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${colors.bg}`}>
          <span className={colors.text}>{icon}</span>
        </div>
        {trend && trendColorKey && (
          <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${TREND_COLORS[trendColorKey]}`}>
            {trend.direction === "up" && (
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
              </svg>
            )}
            {trend.direction === "down" && (
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            )}
            {trend.value}
          </span>
        )}
      </div>
      <div className="mt-4">
        <p className="text-2xl font-bold text-[var(--ukip-text-strong)]">{value}</p>
        <p className="mt-1 text-sm font-medium text-[var(--ukip-muted)]">{label}</p>
        {subtitle && (
          <p className="mt-0.5 text-xs text-[var(--ukip-muted-soft)]">{subtitle}</p>
        )}
      </div>
    </div>
  );
}
