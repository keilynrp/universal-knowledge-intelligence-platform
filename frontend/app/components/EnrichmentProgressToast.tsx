"use client";

import { useEffect, useRef, useState } from "react";
import { useLanguage } from "../contexts/LanguageContext";
import { apiFetch } from "@/lib/api";

export interface EnrichmentBatchState {
    ids: number[];
    skipped: number;
}

interface ProgressData {
    total: number;
    pending: number;
    processing: number;
    completed: number;
    failed: number;
}

type Phase = "progress" | "done" | "hidden";

export function EnrichmentProgressToast({
    batch,
    onComplete,
    onViewFailed,
}: {
    batch: EnrichmentBatchState | null;
    onComplete: () => void;
    onViewFailed: () => void;
}) {
    const { t } = useLanguage();
    const [phase, setPhase] = useState<Phase>("hidden");
    const [progress, setProgress] = useState<ProgressData | null>(null);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const autoDismissRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        if (!batch || batch.ids.length === 0) {
            // Intentional reset inside an effect that also sets up polling below;
            // not purely derivable, so suppress the set-state-in-effect rule here.
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setPhase("hidden");
            return;
        }

        setPhase("progress");
        setProgress(null);

        const poll = async () => {
            try {
                const res = await apiFetch("/enrich/progress", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ ids: batch.ids }),
                });
                if (!res.ok) return;
                const data: ProgressData = await res.json();
                setProgress(data);

                if (data.pending === 0 && data.processing === 0) {
                    // Batch complete
                    if (pollRef.current) {
                        clearInterval(pollRef.current);
                        pollRef.current = null;
                    }
                    setPhase("done");
                    autoDismissRef.current = setTimeout(() => {
                        setPhase("hidden");
                        onComplete();
                    }, 8000);
                }
            } catch {
                // Non-critical polling failure
            }
        };

        poll();
        pollRef.current = setInterval(poll, 3000);

        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
            if (autoDismissRef.current) clearTimeout(autoDismissRef.current);
        };
    }, [batch, onComplete]);

    if (phase === "hidden" || !batch) return null;

    const processed = progress ? progress.completed + progress.failed : 0;
    const total = progress?.total ?? batch.ids.length;
    const pct = total > 0 ? Math.round((processed / total) * 100) : 0;

    return (
        <div className="pointer-events-auto fixed bottom-5 right-5 z-[210] w-80 rounded-xl border border-purple-200 bg-white/95 p-4 shadow-xl backdrop-blur-lg dark:border-purple-700/50 dark:bg-[var(--ukip-panel)]">
            {phase === "progress" && (
                <>
                    <div className="flex items-center gap-2">
                        <svg className="h-4 w-4 animate-spin text-purple-600 dark:text-purple-400" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        <span className="text-sm font-semibold text-purple-800 dark:text-purple-200">
                            {t("page.entity_table.enrichment_progress", { processed: String(processed), total: String(total) })}
                        </span>
                    </div>
                    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-purple-100 dark:bg-purple-900/40">
                        <div
                            className="h-full rounded-full bg-purple-600 transition-all duration-500 dark:bg-purple-400"
                            style={{ width: `${pct}%` }}
                        />
                    </div>
                    {batch.skipped > 0 && (
                        <p className="mt-1.5 text-xs text-purple-600/70 dark:text-purple-300/60">
                            {t("page.entity_table.enrichment_skipped", { count: String(batch.skipped) })}
                        </p>
                    )}
                </>
            )}
            {phase === "done" && progress && (
                <>
                    <div className="flex items-center gap-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-green-100 text-xs font-bold text-green-600 dark:bg-green-800 dark:text-green-300">
                            &#10003;
                        </span>
                        <span className="text-sm font-semibold text-slate-800 dark:text-[var(--ukip-text-strong)]">
                            {t("page.entity_table.enrichment_complete_summary", {
                                succeeded: String(progress.completed),
                                failed: String(progress.failed),
                            })}
                        </span>
                    </div>
                    {progress.failed > 0 && (
                        <button
                            onClick={onViewFailed}
                            className="mt-2 text-xs font-bold text-red-600 underline underline-offset-2 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                        >
                            {t("page.entity_table.enrichment_view_failed")}
                        </button>
                    )}
                </>
            )}
        </div>
    );
}
