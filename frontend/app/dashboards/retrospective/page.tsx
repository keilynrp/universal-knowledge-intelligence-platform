"use client";

import { useCallback, useState, type ReactElement } from "react";
import { apiFetch } from "@/lib/api";
import { Badge, Button, EmptyState, ErrorBanner, Input, PageHeader } from "../../components/ui";
import { useLanguage } from "../../contexts/LanguageContext";

// ── Types (mirror backend/routers/retrospective.py) ─────────────────────────

type MetricValue = string | number | boolean | null;

interface ChangedField {
  prior: MetricValue;
  current: MetricValue;
  prior_provenance: "present" | "unknown" | "unavailable";
}

interface CompareResponse {
  issn_l: string;
  found_prior: boolean;
  as_of: string;
  prior_valid_at: string | null;
  current: Record<string, MetricValue>;
  prior: Record<string, MetricValue> | null;
  changed_fields: Record<string, ChangedField>;
  missing_reason: string | null;
}

interface SeriesPoint {
  valid_at: string;
  payload: Record<string, MetricValue>;
}

const METRIC_FIELDS = ["nif", "nif_bayes", "two_yr_mean_citedness", "works_2yr", "nif_field"] as const;

function fmt(value: MetricValue): string {
  if (value === null || value === undefined) return "—";
  return String(value);
}

export default function RetrospectivePage(): ReactElement {
  const { t } = useLanguage();
  const tr = useCallback(
    (key: string, fallback: string): string => {
      const value = t(key);
      return value === key ? fallback : value;
    },
    [t],
  );

  const [issnL, setIssnL] = useState("");
  const [asOf, setAsOf] = useState("");
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [series, setSeries] = useState<SeriesPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const run = useCallback(async () => {
    const issn = issnL.trim();
    if (!issn || !asOf) return;
    setLoading(true);
    setError(null);
    setNotFound(false);
    setComparison(null);
    setSeries([]);
    try {
      const asOfIso = new Date(asOf).toISOString();
      const cmp = await apiFetch(
        `/retrospective/journals/${encodeURIComponent(issn)}/compare?as_of=${encodeURIComponent(asOfIso)}`,
      );
      if (cmp.status === 404) {
        setNotFound(true);
        return;
      }
      if (!cmp.ok) throw new Error(`HTTP ${cmp.status}`);
      setComparison((await cmp.json()) as CompareResponse);

      const ts = await apiFetch(`/retrospective/journals/${encodeURIComponent(issn)}/timeseries`);
      if (ts.ok) setSeries(((await ts.json()).series ?? []) as SeriesPoint[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : tr("retrospective.load_failed", "Unable to load history."));
    } finally {
      setLoading(false);
    }
  }, [issnL, asOf, tr]);

  const changed = comparison?.changed_fields ?? {};

  return (
    <div className="space-y-6">
      <PageHeader
        title={tr("retrospective.title", "Retrospective — Historical Comparison")}
        description={tr(
          "retrospective.subtitle",
          "Reconstruct what UKIP knew about a journal at a point in time and compare it with its current state. Reads are point-in-time and never fall back to current state when history is missing.",
        )}
      />

      <section className="rounded-2xl border border-[var(--ukip-border)] bg-[var(--ukip-surface)] p-5">
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1 text-sm text-[var(--ukip-muted)]">
            {tr("retrospective.issn", "Journal ISSN-L")}
            <Input
              value={issnL}
              onChange={(e) => setIssnL(e.target.value)}
              placeholder="0028-0836"
              className="w-48"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-[var(--ukip-muted)]">
            {tr("retrospective.as_of", "As of")}
            <Input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} className="w-48" />
          </label>
          <Button onClick={() => void run()} disabled={loading || !issnL.trim() || !asOf}>
            {loading ? tr("retrospective.loading", "Loading…") : tr("retrospective.compare", "Compare")}
          </Button>
        </div>
      </section>

      {error && <ErrorBanner message={error} />}

      {notFound && (
        <EmptyState
          icon="search"
          color="amber"
          title={tr("retrospective.not_found_title", "Journal not found")}
          description={tr("retrospective.not_found_body", "No current metric row exists for that ISSN-L.")}
        />
      )}

      {comparison && !comparison.found_prior && (
        <EmptyState
          icon="bell"
          color="slate"
          title={tr("retrospective.no_history_title", "No history at that date")}
          description={tr(
            "retrospective.no_history_body",
            "No snapshot exists at or before the selected date. Current state is not shown as a substitute.",
          )}
        />
      )}

      {comparison && comparison.found_prior && (
        <section className="rounded-2xl border border-[var(--ukip-border)] bg-[var(--ukip-surface)] p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--ukip-muted)]">
              {tr("retrospective.comparison", "Current vs prior snapshot")}
            </h2>
            {comparison.prior_valid_at && (
              <span className="text-xs text-[var(--ukip-muted)]">
                {tr("retrospective.snapshot_from", "Snapshot from")} {comparison.prior_valid_at.slice(0, 10)}
              </span>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[var(--ukip-muted)]">
                  <th className="py-2 pr-4 font-medium">{tr("retrospective.field", "Field")}</th>
                  <th className="py-2 pr-4 font-medium">{tr("retrospective.prior", "Prior")}</th>
                  <th className="py-2 pr-4 font-medium">{tr("retrospective.current", "Current")}</th>
                  <th className="py-2 font-medium">{tr("retrospective.status", "Status")}</th>
                </tr>
              </thead>
              <tbody>
                {METRIC_FIELDS.map((f) => {
                  const delta = changed[f];
                  const priorVal = comparison.prior ? comparison.prior[f] : null;
                  const currentVal = comparison.current[f];
                  return (
                    <tr key={f} className="border-t border-[var(--ukip-border)]">
                      <td className="py-2 pr-4 font-medium text-[var(--ukip-text)]">{f}</td>
                      <td className="py-2 pr-4 text-[var(--ukip-text)]">{fmt(delta ? delta.prior : priorVal)}</td>
                      <td className="py-2 pr-4 text-[var(--ukip-text)]">{fmt(delta ? delta.current : currentVal)}</td>
                      <td className="py-2">
                        {delta ? (
                          <Badge variant="warning">
                            {tr("retrospective.changed", "changed")}
                            {delta.prior_provenance !== "present" ? ` · ${delta.prior_provenance}` : ""}
                          </Badge>
                        ) : (
                          <Badge variant="default">{tr("retrospective.unchanged", "unchanged")}</Badge>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {series.length > 0 && (
        <section className="rounded-2xl border border-[var(--ukip-border)] bg-[var(--ukip-surface)] p-5">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-[0.16em] text-[var(--ukip-muted)]">
            {tr("retrospective.timeline", "NIF timeline")}
          </h2>
          <ul className="space-y-2">
            {series.map((p) => (
              <li
                key={p.valid_at}
                className="flex items-center justify-between border-b border-[var(--ukip-border)] pb-2 text-sm text-[var(--ukip-text)]"
              >
                <span className="text-[var(--ukip-muted)]">{p.valid_at.slice(0, 10)}</span>
                <span>NIF {fmt(p.payload.nif)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
