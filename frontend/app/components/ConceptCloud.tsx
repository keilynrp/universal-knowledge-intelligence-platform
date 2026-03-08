"use client";

interface ConceptItem {
  concept: string;
  count: number;
}

interface ConceptCloudProps {
  concepts: ConceptItem[];
  maxItems?: number;
}

const PALETTE = [
  "text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 hover:bg-blue-100 dark:hover:bg-blue-500/20",
  "text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-500/10 hover:bg-violet-100 dark:hover:bg-violet-500/20",
  "text-fuchsia-600 dark:text-fuchsia-400 bg-fuchsia-50 dark:bg-fuchsia-500/10 hover:bg-fuchsia-100 dark:hover:bg-fuchsia-500/20",
  "text-cyan-600 dark:text-cyan-400 bg-cyan-50 dark:bg-cyan-500/10 hover:bg-cyan-100 dark:hover:bg-cyan-500/20",
  "text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 hover:bg-emerald-100 dark:hover:bg-emerald-500/20",
  "text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10 hover:bg-amber-100 dark:hover:bg-amber-500/20",
];

export default function ConceptCloud({ concepts, maxItems = 50 }: ConceptCloudProps) {
  const visible = concepts.slice(0, maxItems);

  if (!visible.length) {
    return (
      <div className="flex h-32 items-center justify-center text-sm text-gray-400 dark:text-gray-500">
        No concepts extracted yet. Run enrichment to populate this view.
      </div>
    );
  }

  const maxCount = Math.max(...visible.map((c) => c.count));

  return (
    <div className="flex flex-wrap gap-2">
      {visible.map((c, i) => {
        const ratio = c.count / maxCount;
        const size =
          ratio > 0.75
            ? "text-base px-3 py-1.5"
            : ratio > 0.4
            ? "text-sm px-2.5 py-1"
            : "text-xs px-2 py-0.5";
        const colorClass = PALETTE[i % PALETTE.length];
        return (
          <span
            key={c.concept}
            className={`inline-flex cursor-default items-center gap-1 rounded-full font-medium transition-colors ${size} ${colorClass}`}
            title={`${c.count} record${c.count !== 1 ? "s" : ""}`}
          >
            {c.concept}
            <span className="opacity-60">·{c.count}</span>
          </span>
        );
      })}
    </div>
  );
}
