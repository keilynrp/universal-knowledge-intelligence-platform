"use client";

import { useCallback, useEffect, useRef, useState, type ReactElement } from "react";
import { apiFetch } from "@/lib/api";
import { Badge, EmptyState, ErrorBanner, PageHeader, SkeletonCard } from "../../components/ui";
import { useLanguage } from "../../contexts/LanguageContext";

// ── Types ──────────────────────────────────────────────────────────────────
// Mirrors backend/openalex_lake/status.py::resolve_status + the admin router's
// backfill_total_issns addition.

interface RateLimitSnapshot {
  limit?: number;
  remaining?: number;
  limit_usd?: number;
  remaining_usd?: number;
  prepaid_remaining_usd?: number;
  onetime_remaining?: number;
  last_request_cost_usd?: number;
  reset_seconds?: number;
  captured_at?: string;
}

interface LakeStatus {
  lake?: "not_initialized" | "locked";
  hint?: string;
  phase?: "backfill" | "incremental";
  works_watermark?: string | null;
  backfill_journals_done?: number;
  backfill_total_issns?: number | null;
  journals?: number;
  year_min?: number | null;
  year_max?: number | null;
  tables?: Record<string, number>;
  rate_limit?: RateLimitSnapshot | null;
}

const AUTO_REFRESH_MS = 30_000;
const TABLE_ORDER = [
  "fact_works",
  "fact_authorship",
  "fact_work_topic",
  "fact_work_counts_by_year",
  "fact_citation",
  "dim_author",
  "dim_institution",
  "dim_source",
  "dim_topic",
];

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("en-US");
}

function formatUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `$${value.toFixed(4)}`;
}

