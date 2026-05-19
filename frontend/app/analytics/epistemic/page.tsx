"use client";

import { useState, useEffect, useCallback } from "react";
import { useDomain } from "../../contexts/DomainContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { useAuth } from "../../contexts/AuthContext";
import { apiFetch } from "@/lib/api";
import { useToast } from "../../components/ui/Toast";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts";

// ── Types ────────────────────────────────────────────────────────────────────

interface ParadigmInfo {
  id: string;
  label: string;
}

interface DistributionResponse {
  domain_id: string;
  total_classified: number;
  total_unclassified: number;
  paradigm_counts: Record<string, number>;
  paradigms: ParadigmInfo[];
  by_year: { year: number; paradigm_counts: Record<string, number> }[];
}

// ── Constants ────────────────────────────────────────────────────────────────

const PARADIGM_COLORS: Record<string, string> = {
  empiricist: "#6366f1",
  constructivist: "#8b5cf6",
  critical: "#ec4899",
};

const FALLBACK_COLORS = ["#6366f1", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#06b6d4"];

function getColor(paradigmId: string, index: number): string {
  return PARADIGM_COLORS[paradigmId] || FALLBACK_COLORS[index % FALLBACK_COLORS.length];
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function EpistemicAnalysisPage() {
  const { activeDomain } = useDomain();
  const { t } = useLanguage();
  const { user } = useAuth();
  const { toast } = useToast();

  const [data, setData] = useState<DistributionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [classifying, setClassifying] = useState(false);
  const [noConfig, setNoConfig] = useState(false);

  const domainId = activeDomain?.id ?? "default";
  const isAdmin = user?.role === "super_admin" || user?.role === "admin";

  const fetchDistribution = useCallback(async () => {
    setLoading(true);
    setNoConfig(false);
    try {
      const resp = await apiFetch(`/analytics/epistemic/${domainId}/distribution`);
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
    fetchDistribution();
  }, [fetchDistribution]);

  const handleClassify = async () => {
    setClassifying(true);
    try {
      const resp = await apiFetch(`/analytics/epistemic/${domainId}/classify`, {
        method: "POST",
      });
      if (resp.ok) {
        const result = await resp.json();
        toast(
          `${t("epistemic.classify_success")} (${result.classified} ${t("epistemic.classified")})`,
          "success",
        );
        await fetchDistribution();
      } else {
        toast(t("epistemic.classify_error"), "error");
      }
    } catch {
      toast(t("epistemic.classify_error"), "error");
    } finally {
      setClassifying(false);
    }
  };

  const isEmpty = !data || data.total_classified === 0;

  // Prepare chart data
  const pieData = data
    ? Object.entries(data.paradigm_counts).map(([id, count]) => ({
        name: data.paradigms.find((p) => p.id === id)?.label || id,
        id,
        value: count,
      }))
    : [];

  const paradigmIds = data?.paradigms.map((p) => p.id) || [];

  const areaData = data
    ? data.by_year.map((entry) => {
        const total = Object.values(entry.paradigm_counts).reduce((s, v) => s + v, 0);
        const row: Record<string, unknown> = { year: entry.year };
        for (const pid of paradigmIds) {
          row[pid] = total > 0 ? Math.round(((entry.paradigm_counts[pid] || 0) / total) * 100) : 0;
        }
        return row;
      })
    : [];

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--ukip-text-strong)]">
            {t("epistemic.title")}
          </h1>
          <p className="mt-1 text-sm text-[var(--ukip-muted)]">
            {t("epistemic.subtitle")}
          </p>
        </div>

        {isAdmin && !noConfig && (
          <button
            onClick={handleClassify}
            disabled={classifying}
            className="rounded-lg bg-[var(--ukip-accent)] px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {classifying ? t("epistemic.classifying") : t("epistemic.classify")}
          </button>
        )}
      </div>

      {/* Content */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-8 animate-pulse rounded-md bg-[var(--ukip-panel)]" />
          ))}
        </div>
      ) : noConfig ? (
        /* No epistemology config state */
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--ukip-border)] bg-[var(--ukip-panel)] py-16">
          <svg className="mb-4 h-12 w-12 text-[var(--ukip-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
          <h3 className="text-lg font-semibold text-[var(--ukip-text-strong)]">
            {t("epistemic.no_config_title")}
          </h3>
          <p className="mt-1 max-w-sm text-center text-sm text-[var(--ukip-muted)]">
            {t("epistemic.no_config_description")}
          </p>
        </div>
      ) : isEmpty ? (
        /* Empty state */
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--ukip-border)] bg-[var(--ukip-panel)] py-16">
          <svg className="mb-4 h-12 w-12 text-[var(--ukip-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
          </svg>
          <h3 className="text-lg font-semibold text-[var(--ukip-text-strong)]">
            {t("epistemic.empty_title")}
          </h3>
          <p className="mt-1 max-w-sm text-center text-sm text-[var(--ukip-muted)]">
            {t("epistemic.empty_description")}
          </p>
          {isAdmin && (
            <button
              onClick={handleClassify}
              disabled={classifying}
              className="mt-6 rounded-lg bg-[var(--ukip-accent)] px-5 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {classifying ? t("epistemic.classifying") : t("epistemic.classify")}
            </button>
          )}
        </div>
      ) : (
        /* Charts */
        <div className="space-y-6">
          {/* Summary stats */}
          <div className="flex gap-4">
            <div className="rounded-lg border border-[var(--ukip-border)] bg-[var(--ukip-bg)] px-4 py-3">
              <p className="text-xs text-[var(--ukip-muted)]">{t("epistemic.classified")}</p>
              <p className="text-2xl font-bold text-[var(--ukip-text-strong)]">{data!.total_classified}</p>
            </div>
            <div className="rounded-lg border border-[var(--ukip-border)] bg-[var(--ukip-bg)] px-4 py-3">
              <p className="text-xs text-[var(--ukip-muted)]">{t("epistemic.unclassified")}</p>
              <p className="text-2xl font-bold text-[var(--ukip-muted)]">{data!.total_unclassified}</p>
            </div>
          </div>

          {/* Distribution donut */}
          <div className="rounded-xl border border-[var(--ukip-border)] bg-[var(--ukip-bg)] p-6">
            <h2 className="mb-4 text-lg font-semibold text-[var(--ukip-text-strong)]">
              {t("epistemic.distribution")}
            </h2>
            <div className="flex flex-col items-center gap-6 md:flex-row">
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={120}
                    paddingAngle={3}
                    dataKey="value"
                    nameKey="name"
                  >
                    {pieData.map((entry, i) => (
                      <Cell key={entry.id} fill={getColor(entry.id, i)} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) => [`${Number(value ?? 0)} ${t("epistemic.entities")}`, ""]}
                  />
                </PieChart>
              </ResponsiveContainer>

              {/* Legend */}
              <div className="space-y-2">
                {pieData.map((entry, i) => {
                  const pct = data!.total_classified > 0
                    ? Math.round((entry.value / data!.total_classified) * 100)
                    : 0;
                  return (
                    <div key={entry.id} className="flex items-center gap-2">
                      <div
                        className="h-3 w-3 rounded-full"
                        style={{ backgroundColor: getColor(entry.id, i) }}
                      />
                      <span className="text-sm text-[var(--ukip-text)]">{entry.name}</span>
                      <span className="text-sm font-semibold text-[var(--ukip-muted)]">
                        {pct}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Temporal evolution */}
          {areaData.length > 1 && (
            <div className="rounded-xl border border-[var(--ukip-border)] bg-[var(--ukip-bg)] p-6">
              <h2 className="mb-4 text-lg font-semibold text-[var(--ukip-text-strong)]">
                {t("epistemic.temporal")}
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={areaData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--ukip-border)" />
                  <XAxis dataKey="year" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} unit="%" />
                  <Tooltip formatter={(value) => [`${Number(value ?? 0)}%`, ""]} />
                  <Legend />
                  {paradigmIds.map((pid, i) => (
                    <Area
                      key={pid}
                      type="monotone"
                      dataKey={pid}
                      name={data!.paradigms.find((p) => p.id === pid)?.label || pid}
                      stackId="1"
                      fill={getColor(pid, i)}
                      stroke={getColor(pid, i)}
                      fillOpacity={0.6}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
