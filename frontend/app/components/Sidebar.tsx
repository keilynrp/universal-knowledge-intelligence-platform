"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { useSidebar } from "./SidebarProvider";
import { useLanguage } from "../contexts/LanguageContext";
import { useBranding } from "../contexts/BrandingContext";
import { usePilotMode } from "../contexts/PilotModeContext";
import { BrandLockup } from "./ukip";
import { navSections } from "./sidebarNav";

export default function Sidebar() {
  const pathname = usePathname();
  const { collapsed, mobileOpen, closeMobile } = useSidebar();
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
            <BrandLockup branding={branding} showText={!compactDesktop} size="sm" className="max-w-full" />
          </Link>
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
                            ? "bg-[var(--ukip-primary-soft)] text-[var(--ukip-primary-strong)] shadow-[inset_0_0_0_1px_rgba(124,58,237,0.2)]"
                            : "text-[var(--ukip-muted)] hover:bg-[var(--ukip-panel-strong)] hover:text-[var(--ukip-text-strong)]"
                        }`}
                        title={collapsed && !mobileOpen ? t(item.translationKey) : undefined}
                      >
                        <span
                          className={`shrink-0 ${isActive ? "text-[var(--ukip-primary)]" : "text-[var(--ukip-muted-soft)]"}`}
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
                aria-pressed={pilotMode}
                className={`ukip-focus group w-full rounded-xl border px-3.5 py-3.5 text-left transition-[background-color,border-color,box-shadow] ${
                  pilotMode
                    ? "border-violet-400/40 bg-violet-500/15 shadow-[inset_0_0_0_1px_rgba(139,92,246,0.12)]"
                    : "border-[var(--ukip-border)] bg-[var(--ukip-panel-strong)] hover:border-[var(--ukip-border-strong)]"
                }`}
              >
                <div className="flex min-h-14 items-center gap-4">
                  <div className="min-w-0 flex-1">
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
                    aria-hidden="true"
                    className={`inline-flex h-10 w-[4.25rem] shrink-0 items-center rounded-full p-1 transition-colors ${
                      pilotMode
                        ? "bg-violet-500 shadow-[0_0_0_4px_rgba(139,92,246,0.14)]"
                        : "bg-[var(--ukip-border-strong)] group-hover:bg-[var(--ukip-muted-soft)]"
                    }`}
                  >
                    <span
                      className={`h-8 w-8 rounded-full bg-white shadow-sm transition-transform ${
                        pilotMode ? "translate-x-7" : "translate-x-0"
                      }`}
                    />
                  </span>
                </div>
              </button>
            </div>
          ) : (
            <div className="flex justify-center">
              <BrandLockup branding={branding} showText={false} size="sm" />
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
