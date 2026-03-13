"use client";

import { useState, useEffect, useCallback, Suspense, ReactElement } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────

interface SearchResult {
  doc_type: "entity" | "authority" | "annotation";
  doc_id:   number;
  title:    string;
  snippet:  string;
  href:     string;
}

interface SearchPage {
  total: number;
  skip:  number;
  limit: number;
  items: SearchResult[];
}

// ── Constants ──────────────────────────────────────────────────────────────────

const PAGE_SIZE = 20;

const TYPE_LABELS: Record<string, string> = {
  entity:     "Entity",
  authority:  "Authority",
  annotation: "Annotation",
};

const TYPE_STYLES: Record<string, string> = {
  entity:     "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  authority:  "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  annotation: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
};

const TYPE_ICONS: Record<string, ReactElement> = {
  entity: (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
    </svg>
  ),
  authority: (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
    </svg>
  ),
  annotation: (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
    </svg>
  ),
};

// ── Inner page (uses useSearchParams — must be wrapped in Suspense) ────────────

function SearchInner() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const initialQ       = searchParams.get("q") ?? "";
  const initialType    = searchParams.get("type") ?? "";

  const [query,    setQuery]    = useState(initialQ);
  const [docType,  setDocType]  = useState(initialType);
  const [results,  setResults]  = useState<SearchPage | null>(null);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState<string | null>(null);
  const [skip,     setSkip]     = useState(0);

  const doSearch = useCallback(async (q: string, type: string, currentSkip: number) => {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ q, limit: String(PAGE_SIZE), skip: String(currentSkip) });
      if (type) params.set("doc_type", type);
      const res = await apiFetch(`/search?${params}`);
      if (!res.ok) { setError(await res.text()); return; }
      setResults(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }, []);

  // Run on mount if ?q= is present
  useEffect(() => {
    if (initialQ) doSearch(initialQ, initialType, 0);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSkip(0);
    router.push(`/search?q=${encodeURIComponent(query)}${docType ? `&type=${docType}` : ""}`);
    doSearch(query, docType, 0);
  }

  function handleTypeFilter(t: string) {
    setDocType(t);
    setSkip(0);
    doSearch(query, t, 0);
  }

  function handlePage(newSkip: number) {
    setSkip(newSkip);
    doSearch(query, docType, newSkip);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const totalPages  = results ? Math.ceil(results.total / PAGE_SIZE) : 0;
  const currentPage = Math.floor(skip / PAGE_SIZE) + 1;

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">

      {/* ── Search form ─────────────────────────────────────────────────── */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <div className="pointer-events-none absolute inset-y-0 left-3 flex items-center">
            <svg className="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search entities, authority records, annotations…"
            className="w-full rounded-xl border border-gray-300 bg-white py-2.5 pl-9 pr-4 text-sm text-gray-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          />
        </div>
        <button
          type="submit"
          className="rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          Search
        </button>
      </form>

      {/* ── Type filter pills ────────────────────────────────────────────── */}
      {results && (
        <div className="flex flex-wrap gap-2">
          {["", "entity", "authority", "annotation"].map((t) => (
            <button
              key={t}
              onClick={() => handleTypeFilter(t)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                docType === t
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              }`}
            >
              {t === "" ? `All (${results.total})` : TYPE_LABELS[t]}
            </button>
          ))}
        </div>
      )}

      {/* ── Error ────────────────────────────────────────────────────────── */}
      {error && (
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      )}

      {/* ── Loading ──────────────────────────────────────────────────────── */}
      {loading && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="animate-pulse rounded-xl border border-gray-200 p-4 dark:border-gray-700">
              <div className="mb-2 h-4 w-1/3 rounded bg-gray-200 dark:bg-gray-700" />
              <div className="h-3 w-2/3 rounded bg-gray-100 dark:bg-gray-800" />
            </div>
          ))}
        </div>
      )}

      {/* ── Results ──────────────────────────────────────────────────────── */}
      {!loading && results && (
        <>
          {results.items.length === 0 ? (
            <div className="rounded-xl border border-gray-200 bg-white px-6 py-12 text-center dark:border-gray-700 dark:bg-gray-900">
              <svg className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                No results found for <strong>&ldquo;{query}&rdquo;</strong>.
              </p>
              <p className="mt-1 text-xs text-gray-400">Try a different term or rebuild the search index via Settings.</p>
            </div>
          ) : (
            <ul className="space-y-2">
              {results.items.map((item) => (
                <li key={`${item.doc_type}-${item.doc_id}`}>
                  <Link
                    href={item.href}
                    className="flex items-start gap-4 rounded-xl border border-gray-200 bg-white p-4 hover:border-blue-300 hover:shadow-sm transition-all dark:border-gray-700 dark:bg-gray-900 dark:hover:border-blue-700"
                  >
                    <span className={`mt-0.5 shrink-0 rounded-md p-1.5 ${TYPE_STYLES[item.doc_type] ?? ""}`}>
                      {TYPE_ICONS[item.doc_type]}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-sm font-semibold text-gray-900 dark:text-white">
                          {item.title || "(no title)"}
                        </p>
                        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_STYLES[item.doc_type] ?? ""}`}>
                          {TYPE_LABELS[item.doc_type] ?? item.doc_type}
                        </span>
                      </div>
                      {item.snippet && (
                        <p className="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">
                          {item.snippet}
                        </p>
                      )}
                    </div>
                    <svg className="mt-1 h-4 w-4 shrink-0 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </Link>
                </li>
              ))}
            </ul>
          )}

          {/* Pagination */}
          {results.total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <button
                onClick={() => handlePage(Math.max(0, skip - PAGE_SIZE))}
                disabled={skip === 0}
                className="flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-600 dark:text-gray-300"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                Prev
              </button>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Page {currentPage} of {totalPages}
              </span>
              <button
                onClick={() => handlePage(skip + PAGE_SIZE)}
                disabled={skip + PAGE_SIZE >= results.total}
                className="flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-600 dark:text-gray-300"
              >
                Next
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          )}
        </>
      )}

      {/* ── Empty state (no query yet) ───────────────────────────────────── */}
      {!loading && !results && !error && (
        <div className="rounded-xl border border-dashed border-gray-300 bg-white px-6 py-14 text-center dark:border-gray-700 dark:bg-gray-900">
          <svg className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
            Search across entities, authority records, and annotations
          </p>
          <p className="mt-1 text-xs text-gray-400">Powered by SQLite FTS5 full-text search</p>
        </div>
      )}
    </div>
  );
}

// ── Page (Suspense boundary required for useSearchParams) ─────────────────────

export default function SearchPage() {
  return (
    <Suspense>
      <SearchInner />
    </Suspense>
  );
}
