"use client";

import { useState, useEffect, useCallback } from "react";
import { useDomain } from "../../contexts/DomainContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { apiFetch } from "@/lib/api";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

// ── Types ────────────────────────────────────────────────────────────────────

interface MetricValue {
  value: number | null;
  label: string;
  low_sample?: boolean;
  by_year: { year: number; value: number | null; low_sample?: boolean }[];
}

interface HealthData {
  gini_authorship: MetricValue;
  international_collaboration_rate: MetricValue;
  open_access_rate: MetricValue;
  epistemic_diversity: MetricValue;
  newcomer_rate: MetricValue;
}

// ── Constants ────────────────────────────────────────────────────────────────

const METRIC_KEYS = [
  "gini_authorship",
  "international_collaboration_rate",
  "open_access_rate",
  "epistemic_diversity",
  "newcomer_rate",
] as const;

const METRIC_COLORS: Record<string, string> = {
  gini_authorship: "#6366f1",
  international_collaboration_rate: "#06b6d4",
  open_access_rate: "#10b981",
  epistemic_diversity: "#8b5cf6",
  newcomer_rate: "#f59e0b",
};

function getIndicatorColor(metricId: string, label: string): string {
  if (label === "insufficient_data") return "bg-gray-300";
  if (metricId === "gini_authorship") {
    if (label.includes("low")) return "bg-green-500";
    if (label.includes("moderate")) return "bg-amber-500";
    return "bg-red-500";
  }
  if (metricId === "epistemic_diversity") {
    if (label.includes("high") || label.includes("good")) return "bg-green-500";
    if (label.includes("moderate")) return "bg-amber-500";
    return "bg-red-500";
  }
  // For rates: higher is generally better
  if (label === "high") return "bg-green-500";
  if (label === "moderate") return "bg-amber-500";
  return "bg-red-500";
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function DomainHealthPage() {
  const { activeDomain } = useDomain();
  const { t } = useLanguage();

  const [data, setData] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [noConfig, setNoConfig] = useState(false);
  const [visibleMetrics, setVisibleMetrics] = useState<Set<string>>(
    new Set(METRIC_KEYS)
  );
  const [compareDomain, setCompareDomain] = useState<string>("");
  const [compareData, setCompareData] = useState<HealthData | null>(null);

  const domainId = activeDomain?.id ?? "default";

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    setNoConfig(false);
    try {
      const resp = await apiFetch(`/analytics/domain-health/${domainId}`);
      if (resp.ok) {
        setData(await resp.json());
      } else if (resp.status === 400) {
        setNoConfig(true);
      }
    } catch {
      /* network error */
    } finally {
      setLoading(false);
    }
  }, [domainId]);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  useEffect(() => {
    if (!compareDomain) {
      setCompareData(null);
      return;
    }
    (async () => {
      try {
        const resp = await apiFetch(`/analytics/domain-health/${compareDomain}`);
        if (resp.ok) {
          setCompareData(await resp.json());
        } else {
          setCompareData(null);
        }
      } catch {
        setCompareData(null);
      }
    })();
  }, [compareDomain]);

  const toggleMetric = (key: string) => {
    setVisibleMetrics((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const isEmpty = !data || METRIC_KEYS.every((k) => data[k].value === null);

  // Build trend chart data
  const trendData =
    data && !isEmpty
      ? (() => {
          const allYears = new Set<number>();
          METRIC_KEYS.forEach((k) =>
            data[k].by_year.forEach((e) => allYears.add(e.year))
          );
          return [...allYears].sort().map((year) => {
            const row: Record<string, unknown> = { year };
            METRIC_KEYS.forEach((k) => {
              const entry = data[k].by_year.find((e) => e.year === year);
              row[k] = entry?.value ?? null;
            });
            return row;
          });
        })()
      : [];

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--ukip-text-strong)]">
          {t("domain_health.title")}
        </h1>
        <p className="mt-1 text-sm text-[var(--ukip-muted)]">
          {t("domain_health.subtitle")}
        </p>
      </div>

      {/* Content */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-xl bg-[var(--ukip-panel)]"
            />
          ))}
        </div>
      ) : noConfig ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--ukip-border)] bg-[var(--ukip-panel)] py-16">
          <svg
            className="mb-4 h-12 w-12 text-[var(--ukip-muted)]"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
            />
          </svg>
          <h3 className="text-lg font-semibold text-[var(--ukip-text-strong)]">
            {t("domain_health.no_config_title")}
          </h3>
          <p className="mt-1 max-w-sm text-center text-sm text-[var(--ukip-muted)]">
            {t("domain_health.no_config_description")}
          </p>
        </div>
      ) : isEmpty ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--ukip-border)] bg-[var(--ukip-panel)] py-16">
          <svg
            className="mb-4 h-12 w-12 text-[var(--ukip-muted)]"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
            />
          </svg>
          <h3 className="text-lg font-semibold text-[var(--ukip-text-strong)]">
            {t("domain_health.empty_title")}
          </h3>
          <p className="mt-1 max-w-sm text-center text-sm text-[var(--ukip-muted)]">
            {t("domain_health.empty_description")}
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Metric cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {METRIC_KEYS.map((key) => {
              const metric = data![key];
              const color = getIndicatorColor(key, metric.label);
              return (
                <div
                  key={key}
                  className="rounded-xl border border-[var(--ukip-border)] bg-[var(--ukip-bg)] p-4"
                >
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-medium text-[var(--ukip-muted)]">
                      {t(`domain_health.metric_${key}`)}
                    </p>
                    <div className={`h-2.5 w-2.5 rounded-full ${color}`} />
                  </div>
                  <p className="mt-2 text-2xl font-bold text-[var(--ukip-text-strong)]">
                    {metric.value !== null
                      ? key === "gini_authorship" || key === "epistemic_diversity"
                        ? metric.value.toFixed(3)
                        : `${(metric.value * 100).toFixed(1)}%`
                      : "N/A"}
                  </p>
                  <p className="mt-1 text-xs text-[var(--ukip-muted)]">
                    {t(`domain_health.label_${metric.label}`)}
                  </p>
                  {metric.low_sample && (
                    <p className="mt-1 text-xs text-amber-500">
                      {t("domain_health.low_sample_warning")}
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          {/* Temporal trend */}
          {trendData.length > 1 && (
            <div className="rounded-xl border border-[var(--ukip-border)] bg-[var(--ukip-bg)] p-6">
              <h2 className="mb-4 text-lg font-semibold text-[var(--ukip-text-strong)]">
                {t("domain_health.temporal_trends")}
              </h2>
              {/* Metric toggles */}
              <div className="mb-4 flex flex-wrap gap-2">
                {METRIC_KEYS.map((key) => (
                  <button
                    key={key}
                    onClick={() => toggleMetric(key)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition-opacity ${
                      visibleMetrics.has(key)
                        ? "opacity-100"
                        : "opacity-40"
                    }`}
                    style={{
                      backgroundColor: `${METRIC_COLORS[key]}20`,
                      color: METRIC_COLORS[key],
                    }}
                  >
                    {t(`domain_health.metric_${key}`)}
                  </button>
                ))}
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={trendData}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--ukip-border)"
                  />
                  <XAxis dataKey="year" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  {METRIC_KEYS.filter((k) => visibleMetrics.has(k)).map(
                    (key) => (
                      <Line
                        key={key}
                        type="monotone"
                        dataKey={key}
                        name={t(`domain_health.metric_${key}`)}
                        stroke={METRIC_COLORS[key]}
                        strokeWidth={2}
                        dot={false}
                        connectNulls
                      />
                    )
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Cross-domain comparison */}
          <div className="rounded-xl border border-[var(--ukip-border)] bg-[var(--ukip-bg)] p-6">
            <h2 className="mb-4 text-lg font-semibold text-[var(--ukip-text-strong)]">
              {t("domain_health.compare_title")}
            </h2>
            <select
              className="rounded-lg border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-3 py-2 text-sm text-[var(--ukip-text)]"
              value={compareDomain}
              onChange={(e) => setCompareDomain(e.target.value)}
            >
              <option value="">{t("domain_health.compare_select")}</option>
              {/* Other domains would be listed here */}
            </select>
            {compareData && (
              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                {METRIC_KEYS.map((key) => {
                  const current = data![key];
                  const compare = compareData[key];
                  return (
                    <div
                      key={key}
                      className="flex items-center justify-between rounded-lg border border-[var(--ukip-border)] px-3 py-2"
                    >
                      <span className="text-xs text-[var(--ukip-muted)]">
                        {t(`domain_health.metric_${key}`)}
                      </span>
                      <div className="flex gap-3 text-sm font-semibold">
                        <span className="text-[var(--ukip-text-strong)]">
                          {current.value?.toFixed(3) ?? "N/A"}
                        </span>
                        <span className="text-[var(--ukip-muted)]">vs</span>
                        <span className="text-[var(--ukip-accent)]">
                          {compare.value?.toFixed(3) ?? "N/A"}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