function formatRelativeMinutes(iso: string | undefined): number | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  return Math.max(0, Math.round((Date.now() - then) / 60000));
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function DataOpsPage(): ReactElement {
  const { t } = useLanguage();
  const tr = useCallback((key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  }, [t]);

  const [status, setStatus] = useState<LakeStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    setError(null);
    try {
      const res = await apiFetch("/admin/openalex-lake/status");
      if (res.status === 403) {
        setForbidden(true);
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setStatus(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : tr("dashboards.data_ops.load_failed", "Unable to load the lake status."));
    } finally {
      setLoading(false);
    }
  }, [tr]);

  useEffect(() => {
    void fetchStatus();
    timerRef.current = setInterval(() => void fetchStatus(), AUTO_REFRESH_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [fetchStatus]);

  const rateLimit = status?.rate_limit ?? null;
  const capturedMinutesAgo = formatRelativeMinutes(rateLimit?.captured_at);
  const backfillPct =
    status?.backfill_total_issns && status.backfill_total_issns > 0
      ? Math.min(100, Math.round(((status.backfill_journals_done ?? 0) / status.backfill_total_issns) * 100))
      : null;
  const dailyPct =
    rateLimit?.limit && rateLimit.limit > 0 && rateLimit.remaining !== undefined
      ? Math.round((rateLimit.remaining / rateLimit.limit) * 100)
      : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title={tr("dashboards.data_ops.title", "OpenAlex Lake — Data Ops")}
        description={tr(
          "dashboards.data_ops.subtitle",
          "Ingestion status for the OpenAlex analytical lake: backfill progress, table counts, and the last OpenAlex quota seen during a pull.",
        )}
      />

      {forbidden && (
        <EmptyState
          icon="key"
          color="amber"
          title={tr("dashboards.data_ops.forbidden_title", "Admin access required")}
          description={tr("dashboards.data_ops.forbidden_body", "This page is restricted to admin/super_admin roles.")}
        />
      )}

      {!forbidden && error && <ErrorBanner message={error} onRetry={fetchStatus} variant="card" />}

      {!forbidden && !error && loading && (
        <div className="grid gap-4 md:grid-cols-2">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}

      {!forbidden && !loading && !error && status?.lake === "not_initialized" && (
        <EmptyState
          icon="document"
          color="slate"
          title={tr("dashboards.data_ops.not_initialized_title", "No pull has run yet")}
          description={status.hint ?? tr("dashboards.data_ops.not_initialized_body", "Run the first pull from the backend container.")}
        />
      )}

      {!forbidden && !loading && !error && status?.lake === "locked" && (
        <EmptyState
          icon="bolt"
          color="violet"
          title={tr("dashboards.data_ops.locked_title", "A pull is running right now")}
          description={status.hint ?? tr("dashboards.data_ops.locked_body", "The lake file is locked by the running process. Refresh in a moment.")}
        />
      )}

      {!forbidden && !loading && !error && status && !status.lake && (
        <div className="grid gap-4 lg:grid-cols-2">
          {/* Ingestion phase + backfill progress */}
          <section className="rounded-2xl border border-[var(--ukip-border)] bg-[var(--ukip-surface)] p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--ukip-muted)]">
                {tr("dashboards.data_ops.phase_title", "Ingestion phase")}
              </p>
              <Badge variant={status.phase === "incremental" ? "success" : "info"} dot>
                {status.phase === "incremental"
                  ? tr("dashboards.data_ops.phase_incremental", "Incremental (up to date)")
                  : tr("dashboards.data_ops.phase_backfill", "Backfill in progress")}
              </Badge>
            </div>

            {status.phase === "backfill" && (
              <div className="mt-4">
                <div className="flex items-baseline justify-between text-sm">
                  <span className="font-mono text-[var(--ukip-text)]">
                    {formatNumber(status.backfill_journals_done)} / {formatNumber(status.backfill_total_issns)}
                  </span>
                  <span className="text-xs text-[var(--ukip-muted)]">
                    {tr("dashboards.data_ops.journals_done", "journals completed")}
                  </span>
                </div>
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-[var(--ukip-panel-strong)]">
                  <div
                    className="h-full rounded-full bg-[var(--ukip-violet)] transition-[width]"
                    style={{ width: `${backfillPct ?? 0}%` }}
                  />
                </div>
              </div>
            )}

            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-xs text-[var(--ukip-muted)]">{tr("dashboards.data_ops.journals_with_data", "Journals with data")}</dt>
                <dd className="font-mono font-semibold text-[var(--ukip-text)]">{formatNumber(status.journals)}</dd>
              </div>
              <div>
                <dt className="text-xs text-[var(--ukip-muted)]">{tr("dashboards.data_ops.year_range", "Year range")}</dt>
                <dd className="font-mono font-semibold text-[var(--ukip-text)]">
                  {status.year_min ?? "—"}–{status.year_max ?? "—"}
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="text-xs text-[var(--ukip-muted)]">{tr("dashboards.data_ops.watermark", "Watermark (last complete pass)")}</dt>
                <dd className="font-mono font-semibold text-[var(--ukip-text)]">{status.works_watermark ?? "—"}</dd>
              </div>
            </dl>
          </section>

          {/* OpenAlex quota snapshot */}
          <section className="rounded-2xl border border-[var(--ukip-border)] bg-[var(--ukip-surface)] p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--ukip-muted)]">
              {tr("dashboards.data_ops.quota_title", "OpenAlex quota (last seen)")}
            </p>
            {!rateLimit ? (
              <p className="mt-3 text-sm text-[var(--ukip-muted)]">
                {tr("dashboards.data_ops.quota_none", "No quota captured yet — runs the next time a pull makes a request.")}
              </p>
            ) : (
              <>
                <div className="mt-3">
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="font-mono text-[var(--ukip-text)]">
                      {formatNumber(rateLimit.remaining)} / {formatNumber(rateLimit.limit)}
                    </span>
                    <span className="text-xs text-[var(--ukip-muted)]">{tr("dashboards.data_ops.quota_daily", "daily requests left")}</span>
                  </div>
                  <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-[var(--ukip-panel-strong)]">
                    <div
                      className={`h-full rounded-full transition-[width] ${(dailyPct ?? 100) < 15 ? "bg-[var(--ukip-danger)]" : "bg-[var(--ukip-cyan)]"}`}
                      style={{ width: `${dailyPct ?? 0}%` }}
                    />
                  </div>
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt className="text-xs text-[var(--ukip-muted)]">{tr("dashboards.data_ops.quota_prepaid", "Prepaid credits")}</dt>
                    <dd className="font-mono font-semibold text-[var(--ukip-text)]">{formatUsd(rateLimit.prepaid_remaining_usd)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-[var(--ukip-muted)]">{tr("dashboards.data_ops.quota_last_cost", "Last request cost")}</dt>
                    <dd className="font-mono font-semibold text-[var(--ukip-text)]">{formatUsd(rateLimit.last_request_cost_usd)}</dd>
                  </div>
                  <div className="col-span-2">
                    <dt className="text-xs text-[var(--ukip-muted)]">{tr("dashboards.data_ops.quota_captured", "Captured")}</dt>
                    <dd className="text-sm text-[var(--ukip-text)]">
                      {capturedMinutesAgo === null
                        ? "—"
                        : capturedMinutesAgo < 1
                          ? tr("dashboards.data_ops.just_now", "just now")
                          : `${capturedMinutesAgo} ${tr("dashboards.data_ops.min_ago", "min ago")}`}
                    </dd>
                  </div>
                </dl>
              </>
            )}
          </section>

          {/* Table row counts */}
          <section className="rounded-2xl border border-[var(--ukip-border)] bg-[var(--ukip-surface)] p-5 lg:col-span-2">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--ukip-muted)]">
              {tr("dashboards.data_ops.tables_title", "Ingested rows by table")}
            </p>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {TABLE_ORDER.filter((name) => status.tables && name in status.tables).map((name) => (
                <div key={name} className="rounded-xl border border-[var(--ukip-border)] bg-[var(--ukip-panel)] p-3">
                  <p className="truncate font-mono text-[10px] text-[var(--ukip-muted)]">{name}</p>
                  <p className="mt-1 font-mono text-lg font-bold text-[var(--ukip-text)]">
                    {formatNumber(status.tables?.[name])}
                  </p>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
