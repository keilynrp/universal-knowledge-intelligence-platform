"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { useToast } from "../components/ui";

interface AIIntegration {
    id: number;
    provider_name: string;
    base_url: string | null;
    api_key: string | null;
    model_name: string | null;
    is_active: boolean;
}

const AI_PROVIDERS: Record<string, { label: string; color: string; bgColor: string; icon: string; requiresBaseUrl: boolean; tag: string }> = {
    openai: { label: "OpenAI", color: "text-emerald-700 dark:text-emerald-400", bgColor: "bg-emerald-50 dark:bg-emerald-500/10", icon: "🤖", requiresBaseUrl: false, tag: "Cloud" },
    anthropic: { label: "Anthropic (Claude)", color: "text-orange-700 dark:text-orange-400", bgColor: "bg-orange-50 dark:bg-orange-500/10", icon: "🧠", requiresBaseUrl: false, tag: "Cloud" },
    deepseek: { label: "DeepSeek", color: "text-blue-700 dark:text-blue-400", bgColor: "bg-blue-50 dark:bg-blue-500/10", icon: "🐋", requiresBaseUrl: false, tag: "Cloud" },
    xai: { label: "xAI (Grok)", color: "text-zinc-700 dark:text-zinc-400", bgColor: "bg-zinc-100 dark:bg-zinc-500/20", icon: "✖", requiresBaseUrl: false, tag: "Cloud" },
    google: { label: "Google (Gemini)", color: "text-indigo-700 dark:text-indigo-400", bgColor: "bg-indigo-50 dark:bg-indigo-500/10", icon: "✨", requiresBaseUrl: false, tag: "Cloud" },
    local: { label: "Local LLM (Ollama / VLLM)", color: "text-purple-700 dark:text-purple-400", bgColor: "bg-purple-50 dark:bg-purple-500/10", icon: "💻", requiresBaseUrl: true, tag: "Local" },
};

