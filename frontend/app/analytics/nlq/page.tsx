"use client";

import { useState, useRef, useCallback } from "react";
import Link from "next/link";
import { useDomain } from "../../contexts/DomainContext";
import { apiFetch } from "@/lib/api";
import { Analytics } from "@/lib/analytics";

// ── Types ─────────────────────────────────────────────────────────────────────

interface TranslatedQuery {
  group_by: string[];
  filters: Record<string, string>;
  explanation: string;
}

interface CubeRow {
  values: Record<string, string>;
  count: number;
  pct: number;
}

interface NLQResult {
  question: string;
  translated: TranslatedQuery;
  result: {
    domain_id: string;
    group_by: string[];
    filters: Record<string, string>;
    total: number;
    rows: CubeRow[];
  };
}

// ── Example questions ─────────────────────────────────────────────────────────

const EXAMPLES = [
  "Show publications grouped by year",
  "Which countries have the most entities?",
  "Top research fields by count",
  "Entities by enrichment status",
  "Publications from 2022 grouped by topic",
  "Distribution by source",
];

// ── Sub-components ────────────────────────────────────────────────────────────

function PctBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 rounded-full bg-gray-100 dark:bg-gray-800 flex-shrink-0">
        <div
          className="h-1.5 rounded-full bg-violet-500 transition-all duration-700"
          style={{ width: `${Math.min(value, 100)}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-gray-400 w-9 text-right">
        {value.toFixed(1)}%
      </span>
    </div>
  );
}

function TranslationCard({ translated, onOpenOLAP }: {
  translated: TranslatedQuery;
  onOpenOLAP: () => void;
}) {
  return (
    <div className="rounded-2xl border border-violet-200 bg-violet-50 p-5 dark:border-violet-500/30 dark:bg-violet-900/10">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-violet-100 dark:bg-violet-500/20">
            <svg className="h-4 w-4 text-violet-600 dark:text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          </div>
          <span className="text-sm font-semibold text-violet-800 dark:text-violet-300">
            AI Interpretation
          </span>
        </div>
        <button
          onClick={onOpenOLAP}
          className="flex items-center gap-1 text-xs font-medium text-violet-600 hover:text-violet-800 dark:text-violet-400 dark:hover:text-violet-200 transition-colors"
        >
          Edit in OLAP Explorer →
        </button>
      </div>

      <p className="mt-3 text-sm text-violet-700 dark:text-violet-300">
        {translated.explanation}
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        {translated.group_by.map((dim) => (
          <span
            key={dim}
            className="flex items-center gap-1 rounded-full bg-violet-200 px-3 py-1 text-xs font-medium text-violet-800 dark:bg-violet-500/30 dark:text-violet-200"
          >
            <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h8m-8 6h16" />
            </svg>
            Group by: {dim}
          </span>
        ))}
        {Object.entries(translated.filters).map(([k, v]) => (
          <span
            key={k}
            className="flex items-center gap-1 rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800 dark:bg-amber-500/20 dark:text-amber-300"
          >
            <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
            </svg>
            {k} = {v}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function NLQPage() {
  const { activeDomainId, activeDomain } = useDomain();
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<NLQResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [visibleRows, setVisibleRows] = useState(50);
  const inputRef = useRef<HTMLInputElement>(null);

  const ask = useCallback(async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setVisibleRows(50);

    try {
      const res = await apiFetch("/nlq/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed, domain_id: activeDomainId }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail ?? "Query failed");
      } else {
        setResult(data);
        Analytics.olapQuery(activeDomainId, data.translated.group_by.length);
      }
    } catch {
      setError("Network error — check your connection.");
    } finally {
      setLoading(false);
    }
  }, [activeDomainId]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    ask(question);
  };

  const handleExample = (ex: string) => {
    setQuestion(ex);
    ask(ex);
    inputRef.current?.focus();
  };

  const olapHref = result
    ? `/analytics/olap`
    : "/analytics/olap";

  const isCrossTab = result && result.result.group_by.length === 2;
  const rows = result?.result.rows.slice(0, visibleRows) ?? [];
  const hasMore = result ? visibleRows < result.result.rows.length : false;

  return (
    <div className="flex flex-col gap-8 pb-12">
      {/* ── Breadcrumb ── */}
      <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
        <Link href="/analytics" className="hover:text-gray-800 dark:hover:text-gray-200 transition-colors">
          Analytics
        </Link>
        <span>/</span>
        <span className="text-gray-900 dark:text-white font-medium">Natural Language Query</span>
        {activeDomain && (
          <span className="ml-1 rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-700 dark:bg-violet-500/20 dark:text-violet-300">
            {activeDomain.name}
          </span>
        )}
      </div>

      {/* ── Hero ── */}
      <div className="text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-600 to-purple-600 shadow-lg">
          <svg className="h-8 w-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
          </svg>
        </div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Ask your data anything
        </h1>
        <p className="mt-2 text-gray-500 dark:text-gray-400 max-w-lg mx-auto">
          Type a question in plain English. AI will translate it into an OLAP query and show you the results instantly.
        </p>
      </div>

      {/* ── Search bar ── */}
      <form onSubmit={handleSubmit} className="mx-auto w-full max-w-2xl">
        <div className="relative">
          <div className="pointer-events-none absolute inset-y-0 left-4 flex items-center">
            {loading ? (
              <svg className="h-5 w-5 animate-spin text-violet-500" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
            ) : (
              <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
              </svg>
            )}
          </div>
          <input
            ref={inputRef}
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. Show me publications grouped by country and year…"
            disabled={loading}
            className="w-full rounded-2xl border-2 border-gray-200 bg-white py-4 pl-12 pr-32 text-base text-gray-900 shadow-sm outline-none transition-all placeholder-gray-400 focus:border-violet-500 focus:ring-4 focus:ring-violet-100 disabled:opacity-60 dark:border-gray-700 dark:bg-gray-900 dark:text-white dark:placeholder-gray-500 dark:focus:border-violet-500 dark:focus:ring-violet-500/10"
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="absolute inset-y-2 right-2 flex items-center gap-2 rounded-xl bg-violet-600 px-5 text-sm font-semibold text-white transition hover:bg-violet-700 disabled:opacity-40"
          >
            {loading ? "Thinking…" : "Ask AI"}
          </button>
        </div>

        {/* Example chips */}
        {!result && !loading && (
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => handleExample(ex)}
                className="rounded-full border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-600 transition hover:border-violet-300 hover:bg-violet-50 hover:text-violet-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400 dark:hover:border-violet-500/40 dark:hover:bg-violet-500/10 dark:hover:text-violet-300"
              >
                {ex}
              </button>
            ))}
          </div>
        )}
      </form>

      {/* ── Error ── */}
      {error && (
        <div className="mx-auto w-full max-w-2xl rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/10 dark:text-red-400">
          <div className="flex items-start gap-2">
            <svg className="mt-0.5 h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
            {error}
          </div>
        </div>
      )}

      {/* ── Loading state ── */}
      {loading && (
        <div className="mx-auto flex w-full max-w-2xl flex-col items-center gap-3 py-8">
          <div className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="h-2.5 w-2.5 rounded-full bg-violet-500 animate-bounce"
                style={{ animationDelay: `${i * 150}ms` }}
              />
            ))}
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            AI is interpreting your question…
          </p>
        </div>
      )}

      {/* ── Results ── */}
      {result && !loading && (
        <div className="flex flex-col gap-5">
          {/* Re-ask bar (compact) */}
          <div className="flex items-center gap-3 rounded-xl bg-gray-50 px-4 py-3 dark:bg-gray-800/50">
            <svg className="h-4 w-4 shrink-0 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
            </svg>
            <span className="flex-1 text-sm text-gray-700 dark:text-gray-300 italic">
              &ldquo;{result.question}&rdquo;
            </span>
            <button
              onClick={() => { setResult(null); setQuestion(""); setTimeout(() => inputRef.current?.focus(), 50); }}
              className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
            >
              New question
            </button>
          </div>

          {/* Translation card */}
          <TranslationCard
            translated={result.translated}
            onOpenOLAP={() => window.open(olapHref, "_blank")}
          />

          {/* Results table */}
          <div className="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3.5 dark:border-gray-800">
              <div className="flex items-center gap-3">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Results</h3>
                <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                  {result.result.rows.length} groups · {result.result.total.toLocaleString()} records
                </span>
                {isCrossTab && (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                    Cross-tab
                  </span>
                )}
              </div>
              <Link
                href={olapHref}
                className="flex items-center gap-1 text-xs font-medium text-violet-600 hover:text-violet-800 dark:text-violet-400 transition-colors"
              >
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                </svg>
                Open in OLAP Explorer
              </Link>
            </div>

            {result.result.rows.length === 0 ? (
              <div className="py-12 text-center text-sm text-gray-400">
                No data matched. Try adjusting your question or removing filters.
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-800/60">
                      <tr>
                        <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                          {result.result.group_by[0]}
                        </th>
                        {isCrossTab && (
                          <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                            {result.result.group_by[1]}
                          </th>
                        )}
                        <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                          Count
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                          Share
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                      {rows.map((row, i) => (
                        <tr
                          key={i}
                          className="hover:bg-violet-50/40 dark:hover:bg-violet-500/5 transition-colors"
                        >
                          <td className="px-5 py-3 font-medium text-gray-900 dark:text-white">
                            {row.values[result.result.group_by[0]] ?? (
                              <span className="italic text-gray-400">null</span>
                            )}
                          </td>
                          {isCrossTab && (
                            <td className="px-4 py-3 text-gray-600 dark:text-gray-300">
                              {row.values[result.result.group_by[1]] ?? (
                                <span className="italic text-gray-400">null</span>
                              )}
                            </td>
                          )}
                          <td className="px-4 py-3 text-right tabular-nums font-semibold text-violet-600 dark:text-violet-400">
                            {row.count.toLocaleString()}
                          </td>
                          <td className="px-4 py-3">
                            <PctBar value={row.pct} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {hasMore && (
                  <div className="flex items-center justify-center gap-3 border-t border-gray-100 py-3 dark:border-gray-800">
                    <span className="text-xs text-gray-400">
                      {result.result.rows.length - visibleRows} more rows
                    </span>
                    <button
                      onClick={() => setVisibleRows(v => v + 50)}
                      className="rounded-lg border border-gray-200 bg-white px-4 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400"
                    >
                      Load more
                    </button>
                    <button
                      onClick={() => setVisibleRows(result.result.rows.length)}
                      className="text-xs text-violet-600 hover:underline dark:text-violet-400"
                    >
                      Show all
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Empty state (initial) ── */}
      {!result && !loading && !error && (
        <div className="mx-auto flex w-full max-w-lg flex-col items-center gap-3 py-6 text-center">
          <div className="grid grid-cols-3 gap-3 opacity-60">
            {["📊 Group by year", "🌍 Filter by country", "🔬 Top research fields"].map((t) => (
              <div key={t} className="rounded-xl border border-gray-200 bg-white p-3 text-xs text-gray-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400">
                {t}
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">
            Requires an active AI provider — configure in{" "}
            <Link href="/integrations" className="text-violet-600 hover:underline dark:text-violet-400">
              Integrations → AI Language Models
            </Link>
          </p>
        </div>
      )}
    </div>
  );
}
