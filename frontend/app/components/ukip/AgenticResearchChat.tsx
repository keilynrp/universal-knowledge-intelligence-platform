"use client";

import { FormEvent, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useLanguage } from "../../contexts/LanguageContext";

type ChatMode = "auto" | "rag" | "nlq" | "hybrid";

type AgenticResearchChatProps = {
  domainId: string;
  importBatchId?: number | null;
  provider?: string | null;
  portalSlug?: string | null;
  entityId?: number | null;
  title?: string;
  compact?: boolean;
};

type ChatResponse = {
  answer: string;
  mode_used: string;
  trace_id?: number | null;
  trace?: {
    rag_used?: boolean;
    nlq_used?: boolean;
    tools_used?: string[];
    context_blocks?: string[];
    provider?: string | null;
    model?: string | null;
    errors?: string[];
  };
  sources?: { entity_id?: number | null; label?: string; score?: number | null; source?: string }[];
  follow_up_questions?: string[];
};

const starterPrompts = [
  "Que patrones ocultos debo revisar antes del brief?",
  "Que registros sostienen mejor una lectura ejecutiva?",
  "Que brechas de calidad limitan la confianza del portafolio?",
];

export default function AgenticResearchChat({
  domainId,
  importBatchId,
  provider,
  portalSlug,
  entityId,
  title,
  compact = false,
}: AgenticResearchChatProps) {
  const { t } = useLanguage();
  const [question, setQuestion] = useState(starterPrompts[0]);
  const [mode, setMode] = useState<ChatMode>("auto");
  const [useTools, setUseTools] = useState(true);
  const [persistTrace, setPersistTrace] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<ChatResponse | null>(null);

  const scopeLabel = useMemo(() => {
    const parts = [`${t('agentic_chat.scope_domain')} ${domainId}`];
    if (importBatchId) parts.push(`${t('agentic_chat.scope_ingest')} #${importBatchId}`);
    if (provider) parts.push(`${t('agentic_chat.scope_provider')} ${provider}`);
    if (portalSlug) parts.push(`${t('agentic_chat.scope_portal')} ${portalSlug}`);
    if (entityId) parts.push(`${t('agentic_chat.scope_record')} #${entityId}`);
    return parts.join(" · ");
  }, [domainId, entityId, importBatchId, portalSlug, provider, t]);

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/agentic-chat/query", {
        method: "POST",
        body: JSON.stringify({
          question: question.trim(),
          mode,
          domain_id: domainId,
          import_batch_id: importBatchId ?? null,
          provider: provider ?? null,
          portal_slug: portalSlug ?? null,
          entity_id: entityId ?? null,
          top_k: 6,
          use_tools: useTools,
          persist_trace: persistTrace,
        }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(payload.detail || "No se pudo consultar el asistente.");
      }
      setResponse(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo consultar el asistente.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="ukip-panel-soft overflow-hidden">
      <div className="grid gap-0 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="p-5 md:p-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="ukip-kicker">NLQ + RAG + tools</p>
              <h3 className="mt-1 text-lg font-bold text-[var(--ukip-text-strong)]">{title || t('agentic_chat.title')}</h3>
              <p className="mt-2 text-sm text-[var(--ukip-muted)]">{scopeLabel}</p>
            </div>
            <span className="w-fit rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-xs font-bold text-violet-700 dark:border-violet-500/20 dark:bg-violet-500/10 dark:text-violet-200">
              {response?.mode_used ? `Modo ${response.mode_used}` : "Modo auto"}
            </span>
          </div>

          <form className="mt-5 space-y-4" onSubmit={submit}>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              className="min-h-28 w-full rounded-2xl border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-4 py-3 text-sm text-[var(--ukip-text)] outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-500/10"
              placeholder="Pregunta sobre una ingesta, un registro, patrones, fuentes o evidencia para brief..."
            />
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <select
                  value={mode}
                  onChange={(event) => setMode(event.target.value as ChatMode)}
                  className="rounded-full border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-3 py-2 font-semibold text-[var(--ukip-text)] outline-none"
                >
                  <option value="auto">{t('agentic_chat.mode_auto')}</option>
                  <option value="hybrid">{t('agentic_chat.mode_hybrid')}</option>
                  <option value="rag">RAG</option>
                  <option value="nlq">NLQ</option>
                </select>
                <label className="inline-flex items-center gap-2 rounded-full border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-3 py-2 font-semibold text-[var(--ukip-text)]">
                  <input type="checkbox" checked={useTools} onChange={(event) => setUseTools(event.target.checked)} />
                  {t('agentic_chat.tools')}
                </label>
                <label className="inline-flex items-center gap-2 rounded-full border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-3 py-2 font-semibold text-[var(--ukip-text)]">
                  <input type="checkbox" checked={persistTrace} onChange={(event) => setPersistTrace(event.target.checked)} />
                  {t('agentic_chat.persist_trace')}
                </label>
              </div>
              <button
                type="submit"
                disabled={loading}
                className="inline-flex items-center justify-center rounded-2xl bg-violet-600 px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? t('agentic_chat.analyzing') : t('agentic_chat.ask_portfolio')}
              </button>
            </div>
          </form>

          {!compact && (
            <div className="mt-4 flex flex-wrap gap-2">
              {starterPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => setQuestion(prompt)}
                  className="rounded-full border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-3 py-1.5 text-xs font-semibold text-[var(--ukip-muted)] transition hover:border-violet-300 hover:text-violet-600"
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="border-t border-[var(--ukip-border)] bg-[var(--ukip-surface)] p-5 md:p-6 lg:border-l lg:border-t-0">
          <p className="ukip-kicker">{t('agentic_chat.traceable_response')}</p>
          {error && (
            <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
              {error}
            </div>
          )}
          {!response && !error && (
            <div className="mt-4 rounded-2xl border border-dashed border-[var(--ukip-border)] p-5 text-sm text-[var(--ukip-muted)]">
              {t('agentic_chat.empty_state')}
            </div>
          )}
          {response && (
            <div className="mt-4 space-y-4">
              <p className="whitespace-pre-wrap text-sm leading-6 text-[var(--ukip-text)]">{response.answer}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <TracePill label="RAG" active={Boolean(response.trace?.rag_used)} />
                <TracePill label="NLQ" active={Boolean(response.trace?.nlq_used)} />
              </div>
              {response.trace_id && (
                <p className="rounded-xl bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200">
                  {t('agentic_chat.trace_saved')} #{response.trace_id}
                </p>
              )}
              {(response.trace?.tools_used?.length ?? 0) > 0 && (
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--ukip-muted)]">{t('agentic_chat.tools')}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {response.trace?.tools_used?.map((tool) => (
                      <span key={tool} className="rounded-full bg-violet-100 px-2.5 py-1 text-xs font-bold text-violet-700 dark:bg-violet-500/15 dark:text-violet-200">
                        {tool}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {(response.sources?.length ?? 0) > 0 && (
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--ukip-muted)]">{t('rag.sources')}</p>
                  <ul className="mt-2 space-y-2">
                    {response.sources?.slice(0, 4).map((source, index) => (
                      <li key={`${source.entity_id ?? index}-${source.label}`} className="rounded-xl border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-3 py-2 text-xs text-[var(--ukip-muted)]">
                        <span className="font-bold text-[var(--ukip-text-strong)]">{source.label || `${t('agentic_chat.source')} ${index + 1}`}</span>
                        {source.entity_id ? ` · #${source.entity_id}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function TracePill({ label, active }: { label: string; active: boolean }) {
  return (
    <div className={`rounded-2xl border px-3 py-2 text-xs font-bold ${active ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-200" : "border-[var(--ukip-border)] bg-[var(--ukip-panel)] text-[var(--ukip-muted)]"}`}>
      {label}: {active ? "activo" : "sin uso"}
    </div>
  );
}

export type { AgenticResearchChatProps };
