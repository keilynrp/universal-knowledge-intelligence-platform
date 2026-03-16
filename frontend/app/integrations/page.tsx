"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import AIIntegrations from "./AIIntegrations";
import { apiFetch } from "@/lib/api";
import { PageHeader, TabNav, Badge, useToast } from "../components/ui";
import { useLanguage } from "../contexts/LanguageContext";

interface StoreConnection {
    id: number;
    name: string;
    platform: string;
    base_url: string;
    is_active: boolean;
    last_sync_at: string | null;
    created_at: string | null;
    entity_count: number;
    sync_direction: string;
    notes: string | null;
}

const PLATFORM_META: Record<string, { label: string; color: string; bgColor: string; icon: string }> = {
    woocommerce: { label: "WooCommerce", color: "text-purple-700 dark:text-purple-400", bgColor: "bg-purple-50 dark:bg-purple-500/10", icon: "W" },
    shopify: { label: "Shopify", color: "text-green-700 dark:text-green-400", bgColor: "bg-green-50 dark:bg-green-500/10", icon: "S" },
    bsale: { label: "Bsale", color: "text-blue-700 dark:text-blue-400", bgColor: "bg-blue-50 dark:bg-blue-500/10", icon: "B" },
    custom: { label: "Custom API", color: "text-amber-700 dark:text-amber-400", bgColor: "bg-amber-50 dark:bg-amber-500/10", icon: "⚙" },
};

const DIRECTION_LABELS: Record<string, string> = {
    pull: "← Pull only",
    push: "Push only →",
    bidirectional: "↔ Bidirectional",
};

