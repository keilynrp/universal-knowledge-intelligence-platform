"use client";

import { useEffect, useState } from "react";
import { useLanguage } from "../contexts/LanguageContext";
import type { ToastVariant } from "../components/ui";
import { apiFetch } from "@/lib/api";

type AuthSettingsForm = {
    sso_enabled: boolean;
    sso_login_button_visible: boolean;
    sso_provider_label: string;
    sso_auto_provision: boolean;
    sso_default_role: "viewer" | "editor" | "admin";
    sso_allowed_domains: string;
    sso_provider_configured: boolean;
};

function getErrorMessage(error: unknown, fallback: string) {
    return error instanceof Error ? error.message : fallback;
}

export default function AuthSettingsTab({
    toast,
}: {
    toast: (msg: string, v?: ToastVariant) => void;
}) {
    const { t } = useLanguage();
    const inputClass = "h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white";
    const [form, setForm] = useState<AuthSettingsForm>({
        sso_enabled: false,
        sso_login_button_visible: false,
        sso_provider_label: "SSO",
        sso_auto_provision: true,
        sso_default_role: "viewer",
        sso_allowed_domains: "",
        sso_provider_configured: false,
    });
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        let mounted = true;
        void (async () => {
            try {
                const response = await apiFetch("/settings/auth");
                if (!response.ok) throw new Error(t("settings.auth.toast.load_failed"));
                const data = await response.json() as AuthSettingsForm;
                if (mounted) setForm(data);
            } catch (error) {
                toast(getErrorMessage(error, t("settings.auth.toast.load_failed")), "error");
            } finally {
                if (mounted) setLoading(false);
            }
        })();
        return () => {
            mounted = false;
        };
    }, [t, toast]);

    const setField = <K extends keyof AuthSettingsForm>(key: K, value: AuthSettingsForm[K]) => {
        setForm(prev => ({ ...prev, [key]: value }));
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            const { sso_provider_configured: _ignored, ...payload } = form;
            void _ignored;
            const response = await apiFetch("/settings/auth", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({ detail: t("settings.auth.toast.save_failed") })) as { detail?: string };
                throw new Error(err.detail || t("settings.auth.toast.save_failed"));
            }
            const data = await response.json() as AuthSettingsForm;
            setForm(data);
            toast(t("settings.auth.toast.saved"), "success");
        } catch (error) {
            toast(getErrorMessage(error, t("settings.auth.toast.save_failed")), "error");
        } finally {
            setSaving(false);
        }
    };

    const toggle = (
        key: keyof Pick<AuthSettingsForm, "sso_enabled" | "sso_login_button_visible" | "sso_auto_provision">,
        label: string,
        description: string,
    ) => (
        <button
            type="button"
            onClick={() => setField(key, !form[key])}
            className="flex w-full items-center justify-between gap-4 rounded-xl border border-gray-200 bg-white px-4 py-3 text-left transition hover:bg-gray-50 dark:border-gray-800 dark:bg-gray-900 dark:hover:bg-gray-800"
        >
            <span>
                <span className="block text-sm font-semibold text-gray-900 dark:text-white">{label}</span>
                <span className="mt-1 block text-xs text-gray-500 dark:text-gray-400">{description}</span>
            </span>
            <span className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${form[key] ? "bg-indigo-600" : "bg-gray-300 dark:bg-gray-700"}`}>
                <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${form[key] ? "translate-x-6" : "translate-x-1"}`} />
            </span>
        </button>
    );

    if (loading) {
        return <div className="py-10 text-center text-sm text-gray-400">{t("common.loading")}</div>;
    }

    return (
        <div className="space-y-4">
            <div className="rounded-2xl border border-indigo-100 bg-indigo-50/70 p-4 shadow-sm dark:border-indigo-900/30 dark:bg-indigo-900/10">
                <p className="text-sm font-semibold text-indigo-950 dark:text-indigo-100">{t("settings.auth.guidance_title")}</p>
                <p className="mt-1 text-xs text-indigo-900/80 dark:text-indigo-200/80">{t("settings.auth.guidance_body")}</p>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-500">{t("settings.auth.summary.provider")}</p>
                    <p className={`mt-2 text-sm font-semibold ${form.sso_provider_configured ? "text-emerald-600" : "text-amber-600"}`}>
                        {form.sso_provider_configured ? t("settings.auth.summary.configured") : t("settings.auth.summary.missing_env")}
                    </p>
                </div>
                <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-500">{t("settings.auth.summary.login")}</p>
                    <p className="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
                        {form.sso_enabled && form.sso_login_button_visible ? t("settings.auth.summary.visible") : t("settings.auth.summary.hidden")}
                    </p>
                </div>
                <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-500">{t("settings.auth.summary.new_users")}</p>
                    <p className="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
                        {form.sso_auto_provision ? t("settings.auth.summary.auto_provision_on") : t("settings.auth.summary.auto_provision_off")}
                    </p>
                </div>
            </div>

            <div className="space-y-3">
                {toggle("sso_enabled", t("settings.auth.sso_enabled"), t("settings.auth.sso_enabled_help"))}
                {toggle("sso_login_button_visible", t("settings.auth.sso_login_button_visible"), t("settings.auth.sso_login_button_visible_help"))}
                {toggle("sso_auto_provision", t("settings.auth.sso_auto_provision"), t("settings.auth.sso_auto_provision_help"))}
            </div>

            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h3 className="mb-4 text-base font-semibold text-gray-900 dark:text-white">{t("settings.auth.provider_section")}</h3>
                <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                        <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">{t("settings.auth.provider_label")}</label>
                        <input className={inputClass} value={form.sso_provider_label} onChange={e => setField("sso_provider_label", e.target.value)} placeholder="SSO" />
                    </div>
                    <div>
                        <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">{t("settings.auth.default_role")}</label>
                        <select className={inputClass} value={form.sso_default_role} onChange={e => setField("sso_default_role", e.target.value as AuthSettingsForm["sso_default_role"])}>
                            <option value="viewer">{t("header.user.role.viewer")}</option>
                            <option value="editor">{t("header.user.role.editor")}</option>
                            <option value="admin">{t("header.user.role.admin")}</option>
                        </select>
                    </div>
                    <div className="sm:col-span-2">
                        <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">{t("settings.auth.allowed_domains")}</label>
                        <input className={inputClass} value={form.sso_allowed_domains} onChange={e => setField("sso_allowed_domains", e.target.value)} placeholder="udg.mx, example.edu" />
                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{t("settings.auth.allowed_domains_help")}</p>
                    </div>
                </div>
            </div>

            <button
                onClick={handleSave}
                disabled={saving}
                className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
            >
                {saving ? t("settings.account.saving") : t("settings.auth.save")}
            </button>
        </div>
    );
}