export default function AIIntegrations() {
    const { toast } = useToast();
    const [integrations, setIntegrations] = useState<AIIntegration[]>([]);
    const [loading, setLoading] = useState(true);

    // Form State
    const [showForm, setShowForm] = useState(false);
    const [saving, setSaving] = useState(false);
    const [formData, setFormData] = useState({
        provider_name: "openai",
        base_url: "",
        api_key: "",
        model_name: ""
    });
    const [editingId, setEditingId] = useState<number | null>(null);

    async function fetchIntegrations() {
        try {
            const res = await apiFetch("/ai-integrations");
            if (res.ok) setIntegrations(await res.json());
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => { fetchIntegrations(); }, []);

    function resetForm() {
        setFormData({ provider_name: "openai", base_url: "", api_key: "", model_name: "" });
        setEditingId(null);
        setShowForm(false);
    }

    function openEdit(ai: AIIntegration) {
        setFormData({
            provider_name: ai.provider_name,
            base_url: ai.base_url || "",
            api_key: "", // Don't expose old keys visually
            model_name: ai.model_name || ""
        });
        setEditingId(ai.id);
        setShowForm(true);
    }

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setSaving(true);
        try {
            const payload: any = { ...formData };
            if (editingId && !payload.api_key) delete payload.api_key; // Keep old key if empty

            const path = editingId ? `/ai-integrations/${editingId}` : "/ai-integrations";
            const method = editingId ? "PUT" : "POST";

            const res = await apiFetch(path, {
                method,
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const err = await res.json();
                toast(err.detail || "Error saving integration", "error");
                return;
            }

            resetForm();
            fetchIntegrations();
        } catch (error) {
            console.error(error);
        } finally {
            setSaving(false);
        }
    }

    async function handleActivate(id: number) {
        try {
            await apiFetch(`/ai-integrations/${id}/activate`, { method: "POST" });
            fetchIntegrations();
        } catch (error) {
            console.error("Error activating:", error);
        }
    }

    async function handleDelete(id: number) {
        if (!confirm("Are you sure you want to delete this RAG Integration?")) return;
        try {
            await apiFetch(`/ai-integrations/${id}`, { method: "DELETE" });
            fetchIntegrations();
        } catch (error) {
            console.error("Error deleting:", error);
        }
    }

    const inputClass = "h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white";
    const labelClass = "block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1";

    const selectedMeta = AI_PROVIDERS[formData.provider_name];

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold text-gray-900 dark:text-white">Semantic AI Vectors & RAG Providers</h2>
                    <p className="text-sm text-gray-500">Configure language models for predictive context analysis and semantic extraction (Phase 5).</p>
                </div>
                {!showForm && (
                    <button
                        onClick={() => setShowForm(true)}
                        className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
                    >
                        Configure Model Provider
                    </button>
                )}
            </div>

            {showForm && (
                <div className="rounded-2xl border border-indigo-200 bg-white p-6 dark:border-indigo-500/20 dark:bg-gray-900">
                    <h3 className="mb-4 text-lg font-bold text-gray-900 dark:text-white">
                        {editingId ? "Edit AI RAG Provider" : "Add AI RAG Provider"}
                    </h3>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                            <div>
                                <label className={labelClass}>Provider Ecosystem</label>
                                <select
                                    className={inputClass}
                                    value={formData.provider_name}
                                    onChange={e => setFormData({ ...formData, provider_name: e.target.value })}
                                    disabled={!!editingId}
                                >
                                    {Object.entries(AI_PROVIDERS).map(([key, meta]) => (
                                        <option key={key} value={key}>{meta.label} - {meta.tag}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className={labelClass}>Default Model Name</label>
                                <input
                                    type="text"
                                    className={inputClass}
                                    placeholder="e.g. gpt-4o, claude-3.5-sonnet, llama-3"
                                    value={formData.model_name}
                                    onChange={e => setFormData({ ...formData, model_name: e.target.value })}
                                />
                            </div>
                        </div>

                        {selectedMeta?.requiresBaseUrl && (
                            <div>
                                <label className={labelClass}>Local Base URL</label>
                                <input
                                    type="url"
                                    className={inputClass}
                                    placeholder="http://localhost:11434/api"
                                    required
                                    value={formData.base_url}
                                    onChange={e => setFormData({ ...formData, base_url: e.target.value })}
                                />
                            </div>
                        )}

                        <div>
                            <label className={labelClass}>
                                API Key {selectedMeta?.tag === "Local" ? "(Optional for Local)" : "(Required for Cloud)"}
                            </label>
                            <input
                                type="password"
                                className={inputClass}
                                placeholder={editingId ? "Leave blank to keep current key" : "sk-..."}
                                required={selectedMeta?.tag === "Cloud" && !editingId}
                                value={formData.api_key}
                                onChange={e => setFormData({ ...formData, api_key: e.target.value })}
                            />
                        </div>

                        <div className="flex gap-3 pt-2">
                            <button type="submit" disabled={saving} className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-700">
                                {saving ? "Saving..." : "Save Provider"}
                            </button>
                            <button type="button" onClick={resetForm} className="rounded-lg px-4 py-2.5 text-sm font-medium text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800">
                                Cancel
                            </button>
                        </div>
                    </form>
                </div>
            )}

            {!loading && integrations.length > 0 && (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {integrations.map(ai => {
                        const meta = AI_PROVIDERS[ai.provider_name] || AI_PROVIDERS.local;
                        return (
                            <div key={ai.id} className={`group rounded-2xl border bg-white p-5 dark:bg-gray-900 ${ai.is_active ? 'border-indigo-400 dark:border-indigo-500/50 ring-2 ring-indigo-50 dark:ring-indigo-500/10' : 'border-gray-200 dark:border-gray-800'}`}>
                                <div className="flex items-start justify-between mb-4">
                                    <div className="flex items-center gap-3">
                                        <div className={`flex h-10 w-10 items-center justify-center rounded-xl text-lg ${meta.bgColor} ${meta.color}`}>
                                            {meta.icon}
                                        </div>
                                        <div>
                                            <h3 className="font-bold text-gray-900 dark:text-white capitalize">{ai.provider_name}</h3>
                                            <span className="text-xs font-semibold text-gray-500">{meta.tag} Context</span>
                                        </div>
                                    </div>
                                    {ai.is_active ? (
                                        <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-bold text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-400">
                                            Active Core
                                        </span>
                                    ) : null}
                                </div>

                                <div className="space-y-1.5 text-sm mb-5">
                                    <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                                        <span className="font-medium">Model:</span> {ai.model_name || 'System Default'}
                                    </div>
                                    {ai.base_url && (
                                        <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400 truncate">
                                            <span className="font-medium">URL:</span> {ai.base_url}
                                        </div>
                                    )}
                                    <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                                        <span className="font-medium">API Key:</span> {ai.api_key ? "•••• Key Configured" : "None"}
                                    </div>
                                </div>

                                <div className="flex gap-2 border-t border-gray-100 pt-3 dark:border-gray-800">
                                    {!ai.is_active && (
                                        <button onClick={() => handleActivate(ai.id)} className="flex-1 rounded-lg bg-gray-50 py-1.5 text-xs font-semibold text-gray-700 hover:bg-indigo-50 hover:text-indigo-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-indigo-500/10 dark:hover:text-indigo-400">
                                            Make Active
                                        </button>
                                    )}
                                    <button onClick={() => openEdit(ai)} className="flex-1 rounded-lg px-2 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800">
                                        Edit
                                    </button>
                                    <button onClick={() => handleDelete(ai.id)} className="flex-1 rounded-lg px-2 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10">
                                        Remove
                                    </button>
                                </div>
                            </div>
                        )
                    })}
                </div>
            )}

            {!loading && integrations.length === 0 && !showForm && (
                <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 bg-gray-50/50 py-12 dark:border-gray-700 dark:bg-gray-800/20">
                    <span className="text-4xl mb-3">🧩</span>
                    <p className="text-gray-500 font-medium">No Sematic Providers currently configured.</p>
                    <p className="text-gray-400 text-sm">Add frontier models or run inferences locally to unlock Agent RAG.</p>
                </div>
            )}
        </div>
    )
}
