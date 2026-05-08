"use client";

import { useState } from "react";
import { useLanguage } from "../contexts/LanguageContext";
import { Analytics } from "@/lib/analytics";

// ── Tour step definition ───────────────────────────────────────────────────────

interface TourStep {
  titleKey: string;
  descriptionKey: string;
  icon: string;
  tipKey?: string;
  /** Which area of the screen to highlight: top-left | top-right | center | bottom-left | bottom-right */
  position: "top-left" | "top-right" | "center" | "bottom-left" | "bottom-right";
}

const TOUR_STEPS: TourStep[] = [
  {
    titleKey: "guided_tour.step.welcome.title",
    descriptionKey: "guided_tour.step.welcome.description",
    icon: "🚀",
    tipKey: "guided_tour.step.welcome.tip",
    position: "center",
  },
  {
    titleKey: "guided_tour.step.dashboard.title",
    descriptionKey: "guided_tour.step.dashboard.description",
    icon: "📊",
    tipKey: "guided_tour.step.dashboard.tip",
    position: "top-left",
  },
  {
    titleKey: "guided_tour.step.analytics.title",
    descriptionKey: "guided_tour.step.analytics.description",
    icon: "📈",
    tipKey: "guided_tour.step.analytics.tip",
    position: "top-right",
  },
  {
    titleKey: "guided_tour.step.olap.title",
    descriptionKey: "guided_tour.step.olap.description",
    icon: "🧮",
    tipKey: "guided_tour.step.olap.tip",
    position: "bottom-left",
  },
  {
    titleKey: "guided_tour.step.reports.title",
    descriptionKey: "guided_tour.step.reports.description",
    icon: "📥",
    tipKey: "guided_tour.step.reports.tip",
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
  const { t } = useLanguage();
  const [step, setStep] = useState(0);
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return localStorage.getItem(STORAGE_KEY) === "1";
  });
  const visible = show ?? (autoStart && !dismissed);

  const close = (completed: boolean) => {
    if (completed) {
      localStorage.setItem(STORAGE_KEY, "1");
      Analytics.tourCompleted(step + 1);
    } else {
      Analytics.tourSkipped(step);
    }
    setDismissed(true);
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
  const title = t(current.titleKey);
  const description = t(current.descriptionKey);
  const tip = current.tipKey ? t(current.tipKey) : "";
  const stepLabel = t("guided_tour.step_label", {
    current: step + 1,
    total: TOUR_STEPS.length,
  });

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
        aria-label={t("guided_tour.dialog_label", {
          current: step + 1,
          total: TOUR_STEPS.length,
          title,
        })}
      >
        <div className="overflow-hidden rounded-2xl border border-violet-200 bg-white shadow-2xl dark:border-violet-500/30 dark:bg-gray-900">
          {/* Header */}
          <div className="flex items-center justify-between bg-gradient-to-r from-violet-600 to-purple-600 px-5 py-4">
            <div className="flex items-center gap-2">
              <span className="text-2xl">{current.icon}</span>
              <span className="text-sm font-semibold text-white">
                {stepLabel}
              </span>
            </div>
            <button
              onClick={() => close(false)}
              className="rounded-full p-1 text-violet-200 transition hover:bg-white/20 hover:text-white"
              aria-label={t("guided_tour.skip")}
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Body */}
          <div className="px-5 py-4">
            <h3 className="mb-2 text-base font-bold text-gray-900 dark:text-white">
              {title}
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-300">
              {description}
            </p>
            {tip && (
              <div className="mt-3 flex items-start gap-2 rounded-lg bg-violet-50 px-3 py-2 dark:bg-violet-900/20">
                <span className="mt-0.5 text-sm">💡</span>
                <p className="text-xs text-violet-700 dark:text-violet-300">{tip}</p>
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
                  {t("guided_tour.back")}
                </button>
              )}
              <button
                onClick={next}
                className="rounded-lg bg-violet-600 px-4 py-1.5 text-xs font-semibold text-white transition hover:bg-violet-700"
              >
                {isLast ? t("guided_tour.done") : t("guided_tour.next")}
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
