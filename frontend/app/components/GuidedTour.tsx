"use client";

import { useState, useEffect } from "react";
import { Analytics } from "@/lib/analytics";

// ── Tour step definition ───────────────────────────────────────────────────────

interface TourStep {
  title: string;
  description: string;
  icon: string;
  tip?: string;
  /** Which area of the screen to highlight: top-left | top-right | center | bottom-left | bottom-right */
  position: "top-left" | "top-right" | "center" | "bottom-left" | "bottom-right";
}

const TOUR_STEPS: TourStep[] = [
  {
    title: "Welcome to UKIP!",
    description:
      "Your demo dataset with 1,000 scientific publications is loaded. This quick tour shows you the key features in under 2 minutes.",
    icon: "🚀",
    tip: "You can skip the tour at any time.",
    position: "center",
  },
  {
    title: "Knowledge Dashboard",
    description:
      "This is your main hub. Browse entities, filter by status, and manage your data. The stat cards at the top show live KPIs.",
    icon: "📊",
    tip: "Try switching between Table View and Variant Groups.",
    position: "top-left",
  },
  {
    title: "Executive Analytics",
    description:
      "Go to Analytics → Executive Dashboard for high-level KPIs, temporal trends, and a concept cloud. Perfect for C-level presentations.",
    icon: "📈",
    tip: "Use the 'Export PDF' button to generate a branded report in one click.",
    position: "top-right",
  },
  {
    title: "OLAP Cube Explorer",
    description:
      "Slice your data by any dimension — year, country, field, or institution. Click '↳ Drill' on any row to go deeper.",
    icon: "🧮",
    tip: "Try combining two dimensions for a cross-tab analysis.",
    position: "bottom-left",
  },
  {
    title: "Export & Reports",
    description:
      "Generate reports in Excel, PDF, or PowerPoint. Pick your sections, choose a format, and download a branded document.",
    icon: "📥",
    tip: "Go to Import / Export → Report Builder to build your first report.",
    position: "bottom-right",
  },
];

const STORAGE_KEY = "ukip_guided_tour_completed";

// ── Position styles ────────────────────────────────────────────────────────────

const CARD_POSITIONS: Record<TourStep["position"], string> = {
  center:       "top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2",
  "top-left":   "top-24 left-6",
  "top-right":  "top-24 right-6",
  "bottom-left":"bottom-10 left-6",
  "bottom-right":"bottom-10 right-6",
};

// ── Progress dots ──────────────────────────────────────────────────────────────

function ProgressDots({ total, current }: { total: number; current: number }) {
  return (
    <div className="flex items-center justify-center gap-1.5">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`rounded-full transition-all duration-300 ${
            i === current
              ? "h-2.5 w-2.5 bg-violet-600"
              : i < current
              ? "h-2 w-2 bg-violet-300"
              : "h-2 w-2 bg-gray-300 dark:bg-gray-600"
          }`}
        />
      ))}
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

interface GuidedTourProps {
  /** Tour starts automatically when this is true and the tour hasn't been completed yet. */
  autoStart?: boolean;
  /** Optionally control visibility externally (e.g. a "Take the tour" button). */
  show?: boolean;
  onClose?: () => void;
}

export default function GuidedTour({ autoStart = false, show, onClose }: GuidedTourProps) {
  const [step, setStep] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (show !== undefined) {
      setVisible(show);
      return;
    }
    if (autoStart) {
      const done = localStorage.getItem(STORAGE_KEY);
      if (!done) setVisible(true);
    }
  }, [autoStart, show]);

  const close = (completed: boolean) => {
    if (completed) {
      localStorage.setItem(STORAGE_KEY, "1");
      Analytics.tourCompleted(step + 1);
    } else {
      Analytics.tourSkipped(step);
    }
    setVisible(false);
    onClose?.();
  };

  const next = () => {
    if (step < TOUR_STEPS.length - 1) {
      setStep(s => s + 1);
    } else {
      close(true);
    }
  };

  const prev = () => setStep(s => Math.max(0, s - 1));

  if (!visible) return null;

  const current = TOUR_STEPS[step];
  const isLast = step === TOUR_STEPS.length - 1;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px]"
        onClick={() => close(false)}
      />

      {/* Tour card */}
      <div
        className={`fixed z-50 w-80 max-w-[calc(100vw-2rem)] ${CARD_POSITIONS[current.position]}`}
        role="dialog"
        aria-label={`Tour step ${step + 1} of ${TOUR_STEPS.length}: ${current.title}`}
      >
        <div className="overflow-hidden rounded-2xl border border-violet-200 bg-white shadow-2xl dark:border-violet-500/30 dark:bg-gray-900">
          {/* Header */}
          <div className="flex items-center justify-between bg-gradient-to-r from-violet-600 to-purple-600 px-5 py-4">
            <div className="flex items-center gap-2">
              <span className="text-2xl">{current.icon}</span>
              <span className="text-sm font-semibold text-white">
                Step {step + 1} of {TOUR_STEPS.length}
              </span>
            </div>
            <button
              onClick={() => close(false)}
              className="rounded-full p-1 text-violet-200 transition hover:bg-white/20 hover:text-white"
              aria-label="Skip tour"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Body */}
          <div className="px-5 py-4">
            <h3 className="mb-2 text-base font-bold text-gray-900 dark:text-white">
              {current.title}
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-300">
              {current.description}
            </p>
            {current.tip && (
              <div className="mt-3 flex items-start gap-2 rounded-lg bg-violet-50 px-3 py-2 dark:bg-violet-900/20">
                <span className="mt-0.5 text-sm">💡</span>
                <p className="text-xs text-violet-700 dark:text-violet-300">{current.tip}</p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between border-t border-gray-100 px-5 py-3 dark:border-gray-800">
            <ProgressDots total={TOUR_STEPS.length} current={step} />
            <div className="flex items-center gap-2">
              {step > 0 && (
                <button
                  onClick={prev}
                  className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 transition hover:bg-gray-50 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800"
                >
                  Back
                </button>
              )}
              <button
                onClick={next}
                className="rounded-lg bg-violet-600 px-4 py-1.5 text-xs font-semibold text-white transition hover:bg-violet-700"
              >
                {isLast ? "Got it! 🎉" : "Next →"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

/** Reset the tour (for testing or "Take the tour again" buttons). */
export function resetTour() {
  localStorage.removeItem(STORAGE_KEY);
}
