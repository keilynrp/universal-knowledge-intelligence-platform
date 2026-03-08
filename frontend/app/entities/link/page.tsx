"use client";

import { useState, useCallback } from "react";
import { PageHeader, Badge } from "../../components/ui";
import { apiFetch } from "../../../lib/api";
import { useToast } from "../../components/ui";

// ── Types ──────────────────────────────────────────────────────────────────────

interface EntitySummary {
  id: number;
  entity_name:       string | null;
  brand_capitalized: string | null;
  model:             string | null;
  sku:               string | null;
  gtin:              string | null;
  barcode:           string | null;
  classification:    string | null;
  variant:           string | null;
  unit_of_measure:   string | null;
  enrichment_status: string | null;
  validation_status: string | null;
}

interface Candidate {
  entity_a:      EntitySummary;
  entity_b:      EntitySummary;
  similarity:    number;
  common_tokens: string[];
}

interface ScanResult {
  candidates: Candidate[];
  total:      number;
  threshold:  number;
  scanned:    number;
}

type Strategy = "keep_non_empty" | "keep_primary" | "keep_longest";

// ── Helpers ────────────────────────────────────────────────────────────────────

function simLabel(s: number): { label: string; variant: "error" | "warning" | "info" | "default" } {
  if (s >= 0.95) return { label: "Identical",  variant: "error" };
  if (s >= 0.88) return { label: "Very High",  variant: "warning" };
  if (s >= 0.80) return { label: "High",       variant: "info" };
  return               { label: "Moderate",    variant: "default" };
}

const DISPLAY_FIELDS: Array<{ key: keyof EntitySummary; label: string }> = [
  { key: "entity_name",       label: "Name" },
  { key: "brand_capitalized", label: "Brand" },
  { key: "model",             label: "Model" },
  { key: "sku",               label: "SKU" },
  { key: "gtin",              label: "GTIN" },
  { key: "classification",    label: "Classification" },
  { key: "variant",           label: "Variant" },
  { key: "unit_of_measure",   label: "UOM" },
];

const STRATEGY_LABELS: Record<Strategy, string> = {
  keep_non_empty: "Keep non-empty (fill blanks from secondary)",
  keep_primary:   "Keep primary (ignore all secondary values)",
  keep_longest:   "Keep longest (prefer more complete text)",
};

// ── Sub-components ─────────────────────────────────────────────────────────────

function FieldRow({
  label, valA, valB,
}: { label: string; valA: string | null; valB: string | null }) {
  const diff = (valA || "") !== (valB || "");
  return (
    <tr className={diff ? "bg-amber-50/40 dark:bg-amber-500/5" : ""}>
      <td className="py-1.5 pl-3 pr-2 text-xs font-medium text-gray-500 dark:text-gray-400 w-24 shrink-0">
        {label}
      </td>
      <td className="py-1.5 pr-2 text-xs text-gray-900 dark:text-white max-w-[180px] truncate">
        {valA || <span className="italic text-gray-300 dark:text-gray-600">—</span>}
      </td>
      <td className="py-1.5 pr-3 text-xs text-gray-900 dark:text-white max-w-[180px] truncate">
        {valB || <span className="italic text-gray-300 dark:text-gray-600">—</span>}
      </td>
    </tr>
  );
}

