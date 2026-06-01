import ResearchIcon from "./ResearchersIcons";

type Feedback = "useful" | "review" | null;

interface CalibrationBarProps {
  feedback: Feedback;
  onFeedback: (value: "useful" | "review") => void;
}

export default function CalibrationBar({ feedback, onFeedback }: CalibrationBarProps) {
  return (
    <section className="rounded-xl bg-white p-5 shadow-xs ring-1 ring-slate-950/5 dark:bg-slate-950 dark:ring-white/10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200 dark:bg-emerald-400/10 dark:text-emerald-200 dark:ring-emerald-400/20">
            <ResearchIcon name="check" />
          </span>
          <div className="min-w-0">
            <h2 className="text-base font-bold tracking-tight text-slate-950 dark:text-white">Calibracion stakeholder</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Marca si el mapa parece accionable. Esta senal nos ayuda a ajustar el scoring cuando validemos con usuarios reales.
            </p>
          </div>
        </div>
        <div className="flex gap-2 font-mono text-xs font-medium uppercase tracking-wider">
          <button
            type="button"
            onClick={() => onFeedback("useful")}
            className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 ring-1 transition ${feedback === "useful" ? "bg-emerald-600 text-white ring-emerald-600" : "bg-emerald-50 text-emerald-700 ring-emerald-200 hover:bg-emerald-100 dark:bg-emerald-400/10 dark:text-emerald-200 dark:ring-emerald-400/20"}`}
          >
            <ResearchIcon name="check" className="h-3.5 w-3.5" />
            Util
          </button>
          <button
            type="button"
            onClick={() => onFeedback("review")}
            className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 ring-1 transition ${feedback === "review" ? "bg-amber-600 text-white ring-amber-600" : "bg-amber-50 text-amber-700 ring-amber-200 hover:bg-amber-100 dark:bg-amber-400/10 dark:text-amber-200 dark:ring-amber-400/20"}`}
          >
            <ResearchIcon name="target" className="h-3.5 w-3.5" />
            Revisar
          </button>
        </div>
      </div>
      {feedback && (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm font-medium text-slate-600 dark:bg-white/5 dark:text-slate-300">
          Feedback registrado localmente para este corte: {feedback === "useful" ? "mapa util" : "requiere revision"}.
        </p>
      )}
    </section>
  );
}
