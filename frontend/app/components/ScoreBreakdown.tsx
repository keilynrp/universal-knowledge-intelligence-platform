"use client";

/**
 * Explainable scoring breakdown (Phase 3, Task 12).
 *
 * Renders the per-signal contribution bars (identifiers / name / affiliation /
 * coauthorship) and the raw evidence trail that the authority scoring engine
 * produced for a candidate. Reserved signals (coauthorship / topic) are hidden
 * when zero so the view stays focused on signals that actually contributed.
 */

interface ScoreBreakdownProps {
  breakdown?: Record<string, number> | null;
  evidence?: string[] | null;
  compact?: boolean;
}

const SIGNAL_LABELS: Record<string, string> = {
  identifiers: "Identifiers",
  name: "Name",
  affiliation: "Affiliation",
  coauthorship: "Coauthorship",
  topic: "Topic",
};

// Reserved signals only render when they carry a non-zero contribution.
const RESERVED_SIGNALS = new Set(["coauthorship", "topic"]);

const SIGNAL_COLORS: Record<string, string> = {
  identifiers: "bg-violet-500",
  name: "bg-blue-500",
  affiliation: "bg-emerald-500",
  coauthorship: "bg-amber-500",
  topic: "bg-rose-500",
};

function clamp01(value: number): number {
  if (Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

export default function ScoreBreakdown({ breakdown, evidence, compact = false }: ScoreBreakdownProps) {
  const entries = breakdown
    ? Object.entries(breakdown).filter(
        ([signal, value]) => !(RESERVED_SIGNALS.has(signal) && (value ?? 0) === 0),
      )
    : [];

  const hasData = entries.length > 0 || (evidence?.length ?? 0) > 0;

  if (!hasData) {
    return (
      <p className="text-xs text-gray-400 dark:text-gray-500">Sin desglose disponible</p>
    );
  }

  return (
    <div className={compact ? "space-y-2" : "space-y-3"}>
      {entries.length > 0 && (
        <div className="space-y-1.5">
          {entries.map(([signal, raw]) => {
            const value = clamp01(raw ?? 0);
            const label = SIGNAL_LABELS[signal] ?? signal;
            const color = SIGNAL_COLORS[signal] ?? "bg-gray-400";
            return (
              <div key={signal} className="flex items-center gap-2">
                <span className="w-24 shrink-0 text-xs text-gray-600 dark:text-gray-400">{label}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
                  <div
                    className={`h-full rounded-full ${color}`}
                    style={{ width: `${value * 100}%` }}
                    role="presentation"
                  />
                </div>
                <span className="w-10 shrink-0 text-right text-xs tabular-nums text-gray-700 dark:text-gray-300">
                  {value.toFixed(2)}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {evidence && evidence.length > 0 && (
        <ul className="space-y-0.5 border-t border-gray-100 pt-2 dark:border-gray-800">
          {evidence.map((line, i) => (
            <li
              key={`${i}-${line}`}
              className="font-mono text-[11px] leading-relaxed text-gray-500 dark:text-gray-400"
            >
              {line}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
