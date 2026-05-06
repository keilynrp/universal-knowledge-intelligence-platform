/* eslint-disable @next/next/no-img-element */
"use client";

import { useCallback, useEffect, useState } from "react";
import { useBranding } from "../contexts/BrandingContext";
import { useLanguage } from "../contexts/LanguageContext";
import type { ToastVariant } from "../components/ui";
import { apiFetch } from "@/lib/api";
import FaviconDropZone from "./FaviconDropZone";
import LogoDropZone from "./LogoDropZone";
import { BrandLockup } from "../components/ukip";

function getErrorMessage(error: unknown, fallback: string) {
    return error instanceof Error ? error.message : fallback;
}

export default function BrandingTab({ toast }: { toast: (msg: string, v?: ToastVariant) => void }) {
    const { branding, refreshBranding } = useBranding();
    const { t } = useLanguage();
    const tr = useCallback((key: string, fallback: string) => {
        const value = t(key);
        return value === key ? fallback : value;
    }, [t]);
    const inputClass = "h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white";

    const [form, setForm] = useState({
        platform_name: branding.platform_name,
        logo_url: branding.logo_url,
        favicon_url: branding.favicon_url,
        accent_color: branding.accent_color,
        footer_text: branding.footer_text,
    });
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        setForm({
            platform_name: branding.platform_name,
            logo_url: branding.logo_url,
            favicon_url: branding.favicon_url,
            accent_color: branding.accent_color,
            footer_text: branding.footer_text,
        });
    }, [branding]);

    const handleLogoUploaded = useCallback(async (url: string) => {
        setForm(prev => ({ ...prev, logo_url: url }));
        await refreshBranding();
        toast(t("settings.branding.toast.logo_updated"), "success");
    }, [refreshBranding, t, toast]);

    const handleLogoRemoved = useCallback(async () => {
        setForm(prev => ({ ...prev, logo_url: "" }));
        await refreshBranding();
        toast(t("settings.branding.toast.logo_removed"), "success");
    }, [refreshBranding, t, toast]);

    const handleFaviconUploaded = useCallback(async (url: string) => {
        setForm(prev => ({ ...prev, favicon_url: url }));
        await refreshBranding();
        toast(t("settings.branding.toast.favicon_updated"), "success");
    }, [refreshBranding, t, toast]);

    const handleFaviconRemoved = useCallback(async () => {
        setForm(prev => ({ ...prev, favicon_url: "" }));
        await refreshBranding();
        toast(t("settings.branding.toast.favicon_removed"), "success");
    }, [refreshBranding, t, toast]);

    const handleSave = async () => {
        setSaving(true);
        try {
            const r = await apiFetch("/branding/settings", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(form),
            });
            if (!r.ok) {
                const err = await r.json();
                throw new Error(err.detail || t("settings.branding.toast.save_failed"));
            }
            await refreshBranding();
            toast(t("settings.branding.toast.updated"), "success");
        } catch (error: unknown) {
            toast(getErrorMessage(error, t("settings.branding.toast.save_failed")), "error");
        } finally {
            setSaving(false);
        }
    };

    const fld = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
        setForm(prev => ({ ...prev, [k]: e.target.value }));

    const previewBranding = {
        platform_name: form.platform_name,
        logo_url: form.logo_url,
        favicon_url: form.favicon_url,
        accent_color: form.accent_color,
        footer_text: form.footer_text,
    };

    return (
        <div className="space-y-4">
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <div className="mb-5 rounded-xl border border-indigo-100 bg-indigo-50/70 px-4 py-3 text-sm text-indigo-900 dark:border-indigo-900/30 dark:bg-indigo-900/10 dark:text-indigo-100">
                    <p className="font-semibold">{tr("settings.branding.guidance_title", "Keep this workspace recognizable")}</p>
                    <p className="mt-1 text-xs text-indigo-800/80 dark:text-indigo-200/80">
                        {tr("settings.branding.guidance_body", "Name, logo, favicon, and accent color shape the identity users will see in navigation, browser tabs, and exported artifacts.")}
                    </p>
                </div>
                <h3 className="mb-4 text-base font-semibold text-gray-900 dark:text-white">{t("settings.branding.identity_title")}</h3>
                <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                    <div>
                        <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">{t("settings.branding.platform_name")}</label>
                        <input className={inputClass} value={form.platform_name} onChange={fld("platform_name")} placeholder="UKIP" />
                    </div>
                    <div>
                        <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">{t("settings.branding.accent_color")}</label>
                        <div className="flex items-center gap-2">
                            <input
                                type="color"
                                value={form.accent_color}
                                onChange={fld("accent_color")}
                                className="h-10 w-12 cursor-pointer rounded-lg border border-gray-200 bg-white p-1 dark:border-gray-700 dark:bg-gray-800"
                            />
                            <input className={inputClass} value={form.accent_color} onChange={fld("accent_color")} placeholder="#6366f1" />
                        </div>
                    </div>

                    <div className="sm:col-span-2">
                        <LogoDropZone
                            currentUrl={form.logo_url}
                            accentColor={form.accent_color}
                            onUploaded={handleLogoUploaded}
                            onRemove={handleLogoRemoved}
                        />
                    </div>

                    <div className="sm:col-span-2">
                        <FaviconDropZone
                            currentUrl={form.favicon_url}
                            onUploaded={handleFaviconUploaded}
                            onRemove={handleFaviconRemoved}
                        />
                    </div>

                    <div className="sm:col-span-2">
                        <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">{t("settings.branding.footer_text")}</label>
                        <input className={inputClass} value={form.footer_text} onChange={fld("footer_text")} placeholder={t("settings.branding.footer_placeholder")} />
                    </div>
                </div>
            </div>

            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">{t("common.preview")}</h3>
                <div className="mb-4 flex flex-wrap gap-2">
                    <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${form.logo_url ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300" : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300"}`}>
                        {form.logo_url ? tr("settings.branding.status.logo_ready", "Logo ready") : tr("settings.branding.status.logo_missing", "Logo missing")}
                    </span>
                    <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${form.favicon_url ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300" : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300"}`}>
                        {form.favicon_url ? tr("settings.branding.status.favicon_ready", "Favicon ready") : tr("settings.branding.status.favicon_missing", "Favicon missing")}
                    </span>
                </div>
                <div className="flex items-center gap-3 rounded-xl border border-gray-100 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-gray-800/50">
                    <BrandLockup branding={previewBranding} size="sm" className="max-w-full" />
                </div>
                <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">
                    {tr("settings.branding.preview_help", "This preview reflects the changes currently in the form. Save when you are ready to apply them across the workspace.")}
                </p>
            </div>

            <button
                onClick={handleSave}
                disabled={saving}
                className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
            >
                {saving ? t("settings.branding.saving") : t("settings.branding.save")}
            </button>
        </div>
    );
}
