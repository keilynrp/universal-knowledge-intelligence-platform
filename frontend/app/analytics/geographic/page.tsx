"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useDomain } from "../../contexts/DomainContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { apiFetch } from "@/lib/api";
import { SkeletonList, ErrorBanner, EmptyState as UiEmptyState } from "../../components/ui";
import { flagEmoji } from "./countryMeta";

// Lazy-load WorldMap so d3-geo + the atlas (~140 KB gz) only ship to this page.
const WorldMap = dynamic(
  () => import("../../components/geo/WorldMap").then((m) => m.WorldMap),
  { ssr: false, loading: () => <div className="h-[420px] animate-pulse bg-slate-100 dark:bg-slate-900" /> },
);

interface Country {
  country_code: string;
  country_name: string;
  entity_count: number;
  citation_sum: number;
  percentage: number;
}

interface CollabPair {
  country_a: string;
  country_b: string;
  country_a_name: string;
  country_b_name: string;
  count: number;
}

interface GeoResult {
  domain_id: string;
  coverage: number;
  total_entities: number;
  countries: Country[];
  collaboration_rate?: number;
  top_country_pairs?: CollabPair[];
}

interface YearPoint {
  year: number;
  entity_count: number;
  citation_sum: number;
}

interface CountryDetail {
  country_code: string;
  country_name: string;
  total_entities: number;
  total_citations: number;
  reference_year: number;
  years: number;
  series: YearPoint[];
}

const SORT_OPTIONS = [
  { value: "entity_count", labelKey: "page.geographic.entities" },
  { value: "citation_sum", labelKey: "page.geographic.citations" },
] as const;

const MAP_W = 1000;
const MAP_H = 500;

function KpiCard({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-gray-200 bg-white px-5 py-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <div className={`absolute inset-x-0 top-0 h-0.5 ${accent}`} />
      <p className="text-[11px] uppercase tracking-wider text-gray-500 dark:text-gray-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-gray-900 dark:text-white">{value}</p>
    </div>
  );
}

function MarkerBar({ pct, color = "bg-blue-500" }: { pct: number; color?: string }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
      <div className={`h-2 rounded-full transition-all ${color}`} style={{ width: `${Math.max(2, pct)}%` }} />
    </div>
  );
}

