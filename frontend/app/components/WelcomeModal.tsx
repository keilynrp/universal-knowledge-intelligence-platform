"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

// ── Shown ONCE on first login — stored in localStorage ────────────────────────

const STORAGE_KEY = "ukip_welcomed_v1";

const SLIDES = [
  {
    emoji: "📥",
    title: "Import your knowledge base",
    body: "Upload CSV, Excel, BibTeX or RIS files. UKIP handles any domain — science, healthcare, engineering, or your own custom schema.",
    cta: { label: "Go to Import", href: "/import-export" },
    color: "from-blue-600 to-cyan-500",
  },
  {
    emoji: "✨",
    title: "Enrich & harmonize automatically",
    body: "UKIP enriches entities from Web of Science, OpenAlex, and more. Smart deduplication and harmonization rules keep your data clean.",
    cta: { label: "See Harmonization", href: "/harmonization" },
    color: "from-violet-600 to-purple-500",
  },
  {
    emoji: "📊",
    title: "Analyze & collaborate in real time",
    body: "Executive dashboards, OLAP explorer, topic clusters, and live collaboration. Share insights via embeddable widgets — no login required for consumers.",
    cta: { label: "Open Analytics", href: "/analytics/dashboard" },
    color: "from-emerald-600 to-teal-500",
  },
];

export default function WelcomeModal() {
  const [visible, setVisible] = useState(false);
  const [slide, setSlide] = useState(0);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const seen = localStorage.getItem(STORAGE_KEY);
    if (!seen) setVisible(true);
  }, []);

  const dismiss = () => {
    localStorage.setItem(STORAGE_KEY, "1");
    setVisible(false);
  };

  if (!visible) return null;

  const current = SLIDES[slide];
  const isLast = slide === SLIDES.length - 1;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="relative w-full max-w-md mx-4 rounded-2xl bg-white shadow-2xl overflow-hidden">

        {/* Gradient header */}
        <div className={`bg-gradient-to-br ${current.color} px-8 py-10 text-center text-white`}>
          <div className="text-5xl mb-3">{current.emoji}</div>
          <h2 className="text-xl font-bold leading-snug">{current.title}</h2>
        </div>

        {/* Body */}
        <div className="px-8 py-6">
          <p className="text-sm text-slate-600 leading-relaxed text-center">{current.body}</p>
        </div>

        {/* Slide dots */}
        <div className="flex justify-center gap-2 pb-2">
          {SLIDES.map((_, i) => (
            <button
              key={i}
              onClick={() => setSlide(i)}
              className={`h-2 rounded-full transition-all ${
                i === slide ? "w-6 bg-violet-600" : "w-2 bg-slate-200"
              }`}
            />
          ))}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between gap-3 px-8 py-5 border-t border-slate-100">
          <button
            onClick={dismiss}
            className="text-sm text-slate-400 hover:text-slate-600"
          >
            Skip tour
          </button>
          <div className="flex gap-2">
            {slide > 0 && (
              <button
                onClick={() => setSlide(s => s - 1)}
                className="px-4 py-2 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50"
              >
                Back
              </button>
            )}
            {!isLast ? (
              <button
                onClick={() => setSlide(s => s + 1)}
                className="px-5 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700"
              >
                Next
              </button>
            ) : (
              <Link
                href={current.cta.href}
                onClick={dismiss}
                className="px-5 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700"
              >
                {current.cta.label}
              </Link>
            )}
          </div>
        </div>

        {/* Close button */}
        <button
          onClick={dismiss}
          className="absolute top-3 right-3 rounded-full p-1 text-white/70 hover:text-white"
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
