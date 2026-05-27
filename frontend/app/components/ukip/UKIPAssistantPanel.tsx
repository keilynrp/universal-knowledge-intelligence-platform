"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useBranding } from "@/app/contexts/BrandingContext";
import type { AssistantActionLink, AssistantContext } from "@/app/contexts/AssistantContext";
import BrandLockup from "./BrandLockup";

type AssistantSource = {
  entity_id?: number | null;
  label?: string;
  score?: number | null;
  source?: string;
};

type AssistantResponse = {
  answer: string;
  mode_used: string;
  trace_id?: number | null;
  trace?: {
    rag_used?: boolean;
    nlq_used?: boolean;
    tools_used?: string[];
    provider?: string | null;
    model?: string | null;
    errors?: string[];
  };
  sources?: AssistantSource[];
  follow_up_questions?: string[];
};

type AssistantMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
  time: string;
  mode?: string;
  traceId?: number | null;
  sources?: AssistantSource[];
  tools?: string[];
  pending?: boolean;
  error?: boolean;
};

type AssistantMemoryItem = {
  route: string;
  moduleLabel: string;
  domainId: string;
  summary: string;
  timestamp: string;
};

type AssistantActionCapability = {
  id: string;
  enabled: boolean;
  executable?: boolean;
  allowed_roles: string[];
  requires_confirmation: boolean;
};

type UKIPAssistantPanelProps = {
  context: AssistantContext;
  className?: string;
};

const quickPrompts = [
  "Que brecha limita mas la lectura ejecutiva?",
  "Que entidades deberia revisar antes del brief?",
  "Que fuentes estan aportando mas evidencia?",
];

function nowLabel() {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());
}

function clampPercentage(value?: number | null) {
  if (value == null || Number.isNaN(value)) return null;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function Icon({
  name,
  className = "h-4 w-4",
}: {
  name: "bot" | "send" | "minimize" | "expand" | "close" | "database" | "chart" | "spark" | "shield" | "check" | "copy" | "arrow";
  className?: string;
}) {
  const common = {
    className,
    fill: "none",
    stroke: "currentColor",
    viewBox: "0 0 24 24",
    "aria-hidden": true,
  };
  switch (name) {
    case "send":
      return (
        <svg {...common}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="m5 12 14-7-4 14-3-6-7-1Z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="m12 13 7-8" />
        </svg>
      );
    case "minimize":
      return (
        <svg {...common}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M6 12h12" />
        </svg>
      );
    case "expand":
      return (
        <svg {...common}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 3l6 6M21 3l-6 6M3 21l6-6M21 21l-6-6" />
        </svg>
      );
    case "close":
      return (
        <svg {...common}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="m6 6 12 12M18 6 6 18" />
        </svg>
      );
    case "database":
      return (
        <svg {...common}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M5 6c0 1.66 3.13 3 7 3s7-1.34 7-3-3.13-3-7-3-7 1.34-7 3Z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M5 6v12c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12c0 1.66 3.13 3 7 3s7-1.34 7-3" />
        </svg>
      );
    case "chart":
      return (
        <svg {...common}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M4 19V5M4 19h16" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="m7 15 4-4 3 3 5-7" />
        </svg>
      );
    case "spark":
      return (
        <svg {...common}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z" />
        </svg>
      );
    case "shield":
      return (
        <svg {...common}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M12 3 5 6v5c0 4.4 2.9 7.9 7 10 4.1-2.1 7-5.6 7-10V6l-7-3Z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="m9 12 2 2 4-5" />
        </svg>
      );
    case "check":
      return (
        <svg {...common}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.9} d="m5 13 4 4L19 7" />
        </svg>
      );
    case "copy":
      return (
        <svg {...common}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M8 8h10v12H8z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M6 16H4V4h10v2" />
        </svg>
      );
    case "arrow":
      return (
        <svg {...common}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M5 12h14M13 6l6 6-6 6" />
        </svg>
      );
    case "bot":
    default:
      return (
        <svg {...common}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M12 7V4M8 7h8a4 4 0 0 1 4 4v4a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4v-4a4 4 0 0 1 4-4Z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M9 13h.01M15 13h.01M10 17h4" />
        </svg>
      );
  }
}

const MEMORY_KEY = "ukip_assistant_session_memory";

