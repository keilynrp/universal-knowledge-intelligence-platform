"use client";

import type { ReactNode } from "react";
import { useLanguage } from "../contexts/LanguageContext";
import { EntityConcept } from "../components/ui";

const smallTrend = [
  { x: 0, y: 22 },
  { x: 1, y: 18 },
  { x: 2, y: 24 },
  { x: 3, y: 23 },
  { x: 4, y: 34 },
  { x: 5, y: 38 },
  { x: 6, y: 24 },
  { x: 7, y: 22 },
  { x: 8, y: 31 },
  { x: 9, y: 34 },
  { x: 10, y: 29 },
  { x: 11, y: 25 },
  { x: 12, y: 26 },
];

const monteCarlo = [
  { x: "65", y: 14 },
  { x: "", y: 20 },
  { x: "", y: 31 },
  { x: "", y: 20 },
  { x: "", y: 25 },
  { x: "", y: 39 },
  { x: "", y: 51 },
  { x: "", y: 39 },
  { x: "", y: 62 },
  { x: "", y: 50 },
  { x: "", y: 47 },
  { x: "", y: 49 },
  { x: "", y: 68 },
  { x: "", y: 82 },
  { x: "", y: 73 },
  { x: "95", y: 49 },
];

const timeSeries = [
  1, 1, 2, 2, 3, 4, 3, 6, 8, 5, 8, 4, 5, 13, 9, 16, 11, 16, 17, 27, 23, 34,
  32, 48, 66, 75, 100, 72, 86, 103, 106, 103, 68, 52, 42, 24, 4,
].map((value, index) => ({ year: 2010 + index * 0.44, value }));

const topicSignals = ["Open Education & E-Learning", "Programming language", "Population"];

const heatRows = [
  ["Open Science", "-", "-", "-", "-", "1"],
  ["UNESCO Recommendation...", "-", "2", "-", "-", "-"],
  ["Eating Into Open Science...", "1", "1", "-", "-", "-"],
  ["Open Science in Archaeology", "-", "-", "-", "-", "-"],
  ["Towards wide-scale adoption...", "1", "1", "-", "-", "-"],
];

const conceptTags = [
  ["Computer science", 319, "blue"],
  ["Political science", 197, "violet"],
  ["Engineering", 130, "green"],
  ["Psychology", 110, "green"],
  ["Data science", 97, "amber"],
  ["Biology", 97, "cyan"],
  ["Education", 77, "pink"],
  ["Scientific Computing", 60, "violet"],
  ["Database", 77, "blue"],
  ["Evolution", 66, "rose"],
  ["Artificial Intelligence", 50, "blue"],
  ["Ecology", 55, "slate"],
  ["Knowledge management", 45, "amber"],
  ["Physics", 35, "blue"],
  ["Social psychology", 37, "violet"],
  ["Transparency", 37, "cyan"],
  ["Genetics", 35, "green"],
] as const;

const impactRows = [
  ["1", "Open Science: the Very Idea", "Open Science: the Very Idea", "74,359", "OpenAlex"],
  ["2", "The Open Knowledge Foundation: Open Data Means Better Science", "The Open Knowledge Foundation: Open Data Means Better Science", "74,305", "OpenAlex"],
  ["3", "Open Science in Software Engineering", "Open Science in Software Engineering", "69,813", "OpenAlex"],
  ["4", "Open Science Collaboration", "Open Science Collaboration", "69,813", "OpenAlex"],
  ["5", "Open Science and Open Innovation: Sourcing Knowledge from Universities", "Open Science and Open Innovation: Sourcing Knowledge from Universities", "42,410", "OpenAlex"],
];

