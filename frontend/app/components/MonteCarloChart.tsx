"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from "recharts";

interface MonteCarloData {
    current_citations: number;
    simulation_years: number;
    total_simulations: number;
    predicted_5yr_median: number;
    trajectories: Array<{
        year: string;
        optimistic: number;
        median: number;
        pessimistic: number;
    }>;
}

function getErrorMessage(error: unknown, fallback: string) {
    return error instanceof Error ? error.message : fallback;
}

function clampScore(value: number): number {
    return Math.max(0, Math.min(100, Math.round(value)));
}

export default function MonteCarloChart({ productId }: { productId: number }) {
    const [data, setData] = useState<MonteCarloData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let isMounted = true;

        async function fetchMonteCarlo() {
            setLoading(true);
            setError(null);
            try {
                const res = await apiFetch(`/enrich/montecarlo/${productId}`);
                if (!res.ok) {
                    const errData = await res.json();
                    throw new Error(errData.detail || "Failed to load Monte Carlo simulation");
                }
                const parsed = await res.json();
                if (isMounted) setData(parsed);
            } catch (err: unknown) {
                if (isMounted) setError(getErrorMessage(err, "Failed to load Monte Carlo simulation"));
            } finally {
                if (isMounted) setLoading(false);
            }
        }

        if (productId) {
            fetchMonteCarlo();
        }

        return () => { isMounted = false; };
    }, [productId]);

    if (loading) {
        return (
            <div className="flex h-64 w-full flex-col items-center justify-center rounded-xl bg-gray-50/50 dark:bg-gray-800/20">
                <svg className="h-6 w-6 animate-spin text-purple-600" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span className="mt-3 text-sm font-medium text-gray-500">Running Monte Carlo Simulations...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex h-64 w-full flex-col items-center justify-center rounded-xl bg-red-50/50 p-6 text-center dark:bg-red-500/10">
                <svg className="h-8 w-8 text-red-500 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span className="text-sm font-semibold text-red-700 dark:text-red-400">Simulation Failed</span>
                <span className="text-xs text-red-600/70 dark:text-red-400/70 mt-1">{error}</span>
            </div>
        );
    }

    if (!data) return null;

    const finalPoint = data.trajectories[data.trajectories.length - 1];
    const p10 = finalPoint?.pessimistic ?? data.predicted_5yr_median;
    const p50 = finalPoint?.median ?? data.predicted_5yr_median;
    const p90 = finalPoint?.optimistic ?? data.predicted_5yr_median;
    const growthRatio = (p50 - data.current_citations) / Math.max(data.current_citations, 1);
    const citationSignal = clampScore((Math.log1p(Math.max(p50, 0)) / Math.log1p(5000)) * 100);
    const growthSignal = clampScore(50 + growthRatio * 35);
    const stabilitySignal = clampScore(100 - ((p90 - p10) / Math.max(p50, 1)) * 35);
    const score = clampScore(citationSignal * 0.45 + growthSignal * 0.35 + stabilitySignal * 0.20);
    const confidenceScore = stabilitySignal;
    const confidenceLabel = confidenceScore >= 70 ? "Alta" : confidenceScore >= 45 ? "Media" : "Baja";
    const interpretation = score >= 70
        ? "Registro con potencial alto y base bibliométrica defendible."
        : score >= 45
        ? "Registro con potencial útil, pero conviene leerlo como señal direccional."
        : "Señal temprana: requiere más evidencia antes de sostener una conclusión de impacto.";
    const drivers = [
        { label: "Señal de citas", value: citationSignal },
        { label: "Crecimiento proyectado", value: growthSignal },
        { label: "Estabilidad del rango", value: stabilitySignal },
    ];

    return (
        <div className="space-y-6">
            <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
                <div className="rounded-[1.25rem] bg-gradient-to-br from-violet-600 to-indigo-700 p-6 text-white shadow-[0_18px_45px_rgba(124,58,237,0.28)]">
                    <p className="text-xs font-black uppercase tracking-[0.18em] text-white/70">Impacto proyectado</p>
                    <div className="mt-4 flex items-end justify-between gap-4">
                        <div>
                            <p className="text-6xl font-black tracking-tight">{score}</p>
                            <p className="text-sm font-bold text-white/70">sobre 100</p>
                        </div>
                        <span className="rounded-full bg-white/15 px-4 py-2 text-sm font-black">
                            Confianza {confidenceLabel} · {confidenceScore}/100
                        </span>
                    </div>
                    <p className="mt-5 text-sm font-semibold leading-6 text-white/82">{interpretation}</p>
                </div>

                <div className="grid gap-4 sm:grid-cols-3">
                    <div className="rounded-[1.25rem] border border-gray-100 bg-white p-5 dark:border-white/10 dark:bg-white/[0.04]">
                        <p className="text-[11px] font-black uppercase tracking-[0.14em] text-gray-400">Citas actuales</p>
                        <p className="mt-3 text-3xl font-black text-gray-950 dark:text-white">{data.current_citations}</p>
                    </div>
                    <div className="rounded-[1.25rem] border border-gray-100 bg-white p-5 dark:border-white/10 dark:bg-white/[0.04]">
                        <p className="text-[11px] font-black uppercase tracking-[0.14em] text-gray-400">Mediana a 5 años</p>
                        <p className="mt-3 text-3xl font-black text-violet-600 dark:text-violet-300">{p50}</p>
                    </div>
                    <div className="rounded-[1.25rem] border border-gray-100 bg-white p-5 dark:border-white/10 dark:bg-white/[0.04]">
                        <p className="text-[11px] font-black uppercase tracking-[0.14em] text-gray-400">Rango probable</p>
                        <p className="mt-3 text-3xl font-black text-gray-950 dark:text-white">{p10}-{p90}</p>
                    </div>
                </div>
            </div>

            <div className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr]">
                <div className="rounded-[1.25rem] border border-gray-100 bg-white p-5 dark:border-white/10 dark:bg-white/[0.04]">
                    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                        <div>
                            <h4 className="text-sm font-black uppercase tracking-[0.14em] text-gray-500 dark:text-gray-400">Trayectoria Monte Carlo</h4>
                            <p className="mt-1 text-xs font-semibold text-gray-400">
                                {data.total_simulations} simulaciones · horizonte de {data.simulation_years} años
                            </p>
                        </div>
                        <span className="rounded-full bg-violet-50 px-3 py-1 text-xs font-black text-violet-700 dark:bg-violet-400/10 dark:text-violet-200">
                            p10 / p50 / p90
                        </span>
                    </div>
                    <div className="h-72 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={data.trajectories} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="colorMedian" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" className="dark:stroke-gray-800" />
                                <XAxis dataKey="year" tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "#6b7280" }} dy={10} />
                                <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "#6b7280" }} />
                                <Tooltip
                                    contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)", fontSize: "12px" }}
                                    itemStyle={{ fontWeight: 600 }}
                                />
                                <Area type="monotone" dataKey="optimistic" stroke="none" fill="#ede9fe" fillOpacity={0.55} className="dark:fill-violet-950/50" />
                                <Area type="monotone" dataKey="pessimistic" stroke="none" fill="#ffffff" fillOpacity={1} className="dark:fill-gray-900" />
                                <Area
                                    type="monotone"
                                    dataKey="median"
                                    stroke="#8b5cf6"
                                    strokeWidth={3}
                                    fillOpacity={1}
                                    fill="url(#colorMedian)"
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div className="rounded-[1.25rem] border border-gray-100 bg-white p-5 dark:border-white/10 dark:bg-white/[0.04]">
                    <h4 className="text-sm font-black uppercase tracking-[0.14em] text-gray-500 dark:text-gray-400">Drivers del score</h4>
                    <div className="mt-5 space-y-4">
                        {drivers.map((driver) => (
                            <div key={driver.label}>
                                <div className="mb-1 flex items-center justify-between text-xs font-black text-gray-500 dark:text-gray-400">
                                    <span>{driver.label}</span>
                                    <span>{driver.value}/100</span>
                                </div>
                                <div className="h-2 rounded-full bg-gray-100 dark:bg-white/10">
                                    <div className="h-2 rounded-full bg-violet-600" style={{ width: `${driver.value}%` }} />
                                </div>
                            </div>
                        ))}
                    </div>
                    <div className="mt-6 rounded-2xl bg-gray-50 p-4 text-xs font-semibold leading-5 text-gray-500 dark:bg-white/5 dark:text-gray-400">
                        La métrica pondera señal de citas, crecimiento simulado y estabilidad del rango. Es direccional: no sustituye revisión experta ni validación bibliométrica.
                    </div>
                </div>
            </div>
        </div>
    );
}
