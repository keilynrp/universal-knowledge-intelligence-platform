"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { useTheme } from "../contexts/ThemeContext";
import { useDomain } from "../contexts/DomainContext";
import { useBranding } from "../contexts/BrandingContext";
import { useSidebar } from "./SidebarProvider";
import NotificationBell from "./NotificationBell";
import UserMenu from "./UserMenu";
import { apiFetch } from "@/lib/api";

// ── Page title map ──────────────────────────────────────────────────────────────

const pageTitles: Record<string, { title: string; subtitle: string }> = {
  "/": { title: "Master Data Hub", subtitle: "Browse and search your entity database" },
  "/disambiguation": { title: "Data Disambiguation", subtitle: "Find and resolve data inconsistencies" },
  "/analytics": { title: "Analytics", subtitle: "Key metrics and data quality insights" },
  "/authority": { title: "Authority Control", subtitle: "Normalize and harmonize field values with canonical rules" },
  "/harmonization": { title: "Data Harmonization", subtitle: "Automated pipeline for cleaning and consolidating entity data" },
  "/import-export": { title: "Import / Export", subtitle: "Upload and download dataset in Excel format" },
  "/rag": { title: "Semantic RAG", subtitle: "AI-powered retrieval and semantic analysis" },
  "/domains": { title: "Domain Registry", subtitle: "Manage workspace schemas and entity type definitions" },
  "/analytics/olap": { title: "OLAP Cube Explorer", subtitle: "Multi-dimensional analysis and drill-down across your data" },
  "/analytics/topics": { title: "Topic Modeling", subtitle: "Concept frequency, co-occurrence, clusters, and field correlations" },
  "/artifacts": { title: "Artifact Studio", subtitle: "Build and export strategic intelligence artifacts" },
  "/artifacts/gaps": { title: "Knowledge Gap Detector", subtitle: "Identify and prioritize data quality issues in your domain" },
  "/context":   { title: "Context Engineering", subtitle: "Domain context snapshots, sessions, and tool invocations" },
  "/audit-log": { title: "Audit Log", subtitle: "Complete history of all platform mutations and user activity" },
  "/search":    { title: "Search", subtitle: "Full-text search across entities, authority records, and annotations" },
};

// ── Search result type ─────────────────────────────────────────────────────────

interface SearchHit {
  doc_type: string;
  doc_id:   number;
  title:    string;
  snippet:  string;
  href:     string;
}

const HIT_BADGE: Record<string, string> = {
  entity:     "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400",
  authority:  "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400",
  annotation: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400",
};

// ── GlobalSearch component ─────────────────────────────────────────────────────