function pointsFromData(data: { y?: number; value?: number }[], width = 280, height = 88) {
  const values = data.map((item) => item.y ?? item.value ?? 0);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);
  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - ((value - min) / range) * (height - 8) - 4;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function SparkLine({ data, className = "h-12" }: { data: { y: number }[]; className?: string }) {
  return (
    <svg className={`w-full ${className}`} viewBox="0 0 280 88" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={pointsFromData(data)} fill="none" stroke="#7c3aed" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ImpactLine() {
  const points = pointsFromData(monteCarlo, 320, 112);
  return (
    <svg className="h-28 w-full" viewBox="0 0 320 112" preserveAspectRatio="none" aria-hidden="true">
      <path d={`M0 112 L${points.replaceAll(" ", " L")} L320 112 Z`} fill="rgba(139,92,246,0.08)" />
      <polyline points={points} fill="none" stroke="#8b5cf6" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {points.split(" ").map((point, index) => {
        if (![1, 5, 8, 13, 14].includes(index)) return null;
        const [cx, cy] = point.split(",");
        return <circle key={point} cx={cx} cy={cy} r="3.5" fill="#8b5cf6" stroke="white" strokeWidth="2" />;
      })}
    </svg>
  );
}

function ReferenceRing({ value, label }: { value: number; label: string }) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - value / 100);
  return (
    <div className="relative mt-3 h-48 w-48">
      <svg className="h-full w-full -rotate-90" viewBox="0 0 100 100" aria-hidden="true">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#eadcff" strokeWidth="8" />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke="#7c3aed"
          strokeLinecap="round"
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <p className="text-5xl font-semibold text-violet-600">{value}%</p>
        <p className="mt-1 text-xs font-medium text-slate-600">{label}</p>
      </div>
    </div>
  );
}

function TemporalArea() {
  const width = 900;
  const height = 280;
  const points = pointsFromData(timeSeries, width, height - 28);
  const area = `M0 ${height - 20} L${points.replaceAll(" ", " L")} L${width} ${height - 20} Z`;
  return (
    <svg className="h-72 w-full" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="temporalNativeFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.34" />
          <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[40, 90, 140, 190, 240].map((y) => (
        <line key={y} x1="0" x2={width} y1={y} y2={y} stroke="#edf0f7" strokeWidth="1" />
      ))}
      <path d={area} fill="url(#temporalNativeFill)" />
      <polyline points={points} fill="none" stroke="#7c3aed" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {["2010", "2012", "2014", "2016", "2018", "2020", "2022", "2024", "2026"].map((year, index) => (
        <text key={year} x={index * 112 + 4} y={height - 2} fill="#64748b" fontSize="11">
          {year}
        </text>
      ))}
    </svg>
  );
}

