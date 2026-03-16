"use client";

import { useState, useRef, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { Badge } from "./ui";
import { useDomain } from "../contexts/DomainContext";
import { useLanguage } from "../contexts/LanguageContext";

interface ToolCall {
    tool: string;
    params: Record<string, any>;
    result: any;
}

interface Message {
    role: "user" | "assistant" | "system";
    content: string;
    sources?: any[];
    provider?: string;
    model?: string;
    isLoading?: boolean;
    toolsUsed?: ToolCall[];
    iterations?: number;
    agentic?: boolean;
}

export default function RAGChatInterface() {
    const { t } = useLanguage();
    const { activeDomainId } = useDomain();
    const [messages, setMessages] = useState<Message[]>([
        {
            role: "system",
            content: "🧠 **Semantic Assistant** — Ask anything about your knowledge base. I'll retrieve the most relevant entities and generate a grounded answer.",
        }
    ]);
    const [input, setInput] = useState("");
    const [isQuerying, setIsQuerying] = useState(false);
    const [isIndexing, setIsIndexing] = useState(false);
    const [indexStats, setIndexStats] = useState<{ total_indexed: number } | null>(null);
    const [useContext, setUseContext] = useState(false);
    const [useTools, setUseTools] = useState(false);
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    useEffect(() => {
        fetchStats();
    }, []);

    async function fetchStats() {
        try {
            const res = await apiFetch("/rag/stats");
            if (res.ok) setIndexStats(await res.json());
        } catch { }
    }

    async function handleIndex() {
        setIsIndexing(true);
        try {
            const res = await apiFetch("/rag/index", { method: "POST" });
            if (!res.ok) throw new Error("Indexing failed");
            const data = await res.json();
            setMessages(prev => [...prev, {
                role: "assistant",
                content: `✅ ${t('rag.index.success')} ${data.indexed} items embedded and stored in the Vector Database. ${data.skipped || 0} entities skipped (insufficient data). You can now ask questions about your knowledge hub.`
            }]);
            fetchStats();
        } catch (e) {
            setMessages(prev => [...prev, { role: "assistant", content: "❌ Indexing failed. Make sure an AI provider is configured and active." }]);
        } finally {
            setIsIndexing(false);
        }
    }

    async function handleSend(e: React.FormEvent) {
        e.preventDefault();
        const query = input.trim();
        if (!query || isQuerying) return;

        setInput("");
        const userMessage: Message = { role: "user", content: query };
        const loadingMessage: Message = { role: "assistant", content: "", isLoading: true };
        setMessages(prev => [...prev, userMessage, loadingMessage]);
        setIsQuerying(true);

        try {
            const res = await apiFetch("/rag/query", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    question: query,
                    top_k: 5,
                    use_context: useContext,
                    domain_id: useContext ? (activeDomainId || "default") : undefined,
                    use_tools: useTools,
                })
            });
            const data = await res.json();

            setMessages(prev => {
                const next = [...prev];
                next[next.length - 1] = {
                    role: "assistant",
                    content: data.error
                        ? `⚠️ ${data.error}`
                        : data.answer,
                    sources: data.sources,
                    provider: data.provider,
                    model: data.model,
                    toolsUsed: data.tools_used,
                    iterations: data.iterations,
                    agentic: data.agentic,
                };
                return next;
            });
        } catch {
            setMessages(prev => {
                const next = [...prev];
                next[next.length - 1] = { role: "assistant", content: "❌ Failed to connect to the RAG engine. Make sure the backend is running." };
                return next;
            });
        } finally {
            setIsQuerying(false);
        }
    }

    const formatSourceLabel = (src: any) => {
        const name = src.metadata?.entity_name || src.id;
        const score = Math.round(src.similarity_score * 100);
        return `${name} (${score}%)`;
    };

    return (
        <div className="flex h-[calc(100vh-160px)] sm:h-[calc(100vh-200px)] flex-col rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900 overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3.5 dark:border-gray-800">
                <div className="flex items-center gap-2.5">
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-100 text-lg dark:bg-indigo-500/20">🌌</span>
                    <div>
                        <p className="text-sm font-bold text-gray-900 dark:text-white">Semantic AI Assistant</p>
                        <p className="text-xs text-gray-500">UKIP Semantic RAG — Grounded by repository</p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    {indexStats !== null && (
                        <Badge variant={indexStats.total_indexed > 0 ? "success" : "warning"} dot>
                            {indexStats.total_indexed > 0 ? `${indexStats.total_indexed} entities indexed` : "Not indexed yet"}
                        </Badge>
                    )}
                    <button
                        onClick={handleIndex}
                        disabled={isIndexing}
                        className="flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 transition-colors hover:bg-indigo-100 disabled:opacity-60 dark:border-indigo-500/20 dark:bg-indigo-500/10 dark:text-indigo-400"
                    >
                        {isIndexing ? (
                            <svg className="h-3 w-3 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                        ) : "⚡"}
                        {isIndexing ? t('rag.index.rebuilding') : t('rag.index.rebuild')}
                    </button>
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-3 py-4 sm:px-5 space-y-4" role="log" aria-label="Conversation" aria-live="polite">
                {messages.map((msg, i) => (
                    <div key={i} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                        {msg.role !== "user" && (
                            <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-sm dark:bg-indigo-500/20">
                                {msg.role === "system" ? "🧠" : "✨"}
                            </div>
                        )}
                        <div className={`max-w-[90%] sm:max-w-[75%] space-y-2 ${msg.role === "user" ? "items-end" : ""}`}>
                            <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${msg.role === "user"
                                ? "bg-indigo-600 text-white"
                                : msg.role === "system"
                                    ? "bg-gray-50 text-gray-600 dark:bg-gray-800 dark:text-gray-400 border border-dashed border-gray-200 dark:border-gray-700"
                                    : "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"
                                }`}>
                                {msg.isLoading ? (
                                    <div className="flex items-center gap-2 py-0.5">
                                        <div className="flex gap-1">
                                            <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:0ms]" />
                                            <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:150ms]" />
                                            <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:300ms]" />
                                        </div>
                                        <span className="text-xs text-gray-500">Analyzing knowledge & generating response...</span>
                                    </div>
                                ) : (
                                    <p className="whitespace-pre-wrap">{msg.content}</p>
                                )}
                            </div>

                            {/* Source pills */}
                            {msg.sources && msg.sources.length > 0 && (
                                <div className="flex flex-wrap gap-1.5">
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Sources:</span>
                                    {msg.sources.map((src, j) => (
                                        <span key={j} className="rounded-full border border-indigo-100 bg-white px-2 py-0.5 text-[10px] font-medium text-indigo-600 dark:border-indigo-500/20 dark:bg-gray-800 dark:text-indigo-400">
                                            {formatSourceLabel(src)}
                                        </span>
                                    ))}
                                    {msg.provider && (
                                        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] text-gray-500 dark:bg-gray-700 dark:text-gray-400">
                                            via {msg.provider} / {msg.model}
                                        </span>
                                    )}
                                    {msg.agentic && msg.iterations !== undefined && (
                                        <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-400">
                                            agentic · {msg.iterations} iter
                                        </span>
                                    )}
                                </div>
                            )}

                            {/* Tool calls accordion */}
                            {msg.toolsUsed && msg.toolsUsed.length > 0 && (
                                <details className="mt-1 rounded-lg border border-amber-100 bg-amber-50/60 px-3 py-2 dark:border-amber-500/20 dark:bg-amber-500/5">
                                    <summary className="cursor-pointer text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400">
                                        {msg.toolsUsed.length} tool call{msg.toolsUsed.length > 1 ? "s" : ""} made
                                    </summary>
                                    <div className="mt-2 space-y-1.5">
                                        {msg.toolsUsed.map((tc, j) => (
                                            <div key={j} className="rounded border border-amber-100 bg-white px-2 py-1.5 text-[10px] dark:border-amber-500/20 dark:bg-gray-800">
                                                <span className="font-mono font-bold text-amber-700 dark:text-amber-300">{tc.tool}</span>
                                                {Object.keys(tc.params).length > 0 && (
                                                    <span className="ml-1 text-gray-400">({JSON.stringify(tc.params)})</span>
                                                )}
                                                <div className="mt-0.5 truncate text-gray-500 dark:text-gray-400">
                                                    → {typeof tc.result === "object" ? JSON.stringify(tc.result).slice(0, 120) : String(tc.result)}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </details>
                            )}
                        </div>
                    </div>
                ))}
                <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="border-t border-gray-100 p-4 dark:border-gray-800">
                {/* Toggles */}
                <div className="mb-2 flex flex-wrap items-center gap-2">
                    <button
                        type="button"
                        onClick={() => setUseContext((v) => !v)}
                        className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors ${
                            useContext
                                ? "border-violet-300 bg-violet-50 text-violet-700 dark:border-violet-500/40 dark:bg-violet-500/10 dark:text-violet-300"
                                : "border-gray-200 bg-gray-50 text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
                        }`}
                    >
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1 1 .03 2.798-1.414 2.798H4.212c-1.444 0-2.414-1.798-1.414-2.798L4.2 15.3" />
                        </svg>
                        {useContext ? "Context ON" : "Context OFF"}
                    </button>
                    <button
                        type="button"
                        onClick={() => setUseTools((v) => !v)}
                        title="Agentic mode: LLM can call analytics tools mid-reasoning"
                        className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors ${
                            useTools
                                ? "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-300"
                                : "border-gray-200 bg-gray-50 text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
                        }`}
                    >
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l5.653-4.655m0 0l-2.03 1.208a3.562 3.562 0 01-.766 1.208" />
                        </svg>
                        {useTools ? "Agentic ON" : "Agentic OFF"}
                    </button>
                    {useContext && (
                        <span className="text-xs text-gray-400 dark:text-gray-500">
                            Domain context: {activeDomainId || "default"}
                        </span>
                    )}
                    {useTools && (
                        <span className="text-xs text-amber-500 dark:text-amber-400">
                            LLM may call analytics tools autonomously
                        </span>
                    )}
                </div>
                <form onSubmit={handleSend} className="flex gap-2">
                    <label htmlFor="rag-input" className="sr-only">Ask a question about your knowledge hub</label>
                    <input
                        id="rag-input"
                        type="text"
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        disabled={isQuerying}
                        placeholder="Ask something about your hub..."
                        className="h-11 flex-1 rounded-xl border border-gray-200 bg-gray-50 px-4 text-sm outline-none transition-colors focus:border-indigo-400 focus:bg-white focus:ring-1 focus:ring-indigo-400 disabled:opacity-60 dark:border-gray-700 dark:bg-gray-800 dark:text-white dark:focus:bg-gray-800"
                    />
                    <button
                        type="submit"
                        disabled={isQuerying || !input.trim()}
                        aria-label={isQuerying ? "Sending…" : "Send message"}
                        className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-600 text-white transition-colors hover:bg-indigo-700 disabled:opacity-40"
                    >
                        {isQuerying ? (
                            <svg className="h-4 w-4 animate-spin" aria-hidden="true" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                        ) : (
                            <svg className="h-4 w-4 rotate-90" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                            </svg>
                        )}
                    </button>
                </form>
            </div>
        </div>
    );
}