function GlobalSearch() {
  const router = useRouter();
  const [open,    setOpen]    = useState(false);
  const [query,   setQuery]   = useState("");
  const [hits,    setHits]    = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);

  const inputRef    = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef  = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Debounced live search
  const liveSearch = useCallback((q: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) { setHits([]); setLoading(false); return; }
    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await apiFetch(`/search?q=${encodeURIComponent(q)}&limit=6`);
        if (res.ok) {
          const data = await res.json();
          setHits(data.items ?? []);
        } else {
          setHits([]);
        }
      } catch {
        setHits([]);
      } finally {
        setLoading(false);
      }
    }, 280);
  }, []);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const v = e.target.value;
    setQuery(v);
    setOpen(true);
    liveSearch(v);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && query.trim()) {
      setOpen(false);
      router.push(`/search?q=${encodeURIComponent(query)}`);
    }
    if (e.key === "Escape") {
      setOpen(false);
      setQuery("");
      setHits([]);
    }
  }

  function handleFocus() {
    if (query.trim()) setOpen(true);
  }

  const showDropdown = open && query.trim().length > 0;

  return (
    <div ref={containerRef} className="relative hidden md:block">
      {/* Search input */}
      <div className="relative">
        <div className="pointer-events-none absolute inset-y-0 left-2.5 flex items-center">
          {loading ? (
            <svg className="h-3.5 w-3.5 animate-spin text-gray-400" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="h-3.5 w-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          )}
        </div>
        <input
          ref={inputRef}
          value={query}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          placeholder="Search… (Enter for full results)"
          className="h-8 w-52 rounded-lg border border-gray-200 bg-white pl-7 pr-3 text-xs text-gray-700 placeholder-gray-400 outline-none transition-all focus:w-72 focus:border-blue-400 focus:ring-1 focus:ring-blue-400 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:placeholder-gray-500 dark:focus:border-blue-500"
        />
      </div>

      {/* Dropdown */}
      {showDropdown && (
        <div className="absolute left-0 top-full z-50 mt-1.5 w-80 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-900">
          {hits.length === 0 && !loading && (
            <p className="px-4 py-3 text-xs text-gray-400">No results for &ldquo;{query}&rdquo;</p>
          )}
          {hits.map((hit) => (
            <Link
              key={`${hit.doc_type}-${hit.doc_id}`}
              href={hit.href}
              onClick={() => { setOpen(false); setQuery(""); setHits([]); }}
              className="flex items-start gap-3 px-3 py-2.5 hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              <span className={`mt-0.5 shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${HIT_BADGE[hit.doc_type] ?? "bg-gray-100 text-gray-600"}`}>
                {hit.doc_type}
              </span>
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-gray-800 dark:text-gray-200">
                  {hit.title || "(no title)"}
                </p>
                {hit.snippet && (
                  <p className="truncate text-[10px] text-gray-400">{hit.snippet}</p>
                )}
              </div>
            </Link>
          ))}
          {hits.length > 0 && (
            <div className="border-t border-gray-100 dark:border-gray-800">
              <Link
                href={`/search?q=${encodeURIComponent(query)}`}
                onClick={() => { setOpen(false); }}
                className="block px-3 py-2 text-center text-xs font-medium text-blue-600 hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-900/20"
              >
                See all results →
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Header ─────────────────────────────────────────────────────────────────────

export default function Header() {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
  const { domains, activeDomainId, setActiveDomainId, isLoading } = useDomain();
  const { branding } = useBranding();
  const { toggleMobile } = useSidebar();

  const page = pageTitles[pathname] || { title: "Dashboard", subtitle: "" };

  return (
    <header className="sticky top-0 z-40 flex h-16 items-center border-b border-gray-200 bg-white/80 shadow-sm backdrop-blur-sm dark:border-gray-800 dark:bg-gray-900/80">
      <div className="flex w-full items-center justify-between px-4 lg:px-6">
        <div className="flex items-center gap-3">
          {/* Mobile hamburger — hidden on desktop */}
          <button
            onClick={toggleMobile}
            className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800 lg:hidden"
            aria-label="Open navigation"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>
          <div>
            <h1 className="text-lg font-semibold text-gray-900 dark:text-white">
              {page.title}
            </h1>
            <p className="hidden text-xs text-gray-500 dark:text-gray-400 sm:block">
              {page.subtitle || branding.platform_name}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Global search */}
          <GlobalSearch />

          <div className="h-6 w-px bg-gray-200 dark:bg-gray-800" />

          {/* Domain Selector */}
          <div className="flex items-center gap-2">
            <span className="hidden text-sm font-medium text-gray-500 dark:text-gray-400 lg:inline">Workspace:</span>
            {isLoading ? (
              <div className="h-9 w-40 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800"></div>
            ) : (
              <select
                value={activeDomainId}
                onChange={(e) => setActiveDomainId(e.target.value)}
                className="h-9 cursor-pointer rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 outline-none transition-colors hover:bg-gray-50 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800"
              >
                {domains.map((domain) => (
                  <option key={domain.id} value={domain.id}>
                    {domain.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="h-6 w-px bg-gray-200 dark:bg-gray-800" />

          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-500 transition-colors hover:bg-gray-50 hover:text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? (
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            ) : (
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
          </button>

          {/* Notification bell */}
          <NotificationBell />

          {/* User profile menu */}
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
