"use client";

import { useState } from "react";
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { PageHeader, Badge } from "../../components/ui";
import { apiFetch } from "../../../lib/api";
import { useToast } from "../../components/ui";

// ── Types ──────────────────────────────────────────────────────────────────────

interface YearStats {
  year: number;
  optimistic: number;
  median: number;
  pessimistic: number;
}

interface HistoBucket {
  bucket: string;
  count: number;
}

interface ROIResult {
  p5: number; p10: number; p25: number; p50: number;
  p75: number; p90: number; p95: number;
  net_p10: number; net_p50: number; net_p90: number;
  pessimistic_roi: number; base_roi: number; optimistic_roi: number;
  breakeven_prob: number; breakeven_year: number;
  trajectory: YearStats[];
  histogram: HistoBucket[];
  n_simulations: number;
  params: Record<string, number>;
}

interface FormState {
  investment: number;
  horizon_years: 3 | 5 | 10;
  base_adoption_rate: number;   // 0–100 (UI %), sent as /100
  adoption_volatility: number;  // 0–100 (UI %)
  revenue_per_unit: number;
  market_size: number;
  annual_cost: number;
  n_simulations: number;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmt(n: number, decimals = 0) {
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toFixed(decimals);
}

function pct(n: number) {
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

function exportCsv(result: ROIResult) {
  const rows: string[] = [
    "year,optimistic_roi_pct,median_roi_pct,pessimistic_roi_pct",
    ...result.trajectory.map(
      (r) => `${r.year},${r.optimistic},${r.median},${r.pessimistic}`
    ),
  ];
  const blob = new Blob([rows.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "roi_simulation.csv";
  a.click();
  URL.revokeObjectURL(url);
}

// ── Sub-components ──────────────────────────────────────────────────────────────

function SliderInput({
  label, value, min, max, step, unit, onChange,
}: {
  label: string; value: number; min: number; max: number;
  step: number; unit?: string; onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs font-medium text-gray-600 dark:text-gray-400">{label}</label>
        <span className="text-xs font-mono font-semibold text-gray-900 dark:text-white tabular-nums">
          {value}{unit}
        </span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-1.5 accent-blue-600"
      />
      <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
        <span>{min}{unit}</span><span>{max}{unit}</span>
      </div>
    </div>
  );
}

function NumberInput({
  label, value, min, step, prefix, onChange,
}: {
  label: string; value: number; min?: number; step?: number;
  prefix?: string; onChange: (v: number) => void;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">{label}</label>
      <div className="flex items-center overflow-hidden rounded-lg border border-gray-300 bg-white dark:border-gray-600 dark:bg-gray-800">
        {prefix && (
          <span className="px-2.5 text-sm text-gray-500 dark:text-gray-400 border-r border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700">
            {prefix}
          </span>
        )}
        <input
          type="number"
          value={value}
          min={min ?? 0}
          step={step ?? 1}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full bg-transparent px-3 py-2 text-sm text-gray-900 dark:text-white focus:outline-none"
        />
      </div>
    </div>
  );
}

function ScenarioCard({
  label, roi, net, color,
}: {
  label: string; roi: number; net: number; color: "red" | "blue" | "green";
}) {
  const ring = { red: "ring-red-200 dark:ring-red-500/20", blue: "ring-blue-200 dark:ring-blue-500/20", green: "ring-green-200 dark:ring-green-500/20" }[color];
  const textColor = { red: "text-red-600 dark:text-red-400", blue: "text-blue-600 dark:text-blue-400", green: "text-green-600 dark:text-green-400" }[color];
  const bg = { red: "bg-red-50 dark:bg-red-500/5", blue: "bg-blue-50 dark:bg-blue-500/5", green: "bg-green-50 dark:bg-green-500/5" }[color];
  return (
    <div className={`rounded-2xl ring-1 ${ring} ${bg} p-5`}>
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">{label}</p>
      <p className={`mt-2 text-3xl font-black tabular-nums ${textColor}`}>{pct(roi)}</p>
      <p className="mt-1 text-sm font-medium text-gray-500 dark:text-gray-400">
        Net: {net >= 0 ? "+" : ""}{fmt(net)}
      </p>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

const DEFAULT: FormState = {
  investment: 100_000,
  horizon_years: 5,
  base_adoption_rate: 15,
  adoption_volatility: 5,
  revenue_per_unit: 500,
  market_size: 10_000,
  annual_cost: 20_000,
  n_simulations: 2000,
};

export default function ROICalculatorPage() {
  const { toast } = useToast();
  const [form, setForm] = useState<FormState>(DEFAULT);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ROIResult | null>(null);

  function set<K extends keyof FormState>(key: K, val: FormState[K]) {
    setForm((f) => ({ ...f, [key]: val }));
  }

  const handleRun = async () => {
    setRunning(true);
    try {
      const res = await apiFetch("/analytics/roi", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          base_adoption_rate: form.base_adoption_rate / 100,
          adoption_volatility: form.adoption_volatility / 100,
        }),
      });
      if (!res.ok) {
        const err = await res.text();
        toast(`Simulation failed: ${err}`, "error");
        return;
      }
      const data: ROIResult = await res.json();
      setResult(data);
      toast("Simulation complete", "success");
    } catch {
      toast("Failed to reach backend", "error");
    } finally {
      setRunning(false);
    }
  };

  const horizonOptions: Array<3 | 5 | 10> = [3, 5, 10];

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumbs={[
          { label: "Home", href: "/" },
          { label: "Analytics", href: "/analytics" },
          { label: "ROI Calculator" },
        ]}
        title="ROI Calculator"
        description="Monte Carlo I+D projection — adoption uncertainty over time"
        actions={
          <div className="flex items-center gap-2">
            {result && (
              <button
                onClick={() => exportCsv(result)}
                className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
                Export CSV
              </button>
            )}
            <button
              onClick={handleRun}
              disabled={running}
              className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {running ? (
                <>
                  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Simulating…
                </>
              ) : (
                <>
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                  </svg>
                  Run Simulation
                </>
              )}
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
        {/* ── Input Panel ──────────────────────────────────────────────── */}
        <div className="space-y-5">
          {/* Investment */}
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
            <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">Investment</h3>
            <div className="space-y-4">
              <NumberInput
                label="Initial Investment"
                value={form.investment}
                min={1}
                step={1000}
                prefix="$"
                onChange={(v) => set("investment", v)}
              />
              <NumberInput
                label="Annual Operating Cost"
                value={form.annual_cost}
                min={0}
                step={500}
                prefix="$"
                onChange={(v) => set("annual_cost", v)}
              />
            </div>
          </div>

          {/* Market */}
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
            <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">Market</h3>
            <div className="space-y-4">
              <NumberInput
                label="Total Addressable Market (units)"
                value={form.market_size}
                min={1}
                step={1000}
                onChange={(v) => set("market_size", v)}
              />
              <NumberInput
                label="Revenue per Unit / Year"
                value={form.revenue_per_unit}
                min={1}
                step={10}
                prefix="$"
                onChange={(v) => set("revenue_per_unit", v)}
              />
            </div>
          </div>

          {/* Adoption */}
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
            <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">Adoption Model</h3>
            <div className="space-y-5">
              <SliderInput
                label="Base Adoption Rate"
                value={form.base_adoption_rate}
                min={0} max={100} step={1} unit="%"
                onChange={(v) => set("base_adoption_rate", v)}
              />
              <SliderInput
                label="Adoption Volatility (σ)"
                value={form.adoption_volatility}
                min={0} max={50} step={1} unit="%"
                onChange={(v) => set("adoption_volatility", v)}
              />
            </div>
          </div>

          {/* Simulation */}
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
            <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">Simulation</h3>
            <div className="space-y-4">
              {/* Horizon */}
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">
                  Projection Horizon
                </label>
                <div className="flex gap-2">
                  {horizonOptions.map((h) => (
                    <button
                      key={h}
                      onClick={() => set("horizon_years", h)}
                      className={`flex-1 rounded-lg py-2 text-sm font-semibold transition-colors ${
                        form.horizon_years === h
                          ? "bg-blue-600 text-white"
                          : "border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
                      }`}
                    >
                      {h}yr
                    </button>
                  ))}
                </div>
              </div>

              {/* N simulations */}
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">
                  Iterations
                </label>
                <div className="flex gap-2">
                  {[500, 2000, 5000].map((n) => (
                    <button
                      key={n}
                      onClick={() => set("n_simulations", n)}
                      className={`flex-1 rounded-lg py-2 text-sm font-semibold transition-colors ${
                        form.n_simulations === n
                          ? "bg-blue-600 text-white"
                          : "border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
                      }`}
                    >
                      {n >= 1000 ? `${n / 1000}K` : n}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Results ──────────────────────────────────────────────────── */}
        <div className="space-y-5">
          {!result ? (
            <div className="flex h-full min-h-[320px] items-center justify-center rounded-2xl border-2 border-dashed border-gray-200 dark:border-gray-700">
              <div className="text-center">
                <svg className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M7.5 14.25v2.25m3-4.5v4.5m3-6.75v6.75m3-9v9M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z" />
                </svg>
                <p className="mt-3 text-sm font-medium text-gray-500 dark:text-gray-400">
                  Configure parameters and run a simulation
                </p>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                  Results will appear here
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* Scenario cards */}
              <div className="grid grid-cols-3 gap-4">
                <ScenarioCard label="Pessimistic (P10)" roi={result.pessimistic_roi} net={result.net_p10} color="red" />
                <ScenarioCard label="Base (P50)" roi={result.base_roi} net={result.net_p50} color="blue" />
                <ScenarioCard label="Optimistic (P90)" roi={result.optimistic_roi} net={result.net_p90} color="green" />
              </div>

              {/* Break-even stats */}
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Break-even Probability</p>
                  <p className="mt-2 text-3xl font-black tabular-nums text-gray-900 dark:text-white">
                    {(result.breakeven_prob * 100).toFixed(1)}%
                  </p>
                  <div className="mt-2 h-2 w-full rounded-full bg-gray-100 dark:bg-gray-800">
                    <div
                      className="h-2 rounded-full bg-blue-500 transition-all duration-700"
                      style={{ width: `${result.breakeven_prob * 100}%` }}
                    />
                  </div>
                  <p className="mt-1.5 text-xs text-gray-400">
                    {result.n_simulations.toLocaleString()} simulations
                  </p>
                </div>
                <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Median Break-even Year</p>
                  {result.breakeven_year === -1 ? (
                    <p className="mt-2 text-3xl font-black text-red-500">Never</p>
                  ) : (
                    <>
                      <p className="mt-2 text-3xl font-black tabular-nums text-gray-900 dark:text-white">
                        Yr {result.breakeven_year}
                      </p>
                      <p className="mt-1.5 text-xs text-gray-400">
                        of {form.horizon_years}-year horizon
                      </p>
                    </>
                  )}
                </div>
              </div>

              {/* Trajectory chart */}
              <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Year-by-Year ROI Trajectory</h3>
                    <p className="text-xs text-gray-400 mt-0.5">P10 / P50 / P90 bands across all simulations</p>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    <span className="flex items-center gap-1"><span className="inline-block h-2 w-6 rounded bg-green-400 opacity-60" />Optimistic</span>
                    <span className="flex items-center gap-1"><span className="inline-block h-2 w-6 rounded bg-blue-500" />Median</span>
                    <span className="flex items-center gap-1"><span className="inline-block h-2 w-6 rounded bg-red-400 opacity-60" />Pessimistic</span>
                  </div>
                </div>
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={result.trajectory.map((r) => ({ ...r, year: `Yr ${r.year}` }))}
                      margin={{ top: 5, right: 10, left: -10, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient id="roiMedian" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.25} />
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                      <XAxis dataKey="year" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "#6b7280" }} dy={8} />
                      <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "#6b7280" }}
                        tickFormatter={(v) => `${v}%`} />
                      <Tooltip
                        formatter={(v, name) => [`${(Number(v) || 0).toFixed(1)}%`, String(name ?? "")]}
                        contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)", fontSize: "12px" }}
                      />
                      <Area type="monotone" dataKey="optimistic" stroke="#4ade80" strokeWidth={1.5}
                        fill="#4ade80" fillOpacity={0.1} strokeDasharray="4 2" name="Optimistic" />
                      <Area type="monotone" dataKey="median" stroke="#3b82f6" strokeWidth={2.5}
                        fillOpacity={1} fill="url(#roiMedian)" name="Median" />
                      <Area type="monotone" dataKey="pessimistic" stroke="#f87171" strokeWidth={1.5}
                        fill="none" strokeDasharray="4 2" name="Pessimistic" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Histogram */}
              <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Final ROI Distribution</h3>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Distribution of ROI% at year {form.horizon_years} across {result.n_simulations.toLocaleString()} simulations
                  </p>
                </div>
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={result.histogram}
                      margin={{ top: 5, right: 10, left: -10, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                      <XAxis dataKey="bucket" tickLine={false} axisLine={false}
                        tick={{ fontSize: 9, fill: "#9ca3af" }} interval={3} dy={6} />
                      <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "#6b7280" }} />
                      <Tooltip
                        formatter={(v) => [String(v ?? 0), "Simulations"]}
                        contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)", fontSize: "12px" }}
                      />
                      <Bar dataKey="count" fill="#6366f1" radius={[3, 3, 0, 0]} name="Count" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Percentile table */}
              <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
                <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">Percentile Breakdown</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-100 dark:border-gray-800">
                        {["P5", "P10", "P25", "P50", "P75", "P90", "P95"].map((p) => (
                          <th key={p} className="pb-2 text-center text-xs font-semibold text-gray-400">{p}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        {[result.p5, result.p10, result.p25, result.p50, result.p75, result.p90, result.p95].map((v, i) => (
                          <td key={i} className={`pt-2.5 text-center text-sm font-mono font-semibold ${v >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                            {pct(v)}
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
