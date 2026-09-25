"use client";

import { useEffect, useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useLanguage } from "../contexts/LanguageContext";
import { Badge, SectionHeader, Surface, type ToastVariant } from "../components/ui";
import { apiFetch } from "@/lib/api";
import AvatarUpload from "../components/AvatarUpload";
import PasswordStrength from "../components/PasswordStrength";
import SessionList from "../components/SessionList";
import { ROLE_LABEL_KEYS, ROLE_VARIANTS, type UserRole } from "./userManagementTypes";

type AccountUser = {
    id: number;
    username: string;
    role: string;
    email: string | null;
    is_active: boolean;
    avatar_url?: string | null;
    display_name?: string | null;
    bio?: string | null;
    created_at?: string | null;
};

function getErrorMessage(error: unknown, fallback: string) {
    return error instanceof Error ? error.message : fallback;
}

export default function AccountTab({
    user,
    updateAvatarUrl,
    toast,
}: {
    user: AccountUser | null;
    updateAvatarUrl: (url: string | null) => void;
    toast: (msg: string, v?: ToastVariant) => void;
}) {
    const { refreshUser } = useAuth();
    const { t } = useLanguage();
    const [displayName, setDisplayName] = useState(user?.display_name ?? "");
    const [email, setEmail] = useState(user?.email ?? "");
    const [bio, setBio] = useState(user?.bio ?? "");
    const [profileSaving, setProfileSaving] = useState(false);

    const [currentPw, setCurrentPw] = useState("");
    const [newPw, setNewPw] = useState("");
    const [confirmPw, setConfirmPw] = useState("");
    const [pwSaving, setPwSaving] = useState(false);

    useEffect(() => {
        setDisplayName(user?.display_name ?? "");
        setEmail(user?.email ?? "");
        setBio(user?.bio ?? "");
    }, [user?.bio, user?.display_name, user?.email]);

    async function handleSaveProfile(event: React.FormEvent) {
        event.preventDefault();
        setProfileSaving(true);
        try {
            const body: Record<string, string> = {};
            if (displayName !== (user?.display_name ?? "")) body.display_name = displayName;
            if (email !== (user?.email ?? "")) body.email = email;
            if (bio !== (user?.bio ?? "")) body.bio = bio;
            if (Object.keys(body).length === 0) {
                toast(t("settings.account.toast.no_changes"), "info");
                return;
            }

            const response = await apiFetch("/users/me/profile", {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (!response.ok) {
                const errorBody = await response.json().catch(() => ({ detail: t("settings.account.toast.save_failed") })) as { detail?: string };
                throw new Error(errorBody.detail || t("settings.account.toast.save_failed"));
            }

            await refreshUser();
            toast(t("settings.account.toast.profile_saved"), "success");
        } catch (error: unknown) {
            toast(getErrorMessage(error, t("settings.account.toast.save_error")), "error");
        } finally {
            setProfileSaving(false);
        }
    }

    async function handleChangePassword(event: React.FormEvent) {
        event.preventDefault();
        if (newPw.length < 8) {
            toast(t("settings.account.toast.password_too_short"), "error");
            return;
        }
        if (newPw !== confirmPw) {
            toast(t("settings.account.toast.passwords_no_match"), "error");
            return;
        }

        setPwSaving(true);
        try {
            const response = await apiFetch("/users/me/password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
            });
            if (!response.ok) {
                const errorBody = await response.json().catch(() => ({ detail: t("settings.account.toast.password_change_failed") })) as { detail?: string };
                throw new Error(errorBody.detail || t("settings.account.toast.password_change_failed"));
            }

            toast(t("settings.account.toast.password_updated"), "success");
            setCurrentPw("");
            setNewPw("");
            setConfirmPw("");
        } catch (error: unknown) {
            toast(getErrorMessage(error, t("settings.account.toast.password_change_error")), "error");
        } finally {
            setPwSaving(false);
        }
    }

    const inputClass = "h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white";

    return (
        <div className="space-y-4">
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h3 className="mb-4 text-base font-semibold text-gray-900 dark:text-white">{t("settings.account.profile_picture")}</h3>
                <AvatarUpload
                    username={user?.username ?? ""}
                    role={user?.role ?? "viewer"}
                    currentAvatarUrl={user?.avatar_url}
                    onUpdated={updateAvatarUrl}
                    toast={toast}
                />
            </div>

            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h3 className="mb-1 text-base font-semibold text-gray-900 dark:text-white">{t("settings.account.profile_title")}</h3>
                <p className="mb-5 text-sm text-gray-500 dark:text-gray-400">{t("settings.account.profile_description")}</p>

                <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="flex flex-col gap-1 rounded-xl border border-gray-100 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-800/50">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{t("settings.account.username")}</span>
                        <span className="text-sm font-medium text-gray-800 dark:text-gray-200">{user?.username}</span>
                    </div>
                    <div className="flex flex-col gap-1 rounded-xl border border-gray-100 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-800/50">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{t("settings.account.role")}</span>
                        <Badge variant={ROLE_VARIANTS[user?.role as UserRole] ?? "default"}>
                            {t(ROLE_LABEL_KEYS[user?.role as UserRole] ?? "users.role.viewer")}
                        </Badge>
                    </div>
                </div>

                <form onSubmit={handleSaveProfile} className="max-w-lg space-y-4">
                    <div>
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {t("settings.account.display_name")} <span className="font-normal text-gray-400">({t("common.optional").toLowerCase()})</span>
                        </label>
                        <input
                            type="text"
                            className={inputClass}
                            value={displayName}
                            onChange={event => setDisplayName(event.target.value)}
                            maxLength={100}
                            placeholder={t("settings.account.display_name_placeholder")}
                            autoComplete="name"
                        />
                    </div>
                    <div>
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {t("settings.account.email")}
                        </label>
                        <input
                            type="email"
                            className={inputClass}
                            value={email}
                            onChange={event => setEmail(event.target.value)}
                            maxLength={255}
                            placeholder={t("settings.account.email_placeholder")}
                            autoComplete="email"
                        />
                    </div>
                    <div>
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {t("settings.account.bio")} <span className="font-normal text-gray-400">({t("settings.account.bio_limit")})</span>
                        </label>
                        <textarea
                            className="w-full resize-none rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white"
                            rows={3}
                            value={bio}
                            onChange={event => setBio(event.target.value)}
                            maxLength={500}
                            placeholder={t("settings.account.bio_placeholder")}
                        />
                        <p className="mt-1 text-right text-xs text-gray-400">{bio.length}/500</p>
                    </div>
                    <button
                        type="submit"
                        disabled={profileSaving}
                        className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                    >
                        {profileSaving && (
                            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                        )}
                        {profileSaving ? t("settings.account.saving") : t("settings.account.save_profile")}
                    </button>
                </form>
            </div>

            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h3 className="mb-4 text-base font-semibold text-gray-900 dark:text-white">{t("settings.account.change_password")}</h3>
                <form onSubmit={handleChangePassword} className="max-w-sm space-y-4">
                    <div>
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {t("settings.account.current_password")}
                        </label>
                        <input
                            type="password"
                            className={inputClass}
                            value={currentPw}
                            onChange={event => setCurrentPw(event.target.value)}
                            required
                            autoComplete="current-password"
                        />
                    </div>
                    <div>
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {t("settings.account.new_password")}
                        </label>
                        <input
                            type="password"
                            className={inputClass}
                            value={newPw}
                            onChange={event => setNewPw(event.target.value)}
                            required
                            minLength={8}
                            autoComplete="new-password"
                        />
                        <PasswordStrength password={newPw} />
                    </div>
                    <div>
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {t("settings.account.confirm_new_password")}
                        </label>
                        <input
                            type="password"
                            className={`${inputClass} ${confirmPw && confirmPw !== newPw ? "border-red-400 focus:border-red-500 focus:ring-red-400" : ""}`}
                            value={confirmPw}
                            onChange={event => setConfirmPw(event.target.value)}
                            required
                            autoComplete="new-password"
                        />
                        {confirmPw && confirmPw !== newPw && (
                            <p className="mt-1 text-xs text-red-500">{t("settings.account.toast.passwords_no_match")}</p>
                        )}
                    </div>
                    <button
                        type="submit"
                        disabled={pwSaving || !currentPw || !newPw || newPw !== confirmPw}
                        className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                    >
                        {pwSaving && (
                            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                        )}
                        {pwSaving ? t("settings.account.saving") : t("settings.account.update_password")}
                    </button>
                </form>
            </div>

            <Surface className="p-6">
                <SectionHeader
                    className="mb-4"
                    title={t("sessions.title")}
                    description={t("sessions.description_self")}
                />
                <SessionList
                    endpoint="/auth/sessions"
                    scope="self"
                    showActivity={user?.role === "super_admin" || user?.role === "admin"}
                    toast={toast}
                />
            </Surface>
        </div>
    );
}