function readMemory(): AssistantMemoryItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.sessionStorage.getItem(MEMORY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.slice(0, 8) as AssistantMemoryItem[] : [];
  } catch {
    return [];
  }
}

function writeMemory(items: AssistantMemoryItem[]) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(MEMORY_KEY, JSON.stringify(items.slice(0, 8)));
}

function actionTone(action: AssistantActionLink) {
  if (action.kind === "mutation" || action.requiresConfirmation) return "border-amber-300/25 bg-amber-500/12 text-amber-100 hover:bg-amber-500/18";
  if (action.kind === "export") return "border-emerald-300/25 bg-emerald-500/12 text-emerald-100 hover:bg-emerald-500/18";
  return "border-violet-300/25 bg-violet-500/15 text-violet-100 hover:bg-violet-500/22";
}

function buildBriefHref(context: AssistantContext) {
  const sections = [
    "entity_stats",
    "enrichment_coverage",
    "impact_projection",
    "hidden_patterns",
    "agentic_trace",
    "decision_recommendations",
    "institutional_benchmark",
    "top_secondary_labels",
    "topic_clusters",
  ];
  const params = new URLSearchParams({
    preset: "pilot-brief",
    domain: context.domainId || "all",
    format: "pdf",
    stakeholder: "leadership",
    title: `UKIP Pilot Brief - ${context.moduleLabel ?? context.domainId ?? "workspace"}`,
    sections: sections.join(","),
  });
  if (context.totalEntities != null) params.set("rows", String(context.totalEntities));
  return `/reports?${params.toString()}`;
}

