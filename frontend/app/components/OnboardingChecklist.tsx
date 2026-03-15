"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { apiFetch } from "../../lib/api";

// ── Types ──────────────────────────────────────────────────────────────────

interface OnboardingStep {
  key: string;
  label: string;
  description: string;
  href: string;
  icon: string;
  completed: boolean;
}

interface OnboardingStatus {
  steps: OnboardingStep[];
  completed: number;
  total: number;
  percent: number;
  all_done: boolean;
}

const DISMISSED_KEY = "ukip_onboarding_dismissed_v1";

// ── Icon map ───────────────────────────────────────────────────────────────

function StepIcon({ icon, completed }: { icon: string; completed: boolean }) {
  const iconMap: Record<string, React.ReactNode> = {
    upload: (
      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
      </svg>
    ),
    sparkles: (
      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
      </svg>
    ),
    adjustments: (
      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" />
      </svg>
    ),
    bolt: (
      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
      </svg>
    ),
    chart: (
      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
      </svg>
    ),
  };

  if (completed) {
    return (
      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M4.5 12.75l6 6 9-13.5" />
        </svg>
      </div>
    );
  }
  return (
    <div className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 text-slate-400">
      {iconMap[icon] || iconMap.chart}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export default function OnboardingChecklist({ token }: { token: string | null }) {
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const resp = await apiFetch("/onboarding/status");
      if (resp.ok) setStatus(await resp.json());
    } catch { /* non-critical */ }
  }, [token]);

  useEffect(() => {
    const isDismissed = localStorage.getItem(DISMISSED_KEY) === "1";
    setDismissed(isDismissed);
    load();
  }, [load]);

  const dismiss = () => {
    localStorage.setItem(DISMISSED_KEY, "1");
    setDismissed(true);
  };

  if (dismissed || !status) return null;
  if (status.all_done) return null; // hide when everything is done

  return (
    <div className="rounded-xl border border-violet-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-4 cursor-pointer select-none"
        onClick={() => setCollapsed(c => !c)}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-violet-100 text-violet-600 text-sm font-bold">
            {status.completed}/{status.total}
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900">Getting started</p>
            <p className="text-xs text-slate-400">{status.percent}% complete</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Progress bar */}
          <div className="hidden sm:block w-24 h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-violet-500 rounded-full transition-all"
              style={{ width: `${status.percent}%` }}
            />
          </div>
          <svg
            className={`h-4 w-4 text-slate-400 transition-transform ${collapsed ? "" : "rotate-180"}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Steps list */}
      {!collapsed && (
        <div className="border-t border-slate-100 divide-y divide-slate-50">
          {status.steps.map((step) => (
            <Link
              key={step.key}
              href={step.href}
              className={`flex items-start gap-3 px-5 py-3.5 hover:bg-slate-50 transition-colors ${step.completed ? "opacity-60" : ""}`}
            >
              <StepIcon icon={step.icon} completed={step.completed} />
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium ${step.completed ? "line-through text-slate-400" : "text-slate-800"}`}>
                  {step.label}
                </p>
                <p className="text-xs text-slate-400 truncate">{step.description}</p>
              </div>
              {!step.completed && (
                <svg className="h-4 w-4 text-slate-300 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                </svg>
              )}
            </Link>
          ))}

          {/* Dismiss */}
          <div className="px-5 py-3 flex justify-end">
            <button
              onClick={(e) => { e.preventDefault(); dismiss(); }}
              className="text-xs text-slate-400 hover:text-slate-600"
            >
              Dismiss checklist
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