function Icon({ path, className = "h-4 w-4" }: { path: string; className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d={path} />
    </svg>
  );
}

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-[var(--ukip-border)] bg-white shadow-[0_16px_50px_rgb(91_72_163/0.05)] ${className}`}>
      {children}
    </section>
  );
}

function Label({ children, tone = "violet" }: { children: ReactNode; tone?: "violet" | "blue" }) {
  return (
    <p className={`text-[11px] font-semibold uppercase tracking-[0.12em] ${tone === "blue" ? "text-blue-600" : "text-violet-600"}`}>
      {children}
    </p>
  );
}

function ActionButton({ children, primary = false, icon }: { children: ReactNode; primary?: boolean; icon: string }) {
  return (
    <button
      className={`inline-flex h-11 items-center gap-2 rounded-lg border px-5 text-sm font-medium transition ${
        primary
          ? "border-violet-600 bg-violet-600 text-white shadow-[0_12px_26px_rgb(124_58_237/0.22)] hover:bg-violet-700"
          : "border-[var(--ukip-border)] bg-white text-[var(--ukip-text)] hover:bg-violet-50"
      }`}
    >
      <Icon path={icon} />
      {children}
    </button>
  );
}

function StatCard({ label, value, helper, badge }: { label: string; value: string; helper: string; badge?: string }) {
  return (
    <div className="rounded-xl border border-[var(--ukip-border)] bg-white p-5">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">{label}</p>
      <p className="mt-4 text-4xl font-semibold tracking-normal text-slate-950">{value}</p>
      <p className="mt-2 text-sm text-slate-500">{helper}</p>
      {badge && (
        <span className="mt-4 inline-flex rounded-md bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-600">
          {badge}
        </span>
      )}
    </div>
  );
}

function MiniMetric({ icon, value, label, helper, tone }: { icon: string; value: string; label: ReactNode; helper: string; tone: string }) {
  return (
    <Card className="p-5">
      <div className={`mb-5 flex h-10 w-10 items-center justify-center rounded-lg ${tone}`}>
        <Icon path={icon} />
      </div>
      <p className="text-3xl font-semibold tracking-normal text-slate-950">{value}</p>
      <p className="mt-1 text-sm font-medium text-slate-700">{label}</p>
      <p className="mt-2 text-xs text-slate-500">{helper}</p>
    </Card>
  );
}

function Recommendation({ title, body, tone, actionLabel, impactLabel }: { title: string; body: string; tone: string; actionLabel: string; impactLabel: string }) {
  return (
    <div className={`rounded-xl border p-5 ${tone}`}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-violet-500">{actionLabel}</p>
      <p className="mt-2 text-sm font-semibold text-slate-950">{title}</p>
      <p className="mt-1 text-xs leading-5 text-slate-600">{body}</p>
      <p className="mt-3 text-xs font-semibold text-slate-800">{impactLabel}</p>
    </div>
  );
}

function TopicCard({ title, t }: { title: string; t: (key: string) => string }) {
  return (
    <div className="rounded-xl border border-orange-200 bg-orange-50/25 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
        <div className="flex gap-1">
          <span className="rounded bg-orange-100 px-2 py-1 text-[10px] font-semibold uppercase text-orange-500">{t("dashboard_showcase.experimental")}</span>
          <span className="rounded bg-red-50 px-2 py-1 text-[10px] font-semibold uppercase text-red-500">{t("dashboard_showcase.rising")}</span>
        </div>
      </div>
      <div className="mt-5 grid grid-cols-3 gap-2">
        {[t("dashboard_showcase.accel_label"), t("dashboard_showcase.recent_share"), t("dashboard_showcase.baseline_share")].map((label, index) => (
          <div key={label} className="rounded-lg border border-orange-100 bg-white p-3 text-center">
            <p className="text-[10px] text-slate-500">{label}</p>
            <p className="mt-2 text-lg font-semibold text-slate-950">{index === 2 ? "0.8%" : "14.3%"}</p>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-slate-500">{t("dashboard_showcase.appears_comparison")}</p>
    </div>
  );
}

export default function DashboardsPage() {
  const { t } = useLanguage();

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_22%_0%,rgba(124,58,237,0.08),transparent_28%),linear-gradient(180deg,#fbfbff_0%,#ffffff_52%,#fbfbff_100%)] px-5 py-7 text-[var(--ukip-text)] sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1380px] space-y-6">
        <header className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-semibold tracking-normal text-slate-950">{t("dashboard_showcase.title")}</h1>
              <button className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--ukip-border)] bg-white text-violet-500">
                <Icon path="M11.48 3.499a.6.6 0 011.04 0l2.125 3.78 4.252.85a.6.6 0 01.321 1.008l-2.946 3.18.5 4.31a.6.6 0 01-.841.619L12 15.42l-3.93 1.826a.6.6 0 01-.842-.619l.5-4.31-2.946-3.18a.6.6 0 01.321-1.008l4.252-.85 2.125-3.78z" />
              </button>
            </div>
            <p className="mt-3 text-sm text-slate-500">{t("dashboard_showcase.subtitle")}</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <ActionButton icon="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15">{t("dashboard_showcase.refresh")}</ActionButton>
            <ActionButton icon="M7.5 7.5h-.75A2.25 2.25 0 004.5 9.75v8.25a2.25 2.25 0 002.25 2.25h8.25a2.25 2.25 0 002.25-2.25v-.75M15 3.75h5.25M20.25 3.75V9M20.25 3.75L9.75 14.25">{t("dashboard_showcase.share")}</ActionButton>
            <ActionButton primary icon="M12 3v12m0 0l4-4m-4 4l-4-4M4.5 19.5h15">{t("dashboard_showcase.export_pdf")}</ActionButton>
          </div>
        </header>

        <Card className="p-5">
          <Label>{t("dashboard_showcase.executive_signal")}</Label>
          <div className="mt-5 grid gap-4 lg:grid-cols-[1.15fr_repeat(4,1fr)]">
            <div className="relative overflow-hidden rounded-xl border border-violet-200 bg-violet-50 p-5">
              <div className="absolute right-4 top-4 h-24 w-24 rounded-full bg-violet-200/70 blur-xl" />
              <div className="relative flex h-10 w-10 items-center justify-center rounded-full bg-white text-violet-600">
                <Icon path="M2.25 12s3.75-6.75 9.75-6.75S21.75 12 21.75 12 18 18.75 12 18.75 2.25 12 2.25 12zM15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </div>
              <p className="relative mt-5 text-xl font-semibold text-slate-950">{t("dashboard_showcase.observation")}</p>
              <p className="relative mt-1 text-xs text-slate-600">{t("dashboard_showcase.observation_desc")}</p>
              <div className="relative mt-5 h-12">
                <SparkLine data={smallTrend} />
              </div>
            </div>
            <StatCard label={t("dashboard_showcase.benchmark_score")} value="67%" helper={t("dashboard_showcase.global_percentile")} badge={t("dashboard_showcase.vs_previous")} />
            <StatCard label={t("dashboard_showcase.enrichment_coverage")} value="86.7%" helper={t("dashboard_showcase.enriched_entities")} badge="12pp" />
            <StatCard label={t("dashboard_showcase.avg_quality")} value="51%" helper={t("dashboard_showcase.content_quality")} />
            <div className="rounded-xl border border-[var(--ukip-border)] bg-white p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">{t("dashboard_showcase.main_constraint")}</p>
              <p className="mt-4 text-base font-semibold text-slate-950">{t("dashboard_showcase.avg_quality")}</p>
              <p className="mt-1 text-sm text-slate-500">{t("dashboard_showcase.affects_report")}</p>
              <button className="mt-5 rounded-lg bg-violet-600 px-4 py-3 text-xs font-semibold text-white">{t("dashboard_showcase.view_report_builders")}</button>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <Label>{t("dashboard_showcase.baseline_label")}</Label>
          <div className="mt-5 grid gap-8 xl:grid-cols-[1.45fr_0.85fr_1fr]">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="text-xl font-semibold text-slate-950">{t("dashboard_showcase.portfolio_baseline")}</h2>
                <span className="rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold uppercase text-violet-600">{t("dashboard_showcase.observation")}</span>
              </div>
              <label className="mt-5 block text-xs font-semibold text-slate-700">{t("dashboard_showcase.reference_profile")}</label>
              <select className="mt-2 h-11 w-full rounded-lg border border-[var(--ukip-border)] bg-white px-3 text-sm text-slate-700">
                <option>{t("dashboard_showcase.portfolio_baseline")}</option>
              </select>
              <p className="mt-4 text-sm text-violet-700">{t("dashboard_showcase.readiness")}</p>
              <div className="mt-5 rounded-xl border border-[var(--ukip-border)] p-5">
                <div className="flex items-center gap-3">
                  <p className="text-base font-semibold text-slate-950">{t("dashboard_showcase.avg_quality")}</p>
                  <span className="rounded-md bg-orange-100 px-2 py-1 text-xs font-semibold uppercase text-orange-500">{t("dashboard_showcase.high_severity")}</span>
                </div>
                <p className="mt-3 text-sm text-slate-500">{t("dashboard_showcase.observed_vs_expected")}</p>
              </div>
            </div>
            <div className="flex items-center justify-center border-y border-[var(--ukip-border)] py-6 xl:border-x xl:border-y-0">
              <div className="text-center">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-600">{t("dashboard_showcase.benchmark_score")}</p>
                <ReferenceRing value={67} label={t("dashboard_showcase.percentile")} />
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-violet-600">{t("dashboard_showcase.rules_met")}</p>
              {[t("dashboard_showcase.rule_coverage"), t("dashboard_showcase.rule_quality"), t("dashboard_showcase.rule_metadata")].map((rule, index) => (
                <div key={rule} className="mt-5 flex items-center gap-3 text-sm text-slate-700">
                  <span className={`flex h-7 w-7 items-center justify-center rounded-full border ${index < 2 ? "border-emerald-400 text-emerald-500" : "border-slate-300 text-slate-400"}`}>
                    <Icon path="M4.5 12.75l6 6 9-13.5" className="h-3.5 w-3.5" />
                  </span>
                  {rule}
                </div>
              ))}
            </div>
          </div>
          <div className="mt-8 grid gap-5 lg:grid-cols-3">
            <Recommendation title={t("dashboard_showcase.rec_quality_title")} body={t("dashboard_showcase.rec_quality_body")} tone="border-violet-200 bg-violet-50/60" actionLabel={t("dashboard_showcase.suggested_action")} impactLabel={t("dashboard_showcase.expected_impact")} />
            <Recommendation title={t("dashboard_showcase.rec_metadata_title")} body={t("dashboard_showcase.rec_metadata_body")} tone="border-emerald-200 bg-emerald-50/60" actionLabel={t("dashboard_showcase.suggested_action")} impactLabel={t("dashboard_showcase.expected_impact")} />
            <Recommendation title={t("dashboard_showcase.rec_clusters_title")} body={t("dashboard_showcase.rec_clusters_body")} tone="border-violet-200 bg-violet-50/60" actionLabel={t("dashboard_showcase.suggested_action")} impactLabel={t("dashboard_showcase.expected_impact")} />
          </div>
        </Card>

        <div className="grid gap-4 lg:grid-cols-4">
          <MiniMetric icon="M9 12h6m-6 4h6M8 4h8a2 2 0 012 2v12a2 2 0 01-2 2H8a2 2 0 01-2-2V6a2 2 0 012-2z" value="497" label={<EntityConcept>{t("dashboard_showcase.entities")}</EntityConcept>} helper={t("dashboard_showcase.total_identified")} tone="bg-blue-50 text-blue-600" />
          <MiniMetric icon="M4 19V9m5 10V5m5 14v-7m5 7V8" value="2303.4" label={t("dashboard_showcase.avg_citations")} helper={t("dashboard_showcase.avg_impact")} tone="bg-violet-50 text-violet-600" />
          <MiniMetric icon="M12 21s-7.5-4.35-7.5-10.5A4.5 4.5 0 0112 7.1a4.5 4.5 0 017.5 3.4C19.5 16.65 12 21 12 21z" value="1923" label={t("dashboard_showcase.distinct_concepts")} helper={t("dashboard_showcase.conceptual_diversity")} tone="bg-orange-50 text-orange-500" />
          <Card className="p-5">
            <p className="text-sm font-semibold text-slate-500">{t("dashboard_showcase.avg_quality")}</p>
            <p className="mt-1 text-3xl font-semibold text-slate-950">51%</p>
            <p className="text-sm text-slate-500">{t("dashboard_showcase.percentile")}</p>
            <div className="mt-5 h-3 rounded-full bg-gradient-to-r from-amber-400 via-orange-400 to-rose-500">
              <div className="ml-[51%] h-3 w-1 rounded-full bg-orange-600" />
            </div>
            <p className="mt-4 text-xs text-slate-500">{t("dashboard_showcase.medium_confidence")}</p>
          </Card>
        </div>

        <div className="grid gap-4 xl:grid-cols-3">
          <Card className="p-5">
            <Label>{t("dashboard_showcase.monte_carlo")}</Label>
            <div className="mt-2 flex items-start justify-between">
              <div>
                <h2 className="text-base font-semibold text-slate-950">{t("dashboard_showcase.impact_projection")}</h2>
                <p className="mt-3 max-w-xs text-xs leading-5 text-slate-500">{t("dashboard_showcase.impact_projection_desc")}</p>
              </div>
              <div className="rounded-xl border border-[var(--ukip-border)] p-5 text-center">
                <p className="text-[10px] font-semibold uppercase text-slate-500">{t("dashboard_showcase.expected")}</p>
                <p className="mt-3 text-3xl font-semibold text-slate-950">82</p>
                <p className="text-xs text-slate-500">/100</p>
              </div>
            </div>
            <div className="mt-3 h-28">
              <ImpactLine />
            </div>
            <div className="flex justify-between text-xs text-slate-500"><span>{t("dashboard_showcase.conservative")}</span><span>{t("dashboard_showcase.probable_range")}</span><span>{t("dashboard_showcase.optimistic")}</span></div>
          </Card>
          <Card className="p-5">
            <div className="flex items-start justify-between"><Label tone="blue">{t("dashboard_showcase.report_connection")}</Label><span className="rounded-full bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-600">JDF 74,100</span></div>
            <h2 className="mt-2 text-base font-semibold text-slate-950">{t("dashboard_showcase.narrative_angle")}</h2>
            <p className="mt-5 text-sm leading-6 text-slate-600">{t("dashboard_showcase.narrative_p1")}</p>
            <p className="mt-5 text-sm leading-6 text-slate-600">{t("dashboard_showcase.narrative_p2")}</p>
            <button className="mt-8 rounded-lg bg-violet-600 px-5 py-3 text-sm font-semibold text-white">{t("dashboard_showcase.open_report")}</button>
          </Card>
          <Card className="p-5">
            <div className="flex items-start justify-between"><Label tone="blue">{t("dashboard_showcase.impact_distribution")}</Label><span className="rounded-lg border px-3 py-1 text-xs font-semibold text-slate-700">{t("dashboard_showcase.signals")}</span></div>
            <h2 className="mt-2 text-base font-semibold text-slate-950">{t("dashboard_showcase.hidden_patterns")}</h2>
            <p className="mt-3 text-sm text-slate-500">{t("dashboard_showcase.hidden_patterns_desc")}</p>
            {["Political science", "Open science", "Computer science"].map((item, index) => (
              <div key={item} className="mt-4 flex items-center justify-between rounded-lg bg-slate-50 p-3 text-sm">
                <span className="font-medium text-slate-700">{t("dashboard_showcase.thematic_concentration").replace("{topic}", item)}</span>
                <span className="text-slate-500">{index === 2 ? t("dashboard_showcase.medium_impact") : t("dashboard_showcase.high_impact")}</span>
              </div>
            ))}
            <button className="mt-5 w-full text-right text-sm font-semibold text-violet-600">{t("dashboard_showcase.view_all_signals")}</button>
          </Card>
        </div>

        <Card className="p-5">
          <h2 className="text-lg font-semibold text-slate-950">
            <EntityConcept>{t("dashboard_showcase.entities_over_time")}</EntityConcept>
          </h2>
          <Label tone="blue">{t("dashboard_showcase.temporal_signal")}</Label>
          <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_240px]">
            <div className="h-72">
              <TemporalArea />
            </div>
            <div>
              <div className="rounded-xl border border-[var(--ukip-border)] bg-slate-50 p-5">
                <p className="text-sm font-semibold text-violet-600">{t("dashboard_showcase.insight")}</p>
                <p className="mt-4 text-sm leading-6 text-slate-600">{t("dashboard_showcase.insight_text")}</p>
              </div>
              <div className="mt-5 grid grid-cols-2 rounded-lg bg-slate-100 p-1 text-center text-xs font-semibold">
                <span className="rounded-md bg-violet-100 py-2 text-violet-600">{t("dashboard_showcase.series_mode")}</span>
                <span className="py-2 text-slate-500">{t("dashboard_showcase.cumulative_mode")}</span>
              </div>
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <div><h2 className="text-lg font-semibold text-slate-950">{t("dashboard_showcase.emerging_topics")}</h2><Label tone="blue">{t("dashboard_showcase.acceleration")}</Label></div>
            <button className="rounded-lg border border-[var(--ukip-border)] px-4 py-2 text-sm font-semibold text-violet-600">{t("dashboard_showcase.view_all_signals")}</button>
          </div>
          <div className="mt-5 grid gap-4 lg:grid-cols-3">{topicSignals.map((topic) => <TopicCard key={topic} title={topic} t={t} />)}</div>
        </Card>

        <div className="grid gap-4 xl:grid-cols-[0.95fr_1.35fr]">
          <Card className="p-5">
            <h2 className="text-lg font-semibold text-slate-950">{t("dashboard_showcase.primary_labels_by_year")}</h2>
            <Label tone="blue">{t("dashboard_showcase.density_map")}</Label>
            <div className="mt-5 overflow-hidden rounded-xl border border-[var(--ukip-border)]">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500">
                  <tr><th className="p-3 font-medium">{t("dashboard_showcase.label_col")}</th>{["2020", "2021", "2022", "2024", "2025"].map((y) => <th key={y} className="p-3 font-medium">{y}</th>)}</tr>
                </thead>
                <tbody>{heatRows.map((row) => <tr key={row[0]} className="border-t border-[var(--ukip-border)]"><td className="p-3 font-medium text-slate-700">{row[0]}</td>{row.slice(1).map((cell, index) => <td key={index} className={`p-3 text-center ${cell !== "-" ? "bg-violet-200 text-violet-800" : "bg-violet-50 text-slate-400"}`}>{cell}</td>)}</tr>)}</tbody>
              </table>
            </div>
          </Card>
          <Card className="p-5">
            <div className="flex justify-between"><div><h2 className="text-lg font-semibold text-slate-950">{t("dashboard_showcase.concept_map")}</h2><Label tone="blue">{t("dashboard_showcase.semantic_signal")}</Label></div><button className="text-sm font-semibold text-violet-600">{t("dashboard_showcase.full_analysis")}</button></div>
            <div className="mt-5 flex flex-wrap gap-2">
              {conceptTags.map(([name, count, tone]) => (
                <span key={name} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${
                  tone === "blue" ? "bg-blue-100 text-blue-600" : tone === "green" ? "bg-emerald-100 text-emerald-600" : tone === "amber" ? "bg-orange-100 text-orange-600" : tone === "cyan" ? "bg-cyan-100 text-cyan-600" : tone === "rose" ? "bg-rose-100 text-rose-600" : tone === "pink" ? "bg-pink-100 text-pink-600" : tone === "slate" ? "bg-slate-100 text-slate-600" : "bg-violet-100 text-violet-600"
                }`}>{name} {count}</span>
              ))}
            </div>
          </Card>
        </div>

        <Card className="p-5">
          <div className="flex items-center justify-between"><div><h2 className="text-lg font-semibold text-slate-950"><EntityConcept>{t("dashboard_showcase.top_entities_impact")}</EntityConcept></h2><Label tone="blue">{t("dashboard_showcase.impact_rank")}</Label></div><button className="text-sm font-semibold text-violet-600">{t("dashboard_showcase.view_full_ranking")}</button></div>
          <div className="mt-5 overflow-hidden rounded-xl border border-[var(--ukip-border)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-white text-xs text-slate-500"><tr><th className="px-4 py-3 font-medium">#</th><th className="px-4 py-3 font-medium"><EntityConcept>{t("dashboard_showcase.col_entity")}</EntityConcept></th>{[t("dashboard_showcase.col_primary_label"), t("dashboard_showcase.col_citations"), t("dashboard_showcase.col_source")].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}</tr></thead>
              <tbody>{impactRows.map((row) => <tr key={row[0]} className="border-t border-[var(--ukip-border)]">{row.map((cell, index) => <td key={index} className={`px-4 py-4 ${index === 1 ? "font-semibold text-slate-800" : index === 3 ? "font-semibold text-violet-600" : "text-slate-600"}`}>{index === 4 ? <span className="rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold text-violet-600">{cell}</span> : cell}</td>)}</tr>)}</tbody>
            </table>
          </div>
        </Card>

        <div className="flex flex-col gap-4 rounded-xl border border-violet-200 bg-violet-50 px-6 py-5 text-sm font-medium text-violet-700 sm:flex-row sm:items-center sm:justify-between">
          <span>{t("dashboard_showcase.footer_story")}</span>
          <button className="rounded-lg bg-white px-5 py-3 font-semibold text-violet-600 shadow-sm">{t("dashboard_showcase.strategic_recommendations")}</button>
        </div>
      </div>
    </main>
  );
}
