"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import EntityTable from "./components/EntityTable";
import EntityVariantView from "./components/EntityVariantView";
import ActivityFeed from "./components/ActivityFeed";
import GuidedTour, { resetTour } from "./components/GuidedTour";
import { PageHeader, StatCard } from "./components/ui";
import { useDomain } from "./contexts/DomainContext";
import { apiFetch } from "../lib/api";
import { useAuth } from "./contexts/AuthContext";
import { Analytics } from "../lib/analytics";

interface DashboardStats {
  total: number;
  labels: number;
  models: number;
  enriched: number;
}

interface DemoStatus {
  demo_seeded: boolean;
  demo_entity_count: number;
}

export default function Home() {
  const [viewMode, setViewMode] = useState<"table" | "variants">("table");
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [enrichPct, setEnrichPct] = useState<number>(0);
  const [domainCount, setDomainCount] = useState<number>(0);
  const [demoStatus, setDemoStatus] = useState<DemoStatus | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const { activeDomainId } = useDomain();
  const { token } = useAuth();

  const fetchDemoStatus = useCallback(async () => {
    try {
      const res = await apiFetch("/demo/status");
      if (res.ok) setDemoStatus(await res.json());
    } catch { /* non-critical */ }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const [statsRes, enrichRes, domainsRes] = await Promise.all([
        apiFetch("/stats"),
        apiFetch("/enrich/stats").catch(() => null),
        apiFetch("/domains").catch(() => null),
      ]);
      const s = await statsRes.json();
      setStats(s);
      if (enrichRes && enrichRes.ok) {
        const e = await enrichRes.json();
        setEnrichPct(e.coverage_percent ?? 0);
      }
      if (domainsRes && domainsRes.ok) {
        const d = await domainsRes.json();
        setDomainCount(Array.isArray(d) ? d.length : 0);
      }
    } catch {
      // stats are non-critical
    }
  }, []);

  useEffect(() => {
    if (token) {
      fetchStats();
      fetchDemoStatus();
    }
  }, [token, fetchStats, fetchDemoStatus]);

  const handleLaunchDemo = async () => {
    setDemoLoading(true);
    try {
      const res = await apiFetch("/demo/seed", { method: "POST" });
      if (res.ok) {
        await fetchDemoStatus();
        await fetchStats();
        resetTour(); // reset so tour shows for new demo session
        Analytics.demoSeeded();
      }
    } catch { /* non-critical */ } finally {
      setDemoLoading(false);
    }
  };

  const handleClearDemo = async () => {
    setDemoLoading(true);
    try {
      const res = await apiFetch("/demo/reset", { method: "DELETE" });
      if (res.ok) {
        await fetchDemoStatus();
        await fetchStats();
      }
    } catch { /* non-critical */ } finally {
      setDemoLoading(false);
    }
  };

  const viewToggle = (
    <div className="inline-flex rounded-lg border border-gray-200 p-1 bg-white dark:border-gray-700 dark:bg-gray-900">
      <button
        onClick={() => setViewMode("table")}
        className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
          viewMode === "table"
            ? "bg-blue-600 text-white"
            : "text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
        }`}
      >
        Table View
      </button>
      <button
        onClick={() => setViewMode("variants")}
        className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
          viewMode === "variants"
            ? "bg-blue-600 text-white"
            : "text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
        }`}
      >
        Variant Groups
      </button>
    </div>
  );

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumbs={[{ label: "Home" }]}
        title="Knowledge Dashboard"
        description="Centralized entity management and harmonization tools"
        actions={viewToggle}
      />

      {/* Metric cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
          }
          iconColor="blue"
          label="Total Entities"
          value={stats?.total?.toLocaleString() ?? "—"}
        />
        <StatCard
          icon={
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
          iconColor="emerald"
          label="Enrichment Coverage"
          value={`${Math.round(enrichPct)}%`}
          trend={enrichPct > 0 ? { value: `${Math.round(enrichPct)}%`, direction: "up", positive: true } : undefined}
        />
        <StatCard
          icon={
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 6h.008v.008H6V6z" />
            </svg>
          }
          iconColor="amber"
          label="Unique Primary Labels"
          value={stats?.labels?.toLocaleString() ?? "—"}
        />
        <StatCard
          icon={
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375" />
            </svg>
          }
          iconColor="violet"
          label="Active Domains"
          value={domainCount || "—"}
        />
      </div>

      {/* Demo mode banner */}
      {demoStatus !== null && (
        !demoStatus.demo_seeded ? (
          <div className="flex items-center justify-between rounded-xl border border-indigo-200 bg-indigo-50 px-5 py-4 dark:border-indigo-900/40 dark:bg-indigo-900/10">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-100 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-indigo-900 dark:text-indigo-200">Try UKIP Demo</p>
                <p className="text-xs text-indigo-600 dark:text-indigo-400">Load 1,000 pre-generated entities across Technology, Healthcare, Science and Engineering to explore all platform features.</p>
              </div>
            </div>
            <button
              onClick={handleLaunchDemo}
              disabled={demoLoading}
              className="flex shrink-0 items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors disabled:opacity-50"
            >
              {demoLoading ? (
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : "Launch Demo"}
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 px-5 py-3.5 dark:border-amber-900/40 dark:bg-amber-900/10">
            <div className="flex items-center gap-3">
              <span className="text-lg">demo</span>
              <div>
                <p className="text-sm font-medium text-amber-900 dark:text-amber-200">Demo mode active</p>
                <p className="text-xs text-amber-600 dark:text-amber-400">{demoStatus.demo_entity_count.toLocaleString()} demo entities loaded. Clear them when you are ready to import your own data.</p>
              </div>
            </div>
            <button
              onClick={handleClearDemo}
              disabled={demoLoading}
              className="flex shrink-0 items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-4 py-2 text-sm font-medium text-amber-700 hover:bg-amber-50 transition-colors disabled:opacity-50 dark:border-amber-700 dark:bg-amber-900/20 dark:text-amber-300"
            >
              {demoLoading ? "Clearing..." : "Clear Demo"}
            </button>
          </div>
        )
      )}

      {/* Quick action cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Link href="/import-export" className="group rounded-2xl bg-gradient-to-br from-blue-600 to-cyan-500 p-5 text-white shadow-sm transition-shadow hover:shadow-md">
          <div className="flex items-center gap-3">
            <svg className="h-8 w-8 opacity-80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
            </svg>
            <div>
              <p className="font-semibold">Import Data</p>
              <p className="text-sm text-white/70">Upload Excel, CSV, JSON-LD</p>
            </div>
          </div>
        </Link>
        <Link href="/authority" className="group rounded-2xl bg-gradient-to-br from-violet-600 to-purple-500 p-5 text-white shadow-sm transition-shadow hover:shadow-md">
          <div className="flex items-center gap-3">
            <svg className="h-8 w-8 opacity-80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            <div>
              <p className="font-semibold">Authority Resolution</p>
              <p className="text-sm text-white/70">Wikidata, VIAF, ORCID, DBpedia</p>
            </div>
          </div>
        </Link>
        <Link href="/analytics/olap" className="group rounded-2xl bg-gradient-to-br from-emerald-600 to-teal-500 p-5 text-white shadow-sm transition-shadow hover:shadow-md">
          <div className="flex items-center gap-3">
            <svg className="h-8 w-8 opacity-80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
            </svg>
            <div>
              <p className="font-semibold">OLAP Explorer</p>
              <p className="text-sm text-white/70">Multi-dimensional analysis</p>
            </div>
          </div>
        </Link>
      </div>

      {/* Activity feed + Entity browser */}
      <div className="grid grid-cols-1 gap-6 2xl:grid-cols-[1fr_280px]">
        <div>
          {viewMode === "table" ? <EntityTable /> : <EntityVariantView />}
        </div>
        <div>
          <ActivityFeed />
        </div>
      </div>

      {/* Guided tour — auto-starts after demo is seeded */}
      <GuidedTour autoStart={demoStatus?.demo_seeded === true} />
    </div>
  );
}