function CandidateCard({
  candidate, onMerge, onDismiss,
}: {
  candidate: Candidate;
  onMerge: (primary: EntitySummary, secondary: EntitySummary, strategy: Strategy) => Promise<void>;
  onDismiss: (a: EntitySummary, b: EntitySummary) => Promise<void>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [primary, setPrimary] = useState<"a" | "b">("a");
  const [strategy, setStrategy] = useState<Strategy>("keep_non_empty");
  const [merging, setMerging] = useState(false);
  const [dismissing, setDismissing] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  const { entity_a, entity_b, similarity, common_tokens } = candidate;
  const sim = simLabel(similarity);

  if (dismissed) return null;

  async function handleMerge() {
    setMerging(true);
    const [prim, sec] = primary === "a" ? [entity_a, entity_b] : [entity_b, entity_a];
    await onMerge(prim, sec, strategy);
    setMerging(false);
    setDismissed(true);
  }

  async function handleDismiss() {
    setDismissing(true);
    await onDismiss(entity_a, entity_b);
    setDismissed(true);
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900">
      {/* Header row */}
      <div className="flex items-center justify-between gap-4 border-b border-gray-100 px-4 py-3 dark:border-gray-800">
        <div className="flex items-center gap-3 min-w-0">
          <Badge variant={sim.variant} size="md">
            {(similarity * 100).toFixed(1)}% — {sim.label}
          </Badge>
          {common_tokens.length > 0 && (
            <span className="hidden truncate text-xs text-gray-400 dark:text-gray-500 sm:block">
              Common: {common_tokens.slice(0, 6).join(" · ")}
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 dark:border-blue-500/30 dark:bg-blue-500/10 dark:text-blue-400 dark:hover:bg-blue-500/20"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            Merge
          </button>
          <button
            onClick={handleDismiss}
            disabled={dismissing}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
            Not a duplicate
          </button>
        </div>
      </div>

      {/* Field comparison table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-800">
              <th className="pb-2 pl-3 pt-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-400 w-24" />
              <th className="pb-2 pt-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                Entity #{entity_a.id}
              </th>
              <th className="pb-2 pr-3 pt-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                Entity #{entity_b.id}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50 dark:divide-gray-800/50">
            {DISPLAY_FIELDS.map(({ key, label }) => (
              <FieldRow
                key={key}
                label={label}
                valA={entity_a[key] as string | null}
                valB={entity_b[key] as string | null}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Merge panel (inline expand) */}
      {expanded && (
        <div className="border-t border-blue-100 bg-blue-50/50 px-4 py-4 dark:border-blue-500/20 dark:bg-blue-500/5">
          <p className="mb-3 text-xs font-semibold text-blue-800 dark:text-blue-300">
            Configure merge
          </p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {/* Primary selector */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">
                Keep as primary (survives merge)
              </label>
              <div className="flex gap-2">
                {(["a", "b"] as const).map((side) => {
                  const entity = side === "a" ? entity_a : entity_b;
                  return (
                    <button
                      key={side}
                      onClick={() => setPrimary(side)}
                      className={`flex-1 rounded-xl border py-2 px-3 text-left text-xs transition-colors ${
                        primary === side
                          ? "border-blue-400 bg-blue-600 text-white"
                          : "border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
                      }`}
                    >
                      <span className="font-semibold">#{entity.id}</span>
                      <span className="ml-1 opacity-80 truncate">
                        {entity.entity_name?.slice(0, 20) ?? "—"}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Strategy selector */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">
                Field merge strategy
              </label>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value as Strategy)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-gray-900 focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-white"
              >
                {(Object.entries(STRATEGY_LABELS) as [Strategy, string][]).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="mt-4 flex gap-2">
            <button
              onClick={handleMerge}
              disabled={merging}
              className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {merging ? (
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              )}
              Confirm Merge
            </button>
            <button
              onClick={() => setExpanded(false)}
              className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function EntityLinkerPage() {
  const { toast } = useToast();
  const [threshold, setThreshold] = useState(0.82);
  const [limit, setLimit]         = useState(500);
  const [scanning, setScanning]   = useState(false);
  const [result, setResult]       = useState<ScanResult | null>(null);
  const [merged, setMerged]       = useState(0);
  const [dismissed, setDismissed] = useState(0);

  const handleScan = useCallback(async () => {
    setScanning(true);
    try {
      const res = await apiFetch("/entities/link/find", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ threshold, limit }),
      });
      if (!res.ok) {
        toast(`Scan failed: ${await res.text()}`, "error");
        return;
      }
      const data: ScanResult = await res.json();
      setResult(data);
      setMerged(0);
      setDismissed(0);
      if (data.total === 0) {
        toast("No duplicate candidates found above threshold", "success");
      } else {
        toast(`Found ${data.total} candidate pair${data.total === 1 ? "" : "s"}`, "success");
      }
    } catch {
      toast("Failed to reach backend", "error");
    } finally {
      setScanning(false);
    }
  }, [threshold, limit, toast]);

  const handleMerge = useCallback(async (
    primary: EntitySummary,
    secondary: EntitySummary,
    strategy: Strategy,
  ) => {
    try {
      const res = await apiFetch("/entities/link/merge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          primary_id:    primary.id,
          secondary_ids: [secondary.id],
          strategy,
        }),
      });
      if (!res.ok) {
        toast(`Merge failed: ${await res.text()}`, "error");
        return;
      }
      setMerged((n) => n + 1);
      toast(`Entity #${secondary.id} merged into #${primary.id}`, "success");
    } catch {
      toast("Merge request failed", "error");
    }
  }, [toast]);

  const handleDismiss = useCallback(async (
    a: EntitySummary,
    b: EntitySummary,
  ) => {
    try {
      await apiFetch("/entities/link/dismiss", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entity_a_id: a.id, entity_b_id: b.id }),
      });
      setDismissed((n) => n + 1);
    } catch {
      toast("Dismiss request failed", "error");
    }
  }, [toast]);

  const limitOptions = [250, 500, 1000, 2000];

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumbs={[
          { label: "Home", href: "/" },
          { label: "Data" },
          { label: "Entity Linker" },
        ]}
        title="Entity Linker"
        description="Find and merge near-duplicate entities using TF-IDF cosine similarity"
        actions={
          <button
            onClick={handleScan}
            disabled={scanning}
            className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {scanning ? (
              <>
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Scanning…
              </>
            ) : (
              <>
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803 7.5 7.5 0 0016.803 15.803z" />
                </svg>
                Run Scan
              </>
            )}
          </button>
        }
      />

      {/* Config panel */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          {/* Threshold */}
          <div>
            <div className="mb-1 flex items-center justify-between">
              <label className="text-xs font-medium text-gray-600 dark:text-gray-400">
                Similarity Threshold
              </label>
              <span className="rounded-lg bg-blue-100 px-2 py-0.5 text-xs font-bold text-blue-700 dark:bg-blue-500/20 dark:text-blue-400">
                {(threshold * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min={0.50} max={0.99} step={0.01}
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              className="w-full h-1.5 accent-blue-600"
            />
            <div className="mt-0.5 flex justify-between text-[10px] text-gray-400">
              <span>50% — broader</span>
              <span>99% — stricter</span>
            </div>
            <p className="mt-1.5 text-xs text-gray-400 dark:text-gray-500">
              {threshold >= 0.95
                ? "Only virtually identical entities"
                : threshold >= 0.88
                ? "Very likely duplicates (recommended for merging)"
                : threshold >= 0.80
                ? "Likely duplicates — some false positives expected"
                : "Broad scan — many false positives, review carefully"}
            </p>
          </div>

          {/* Limit */}
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">
              Entities to scan
            </label>
            <div className="flex gap-2">
              {limitOptions.map((n) => (
                <button
                  key={n}
                  onClick={() => setLimit(n)}
                  className={`flex-1 rounded-lg py-2 text-sm font-semibold transition-colors ${
                    limit === n
                      ? "bg-blue-600 text-white"
                      : "border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
                  }`}
                >
                  {n >= 1000 ? `${n / 1000}K` : n}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-xs text-gray-400 dark:text-gray-500">
              Higher limits increase scan time. 500 is recommended for most catalogs.
            </p>
          </div>
        </div>
      </div>

      {/* Results area */}
      {!result ? (
        <div className="flex min-h-[280px] items-center justify-center rounded-2xl border-2 border-dashed border-gray-200 dark:border-gray-700">
          <div className="text-center">
            <svg className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <p className="mt-3 text-sm font-medium text-gray-500 dark:text-gray-400">
              Configure threshold and run a scan
            </p>
            <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
              Candidate pairs will appear here
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Summary bar */}
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-semibold text-gray-900 dark:text-white">
              {result.total} candidate pair{result.total !== 1 ? "s" : ""} found
            </span>
            <Badge variant="default" size="sm">
              {(result.threshold * 100).toFixed(0)}% threshold
            </Badge>
            <Badge variant="default" size="sm">
              {result.scanned} entities scanned
            </Badge>
            {merged > 0 && <Badge variant="success" size="sm">{merged} merged</Badge>}
            {dismissed > 0 && <Badge variant="warning" size="sm">{dismissed} dismissed</Badge>}
          </div>

          {result.total === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-gray-200 bg-white py-16 dark:border-gray-700 dark:bg-gray-900">
              <svg className="h-10 w-10 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="mt-3 text-sm font-medium text-gray-600 dark:text-gray-400">
                No duplicates detected above {(result.threshold * 100).toFixed(0)}% similarity
              </p>
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                Try lowering the threshold for a broader scan
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {result.candidates.map((c, i) => (
                <CandidateCard
                  key={`${c.entity_a.id}-${c.entity_b.id}-${i}`}
                  candidate={c}
                  onMerge={handleMerge}
                  onDismiss={handleDismiss}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