export default function IntegrationsPage() {
    const { toast } = useToast();
    const { t } = useLanguage();
    const [activeTab, setActiveTab] = useState<"stores" | "ai">("stores");
    const [stores, setStores] = useState<StoreConnection[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [editingStore, setEditingStore] = useState<StoreConnection | null>(null);
    const [saving, setSaving] = useState(false);

    // Form state
    const [formData, setFormData] = useState({
        name: "",
        platform: "woocommerce",
        base_url: "",
        api_key: "",
        api_secret: "",
        access_token: "",
        sync_direction: "bidirectional",
        notes: "",
    });

    async function fetchStores() {
        try {
            const res = await apiFetch("/stores");
            if (!res.ok) throw new Error("Failed");
            const data = await res.json();
            setStores(data);
        } catch {
            toast("Failed to load store connections", "error");
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => { fetchStores(); }, []);

    function resetForm() {
        setFormData({ name: "", platform: "woocommerce", base_url: "", api_key: "", api_secret: "", access_token: "", sync_direction: "bidirectional", notes: "" });
        setEditingStore(null);
        setShowForm(false);
    }

    function openEditForm(store: StoreConnection) {
        setEditingStore(store);
        setFormData({
            name: store.name,
            platform: store.platform,
            base_url: store.base_url,
            api_key: "",
            api_secret: "",
            access_token: "",
            sync_direction: store.sync_direction,
            notes: store.notes || "",
        });
        setShowForm(true);
    }

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setSaving(true);

        try {
            const payload: Record<string, any> = { ...formData };
            // Don't send empty credential fields on update
            if (editingStore) {
                if (!payload.api_key) delete payload.api_key;
                if (!payload.api_secret) delete payload.api_secret;
                if (!payload.access_token) delete payload.access_token;
            }

            const path = editingStore ? `/stores/${editingStore.id}` : "/stores";
            const method = editingStore ? "PUT" : "POST";

            const res = await apiFetch(path, {
                method,
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                const err = await res.json();
                toast(err.detail || "Error saving store", "error");
                return;
            }

            toast(editingStore ? "Store updated" : "Store connected", "success");
            resetForm();
            fetchStores();
        } catch {
            toast("Failed to save store connection", "error");
        } finally {
            setSaving(false);
        }
    }

    async function handleDelete(store: StoreConnection) {
        if (!confirm(`Delete "${store.name}" and all its sync data?`)) return;
        try {
            const res = await apiFetch(`/stores/${store.id}`, { method: "DELETE" });
            if (!res.ok) throw new Error();
            toast(`"${store.name}" deleted`, "success");
            fetchStores();
        } catch {
            toast("Failed to delete store", "error");
        }
    }

    async function handleToggle(store: StoreConnection) {
        try {
            const res = await apiFetch(`/stores/${store.id}/toggle`, { method: "POST" });
            if (!res.ok) throw new Error();
            fetchStores();
        } catch {
            toast("Failed to update store status", "error");
        }
    }

    const inputClass = "h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white";
    const labelClass = "block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1";

    return (
        <div className="space-y-6">
            <PageHeader
                breadcrumbs={[{ label: "Home", href: "/" }, { label: t('page.integrations.breadcrumb') }]}
                title={t('page.integrations.title')}
                description="Connect external e-commerce stores or configure predictive Semantic Generative AI (RAG)."
            />
            <TabNav
                tabs={[
                    { id: "stores", label: t('page.integrations.tab_stores') },
                    { id: "ai", label: t('page.integrations.tab_ai') },
                ]}
                activeTab={activeTab}
                onTabChange={(id) => setActiveTab(id as "stores" | "ai")}
            />

            {activeTab === "ai" && <AIIntegrations />}

            {activeTab === "stores" && (
                <div className="space-y-6">
                    <div className="flex justify-end">
                        <button
                            onClick={() => { resetForm(); setShowForm(true); }}
                            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                        >
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                            </svg>
                            {t('page.integrations.add_store_button')}
                        </button>
                    </div>

                    {/* Create / Edit Form */}
                    {showForm && (
                        <div className="rounded-2xl border border-blue-200 bg-white p-6 dark:border-blue-500/20 dark:bg-gray-900">
                            <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
                                {editingStore ? `Edit: ${editingStore.name}` : t('page.integrations.new_store_title')}
                            </h2>
                            <form onSubmit={handleSubmit} className="space-y-4">
                                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                                    <div>
                                        <label className={labelClass}>{t('page.integrations.store_name_label')} *</label>
                                        <input
                                            type="text"
                                            required
                                            className={inputClass}
                                            placeholder="e.g. Mi Tienda Principal"
                                            value={formData.name}
                                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                        />
                                    </div>
                                    <div>
                                        <label className={labelClass}>{t('page.integrations.platform_label')} *</label>
                                        <select
                                            className={inputClass}
                                            value={formData.platform}
                                            onChange={(e) => setFormData({ ...formData, platform: e.target.value })}
                                        >
                                            <option value="woocommerce">WooCommerce</option>
                                            <option value="shopify">Shopify</option>
                                            <option value="bsale">Bsale</option>
                                            <option value="custom">Custom API</option>
                                        </select>
                                    </div>
                                </div>

                                <div>
                                    <label className={labelClass}>{t('page.integrations.base_url_label')} *</label>
                                    <input
                                        type="url"
                                        required
                                        className={inputClass}
                                        placeholder="https://mitienda.com"
                                        value={formData.base_url}
                                        onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                                    />
                                    <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                                        {formData.platform === "woocommerce" && "WordPress site URL (e.g. https://mitienda.com)"}
                                        {formData.platform === "shopify" && "Shopify store URL (e.g. https://mitienda.myshopify.com)"}
                                        {formData.platform === "bsale" && "Bsale API base URL (e.g. https://api.bsale.io)"}
                                        {formData.platform === "custom" && "Your custom API base URL"}
                                    </p>
                                </div>

                                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                                    <div>
                                        <label className={labelClass}>{t('page.integrations.api_key_label')}</label>
                                        <input
                                            type="password"
                                            className={inputClass}
                                            placeholder={editingStore ? "Leave blank to keep current" : "Consumer key / API key"}
                                            value={formData.api_key}
                                            onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                                        />
                                    </div>
                                    <div>
                                        <label className={labelClass}>API Secret</label>
                                        <input
                                            type="password"
                                            className={inputClass}
                                            placeholder={editingStore ? "Leave blank to keep current" : "Consumer secret"}
                                            value={formData.api_secret}
                                            onChange={(e) => setFormData({ ...formData, api_secret: e.target.value })}
                                        />
                                    </div>
                                    <div>
                                        <label className={labelClass}>Access Token</label>
                                        <input
                                            type="password"
                                            className={inputClass}
                                            placeholder={editingStore ? "Leave blank to keep current" : "OAuth access token"}
                                            value={formData.access_token}
                                            onChange={(e) => setFormData({ ...formData, access_token: e.target.value })}
                                        />
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                                    <div>
                                        <label className={labelClass}>{t('page.integrations.sync_direction_label')}</label>
                                        <select
                                            className={inputClass}
                                            value={formData.sync_direction}
                                            onChange={(e) => setFormData({ ...formData, sync_direction: e.target.value })}
                                        >
                                            <option value="bidirectional">↔ Bidirectional</option>
                                            <option value="pull">← Pull only (Store → DB)</option>
                                            <option value="push">Push only (DB → Store) →</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label className={labelClass}>{t('page.integrations.notes_label')}</label>
                                        <input
                                            type="text"
                                            className={inputClass}
                                            placeholder="Optional notes about this connection"
                                            value={formData.notes}
                                            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                                        />
                                    </div>
                                </div>

                                <div className="flex items-center gap-3 pt-2">
                                    <button
                                        type="submit"
                                        disabled={saving}
                                        className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                                    >
                                        {saving ? (
                                            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                            </svg>
                                        ) : null}
                                        {editingStore ? t('page.integrations.update_button') : t('page.integrations.save_button')}
                                    </button>
                                    <button
                                        type="button"
                                        onClick={resetForm}
                                        className="rounded-lg px-4 py-2.5 text-sm font-medium text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
                                    >
                                        Cancel
                                    </button>
                                </div>
                            </form>
                        </div>
                    )}

                    {/* Store Cards */}
                    {loading ? (
                        <div className="flex h-64 items-center justify-center">
                            <svg className="h-8 w-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                        </div>
                    ) : stores.length === 0 && !showForm ? (
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 bg-white py-16 dark:border-gray-700 dark:bg-gray-900">
                            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-blue-50 dark:bg-blue-500/10">
                                <svg className="h-8 w-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.86-9.86a4.5 4.5 0 00-6.364 6.364L12 10.5" />
                                </svg>
                            </div>
                            <h3 className="mb-1 text-lg font-semibold text-gray-900 dark:text-white">{t('page.integrations.empty_title')}</h3>
                            <p className="mb-4 max-w-sm text-center text-sm text-gray-500 dark:text-gray-400">
                                Connect your WooCommerce, Shopify, Bsale, or custom API stores to sync and manage your product catalog.
                            </p>
                            <button
                                onClick={() => { resetForm(); setShowForm(true); }}
                                className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                            >
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                </svg>
                                {t('page.integrations.empty_button')}
                            </button>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
                            {stores.map((store) => {
                                const meta = PLATFORM_META[store.platform] || PLATFORM_META.custom;
                                return (
                                    <div
                                        key={store.id}
                                        className={`group relative rounded-2xl border bg-white p-5 shadow-sm transition-all hover:shadow-md dark:bg-gray-900 ${store.is_active
                                            ? "border-gray-200 dark:border-gray-800"
                                            : "border-gray-200/60 opacity-60 dark:border-gray-800/60"
                                            }`}
                                    >
                                        {/* Header */}
                                        <div className="mb-4 flex items-start justify-between">
                                            <div className="flex items-center gap-3">
                                                <div className={`flex h-10 w-10 items-center justify-center rounded-xl text-lg font-bold ${meta.bgColor} ${meta.color}`}>
                                                    {meta.icon}
                                                </div>
                                                <div>
                                                    <h3 className="font-semibold text-gray-900 dark:text-white">{store.name}</h3>
                                                    <span className={`text-xs font-medium ${meta.color}`}>{meta.label}</span>
                                                </div>
                                            </div>
                                            <Badge variant={store.is_active ? "success" : "default"} dot>
                                                {store.is_active ? "Active" : "Inactive"}
                                            </Badge>
                                        </div>

                                        {/* Info */}
                                        <div className="mb-4 space-y-2 text-sm">
                                            <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                                                <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                                                </svg>
                                                <span className="truncate">{store.base_url}</span>
                                            </div>
                                            <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                                                <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                                                </svg>
                                                <span>{DIRECTION_LABELS[store.sync_direction] || store.sync_direction}</span>
                                            </div>
                                            <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                                                <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                                                </svg>
                                                <span>{store.entity_count.toLocaleString()} mapped products</span>
                                            </div>
                                            {store.notes && (
                                                <div className="flex items-start gap-2 text-gray-400 dark:text-gray-500">
                                                    <svg className="mt-0.5 h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                                                    </svg>
                                                    <span className="text-xs">{store.notes}</span>
                                                </div>
                                            )}
                                        </div>

                                        {/* Actions */}
                                        <div className="flex items-center gap-2 border-t border-gray-100 pt-3 dark:border-gray-800">
                                            <Link
                                                href={`/integrations/${store.id}`}
                                                className="flex-1 rounded-lg px-3 py-1.5 text-center text-xs font-medium text-blue-600 transition-colors hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-500/10"
                                            >
                                                {t('page.integrations.details_button')}
                                            </Link>
                                            <button
                                                onClick={() => openEditForm(store)}
                                                className="flex-1 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
                                            >
                                                {t('page.integrations.edit_button')}
                                            </button>
                                            <button
                                                onClick={() => handleToggle(store)}
                                                className={`flex-1 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${store.is_active
                                                    ? "text-amber-600 hover:bg-amber-50 dark:text-amber-400 dark:hover:bg-amber-500/10"
                                                    : "text-green-600 hover:bg-green-50 dark:text-green-400 dark:hover:bg-green-500/10"
                                                    }`}
                                            >
                                                {store.is_active ? t('page.integrations.deactivate_button') : t('page.integrations.activate_button')}
                                            </button>
                                            <button
                                                onClick={() => handleDelete(store)}
                                                className="flex-1 rounded-lg px-3 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
                                            >
                                                Delete
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
