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
  blue:    { bg: "bg-blue-50 dark:bg-blue-500/10",    text: "text-blue-600 dark:text-blue-400" },
  emerald: { bg: "bg-emerald-50 dark:bg-emerald-500/10", text: "text-emerald-600 dark:text-emerald-400" },
  amber:   { bg: "bg-amber-50 dark:bg-amber-500/10",  text: "text-amber-600 dark:text-amber-400" },
  violet:  { bg: "bg-violet-50 dark:bg-violet-500/10", text: "text-violet-600 dark:text-violet-400" },
  red:     { bg: "bg-red-50 dark:bg-red-500/10",      text: "text-red-600 dark:text-red-400" },
  gray:    { bg: "bg-gray-100 dark:bg-gray-800",      text: "text-gray-600 dark:text-gray-400" },
};

const TREND_COLORS = {
  positive: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400",
  negative: "bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400",
  neutral:  "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
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
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
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
        <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
        <p className="mt-1 text-sm font-medium text-gray-500 dark:text-gray-400">{label}</p>
        {subtitle && (
          <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">{subtitle}</p>
        )}
      </div>
    </div>
  );
}