export default function GeographicPage() {
  const { activeDomainId } = useDomain();
  const { t } = useLanguage();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<GeoResult | null>(null);
  const [sortBy, setSortBy] = useState<string>("entity_count");

  const currentYear = new Date().getFullYear();
  const [yearFrom, setYearFrom] = useState<string>("");
  const [yearTo, setYearTo] = useState<string>("");
  const [minCitations, setMinCitations] = useState<string>("");
  const [showCollab, setShowCollab] = useState<boolean>(false);

  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<CountryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [hover, setHover] = useState<{ code: string; x: number; y: number } | null>(null);

  const fetchGeo = useCallback(
    async (
      domainId: string,
      sort: string,
      yf: string,
      yt: string,
      mc: string,
      collab: boolean,
    ) => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ sort_by: sort, limit: "30" });
        if (yf) params.set("year_from", yf);
        if (yt) params.set("year_to", yt);
        if (mc) params.set("min_citations", mc);
        if (collab) params.set("include_collaboration", "true");
        const r = await apiFetch(`/analyzers/geographic/${domainId}?${params}`);
        if (!r.ok) throw new Error(`Server responded with ${r.status}`);
        setData(await r.json());
      } catch (err) {
        setError(err instanceof Error ? err.message : t("page.geographic.error_load"));
      } finally {
        setLoading(false);
      }
    },
    [t],
  );

  useEffect(() => {
    fetchGeo(activeDomainId, sortBy, yearFrom, yearTo, minCitations, showCollab);
  }, [activeDomainId, sortBy, yearFrom, yearTo, minCitations, showCollab, fetchGeo]);

  const fetchDetail = useCallback(async (code: string) => {
    if (code === "OTHER") return;
    setDetailLoading(true);
    setDetail(null);
    try {
      const r = await apiFetch(`/analyzers/geographic/${activeDomainId}/country/${code}?years=9`);
      if (r.ok) setDetail(await r.json());
    } catch {
      // swallow — detail card will show fallback
    } finally {
      setDetailLoading(false);
    }
  }, [activeDomainId]);

  useEffect(() => {
    if (selected) fetchDetail(selected);
  }, [selected, fetchDetail]);

  const countries = useMemo(() => data?.countries ?? [], [data?.countries]);
  const visibleCountries = useMemo(
    () => countries.filter((c) => c.country_code !== "OTHER"),
    [countries],
  );
  const totalCitations = useMemo(
    () => countries.reduce((acc, c) => acc + (c.citation_sum || 0), 0),
    [countries],
  );

  const maxEntityCount = visibleCountries.length
    ? Math.max(...visibleCountries.map((c) => c.entity_count), 1)
    : 1;
  const maxCitationSum = visibleCountries.length
    ? Math.max(...visibleCountries.map((c) => c.citation_sum), 1)
    : 1;

  const selectedCountry = countries.find((c) => c.country_code === selected) || null;
  // Display info for the panel header — falls back to the API-returned name
  // when the user clicks a country that has no entities in the filtered
  // dataset (otherwise the panel would stay on the "Pick a country" hint).
  const selectedName =
    selectedCountry?.country_name || detail?.country_name || selected || "";

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            {t("page.geographic.title")}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("page.geographic.subtitle")}
          </p>
        </div>
        <Link href="/analytics" className="text-sm text-blue-600 hover:underline dark:text-blue-400">
          &larr; {t("nav.analytics")}
        </Link>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-900">
        <div className="flex flex-col gap-1">
          <label className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
            {t("page.geographic.sort_by")}
          </label>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="rounded border border-gray-300 bg-white px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {t(opt.labelKey)}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label
            htmlFor="geo-year-from"
            className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-gray-400"
          >
            {t("page.geographic.year_from") || "Year from"}
          </label>
          <input
            id="geo-year-from"
            type="number"
            min={1900}
            max={currentYear}
            value={yearFrom}
            onChange={(e) => setYearFrom(e.target.value)}
            placeholder="—"
            className="w-24 rounded border border-gray-300 bg-white px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label
            htmlFor="geo-year-to"
            className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-gray-400"
          >
            {t("page.geographic.year_to") || "Year to"}
          </label>
          <input
            id="geo-year-to"
            type="number"
            min={1900}
            max={currentYear}
            value={yearTo}
            onChange={(e) => setYearTo(e.target.value)}
            placeholder="—"
            className="w-24 rounded border border-gray-300 bg-white px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label
            htmlFor="geo-min-citations"
            className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-gray-400"
          >
            {t("page.geographic.min_citations") || "Min citations"}
          </label>
          <input
            id="geo-min-citations"
            type="number"
            min={0}
            value={minCitations}
            onChange={(e) => setMinCitations(e.target.value)}
            placeholder="0"
            className="w-24 rounded border border-gray-300 bg-white px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
          />
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
            {t("page.geographic.collab_title") || "International collaborations"}
          </span>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded border border-gray-300 px-2 py-1 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200">
            <input
              id="geo-show-collab"
              type="checkbox"
              checked={showCollab}
              onChange={(e) => setShowCollab(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span>{t("page.geographic.show_collab") || "Show pairs"}</span>
          </label>
        </div>

        {(yearFrom || yearTo || minCitations) && (
          <button
            onClick={() => {
              setYearFrom("");
              setYearTo("");
              setMinCitations("");
            }}
            className="rounded-full border border-gray-300 px-3 py-1 text-xs text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            {t("page.geographic.clear_filters") || "Clear filters"}
          </button>
        )}

        {selected && (
          <button
            onClick={() => setSelected(null)}
            className="ml-auto rounded-full border border-gray-300 px-3 py-1 text-xs text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            {t("page.geographic.reset_view") || "Reset view"}
          </button>
        )}
      </div>

      {loading && (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
          <SkeletonList rows={10} />
        </div>
      )}

      {!loading && error && (
        <ErrorBanner
          message={t("page.geographic.error_load")}
          detail={error}
          onRetry={() =>
            fetchGeo(activeDomainId, sortBy, yearFrom, yearTo, minCitations, showCollab)
          }
        />
      )}

      {!loading && !error && data && (
        <>
          {/* KPI cards */}
          <div
            className={`grid grid-cols-2 gap-4 ${
              showCollab && data.collaboration_rate !== undefined
                ? "sm:grid-cols-5"
                : "sm:grid-cols-4"
            }`}
          >
            <KpiCard
              label={t("page.geographic.entities")}
              value={data.total_entities.toLocaleString()}
              accent="bg-blue-500"
            />
            <KpiCard
              label={t("page.geographic.active_countries") || "Active countries"}
              value={visibleCountries.length.toLocaleString()}
              accent="bg-emerald-500"
            />
            <KpiCard
              label={t("page.geographic.global_coverage") || "Global coverage"}
              value={`${(data.coverage * 100).toFixed(1)}%`}
              accent="bg-violet-500"
            />
            <KpiCard
              label={t("page.geographic.global_impact") || "Global impact (citations)"}
              value={totalCitations.toLocaleString()}
              accent="bg-amber-500"
            />
            {showCollab && data.collaboration_rate !== undefined && (
              <KpiCard
                label={t("page.geographic.collab_rate") || "Collaboration rate"}
                value={`${data.collaboration_rate.toFixed(1)}%`}
                accent="bg-pink-500"
              />
            )}
          </div>

          {/* Map + Detail panel */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="relative col-span-1 overflow-hidden rounded-2xl border border-gray-200 bg-gradient-to-br from-slate-50 to-blue-50 lg:col-span-2 dark:border-gray-800 dark:from-gray-950 dark:to-blue-950">
              <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100 dark:border-gray-800/60">
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {t("page.geographic.world_map") || "World heatmap"}
                </h3>
                <span className="text-[11px] text-gray-500 dark:text-gray-500">
                  {visibleCountries.length} {t("page.geographic.active_countries") || "active"}
                </span>
              </div>
              <WorldMap
                data={visibleCountries}
                selected={selected}
                onCountryClick={(code) => setSelected(code)}
                onCountryHover={setHover}
                labels={{
                  zoomIn: t("page.geographic.zoom_in") || "Zoom in",
                  zoomOut: t("page.geographic.zoom_out") || "Zoom out",
                  zoomReset: t("page.geographic.zoom_reset") || "Reset zoom",
                }}
                screenOverlay={
                  hover &&
                  (() => {
                    const hc = visibleCountries.find(
                      (c) => c.country_code === hover.code,
                    );
                    if (!hc) return null;
                    const leftPct = (hover.x / MAP_W) * 100;
                    const topPct = (hover.y / MAP_H) * 100;
                    return (
                      <div
                        className="pointer-events-none absolute z-20 -translate-x-1/2 -translate-y-full rounded-lg border border-gray-200 bg-white/95 px-3 py-2 text-xs shadow-lg backdrop-blur-sm dark:border-gray-700 dark:bg-gray-900/95"
                        style={{ left: `${leftPct}%`, top: `${topPct}%` }}
                        role="tooltip"
                      >
                        <div className="flex items-center gap-1.5 font-medium text-gray-900 dark:text-white">
                          <span>{flagEmoji(hc.country_code)}</span>
                          <span>{hc.country_name}</span>
                        </div>
                        <div className="mt-1 text-gray-600 dark:text-gray-300">
                          <span className="tabular-nums">
                            {hc.entity_count.toLocaleString()}
                          </span>{" "}
                          {t("page.geographic.entities").toLowerCase()} ·{" "}
                          <span className="tabular-nums">
                            {hc.citation_sum.toLocaleString()}
                          </span>{" "}
                          {t("page.geographic.citations").toLowerCase()}
                        </div>
                      </div>
                    );
                  })()
                }
              />
            </div>

            {/* Detail / inspection panel */}
            <div className="col-span-1 rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
              {!selected && (
                <div className="flex h-full min-h-[420px] flex-col items-center justify-center p-6 text-center">
                  <div className="text-4xl">🗺️</div>
                  <p className="mt-3 text-sm font-medium text-gray-700 dark:text-gray-200">
                    {t("page.geographic.pick_country") || "Pick a country"}
                  </p>
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    {t("page.geographic.pick_hint") ||
                      "Click a row or a marker to inspect its 9-year citation evolution."}
                  </p>
                </div>
              )}

              {selected && (
                <div className="flex h-full min-h-[420px] flex-col">
                  <div className="flex items-start justify-between border-b border-gray-100 px-5 py-4 dark:border-gray-800">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-2xl leading-none">{flagEmoji(selected)}</span>
                        <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                          {selectedName}
                        </h3>
                        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-mono text-gray-500 dark:bg-gray-800 dark:text-gray-400">
                          {selected}
                        </span>
                      </div>
                      <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                        {selectedCountry
                          ? `${selectedCountry.percentage.toFixed(1)}% ${t("page.geographic.of_total") || "of total"}`
                          : t("page.geographic.no_data_in_filters") ||
                            "No entities match the current filters"}
                      </p>
                    </div>
                    <button
                      onClick={() => setSelected(null)}
                      className="rounded-full p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                      aria-label="Close"
                    >
                      ✕
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-3 px-5 py-4">
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
                        {t("page.geographic.entities")}
                      </p>
                      <p className="mt-1 text-xl font-semibold tabular-nums text-gray-900 dark:text-white">
                        {(selectedCountry?.entity_count ?? detail?.total_entities ?? 0).toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
                        {t("page.geographic.citations")}
                      </p>
                      <p className="mt-1 text-xl font-semibold tabular-nums text-gray-900 dark:text-white">
                        {(selectedCountry?.citation_sum ?? detail?.total_citations ?? 0).toLocaleString()}
                      </p>
                    </div>
                  </div>

                  <div className="flex-1 px-5 pb-5">
                    <p className="mb-2 text-[11px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
                      {t("page.geographic.sparkline_title") || "Citations · last 9 years"}
                    </p>
                    {detailLoading && (
                      <div className="h-32 animate-pulse rounded bg-gray-100 dark:bg-gray-800" />
                    )}
                    {!detailLoading && detail && detail.series.length > 0 && (
                      <div className="h-32">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={detail.series} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                            <defs>
                              <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.55} />
                                <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 6" stroke="#94a3b8" strokeOpacity={0.15} vertical={false} />
                            <XAxis
                              dataKey="year"
                              tick={{ fontSize: 10, fill: "#64748b" }}
                              axisLine={false}
                              tickLine={false}
                            />
                            <YAxis tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} width={32} />
                            <Tooltip
                              contentStyle={{
                                background: "rgba(15,23,42,0.92)",
                                border: "none",
                                borderRadius: 6,
                                color: "#f8fafc",
                                fontSize: 11,
                              }}
                              labelStyle={{ color: "#cbd5e1" }}
                              formatter={(v) => [Number(v).toLocaleString(), t("page.geographic.citations")] as [string, string]}
                            />
                            <Area
                              type="monotone"
                              dataKey="citation_sum"
                              stroke="#3b82f6"
                              strokeWidth={2}
                              fill="url(#sparkFill)"
                              dot={{ r: 2.5, fill: "#3b82f6" }}
                              activeDot={{ r: 4 }}
                              isAnimationActive
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                    {!detailLoading && detail && detail.series.every((p) => p.citation_sum === 0) && (
                      <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                        {t("page.geographic.no_year_data") || "No yearly data available for this country."}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Ranked table */}
          {countries.length === 0 ? (
            <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
              <UiEmptyState
                icon="globe"
                color="blue"
                title={t("page.geographic.empty_title")}
                description={t("page.geographic.empty_description")}
                size="compact"
              />
            </div>
          ) : (
            <div className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
              <div className="grid grid-cols-[2.5rem_1fr_8rem_5rem_6rem_4rem] items-center gap-2 border-b border-gray-100 px-4 py-2 text-[11px] font-medium uppercase tracking-wider text-gray-400 dark:border-gray-800">
                <span>#</span>
                <span>{t("page.geographic.country")}</span>
                <span>{t("page.geographic.distribution") || "Distribution"}</span>
                <span className="text-right">{t("page.geographic.entities")}</span>
                <span className="text-right">{t("page.geographic.citations")}</span>
                <span className="text-right">{t("page.geographic.percentage")}</span>
              </div>
              <div className="divide-y divide-gray-100 dark:divide-gray-800">
                {countries.map((c, i) => {
                  const isSel = selected === c.country_code;
                  const pct =
                    sortBy === "citation_sum"
                      ? (c.citation_sum / maxCitationSum) * 100
                      : (c.entity_count / maxEntityCount) * 100;
                  return (
                    <button
                      key={c.country_code}
                      type="button"
                      onClick={() => c.country_code !== "OTHER" && setSelected(c.country_code)}
                      className={`grid w-full grid-cols-[2.5rem_1fr_8rem_5rem_6rem_4rem] items-center gap-2 px-4 py-3 text-left transition ${
                        isSel
                          ? "bg-blue-50 dark:bg-blue-900/20"
                          : "hover:bg-gray-50 dark:hover:bg-gray-800/40"
                      } ${c.country_code === "OTHER" ? "cursor-default" : "cursor-pointer"}`}
                    >
                      <span className="font-mono text-xs text-gray-400">{i + 1}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-lg leading-none">{flagEmoji(c.country_code)}</span>
                        <span className="text-sm font-medium text-gray-800 dark:text-gray-200">
                          {c.country_name}
                        </span>
                        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-mono text-gray-500 dark:bg-gray-800 dark:text-gray-400">
                          {c.country_code}
                        </span>
                      </div>
                      <MarkerBar pct={pct} color={c.country_code === "OTHER" ? "bg-gray-400" : "bg-blue-500"} />
                      <span className="text-right text-sm tabular-nums text-gray-700 dark:text-gray-300">
                        {c.entity_count.toLocaleString()}
                      </span>
                      <span className="text-right text-sm tabular-nums text-gray-700 dark:text-gray-300">
                        {c.citation_sum.toLocaleString()}
                      </span>
                      <span className="text-right text-xs text-gray-400">{c.percentage.toFixed(1)}%</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* International collaboration pairs */}
          {showCollab && data.top_country_pairs && data.top_country_pairs.length > 0 && (
            <div
              data-testid="collab-pairs"
              className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900"
            >
              <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3 dark:border-gray-800">
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {t("page.geographic.top_pairs")}
                </h3>
                {selected && (
                  <span className="text-[11px] text-gray-500 dark:text-gray-400">
                    {t("page.geographic.pairs_filtered_hint") || "Filtered by selected country"}
                  </span>
                )}
              </div>
              <div className="divide-y divide-gray-100 dark:divide-gray-800">
                {data.top_country_pairs
                  .filter(
                    (pair) =>
                      !selected ||
                      pair.country_a === selected ||
                      pair.country_b === selected,
                  )
                  .map((pair, i) => (
                    <div
                      key={`${pair.country_a}-${pair.country_b}`}
                      className="flex items-center gap-3 px-4 py-3"
                    >
                      <span className="w-6 text-right text-xs font-mono text-gray-400">
                        {i + 1}
                      </span>
                      <button
                        type="button"
                        onClick={() => setSelected(pair.country_a)}
                        className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 hover:bg-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:hover:bg-blue-900/50"
                      >
                        <span>{flagEmoji(pair.country_a)}</span>
                        <span>{pair.country_a_name}</span>
                      </button>
                      <span className="text-gray-300 dark:text-gray-600">&harr;</span>
                      <button
                        type="button"
                        onClick={() => setSelected(pair.country_b)}
                        className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 hover:bg-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:hover:bg-emerald-900/50"
                      >
                        <span>{flagEmoji(pair.country_b)}</span>
                        <span>{pair.country_b_name}</span>
                      </button>
                      <span className="ml-auto rounded bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                        {pair.count.toLocaleString()}{" "}
                        {t("page.geographic.shared") || "shared"}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
