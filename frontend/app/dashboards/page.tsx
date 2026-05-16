"use client";

import type { ReactNode } from "react";

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

function ReferenceRing({ value }: { value: number }) {
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
        <p className="mt-1 text-xs font-medium text-slate-600">Percentil</p>
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
    <svg className="h-72 w-full" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-label="Serie temporal de entidades">
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

function MiniMetric({ icon, value, label, helper, tone }: { icon: string; value: string; label: string; helper: string; tone: string }) {
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

function Recommendation({ title, body, tone }: { title: string; body: string; tone: string }) {
  return (
    <div className={`rounded-xl border p-5 ${tone}`}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-violet-500">Acción sugerida</p>
      <p className="mt-2 text-sm font-semibold text-slate-950">{title}</p>
      <p className="mt-1 text-xs leading-5 text-slate-600">{body}</p>
      <p className="mt-3 text-xs font-semibold text-slate-800">Impacto esperado: +6-12pp</p>
    </div>
  );
}

function TopicCard({ title }: { title: string }) {
  return (
    <div className="rounded-xl border border-orange-200 bg-orange-50/25 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
        <div className="flex gap-1">
          <span className="rounded bg-orange-100 px-2 py-1 text-[10px] font-semibold uppercase text-orange-500">Experimental</span>
          <span className="rounded bg-red-50 px-2 py-1 text-[10px] font-semibold uppercase text-red-500">Alza</span>
        </div>
      </div>
      <div className="mt-5 grid grid-cols-3 gap-2">
        {["Aceleración", "Participación reciente", "Participación base"].map((label, index) => (
          <div key={label} className="rounded-lg border border-orange-100 bg-white p-3 text-center">
            <p className="text-[10px] text-slate-500">{label}</p>
            <p className="mt-2 text-lg font-semibold text-slate-950">{index === 2 ? "0.8%" : "14.3%"}</p>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-slate-500">Aparece 2 veces en 2024-2025 vs 1 en 2021-2023.</p>
    </div>
  );
}

export default function DashboardsPage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_22%_0%,rgba(124,58,237,0.08),transparent_28%),linear-gradient(180deg,#fbfbff_0%,#ffffff_52%,#fbfbff_100%)] px-5 py-7 text-[var(--ukip-text)] sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1380px] space-y-6">
        <header className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-semibold tracking-normal text-slate-950">Panel Ejecutivo</h1>
              <button className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--ukip-border)] bg-white text-violet-500">
                <Icon path="M11.48 3.499a.6.6 0 011.04 0l2.125 3.78 4.252.85a.6.6 0 01.321 1.008l-2.946 3.18.5 4.31a.6.6 0 01-.841.619L12 15.42l-3.93 1.826a.6.6 0 01-.842-.619l.5-4.31-2.946-3.18a.6.6 0 01.321-1.008l4.252-.85 2.125-3.78z" />
              </button>
            </div>
            <p className="mt-3 text-sm text-slate-500">Indicadores clave, tendencias temporales y panorama conceptual para tomadores de decisiones.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <ActionButton icon="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15">Actualizar</ActionButton>
            <ActionButton icon="M7.5 7.5h-.75A2.25 2.25 0 004.5 9.75v8.25a2.25 2.25 0 002.25 2.25h8.25a2.25 2.25 0 002.25-2.25v-.75M15 3.75h5.25M20.25 3.75V9M20.25 3.75L9.75 14.25">Compartir</ActionButton>
            <ActionButton primary icon="M12 3v12m0 0l4-4m-4 4l-4-4M4.5 19.5h15">Exportar PDF</ActionButton>
          </div>
        </header>

        <Card className="p-5">
          <Label>Executive Signal</Label>
          <div className="mt-5 grid gap-4 lg:grid-cols-[1.15fr_repeat(4,1fr)]">
            <div className="relative overflow-hidden rounded-xl border border-violet-200 bg-violet-50 p-5">
              <div className="absolute right-4 top-4 h-24 w-24 rounded-full bg-violet-200/70 blur-xl" />
              <div className="relative flex h-10 w-10 items-center justify-center rounded-full bg-white text-violet-600">
                <Icon path="M2.25 12s3.75-6.75 9.75-6.75S21.75 12 21.75 12 18 18.75 12 18.75 2.25 12 2.25 12zM15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </div>
              <p className="relative mt-5 text-xl font-semibold text-slate-950">Observación</p>
              <p className="relative mt-1 text-xs text-slate-600">Panorama actual del portafolio</p>
              <div className="relative mt-5 h-12">
                <SparkLine data={smallTrend} />
              </div>
            </div>
            <StatCard label="Puntaje de referencia" value="67%" helper="Percentil global" badge="8pp vs periodo anterior" />
            <StatCard label="Cobertura de enriquecimiento" value="86.7%" helper="Entidades enriquecidas" badge="12pp" />
            <StatCard label="Calidad promedio" value="51%" helper="Calidad del contenido" />
            <div className="rounded-xl border border-[var(--ukip-border)] bg-white p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Principal restricción actual</p>
              <p className="mt-4 text-base font-semibold text-slate-950">Calidad promedio</p>
              <p className="mt-1 text-sm text-slate-500">Afecta consistencia del informe</p>
              <button className="mt-5 rounded-lg bg-violet-600 px-4 py-3 text-xs font-semibold text-white">Ver constructores del informe</button>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <Label>Línea Base de Referencia Institucional</Label>
          <div className="mt-5 grid gap-8 xl:grid-cols-[1.45fr_0.85fr_1fr]">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="text-xl font-semibold text-slate-950">Línea Base de Portafolio de Investigación</h2>
                <span className="rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold uppercase text-violet-600">Observación</span>
              </div>
              <label className="mt-5 block text-xs font-semibold text-slate-700">Perfil de referencia</label>
              <select className="mt-2 h-11 w-full rounded-lg border border-[var(--ukip-border)] bg-white px-3 text-sm text-slate-700">
                <option>Línea Base de Portafolio de Investigación</option>
              </select>
              <p className="mt-4 text-sm text-violet-700">Preparación del 66.7% con 2 de 3 reglas actualmente satisfechas.</p>
              <div className="mt-5 rounded-xl border border-[var(--ukip-border)] p-5">
                <div className="flex items-center gap-3">
                  <p className="text-base font-semibold text-slate-950">Calidad promedio</p>
                  <span className="rounded-md bg-orange-100 px-2 py-1 text-xs font-semibold uppercase text-orange-500">Alta</span>
                </div>
                <p className="mt-3 text-sm text-slate-500">Calidad promedio observado 51%, esperado al menos 63%.</p>
              </div>
            </div>
            <div className="flex items-center justify-center border-y border-[var(--ukip-border)] py-6 xl:border-x xl:border-y-0">
              <div className="text-center">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-600">Puntaje de referencia</p>
                <ReferenceRing value={67} />
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-violet-600">Reglas actualmente satisfechas</p>
              {["Cobertura mínima alcanzada (86.7%)", "Calidad mínima del contenido (51%)", "Consistencia de metadatos (pendiente)"].map((rule, index) => (
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
            <Recommendation title="Mejorar calidad del contenido" body="Priorizar entidades y fuentes con bajo impacto." tone="border-violet-200 bg-violet-50/60" />
            <Recommendation title="Enriquecer metadatos clave" body="Aumenta la encontrabilidad y consistencia." tone="border-emerald-200 bg-emerald-50/60" />
            <Recommendation title="Explorar clústeres conceptuales" body="Descubrir temas emergentes y relaciones." tone="border-violet-200 bg-violet-50/60" />
          </div>
        </Card>

        <div className="grid gap-4 lg:grid-cols-4">
          <MiniMetric icon="M9 12h6m-6 4h6M8 4h8a2 2 0 012 2v12a2 2 0 01-2 2H8a2 2 0 01-2-2V6a2 2 0 012-2z" value="497" label="Entidades" helper="Total identificadas" tone="bg-blue-50 text-blue-600" />
          <MiniMetric icon="M4 19V9m5 10V5m5 14v-7m5 7V8" value="2303.4" label="Citas promedio" helper="Impacto promedio" tone="bg-violet-50 text-violet-600" />
          <MiniMetric icon="M12 21s-7.5-4.35-7.5-10.5A4.5 4.5 0 0112 7.1a4.5 4.5 0 017.5 3.4C19.5 16.65 12 21 12 21z" value="1923" label="Conceptos distintos" helper="Diversidad conceptual" tone="bg-orange-50 text-orange-500" />
          <Card className="p-5">
            <p className="text-sm font-semibold text-slate-500">Calidad promedio</p>
            <p className="mt-1 text-3xl font-semibold text-slate-950">51%</p>
            <p className="text-sm text-slate-500">Percentil</p>
            <div className="mt-5 h-3 rounded-full bg-gradient-to-r from-amber-400 via-orange-400 to-rose-500">
              <div className="ml-[51%] h-3 w-1 rounded-full bg-orange-600" />
            </div>
            <p className="mt-4 text-xs text-slate-500">Confianza media</p>
          </Card>
        </div>

        <div className="grid gap-4 xl:grid-cols-3">
          <Card className="p-5">
            <Label>Proyección Monte Carlo</Label>
            <div className="mt-2 flex items-start justify-between">
              <div>
                <h2 className="text-base font-semibold text-slate-950">Proyección de impacto</h2>
                <p className="mt-3 max-w-xs text-xs leading-5 text-slate-500">Simulación del impacto potencial al mejorar la cobertura y conectividad de entidades.</p>
              </div>
              <div className="rounded-xl border border-[var(--ukip-border)] p-5 text-center">
                <p className="text-[10px] font-semibold uppercase text-slate-500">Esperado</p>
                <p className="mt-3 text-3xl font-semibold text-slate-950">82</p>
                <p className="text-xs text-slate-500">/100</p>
              </div>
            </div>
            <div className="mt-3 h-28">
              <ImpactLine />
            </div>
            <div className="flex justify-between text-xs text-slate-500"><span>Conservador 65</span><span>Rango probable 66-95</span><span>Optimista 95</span></div>
          </Card>
          <Card className="p-5">
            <div className="flex items-start justify-between"><Label tone="blue">Conexión con el informe</Label><span className="rounded-full bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-600">JDF 74,100</span></div>
            <h2 className="mt-2 text-base font-semibold text-slate-950">Ángulo narrativo</h2>
            <p className="mt-5 text-sm leading-6 text-slate-600">El portafolio ya sostiene una narrativa de impacto defensible ante stakeholders.</p>
            <p className="mt-5 text-sm leading-6 text-slate-600">Enfócate en reforzar los impactos de mayor relevancia y oportunidades de posicionamiento.</p>
            <button className="mt-8 rounded-lg bg-violet-600 px-5 py-3 text-sm font-semibold text-white">Abrir informe con proyección</button>
          </Card>
          <Card className="p-5">
            <div className="flex items-start justify-between"><Label tone="blue">Distribución de impacto</Label><span className="rounded-lg border px-3 py-1 text-xs font-semibold text-slate-700">5 señales</span></div>
            <h2 className="mt-2 text-base font-semibold text-slate-950">Patrones ocultos</h2>
            <p className="mt-3 text-sm text-slate-500">Clústeres, valores atípicos, brechas y señales de grano no evidentes.</p>
            {["Political science", "Open science", "Computer science"].map((item, index) => (
              <div key={item} className="mt-4 flex items-center justify-between rounded-lg bg-slate-50 p-3 text-sm">
                <span className="font-medium text-slate-700">Concentración temática: {item}</span>
                <span className="text-slate-500">{index === 2 ? "Medio impacto" : "Alto impacto"}</span>
              </div>
            ))}
            <button className="mt-5 w-full text-right text-sm font-semibold text-violet-600">Ver todas las señales</button>
          </Card>
        </div>

        <Card className="p-5">
          <h2 className="text-lg font-semibold text-slate-950">Entidades en el Tiempo</h2>
          <Label tone="blue">Temporal Signal</Label>
          <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_240px]">
            <div className="h-72">
              <TemporalArea />
            </div>
            <div>
              <div className="rounded-xl border border-[var(--ukip-border)] bg-slate-50 p-5">
                <p className="text-sm font-semibold text-violet-600">Insight</p>
                <p className="mt-4 text-sm leading-6 text-slate-600">Crecimiento sostenido desde 2017 con pico en 2034. Requiere consolidación en 2035.</p>
              </div>
              <div className="mt-5 grid grid-cols-2 rounded-lg bg-slate-100 p-1 text-center text-xs font-semibold">
                <span className="rounded-md bg-violet-100 py-2 text-violet-600">Modo serie</span>
                <span className="py-2 text-slate-500">Modo acumulado</span>
              </div>
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <div><h2 className="text-lg font-semibold text-slate-950">Señales Emergentes de Tópicos</h2><Label tone="blue">Aceleración</Label></div>
            <button className="rounded-lg border border-[var(--ukip-border)] px-4 py-2 text-sm font-semibold text-violet-600">Ver todas las señales</button>
          </div>
          <div className="mt-5 grid gap-4 lg:grid-cols-3">{topicSignals.map((topic) => <TopicCard key={topic} title={topic} />)}</div>
        </Card>

        <div className="grid gap-4 xl:grid-cols-[0.95fr_1.35fr]">
          <Card className="p-5">
            <h2 className="text-lg font-semibold text-slate-950">Principales Etiquetas Primarias por Año</h2>
            <Label tone="blue">Density Map</Label>
            <div className="mt-5 overflow-hidden rounded-xl border border-[var(--ukip-border)]">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500">
                  <tr><th className="p-3 font-medium">Etiqueta</th>{["2020", "2021", "2022", "2024", "2025"].map((y) => <th key={y} className="p-3 font-medium">{y}</th>)}</tr>
                </thead>
                <tbody>{heatRows.map((row) => <tr key={row[0]} className="border-t border-[var(--ukip-border)]"><td className="p-3 font-medium text-slate-700">{row[0]}</td>{row.slice(1).map((cell, index) => <td key={index} className={`p-3 text-center ${cell !== "-" ? "bg-violet-200 text-violet-800" : "bg-violet-50 text-slate-400"}`}>{cell}</td>)}</tr>)}</tbody>
              </table>
            </div>
          </Card>
          <Card className="p-5">
            <div className="flex justify-between"><div><h2 className="text-lg font-semibold text-slate-950">Mapa de Conceptos de Conocimiento</h2><Label tone="blue">Semantic Signal</Label></div><button className="text-sm font-semibold text-violet-600">Análisis completo →</button></div>
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
          <div className="flex items-center justify-between"><div><h2 className="text-lg font-semibold text-slate-950">Entidades principales por impacto</h2><Label tone="blue">Impact Rank</Label></div><button className="text-sm font-semibold text-violet-600">Ver todo el ranking →</button></div>
          <div className="mt-5 overflow-hidden rounded-xl border border-[var(--ukip-border)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-white text-xs text-slate-500"><tr>{["#", "Entidad", "Etiqueta principal", "Citas", "Fuente"].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}</tr></thead>
              <tbody>{impactRows.map((row) => <tr key={row[0]} className="border-t border-[var(--ukip-border)]">{row.map((cell, index) => <td key={index} className={`px-4 py-4 ${index === 1 ? "font-semibold text-slate-800" : index === 3 ? "font-semibold text-violet-600" : "text-slate-600"}`}>{index === 4 ? <span className="rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold text-violet-600">{cell}</span> : cell}</td>)}</tr>)}</tbody>
            </table>
          </div>
        </Card>

        <div className="flex flex-col gap-4 rounded-xl border border-violet-200 bg-violet-50 px-6 py-5 text-sm font-medium text-violet-700 sm:flex-row sm:items-center sm:justify-between">
          <span>Este dashboard cuenta una historia: cobertura sólida, calidad en mejora y oportunidades claras para aumentar el impacto.</span>
          <button className="rounded-lg bg-white px-5 py-3 font-semibold text-violet-600 shadow-sm">Ver recomendaciones estratégicas</button>
        </div>
      </div>
    </main>
  );
}
