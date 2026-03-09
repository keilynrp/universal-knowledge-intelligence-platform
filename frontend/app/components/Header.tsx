"use client";

import { usePathname } from "next/navigation";
import { useTheme } from "../contexts/ThemeContext";
import { useDomain } from "../contexts/DomainContext";
import { useBranding } from "../contexts/BrandingContext";
import { useSidebar } from "./SidebarProvider";
import NotificationBell from "./NotificationBell";
import UserMenu from "./UserMenu";

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
};

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
        <div className="flex items-center gap-4">
          {/* Domain Selector */}
          <div className="flex items-center gap-2">
            <span className="hidden text-sm font-medium text-gray-500 dark:text-gray-400 sm:inline">Workspace:</span>
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

