"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { useDomain } from "../contexts/DomainContext";
import { useBranding } from "../contexts/BrandingContext";
import { useLanguage } from "../contexts/LanguageContext";
import { useSidebar } from "./SidebarProvider";
import NotificationBell from "./NotificationBell";
import UserMenu from "./UserMenu";
import { apiFetch } from "@/lib/api";

// ── Page title map ──────────────────────────────────────────────────────────────

const pageTitles: Record<string, { titleKey: string; subtitleKey: string; titleFallback: string; subtitleFallback: string }> = {
  "/": { titleKey: "header.page.home.title", subtitleKey: "header.page.home.subtitle", titleFallback: "Master Data Hub", subtitleFallback: "Browse and search your entity database" },
  "/disambiguation": { titleKey: "header.page.disambiguation.title", subtitleKey: "header.page.disambiguation.subtitle", titleFallback: "Data Disambiguation", subtitleFallback: "Find and resolve data inconsistencies" },
  "/analytics": { titleKey: "header.page.analytics.title", subtitleKey: "header.page.analytics.subtitle", titleFallback: "Analytics", subtitleFallback: "Key metrics and data quality insights" },
  "/authority": { titleKey: "header.page.authority.title", subtitleKey: "header.page.authority.subtitle", titleFallback: "Authority Control", subtitleFallback: "Normalize and harmonize field values with canonical rules" },
  "/harmonization": { titleKey: "header.page.harmonization.title", subtitleKey: "header.page.harmonization.subtitle", titleFallback: "Data Harmonization", subtitleFallback: "Automated pipeline for cleaning and consolidating entity data" },
  "/import-export": { titleKey: "header.page.import_export.title", subtitleKey: "header.page.import_export.subtitle", titleFallback: "Import / Export", subtitleFallback: "Upload and download dataset in Excel format" },
  "/rag": { titleKey: "header.page.rag.title", subtitleKey: "header.page.rag.subtitle", titleFallback: "Semantic RAG", subtitleFallback: "AI-powered retrieval and semantic analysis" },
  "/domains": { titleKey: "header.page.domains.title", subtitleKey: "header.page.domains.subtitle", titleFallback: "Domain Registry", subtitleFallback: "Manage workspace schemas and entity type definitions" },
  "/analytics/olap": { titleKey: "header.page.analytics_olap.title", subtitleKey: "header.page.analytics_olap.subtitle", titleFallback: "OLAP Cube Explorer", subtitleFallback: "Multi-dimensional analysis and drill-down across your data" },
  "/analytics/nlq":  { titleKey: "header.page.analytics_nlq.title", subtitleKey: "header.page.analytics_nlq.subtitle", titleFallback: "Natural Language Query", subtitleFallback: "Ask your data anything in plain English — AI translates it to OLAP" },
  "/analytics/topics": { titleKey: "header.page.analytics_topics.title", subtitleKey: "header.page.analytics_topics.subtitle", titleFallback: "Topic Modeling", subtitleFallback: "Concept frequency, co-occurrence, clusters, and field correlations" },
  "/artifacts": { titleKey: "header.page.artifacts.title", subtitleKey: "header.page.artifacts.subtitle", titleFallback: "Artifact Studio", subtitleFallback: "Build and export strategic intelligence artifacts" },
  "/artifacts/gaps": { titleKey: "header.page.artifacts_gaps.title", subtitleKey: "header.page.artifacts_gaps.subtitle", titleFallback: "Knowledge Gap Detector", subtitleFallback: "Identify and prioritize data quality issues in your domain" },
  "/context":   { titleKey: "header.page.context.title", subtitleKey: "header.page.context.subtitle", titleFallback: "Context Engineering", subtitleFallback: "Domain context snapshots, sessions, and tool invocations" },
  "/audit-log": { titleKey: "header.page.audit_log.title", subtitleKey: "header.page.audit_log.subtitle", titleFallback: "Audit Log", subtitleFallback: "Complete history of all platform mutations and user activity" },
  "/search": { titleKey: "header.page.search.title", subtitleKey: "header.page.search.subtitle", titleFallback: "Search", subtitleFallback: "Full-text search across entities, authority records, and annotations" },
  "/entities/link": { titleKey: "header.page.entities_link.title", subtitleKey: "header.page.entities_link.subtitle", titleFallback: "Entity Linker", subtitleFallback: "Detect and resolve near-duplicate entities" },
  "/notifications": { titleKey: "header.page.notifications.title", subtitleKey: "header.page.notifications.subtitle", titleFallback: "Notification Center", subtitleFallback: "Activity feed with read/unread state and action links" },
  "/reports/scheduled": { titleKey: "header.page.reports_scheduled.title", subtitleKey: "header.page.reports_scheduled.subtitle", titleFallback: "Scheduled Reports", subtitleFallback: "Recurring report delivery via email — PDF, Excel, and HTML" },
  "/dashboards": { titleKey: "header.page.dashboards.title", subtitleKey: "header.page.dashboards.subtitle", titleFallback: "My Dashboards", subtitleFallback: "Personalised widget dashboards — build your own data view" },
  "/settings/alerts": { titleKey: "header.page.settings_alerts.title", subtitleKey: "header.page.settings_alerts.subtitle", titleFallback: "Alert Channels", subtitleFallback: "Push platform events to Slack, Teams, Discord, or any webhook" },
  "/settings/api-keys": { titleKey: "header.page.settings_api_keys.title", subtitleKey: "header.page.settings_api_keys.subtitle", titleFallback: "API Keys", subtitleFallback: "Generate and manage long-lived API keys for programmatic access" },
  "/settings/organizations": { titleKey: "header.page.settings_organizations.title", subtitleKey: "header.page.settings_organizations.subtitle", titleFallback: "Organizations", subtitleFallback: "Manage multi-tenant workspaces and member access" },
  "/settings/users": { titleKey: "header.page.settings_users.title", subtitleKey: "header.page.settings_users.subtitle", titleFallback: "User Management", subtitleFallback: "Manage user accounts, roles, and platform access" },
  "/profile": { titleKey: "header.page.profile.title", subtitleKey: "header.page.profile.subtitle", titleFallback: "My Profile", subtitleFallback: "Manage your personal information, avatar, and password" },
  "/demo/sales": { titleKey: "header.page.demo_sales.title", subtitleKey: "header.page.demo_sales.subtitle", titleFallback: "Sales Deck", subtitleFallback: "Executive narrative — printable to PDF for prospects and stakeholders" },
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
  const { t } = useLanguage();
  const [open,    setOpen]    = useState(false);
  const [query,   setQuery]   = useState("");
  const [hits,    setHits]    = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);

  const inputRef    = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dropdownId = "global-search-results";

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
    <div ref={containerRef} className="relative hidden min-w-0 flex-1 md:block">
      {/* Search input */}
      <div className="relative">
        <div className="pointer-events-none absolute inset-y-0 left-4 flex items-center">
          {loading ? (
            <svg className="h-4 w-4 animate-spin text-slate-400" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
          placeholder={t("header.search.placeholder")}
          aria-label={t("header.search.aria")}
          aria-autocomplete="list"
          aria-controls={showDropdown ? dropdownId : undefined}
          aria-expanded={showDropdown}
          role="combobox"
          className="ukip-focus h-10 w-full rounded-xl border border-slate-200 bg-slate-50/90 pl-11 pr-16 text-sm text-slate-800 shadow-sm outline-none transition focus:border-violet-300 focus:bg-white dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-text)] dark:placeholder:text-[var(--ukip-muted-soft)]"
        />
        <span className="pointer-events-none absolute inset-y-0 right-3 hidden items-center rounded-md border border-slate-200 bg-white px-2 font-mono text-xs text-slate-500 shadow-sm dark:border-white/10 dark:bg-white/10 dark:text-[var(--ukip-muted)] lg:flex">
          ⌘K
        </span>
      </div>

      {/* Dropdown */}
      {showDropdown && (
        <div id={dropdownId} className="absolute left-0 top-full z-50 mt-1.5 w-80 overflow-hidden rounded-xl border border-[var(--ukip-border)] bg-[var(--ukip-panel)] shadow-[var(--ukip-shadow-panel)]">
          {hits.length === 0 && !loading && (
            <p className="px-4 py-3 text-xs text-[var(--ukip-muted)]">{t("header.search.no_results", { query })}</p>
          )}
          {hits.map((hit) => (
            <Link
              key={`${hit.doc_type}-${hit.doc_id}`}
              href={hit.href}
              onClick={() => { setOpen(false); setQuery(""); setHits([]); }}
              className="flex items-start gap-3 px-3 py-2.5 hover:bg-[var(--ukip-panel-strong)]"
            >
              <span className={`mt-0.5 shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${HIT_BADGE[hit.doc_type] ?? "bg-gray-100 text-gray-600"}`}>
                {hit.doc_type}
              </span>
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-[var(--ukip-text-strong)]">
                  {hit.title || t("header.search.no_title")}
                </p>
                {hit.snippet && (
                  <p className="truncate text-[10px] text-[var(--ukip-muted)]">{hit.snippet}</p>
                )}
              </div>
            </Link>
          ))}
          {hits.length > 0 && (
            <div className="border-t border-[var(--ukip-border)]">
              <Link
                href={`/search?q=${encodeURIComponent(query)}`}
                onClick={() => { setOpen(false); }}
                className="block px-3 py-2 text-center text-xs font-medium text-[var(--ukip-cyan)] hover:bg-[var(--ukip-panel-strong)]"
              >
                {t("header.search.view_all")}
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
  const { t } = useLanguage();
  const { domains, activeDomainId, activeDomain, setActiveDomainId, isLoading } = useDomain();
  const { branding } = useBranding();
  const { toggle, toggleMobile } = useSidebar();
  const tr = useCallback((key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  }, [t]);

  const page = pageTitles[pathname] || {
    titleKey: "header.page.default.title",
    subtitleKey: "header.page.default.subtitle",
    titleFallback: "Dashboard",
    subtitleFallback: "",
  };
  const activeDomainLabel = useMemo(() => {
    if (isLoading) return t("header.workspace.loading");
    if (activeDomain?.name) return activeDomain.name;
    if (activeDomainId === "default") return t("header.workspace.default_name");
    return activeDomainId || t("header.workspace.none");
  }, [activeDomain?.name, activeDomainId, isLoading, t]);
  const hasDomains = domains.length > 0;
  const currentTitle = t(page.titleKey) === page.titleKey ? page.titleFallback : t(page.titleKey);

  return (
    <header className="sticky top-0 z-40 flex h-16 items-center border-b border-slate-200 bg-white/95 shadow-sm backdrop-blur-xl dark:border-white/10 dark:bg-[var(--ukip-header-bg)]">
      <div className="flex w-full min-w-0 items-center gap-3 px-4 lg:px-5">
        <div className="flex min-w-0 shrink-0 items-center gap-4">
          <button
            onClick={toggleMobile}
            className="rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:text-[var(--ukip-muted)] dark:hover:bg-[var(--ukip-panel-strong)] dark:hover:text-[var(--ukip-text-strong)] lg:hidden"
            aria-label={t("header.mobile.open_navigation")}
          >
            <svg className="h-5 w-5" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>
          <button
            onClick={toggle}
            className="hidden rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:text-[var(--ukip-muted)] dark:hover:bg-[var(--ukip-panel-strong)] dark:hover:text-[var(--ukip-text-strong)] lg:inline-flex"
            aria-label={t("sidebar.collapse")}
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4.5 6.75h15m-15 5.25h15m-15 5.25h15M8.25 4.5v15" />
            </svg>
          </button>
          <div className="hidden h-6 w-px bg-slate-200 dark:bg-[var(--ukip-border)] lg:block" />
          <nav className="hidden min-w-0 items-center gap-2 text-sm md:flex" aria-label="Breadcrumb">
            <span className="text-slate-500 dark:text-[var(--ukip-muted)]">
              {tr("page.home.breadcrumb", "Workspace")}
            </span>
            <span className="text-slate-300 dark:text-[var(--ukip-muted-soft)]">/</span>
            <span className="max-w-[12rem] truncate font-semibold text-slate-900 dark:text-[var(--ukip-text-strong)]">
              {pathname === "/" ? tr("page.home.summary_title", "Resumen") : currentTitle}
            </span>
          </nav>
        </div>

        <div className="mx-auto hidden min-w-[18rem] max-w-[32rem] flex-1 md:block">
          <GlobalSearch />
        </div>

        <div className="ml-auto flex min-w-0 shrink-0 items-center gap-2">
          <div className="hidden min-w-0 items-center lg:flex">
            {isLoading ? (
              <div className="h-10 w-48 animate-pulse rounded-xl bg-slate-100 dark:bg-[var(--ukip-panel-strong)]"></div>
            ) : (
              <label className="relative block">
                <span className="sr-only">{t("header.workspace.label")}</span>
                <select
                  id="workspace-select"
                  value={activeDomainId}
                  onChange={(e) => setActiveDomainId(e.target.value)}
                  aria-label={t("header.workspace.aria")}
                  title={activeDomainLabel || branding.platform_name}
                  disabled={!hasDomains}
                  className="ukip-focus h-10 max-w-[13rem] cursor-pointer appearance-none rounded-xl border border-slate-200 bg-white py-0 pl-4 pr-9 text-sm font-medium text-slate-700 shadow-sm outline-none transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-text)] dark:hover:bg-[var(--ukip-panel-strong)] xl:max-w-[16rem]"
                >
                  {hasDomains ? (
                    domains.map((domain) => (
                      <option key={domain.id} value={domain.id}>
                        {domain.name}
                      </option>
                    ))
                  ) : (
                    <option value={activeDomainId || "default"}>
                      {t("header.workspace.none")}
                    </option>
                  )}
                </select>
                <svg className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500 dark:text-[var(--ukip-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.25 9.75L12 13.5l3.75-3.75" />
                </svg>
              </label>
            )}
          </div>
          <NotificationBell />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
