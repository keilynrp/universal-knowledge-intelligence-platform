/* eslint-disable @next/next/no-img-element */
"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { useSidebar } from "./SidebarProvider";
import { useLanguage } from "../contexts/LanguageContext";
import { useBranding, type BrandingSettings } from "../contexts/BrandingContext";
import { usePilotMode } from "../contexts/PilotModeContext";
import { navSections } from "./sidebarNav";

// ── Logo icon — shows uploaded image or default DB icon ───────────────────────

function LogoIcon({ branding, size = 8 }: { branding: BrandingSettings; size?: number }) {
  const apiBase = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
  const logoSrc = branding.logo_url?.startsWith("/static/")
    ? `${apiBase}${branding.logo_url}`
    : branding.logo_url || "";
  const px = `h-${size} w-${size}`;

  return (
    <div
      className={`flex ${px} items-center justify-center overflow-hidden rounded-lg`}
      style={{ backgroundColor: branding.accent_color || "#6366f1" }}
    >
      {logoSrc ? (
        <img
          src={logoSrc}
          alt={branding.platform_name}
          className="h-full w-full object-contain p-1"
          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
        />
      ) : (
        <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
        </svg>
      )}
    </div>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const { collapsed, toggle, mobileOpen, closeMobile } = useSidebar();
  const { t } = useLanguage();
  const { branding } = useBranding();
  const { pilotMode, togglePilotMode } = usePilotMode();
  const tr = (key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  };
  const visibleSections = pilotMode
    ? navSections
        .map((section) => ({
          ...section,
          items: section.items.filter((item) =>
            [
              "/",
              "/import",
              "/import/scientific",
              "/import-export",
              "/authority",
              "/analytics/dashboard",
              "/reports",
            ].includes(item.href),
          ),
        }))
        .filter((section) => section.items.length > 0)
    : navSections;

  // On desktop: fixed sidebar, collapsed or expanded
  // On mobile: full-width drawer, hidden until mobileOpen
  const desktopWidth = collapsed ? "lg:w-16" : "lg:w-64";
  const mobileTranslate = mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0";
  const compactDesktop = collapsed && !mobileOpen;

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={closeMobile}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed left-0 top-0 z-50 flex h-screen w-72 flex-col overflow-hidden border-r border-[var(--ukip-border)] bg-[var(--ukip-sidebar-bg)] shadow-[var(--ukip-shadow-panel)] backdrop-blur-xl transition-[width,transform] duration-300 ease-out ${desktopWidth} ${mobileTranslate}`}
      >
        {/* Logo */}
        <div
          className={`relative flex h-16 items-center border-b border-[var(--ukip-border)] ${
            compactDesktop ? "justify-center px-3" : "justify-between px-6"
          }`}
        >
          <Link
            href="/"
            className={`flex min-w-0 items-center ${compactDesktop ? "justify-center" : "gap-2"}`}
            onClick={closeMobile}
            aria-label={branding.platform_name}
          >
            <LogoIcon branding={branding} size={8} />
            {!compactDesktop && (
              <span className="truncate text-base font-semibold text-[var(--ukip-text-strong)] transition-opacity duration-200">
                {branding.platform_name}
              </span>
            )}
          </Link>
          {/* Desktop collapse toggle — hidden on mobile */}
          <button
            onClick={toggle}
            aria-label={collapsed ? tr("sidebar.expand", "Expand sidebar") : tr("sidebar.collapse", "Collapse sidebar")}
            className={`hidden rounded-lg p-1.5 text-[var(--ukip-muted)] transition-colors hover:bg-[var(--ukip-panel-strong)] hover:text-[var(--ukip-text-strong)] lg:block ${
              compactDesktop ? "absolute right-1 top-1/2 -translate-y-1/2" : ""
            }`}
          >
            <svg className="h-5 w-5" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {collapsed ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
              )}
            </svg>
          </button>
          {/* Mobile close button */}
          <button
            onClick={closeMobile}
            aria-label={tr("sidebar.close_navigation", "Close navigation")}
            className="rounded-lg p-1.5 text-[var(--ukip-muted)] hover:bg-[var(--ukip-panel-strong)] hover:text-[var(--ukip-text-strong)] lg:hidden"
          >
            <svg className="h-5 w-5" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Navigation */}
        <nav className={`flex-1 overflow-y-auto py-4 ${compactDesktop ? "px-2" : "px-4"}`}>
          {visibleSections.map((section, sectionIdx) => (
            <div key={section.header} className={sectionIdx > 0 ? "mt-6" : ""}>
              {compactDesktop ? (
                sectionIdx > 0 && <div className="mx-2 mb-3 h-px bg-[var(--ukip-border)]" />
              ) : (
                <div className="mb-2 px-3">
                  <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--ukip-muted-soft)]">
                    {t(section.translationKey)}
                  </span>
                </div>
              )}
              <ul className="space-y-1">
                {section.items.map((item) => {
                  const isActive =
                    item.href === "/"
                      ? pathname === "/"
                      : pathname === item.href || pathname.startsWith(item.href + "/");
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={closeMobile}
                        className={`flex items-center rounded-lg py-2.5 text-sm font-medium transition-[background-color,color,padding] duration-200 ${
                          compactDesktop ? "justify-center px-1.5" : "gap-3 px-3"
                        } ${
                          isActive
                            ? "bg-violet-500/15 text-violet-200 shadow-[inset_0_0_0_1px_rgba(167,139,250,0.26)]"
                            : "text-[var(--ukip-muted)] hover:bg-[var(--ukip-panel-strong)] hover:text-[var(--ukip-text-strong)]"
                        }`}
                        title={collapsed && !mobileOpen ? t(item.translationKey) : undefined}
                      >
                        <span
                          className={`shrink-0 ${isActive ? "text-violet-300" : "text-[var(--ukip-muted-soft)]"}`}
                        >
                          {item.icon}
                        </span>
                        {!compactDesktop && <span className="truncate">{t(item.translationKey)}</span>}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className={`border-t border-[var(--ukip-border)] py-4 ${compactDesktop ? "px-2" : "px-4"}`}>
          {!compactDesktop ? (
            <div className="space-y-3">
              <button
                onClick={togglePilotMode}
                className={`w-full rounded-xl border px-3 py-3 text-left transition-colors ${
                  pilotMode
                    ? "border-violet-400/30 bg-violet-500/15"
                    : "border-[var(--ukip-border)] bg-[var(--ukip-panel-strong)]"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold text-[var(--ukip-text-strong)]">
                      {pilotMode
                        ? tr("sidebar.pilot_mode.on", "Pilot mode on")
                        : tr("sidebar.pilot_mode.off", "Full workspace")}
                    </p>
                    <p className="mt-1 text-[11px] leading-4 text-[var(--ukip-muted)]">
                      {pilotMode
                        ? tr("sidebar.pilot_mode.on_help", "Showing the shortest path for imports, enrichment, review, and briefing.")
                        : tr("sidebar.pilot_mode.off_help", "Showing the full UKIP workspace, including advanced tools.")}
                    </p>
                  </div>
                  <span
                    className={`inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      pilotMode ? "bg-violet-500" : "bg-[var(--ukip-border-strong)]"
                    }`}
                  >
                    <span
                      className={`h-5 w-5 rounded-full bg-white transition-transform ${
                        pilotMode ? "translate-x-5" : "translate-x-0.5"
                      }`}
                    />
                  </span>
                </div>
              </button>
              <div className="rounded-lg border border-[var(--ukip-border)] bg-[var(--ukip-panel-strong)] px-3 py-3">
                <p className="text-xs font-semibold text-[var(--ukip-text-strong)]">UKIP</p>
              </div>
            </div>
          ) : (
            <div className="flex justify-center">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[var(--ukip-panel-strong)] text-xs font-bold text-[var(--ukip-muted)]">
                U
              </span>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