export default function UKIPAssistantPanel({ context, className = "" }: UKIPAssistantPanelProps) {
  const { branding } = useBranding();
  const [open, setOpen] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<AssistantMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hola. Soy UKIP Assistant. Estoy conectado al circuito de enriquecimiento, RAG, NLQ y señales del dashboard para ayudarte a interpretar tus datos con evidencia.",
      time: nowLabel(),
    },
  ]);
  const [memory, setMemory] = useState<AssistantMemoryItem[]>([]);
  const [pendingAction, setPendingAction] = useState<AssistantActionLink | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [executingActionId, setExecutingActionId] = useState<string | null>(null);
  const [capabilities, setCapabilities] = useState<Record<string, AssistantActionCapability>>({});
  const requestSeq = useRef(0);

  const connectedSources = context.activeSources ?? 0;
  const enrichmentPct = clampPercentage(context.enrichmentPct);
  const qualityPct = clampPercentage(context.qualityPct);
  const readinessPct = clampPercentage(context.readinessPct);

  const contextualSummary = useMemo(() => {
    const parts = [
      `${(context.totalEntities ?? 0).toLocaleString()} registros`,
      enrichmentPct != null ? `${enrichmentPct}% enriquecido` : null,
      qualityPct != null ? `${qualityPct}% calidad` : null,
      readinessPct != null ? `${readinessPct}% readiness` : null,
    ].filter(Boolean);
    return parts.join(" · ");
  }, [context.totalEntities, enrichmentPct, qualityPct, readinessPct]);
  const contextualActions = useMemo<AssistantActionLink[]>(() => {
    const applyCapabilities = (actions: AssistantActionLink[]) =>
      actions
        .filter((action) => capabilities[action.id]?.enabled !== false)
        .filter((action) => capabilities[action.id]?.executable !== false)
        .map((action) => ({
          ...action,
          requiresConfirmation: capabilities[action.id]?.requires_confirmation ?? action.requiresConfirmation,
        }))
        .slice(0, 4);
    if (context.actionLinks?.length) return applyCapabilities(context.actionLinks);
    const currentRoute = context.route || "/";
    const briefHref = buildBriefHref(context);
    return applyCapabilities([
      { id: "open-current", label: "Abrir vista actual", href: currentRoute, kind: "navigate" },
      { id: "open-dashboard", label: "Ver dashboard", href: "/analytics/dashboard", kind: "navigate" },
      { id: "open-rag", label: "Consultar RAG", href: "/rag", kind: "navigate" },
      { id: "open-reports", label: "Preparar brief", href: briefHref, kind: "export", requiresConfirmation: true, confirmationLabel: "Se abrira reportes con dominio, formato PDF, secciones ejecutivas y titulo prellenados desde el contexto actual. Podras revisar antes de generar." },
    ]);
  }, [capabilities, context]);

  useEffect(() => {
    setMemory(readMemory());
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiFetch("/assistant/actions")
      .then((response) => response.ok ? response.json() : null)
      .then((payload: { items?: AssistantActionCapability[] } | null) => {
        if (cancelled || !payload?.items) return;
        setCapabilities(Object.fromEntries(payload.items.map((item) => [item.id, item])));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const summary = contextualSummary || context.leadingGap || (context.recommendedActions ?? [])[0] || "Contexto activo";
    const item: AssistantMemoryItem = {
      route: context.route,
      moduleLabel: context.moduleLabel ?? "Workspace UKIP",
      domainId: context.domainId,
      summary,
      timestamp: new Date().toISOString(),
    };
    setMemory((current) => {
      const withoutSameRoute = current.filter((entry) => entry.route !== item.route);
      const next = [item, ...withoutSameRoute].slice(0, 6);
      writeMemory(next);
      return next;
    });
  }, [context.domainId, context.leadingGap, context.moduleLabel, context.recommendedActions, context.route, contextualSummary]);

  const systemPrompt = useMemo(() => {
    return [
      "Contexto actual de UKIP:",
      `ruta=${context.route}`,
      `modulo=${context.moduleLabel ?? "Workspace UKIP"}`,
      `dominio=${context.domainId}`,
      `registros=${context.totalEntities ?? "desconocido"}`,
      `enriquecidos=${context.enrichedCount ?? "desconocido"}`,
      `porcentaje_enriquecimiento=${context.enrichmentPct ?? "desconocido"}`,
      `calidad=${context.qualityPct ?? "desconocido"}`,
      `readiness=${context.readinessPct ?? "desconocido"}`,
      `fuentes_activas=${connectedSources}`,
      `brecha_principal=${context.leadingGap ?? "sin brecha principal"}`,
      `acciones_recomendadas=${(context.recommendedActions ?? []).join(" | ") || "sin acciones cargadas"}`,
      `memoria_sesion=${memory.map((item) => `${item.moduleLabel}: ${item.summary}`).join(" -> ") || "sin memoria previa"}`,
    ].join("\n");
  }, [connectedSources, context, memory]);

  async function recordAssistantAction(
    action: AssistantActionLink,
    status: "started" | "success" | "error" | "navigated",
    statusCode?: number,
    detail?: string,
  ) {
    try {
      await apiFetch("/audit-log/assistant-action", {
        method: "POST",
        body: JSON.stringify({
          action_id: action.id,
          label: action.label,
          href: action.href,
          kind: action.kind,
          route: context.route,
          module_label: context.moduleLabel ?? "Workspace UKIP",
          domain_id: context.domainId,
          api_path: action.apiPath,
          method: action.method ?? (action.apiPath ? "POST" : undefined),
          status,
          status_code: statusCode,
          detail,
        }),
      });
    } catch {
      // Assistant auditing is best-effort and must never block the user action.
    }
  }

  function requestAction(action: AssistantActionLink) {
    if (action.requiresConfirmation || action.kind === "mutation") {
      setPendingAction(action);
      return;
    }
    void recordAssistantAction(action, "navigated");
    if (typeof window !== "undefined") window.location.href = action.href;
  }

  async function executeAction(action: AssistantActionLink) {
    if (!action.apiPath) {
      setPendingAction(null);
      void recordAssistantAction(action, "navigated");
      if (typeof window !== "undefined") window.location.href = action.href;
      return;
    }

    setExecutingActionId(action.id);
    const actionMessageId = `action-${Date.now()}`;
    setMessages((current) => [
      ...current,
      {
        id: actionMessageId,
        role: "assistant",
        content: `Ejecutando accion controlada: ${action.label}...`,
        time: nowLabel(),
        pending: true,
      },
    ]);

    let actionErrorRecorded = false;
    try {
      await recordAssistantAction(action, "started");
      const response = await apiFetch(action.apiPath, {
        method: action.method ?? "POST",
        headers: { "X-Assistant-Action-Id": action.id },
      });
      if (action.responseType === "blob") {
        if (!response.ok) {
          const detail = await response.text().catch(() => `HTTP ${response.status}`);
          await recordAssistantAction(action, "error", response.status, detail);
          actionErrorRecorded = true;
          throw new Error(detail || `HTTP ${response.status}`);
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = action.downloadFilename ?? `ukip_assistant_export_${new Date().toISOString().slice(0, 10)}.csv`;
        anchor.click();
        URL.revokeObjectURL(url);
        setMessages((current) =>
          current.map((message) =>
            message.id === actionMessageId
              ? {
                  ...message,
                  pending: false,
                  content: action.successLabel ?? "Exportacion descargada correctamente.",
                }
            : message,
          ),
        );
        await recordAssistantAction(action, "success", response.status, "blob_downloaded");
        setPendingAction(null);
        return;
      }
      const payload = await response.json().catch(() => null) as Record<string, unknown> | null;
      if (!response.ok) {
        const detail = payload && typeof payload.detail === "string" ? payload.detail : `HTTP ${response.status}`;
        await recordAssistantAction(action, "error", response.status, detail);
        actionErrorRecorded = true;
        throw new Error(detail);
      }
      const indexed = typeof payload?.indexed === "number" ? ` (${payload.indexed.toLocaleString()} registros indexados)` : "";
      const skipped = typeof payload?.skipped === "number" && payload.skipped > 0 ? `, ${payload.skipped.toLocaleString()} omitidos` : "";
      setMessages((current) =>
        current.map((message) =>
          message.id === actionMessageId
            ? {
                ...message,
                pending: false,
                content: `${action.successLabel ?? "Accion completada."}${indexed}${skipped}`,
              }
            : message,
        ),
      );
      await recordAssistantAction(action, "success", response.status, "json_response");
      setPendingAction(null);
    } catch (error) {
      if (!actionErrorRecorded) {
        await recordAssistantAction(action, "error", undefined, error instanceof Error ? error.message : "Unknown error");
      }
      setMessages((current) =>
        current.map((message) =>
          message.id === actionMessageId
            ? {
                ...message,
                pending: false,
                error: true,
                content: error instanceof Error ? `No se pudo ejecutar "${action.label}": ${error.message}` : `No se pudo ejecutar "${action.label}".`,
              }
            : message,
        ),
      );
    } finally {
      setExecutingActionId(null);
    }
  }

  async function askAssistant(question: string) {
    if (!question.trim() || isSending) return;
    const trimmed = question.trim();
    const requestId = requestSeq.current + 1;
    requestSeq.current = requestId;
    setInput("");
    setIsSending(true);
    setMessages((current) => [
      ...current,
      { id: `u-${requestId}`, role: "user", content: trimmed, time: nowLabel() },
      { id: `a-${requestId}`, role: "assistant", content: "Analizando con RAG, NLQ y contexto del dashboard...", time: nowLabel(), pending: true },
    ]);

    try {
      const response = await apiFetch("/agentic-chat/query", {
        method: "POST",
        body: JSON.stringify({
          question: `${trimmed}\n\n${systemPrompt}`,
          mode: "hybrid",
          domain_id: context.domainId || "all",
          top_k: 6,
          use_tools: true,
          persist_trace: true,
        }),
      });
      const payload = (await response.json().catch(() => ({}))) as Partial<AssistantResponse> & { detail?: string };
      if (!response.ok) {
        throw new Error(payload.detail || "No se pudo consultar UKIP Assistant.");
      }

      setMessages((current) =>
        current.map((message) =>
          message.id === `a-${requestId}`
            ? {
                id: message.id,
                role: "assistant",
                content: payload.answer || "No encontre una respuesta con la evidencia disponible.",
                time: nowLabel(),
                mode: payload.mode_used,
                traceId: payload.trace_id,
                sources: payload.sources ?? [],
                tools: payload.trace?.tools_used ?? [],
              }
            : message,
        ),
      );
    } catch (error) {
      setMessages((current) =>
        current.map((message) =>
          message.id === `a-${requestId}`
            ? {
                ...message,
                pending: false,
                error: true,
                content: error instanceof Error ? error.message : "No se pudo conectar con el asistente.",
              }
            : message,
        ),
      );
    } finally {
      setIsSending(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void askAssistant(input);
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={`fixed bottom-6 right-6 z-40 flex h-16 w-16 items-center justify-center rounded-full border border-violet-300 bg-violet-600 text-white shadow-[0_18px_50px_rgb(124_58_237/0.38)] transition hover:bg-violet-500 ${className}`}
        aria-label="Abrir UKIP Assistant"
      >
        <Icon name="bot" className="h-7 w-7" />
      </button>
    );
  }

  return (
    <aside
      className={`fixed z-40 ${expanded ? "inset-x-4 bottom-4 top-20 max-w-none" : "bottom-6 right-6 top-auto w-[min(440px,calc(100vw-2rem))]"} ${className}`}
      aria-label="UKIP Assistant"
    >
      <div className="flex max-h-[calc(100vh-7rem)] flex-col overflow-hidden rounded-2xl border border-violet-400/35 bg-slate-950 text-white shadow-[0_24px_80px_rgb(15_23_42/0.42)]">
        <header className="border-b border-white/10 bg-[radial-gradient(circle_at_10%_0%,rgba(124,58,237,0.42),transparent_36%),linear-gradient(135deg,rgba(15,23,42,0.98),rgba(30,27,75,0.94))] px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <BrandLockup
                  branding={branding}
                  showText={false}
                  size="sm"
                  markClassName="!rounded-xl !bg-violet-600"
                />
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h2 className="truncate text-sm font-semibold tracking-normal text-white">UKIP Assistant</h2>
                    <span className="rounded bg-violet-500 px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">Beta</span>
                  </div>
                  <p className="mt-1 flex items-center gap-1.5 text-xs font-medium text-emerald-300">
                    <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_16px_rgb(52_211_153/0.9)]" />
                    En linea
                  </p>
                </div>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <button
                type="button"
                onClick={() => setExpanded((value) => !value)}
                className="rounded-lg p-2 text-slate-300 transition hover:bg-white/10 hover:text-white"
                aria-label={expanded ? "Reducir asistente" : "Expandir asistente"}
              >
                <Icon name={expanded ? "minimize" : "expand"} />
              </button>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-lg p-2 text-slate-300 transition hover:bg-white/10 hover:text-white"
                aria-label="Cerrar UKIP Assistant"
              >
                <Icon name="close" />
              </button>
            </div>
          </div>

          <div className="mt-3 rounded-xl border border-white/10 bg-white/8 px-3 py-2 text-xs text-slate-200">
            <div className="flex items-center gap-2 font-semibold text-emerald-300">
              <Icon name="check" className="h-3.5 w-3.5" />
              Conectado a {context.moduleLabel ?? "UKIP"}
            </div>
            <p className="mt-1 line-clamp-2 text-slate-300">{contextualSummary || "Contexto del dashboard activo"}</p>
          </div>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto bg-slate-950 px-4 py-4" role="log" aria-live="polite">
          {messages.map((message) => (
            <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[88%] ${message.role === "assistant" ? "flex gap-2" : ""}`}>
                {message.role === "assistant" && (
                  <span className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-violet-600 text-white shadow-[0_0_22px_rgb(124_58_237/0.45)]">
                    <Icon name="bot" />
                  </span>
                )}
                <div>
                  <div
                    className={`rounded-2xl px-4 py-3 text-sm leading-6 ${
                      message.role === "user"
                        ? "bg-violet-600 text-white shadow-[0_12px_30px_rgb(124_58_237/0.28)]"
                        : message.error
                          ? "border border-red-400/30 bg-red-500/10 text-red-100"
                          : "border border-white/10 bg-white/8 text-slate-100"
                    }`}
                  >
                    {message.pending ? (
                      <span className="inline-flex items-center gap-2">
                        <span className="flex gap-1">
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-violet-300" />
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-violet-300 [animation-delay:120ms]" />
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-violet-300 [animation-delay:240ms]" />
                        </span>
                        {message.content}
                      </span>
                    ) : (
                      <p className="whitespace-pre-wrap">{message.content}</p>
                    )}
                  </div>
                  <div className={`mt-1 flex flex-wrap items-center gap-1.5 text-[10px] ${message.role === "user" ? "justify-end text-violet-200" : "text-slate-400"}`}>
                    <span>{message.time}</span>
                    {message.mode && <span className="rounded-full bg-white/10 px-2 py-0.5">modo {message.mode}</span>}
                    {message.traceId && <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-emerald-200">trace #{message.traceId}</span>}
                  </div>
                  {!!message.sources?.length && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {message.sources.slice(0, 4).map((source, index) => (
                        <Link
                          key={`${source.entity_id ?? index}-${source.label ?? source.source ?? "source"}`}
                          href={source.entity_id ? `/entities/${source.entity_id}` : "/rag"}
                          className="rounded-full border border-violet-300/20 bg-violet-500/15 px-2 py-1 text-[10px] font-semibold text-violet-100 transition hover:border-violet-200 hover:bg-violet-500/25"
                        >
                          {source.label || source.source || `Fuente ${index + 1}`}
                        </Link>
                      ))}
                    </div>
                  )}
                  {!!message.tools?.length && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {message.tools.slice(0, 3).map((tool) => (
                        <span key={tool} className="rounded-full border border-cyan-300/20 bg-cyan-500/15 px-2 py-1 text-[10px] font-semibold text-cyan-100">
                          {tool}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}

          <div className="rounded-2xl border border-white/10 bg-white/6 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">Preguntas contextuales</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {quickPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => void askAssistant(prompt)}
                  disabled={isSending}
                  className="rounded-full border border-white/10 bg-white/8 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:border-violet-300/40 hover:bg-violet-500/20 disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/6 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">Acciones asistidas</p>
            <div className="mt-2 grid gap-2">
              {contextualActions.map((action) => (
                <button
                  key={action.id}
                  type="button"
                  onClick={() => requestAction(action)}
                  className={`flex items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left text-xs font-semibold transition ${actionTone(action)}`}
                >
                  <span className="min-w-0 truncate">{action.label}</span>
                  <Icon name="arrow" className="h-3.5 w-3.5 shrink-0" />
                </button>
              ))}
            </div>
          </div>
          {memory.length > 1 && (
            <div className="rounded-2xl border border-white/10 bg-white/6 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">Memoria de sesion</p>
              <div className="mt-2 space-y-1.5">
                {memory.slice(1, 4).map((item) => (
                  <Link
                    key={`${item.route}-${item.timestamp}`}
                    href={item.route}
                    className="block rounded-lg px-2 py-1.5 text-xs text-slate-300 transition hover:bg-white/8 hover:text-white"
                  >
                    <span className="font-semibold text-slate-100">{item.moduleLabel}</span>
                    <span className="ml-1 text-slate-400">{item.summary}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
          {pendingAction && (
            <div className="rounded-2xl border border-amber-300/25 bg-amber-500/12 p-3 text-xs text-amber-50">
              <p className="font-semibold">Confirmacion requerida</p>
              <p className="mt-1 text-amber-100/80">
                {pendingAction.confirmationLabel ?? "Esta accion puede cambiar el flujo de trabajo o abrir una operacion sensible."}
              </p>
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  onClick={() => void executeAction(pendingAction)}
                  disabled={executingActionId === pendingAction.id}
                  className="rounded-lg bg-amber-300 px-3 py-1.5 font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {executingActionId === pendingAction.id ? "Ejecutando..." : "Continuar"}
                </button>
                <button
                  type="button"
                  onClick={() => setPendingAction(null)}
                  className="rounded-lg border border-amber-200/25 px-3 py-1.5 font-semibold text-amber-50"
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}
        </div>

        <form onSubmit={submit} className="border-t border-white/10 bg-slate-900/96 p-3">
          <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-slate-950 px-3 py-2 focus-within:border-violet-300/50">
            <label htmlFor="ukip-assistant-input" className="sr-only">Pregunta para UKIP Assistant</label>
            <input
              id="ukip-assistant-input"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              disabled={isSending}
              placeholder="Escribe tu pregunta..."
              className="h-10 min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-500 disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={isSending || !input.trim()}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-600 text-white transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-45"
              aria-label="Enviar pregunta"
            >
              <Icon name="send" />
            </button>
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center gap-1.5">
                <Icon name="database" className="h-3.5 w-3.5" />
                Datos
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Icon name="chart" className="h-3.5 w-3.5" />
                Graficos
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Icon name="spark" className="h-3.5 w-3.5" />
                Insights
              </span>
            </div>
            <span className="inline-flex items-center gap-1.5 text-emerald-300">
              <Icon name="shield" className="h-3.5 w-3.5" />
              Seguro y privado
            </span>
          </div>
        </form>

        <footer className="flex flex-wrap items-center gap-3 border-t border-white/10 bg-slate-950 px-4 py-2 text-[11px] font-medium text-slate-300">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            RAG activo
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-cyan-400" />
            {connectedSources.toLocaleString()} fuentes conectadas
          </span>
          <span className="text-slate-500">Ultima actualizacion: {nowLabel()}</span>
        </footer>
      </div>
    </aside>
  );
}

export type { UKIPAssistantPanelProps };
