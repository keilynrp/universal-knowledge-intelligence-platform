"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { PageHeader, Badge } from "../../components/ui";

// ── Types ──────────────────────────────────────────────────────────────────────

interface EntitySnap {
  id:                number;
  entity_name:       string | null;
  brand_capitalized: string | null;
  model:             string | null;
  sku:               string | null;
  enrichment_status: string;
  validation_status: string;
}

interface LinkCandidate {
  entity_a:       EntitySnap;
  entity_b:       EntitySnap;
  score:          number;       // 0.0 – 1.0
  matched_fields: string[];
}

interface Dismissal {
  id:          number;
  entity_a_id: number;
  entity_b_id: number;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function simLabel(s: number): { label: string; variant: "error" | "warning" | "info" | "default" } {
  if (s >= 0.95) return { label: "Identical",  variant: "error"   };
  if (s >= 0.88) return { label: "Very High",  variant: "warning" };
  if (s >= 0.80) return { label: "High",       variant: "info"    };
  return               { label: "Moderate",    variant: "default" };
}

const DISPLAY_FIELDS: Array<{ key: keyof EntitySnap; label: string }> = [
  { key: "entity_name",       label: "Name"   },
  { key: "brand_capitalized", label: "Primary Label"  },
  { key: "model",             label: "Secondary Label"  },
  { key: "sku",               label: "SKU"    },
];

function FieldRow({ label, valA, valB }: { label: string; valA: string | null; valB: string | null }) {
  const diff = (valA || "") !== (valB || "");
  return (
    <tr className={diff ? "bg-amber-50/40 dark:bg-amber-500/5" : ""}>
      <td className="w-20 shrink-0 py-1.5 pl-3 pr-2 text-xs font-medium text-gray-500 dark:text-gray-400">{label}</td>
      <td className="max-w-[180px] truncate py-1.5 pr-2 text-xs text-gray-900 dark:text-white">
        {valA || <span className="italic text-gray-300 dark:text-gray-600">—</span>}
      </td>
      <td className="max-w-[180px] truncate py-1.5 pr-3 text-xs text-gray-900 dark:text-white">
        {valB || <span className="italic text-gray-300 dark:text-gray-600">—</span>}
      </td>
    </tr>
  );
}

// ── CandidateCard ─────────────────────────────────────────────────────────────

function CandidateCard({
  candidate,
  onMerge,
  onDismiss,
}: {
  candidate: LinkCandidate;
  onMerge:   (winnerId: number, loserId: number) => Promise<void>;
  onDismiss: (aId: number, bId: number) => Promise<void>;
}) {
  const [expanded,   setExpanded]  = useState(false);
  const [primary,    setPrimary]   = useState<"a" | "b">("a");
  const [merging,    setMerging]   = useState(false);
  const [dismissing, setDismissing] = useState(false);
  const [resolved,   setResolved]  = useState(false);

  const { entity_a, entity_b, score, matched_fields } = candidate;
  const sim = simLabel(score);

  if (resolved) return null;

  async function handleMerge() {
    setMerging(true);
    const [wId, lId] = primary === "a"
      ? [entity_a.id, entity_b.id]
      : [entity_b.id, entity_a.id];
    await onMerge(wId, lId);
    setMerging(false);
    setResolved(true);
  }

  async function handleDismiss() {
    setDismissing(true);
    await onDismiss(entity_a.id, entity_b.id);
    setDismissed(true);
    setResolved(true);
  }

  function setDismissed(_v: boolean) {}   // local state already tracked by resolved

  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 border-b border-gray-100 px-4 py-3 dark:border-gray-800">
        <div className="flex min-w-0 items-center gap-3">
          <Badge variant={sim.variant} size="md">
            {Math.round(score * 100)}% — {sim.label}
          </Badge>
          {matched_fields.length > 0 && (
            <span className="hidden truncate text-xs text-gray-400 dark:text-gray-500 sm:block">
              Matched: {matched_fields.join(" · ")}
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 dark:border-blue-500/30 dark:bg-blue-500/10 dark:text-blue-400"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l-1.757 1.757a4.5 4.5 0 01-6.364-6.364l4.5-4.5a4.5 4.5 0 011.242 7.244" />
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
              <th className="w-20 pb-2 pl-3 pt-2.5" />
              <th className="pb-2 pt-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                <Link href={`/entities/${entity_a.id}`} className="hover:text-blue-600 hover:underline">
                  Entity #{entity_a.id}
                </Link>
              </th>
              <th className="pb-2 pr-3 pt-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                <Link href={`/entities/${entity_b.id}`} className="hover:text-blue-600 hover:underline">
                  Entity #{entity_b.id}
                </Link>
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

      {/* Merge panel */}
      {expanded && (
        <div className="border-t border-blue-100 bg-blue-50/50 px-4 py-4 dark:border-blue-500/20 dark:bg-blue-500/5">
          <p className="mb-3 text-xs font-semibold text-blue-800 dark:text-blue-300">
            Choose which entity to keep (winner absorbs the other's empty fields)
          </p>
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
                  <span className="ml-1 truncate opacity-80">
                    {entity.entity_name?.slice(0, 22) ?? "—"}
                  </span>
                </button>
              );
            })}
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
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l-1.757 1.757a4.5 4.5 0 01-6.364-6.364l4.5-4.5a4.5 4.5 0 011.242 7.244" />
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
  const [threshold,     setThreshold]     = useState(0.82);
  const [scanning,      setScanning]      = useState(false);
  const [candidates,    setCandidates]    = useState<LinkCandidate[] | null>(null);
  const [error,         setError]         = useState<string | null>(null);
  const [dismissals,    setDismissals]    = useState<Dismissal[]>([]);
  const [showDismissed, setShowDismissed] = useState(false);

  const fetchDismissals = useCallback(async () => {
    const r = await apiFetch("/linker/dismissals");
    if (r.ok) setDismissals(await r.json());
  }, []);

  useEffect(() => { fetchDismissals(); }, [fetchDismissals]);

  async function handleScan() {
    setScanning(true);
    setError(null);
    try {
      const r = await apiFetch(`/linker/candidates?threshold=${threshold}&limit=20`);
      if (!r.ok) { setError(await r.text()); return; }
      setCandidates(await r.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setScanning(false);
    }
  }

  const handleMerge = useCallback(async (winnerId: number, loserId: number) => {
    const r = await apiFetch("/linker/merge", {
      method: "POST",
      body: JSON.stringify({ winner_id: winnerId, loser_id: loserId }),
    });
    if (!r.ok) setError(await r.text());
  }, []);

  const handleDismiss = useCallback(async (aId: number, bId: number) => {
    await apiFetch("/linker/dismiss", {
      method: "POST",
      body: JSON.stringify({ entity_a_id: aId, entity_b_id: bId }),
    });
    fetchDismissals();
  }, [fetchDismissals]);

  async function undoDismissal(id: number) {
    const r = await apiFetch(`/linker/dismissals/${id}`, { method: "DELETE" });
    if (r.ok || r.status === 204) {
      setDismissals(prev => prev.filter(d => d.id !== id));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumbs={[
          { label: "Home", href: "/" },
          { label: "Data" },
          { label: "Entity Linker" },
        ]}
        title="Entity Linker"
        description="Find and merge near-duplicate entities using fuzzy field matching"
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
        <div className="flex items-center gap-6">
          <div className="flex-1">
            <div className="mb-1 flex items-center justify-between">
              <label className="text-xs font-medium text-gray-600 dark:text-gray-400">
                Similarity Threshold
              </label>
              <span className="rounded-lg bg-blue-100 px-2 py-0.5 text-xs font-bold text-blue-700 dark:bg-blue-500/20 dark:text-blue-400">
                {Math.round(threshold * 100)}%
              </span>
            </div>
            <input
              type="range" min={50} max={99} step={1}
              value={Math.round(threshold * 100)}
              onChange={(e) => setThreshold(Number(e.target.value) / 100)}
              className="h-1.5 w-full accent-blue-600"
            />
            <div className="mt-0.5 flex justify-between text-[10px] text-gray-400">
              <span>50% — broader</span>
              <span>99% — stricter</span>
            </div>
          </div>
          <p className="max-w-xs text-xs text-gray-400 dark:text-gray-500">
            {threshold >= 0.95
              ? "Only virtually identical entities"
              : threshold >= 0.88
              ? "Very likely duplicates — recommended for merging"
              : threshold >= 0.80
              ? "Likely duplicates — some false positives expected"
              : "Broad scan — review carefully"}
          </p>
        </div>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      {/* Results */}
      {candidates === null ? (
        <div className="flex min-h-[260px] items-center justify-center rounded-2xl border-2 border-dashed border-gray-200 dark:border-gray-700">
          <div className="text-center">
            <svg className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l-1.757 1.757a4.5 4.5 0 01-6.364-6.364l4.5-4.5a4.5 4.5 0 011.242 7.244" />
            </svg>
            <p className="mt-3 text-sm font-medium text-gray-500 dark:text-gray-400">
              Configure threshold and run a scan
            </p>
          </div>
        </div>
      ) : candidates.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-gray-200 bg-white py-16 dark:border-gray-700 dark:bg-gray-900">
          <svg className="h-10 w-10 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="mt-3 text-sm font-medium text-gray-600 dark:text-gray-400">
            No duplicates found above {Math.round(threshold * 100)}% similarity
          </p>
          <p className="mt-1 text-xs text-gray-400">Try lowering the threshold</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-gray-900 dark:text-white">
              {candidates.length} candidate pair{candidates.length !== 1 ? "s" : ""}
            </span>
            <Badge variant="default" size="sm">{Math.round(threshold * 100)}% threshold</Badge>
          </div>
          <div className="space-y-3">
            {candidates.map((c) => (
              <CandidateCard
                key={`${c.entity_a.id}-${c.entity_b.id}`}
                candidate={c}
                onMerge={handleMerge}
                onDismiss={handleDismiss}
              />
            ))}
          </div>
        </div>
      )}

      {/* Dismissed pairs */}
      {dismissals.length > 0 && (
        <div className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
          <button
            onClick={() => setShowDismissed(!showDismissed)}
            className="flex w-full items-center justify-between px-5 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <span>Dismissed pairs ({dismissals.length})</span>
            <svg
              className={`h-4 w-4 transition-transform ${showDismissed ? "rotate-180" : ""}`}
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {showDismissed && (
            <div className="border-t border-gray-100 px-5 py-3 dark:border-gray-800">
              <ul className="space-y-2">
                {dismissals.map((d) => (
                  <li key={d.id} className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                    <span>
                      Entity{" "}
                      <Link href={`/entities/${d.entity_a_id}`} className="text-blue-500 hover:underline">
                        #{d.entity_a_id}
                      </Link>
                      {" "}+{" "}
                      <Link href={`/entities/${d.entity_b_id}`} className="text-blue-500 hover:underline">
                        #{d.entity_b_id}
                      </Link>
                    </span>
                    <button
                      onClick={() => undoDismissal(d.id)}
                      className="text-xs text-blue-600 hover:underline dark:text-blue-400"
                    >
                      Undo
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
