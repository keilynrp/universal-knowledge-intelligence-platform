"use client";

import { useState, useEffect } from "react";
import { useLanguage } from "../contexts/LanguageContext";
import { useTheme } from "../contexts/ThemeContext";
import { useBranding } from "../contexts/BrandingContext";
import type { Language } from "../i18n/translations";
type Theme = "light" | "dark";
import { useAuth } from "../contexts/AuthContext";
import { PageHeader, TabNav, Badge, useToast } from "../components/ui";
import { apiFetch } from "@/lib/api";
import AvatarUpload from "../components/AvatarUpload";
import PasswordStrength from "../components/PasswordStrength";

// ── Types ───────────────────────────────────────────────────────────────────

type Tab = "preferences" | "account" | "users" | "webhooks" | "notifications" | "branding";

type UserRole = "super_admin" | "admin" | "editor" | "viewer";

interface UserRecord {
    id: number;
    username: string;
    email: string | null;
    role: UserRole;
    is_active: boolean;
    created_at: string | null;
}

// ── Role badge helper ────────────────────────────────────────────────────────

const ROLE_VARIANTS: Record<UserRole, "error" | "warning" | "info" | "default"> = {
    super_admin: "error",
    admin:       "warning",
    editor:      "info",
    viewer:      "default",
};

const ROLE_LABELS: Record<UserRole, string> = {
    super_admin: "Super Admin",
    admin:       "Admin",
    editor:      "Editor",
    viewer:      "Viewer",
};

// ── Main Page ────────────────────────────────────────────────────────────────

export default function SettingsPage() {
    const { language, setLanguage, t } = useLanguage();
    const { theme, setTheme } = useTheme();
    const { user, updateAvatarUrl } = useAuth();
    const { toast } = useToast();

    const isSuperAdmin = user?.role === "super_admin";

    const isAdmin = user?.role === "super_admin" || user?.role === "admin";

    const tabs = [
        { id: "preferences", label: "Preferences" },
        { id: "account",     label: "Account" },
        ...(isSuperAdmin ? [{ id: "users", label: "User Management" }] : []),
        ...(isAdmin ? [{ id: "webhooks",      label: "Webhooks" }] : []),
        ...(isAdmin ? [{ id: "notifications", label: "Notifications" }] : []),
        ...(isAdmin ? [{ id: "branding",      label: "Branding" }] : []),
    ];

    const [tab, setTab] = useState<Tab>("preferences");

    return (
        <div className="space-y-6">
            <PageHeader
                breadcrumbs={[{ label: "Home", href: "/" }, { label: "Settings" }]}
                title={t("settings.title")}
                description={t("settings.subtitle")}
            />

            <TabNav
                tabs={tabs}
                activeTab={tab}
                onTabChange={(id) => setTab(id as Tab)}
            />

            {tab === "preferences" && (
                <PreferencesTab
                    language={language}
                    setLanguage={setLanguage}
                    theme={theme}
                    setTheme={setTheme}
                    t={t}
                />
            )}
            {tab === "account"        && <AccountTab user={user} updateAvatarUrl={updateAvatarUrl} toast={toast} />}
            {tab === "users"          && isSuperAdmin && <UsersTab currentUserId={user?.id ?? 0} toast={toast} />}
            {tab === "webhooks"       && isAdmin && <WebhooksTab toast={toast} />}
            {tab === "notifications"  && isAdmin && <NotificationsTab toast={toast} />}
            {tab === "branding"       && isAdmin && <BrandingTab toast={toast} />}
        </div>
    );
}

// ── Tab: Preferences ─────────────────────────────────────────────────────────

function PreferencesTab({
    language, setLanguage, theme, setTheme, t,
}: {
    language: Language;
    setLanguage: (l: Language) => void;
    theme: Theme;
    setTheme: (t: Theme) => void;
    t: (k: string) => string;
}) {
    return (
        <div className="space-y-4">
            {/* Language */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <div className="flex items-start justify-between">
                    <div>
                        <h3 className="text-base font-medium text-gray-900 dark:text-white">{t("settings.language")}</h3>
                        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t("settings.language.desc")}</p>
                    </div>
                    <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 p-1 dark:border-gray-700 dark:bg-gray-800">
                        {(["en", "es"] as const).map((lang) => (
                            <button
                                key={lang}
                                onClick={() => setLanguage(lang)}
                                className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                                    language === lang
                                        ? "bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white"
                                        : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                                }`}
                            >
                                <span className="text-lg">{lang === "en" ? "🇺🇸" : "🇪🇸"}</span>
                                {lang === "en" ? "English" : "Español"}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Theme */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <div className="flex items-start justify-between">
                    <div>
                        <h3 className="text-base font-medium text-gray-900 dark:text-white">{t("settings.theme")}</h3>
                        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t("settings.theme.desc")}</p>
                    </div>
                    <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 p-1 dark:border-gray-700 dark:bg-gray-800">
                        <button
                            onClick={() => setTheme("light" as Theme)}
                            className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                                theme === "light"
                                    ? "bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white"
                                    : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                            }`}
                        >
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                            </svg>
                            {t("settings.theme.light")}
                        </button>
                        <button
                            onClick={() => setTheme("dark" as Theme)}
                            className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                                theme === "dark"
                                    ? "bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white"
                                    : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                            }`}
                        >
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                            </svg>
                            {t("settings.theme.dark")}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

// ── Tab: Account ─────────────────────────────────────────────────────────────

function AccountTab({ user, updateAvatarUrl, toast }: { user: any; updateAvatarUrl: (url: string | null) => void; toast: (msg: string, v?: any) => void }) {
    // ── Profile edit state ────────────────────────────────────────────────────
    const { refreshUser } = useAuth();
    const [displayName, setDisplayName] = useState(user?.display_name ?? "");
    const [email, setEmail]             = useState(user?.email ?? "");
    const [bio, setBio]                 = useState(user?.bio ?? "");
    const [profileSaving, setProfileSaving] = useState(false);

    // Keep form in sync if user object updates (e.g. after avatar upload refreshes user)
    useEffect(() => {
        setDisplayName(user?.display_name ?? "");
        setEmail(user?.email ?? "");
        setBio(user?.bio ?? "");
    }, [user?.display_name, user?.email, user?.bio]);

    async function handleSaveProfile(e: React.FormEvent) {
        e.preventDefault();
        setProfileSaving(true);
        try {
            const body: Record<string, string> = {};
            if (displayName !== (user?.display_name ?? "")) body.display_name = displayName;
            if (email !== (user?.email ?? ""))               body.email        = email;
            if (bio !== (user?.bio ?? ""))                   body.bio          = bio;
            if (Object.keys(body).length === 0) {
                toast("No changes to save", "info");
                return;
            }
            const res = await apiFetch("/users/me/profile", {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Failed to save profile");
            }
            await refreshUser();
            toast("Profile updated successfully", "success");
        } catch (err: any) {
            toast(err.message || "Error saving profile", "error");
        } finally {
            setProfileSaving(false);
        }
    }

    // ── Password change state ─────────────────────────────────────────────────
    const [currentPw, setCurrentPw] = useState("");
    const [newPw, setNewPw] = useState("");
    const [confirmPw, setConfirmPw] = useState("");
    const [pwSaving, setPwSaving] = useState(false);

    async function handleChangePassword(e: React.FormEvent) {
        e.preventDefault();
        if (newPw.length < 8) {
            toast("New password must be at least 8 characters", "error");
            return;
        }
        if (newPw !== confirmPw) {
            toast("Passwords do not match", "error");
            return;
        }
        setPwSaving(true);
        try {
            const res = await apiFetch("/users/me/password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Failed to change password");
            }
            toast("Password updated successfully", "success");
            setCurrentPw("");
            setNewPw("");
            setConfirmPw("");
        } catch (err: any) {
            toast(err.message || "Error changing password", "error");
        } finally {
            setPwSaving(false);
        }
    }

    const inputClass = "h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white";

    return (
        <div className="space-y-4">
            {/* Avatar */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h3 className="mb-4 text-base font-semibold text-gray-900 dark:text-white">Profile Picture</h3>
                <AvatarUpload
                    username={user?.username ?? ""}
                    role={user?.role ?? "viewer"}
                    currentAvatarUrl={user?.avatar_url}
                    onUpdated={updateAvatarUrl}
                    toast={toast}
                />
            </div>

            {/* Profile info — editable */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h3 className="mb-1 text-base font-semibold text-gray-900 dark:text-white">Profile</h3>
                <p className="mb-5 text-sm text-gray-500 dark:text-gray-400">Update your display name, email address, and bio.</p>

                {/* Read-only fields */}
                <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="flex flex-col gap-1 rounded-xl border border-gray-100 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-800/50">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Username</span>
                        <span className="text-sm font-medium text-gray-800 dark:text-gray-200">{user?.username}</span>
                    </div>
                    <div className="flex flex-col gap-1 rounded-xl border border-gray-100 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-800/50">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Role</span>
                        <Badge variant={ROLE_VARIANTS[user?.role as UserRole] ?? "default"}>
                            {ROLE_LABELS[user?.role as UserRole] ?? user?.role}
                        </Badge>
                    </div>
                </div>

                {/* Editable fields */}
                <form onSubmit={handleSaveProfile} className="space-y-4 max-w-lg">
                    <div>
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Display name <span className="text-gray-400 font-normal">(optional)</span>
                        </label>
                        <input
                            type="text"
                            className={inputClass}
                            value={displayName}
                            onChange={e => setDisplayName(e.target.value)}
                            maxLength={100}
                            placeholder="Your full name or nickname"
                            autoComplete="name"
                        />
                    </div>
                    <div>
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Email address
                        </label>
                        <input
                            type="email"
                            className={inputClass}
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            maxLength={255}
                            placeholder="you@example.com"
                            autoComplete="email"
                        />
                    </div>
                    <div>
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Bio <span className="text-gray-400 font-normal">(max 500 chars)</span>
                        </label>
                        <textarea
                            className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white resize-none"
                            rows={3}
                            value={bio}
                            onChange={e => setBio(e.target.value)}
                            maxLength={500}
                            placeholder="A short description about yourself…"
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
                        {profileSaving ? "Saving…" : "Save Profile"}
                    </button>
                </form>
            </div>

            {/* Change password */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h3 className="mb-4 text-base font-semibold text-gray-900 dark:text-white">Change Password</h3>
                <form onSubmit={handleChangePassword} className="space-y-4 max-w-sm">
                    <div>
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Current password
                        </label>
                        <input
                            type="password"
                            className={inputClass}
                            value={currentPw}
                            onChange={e => setCurrentPw(e.target.value)}
                            required
                            autoComplete="current-password"
                        />
                    </div>
                    <div>
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            New password
                        </label>
                        <input
                            type="password"
                            className={inputClass}
                            value={newPw}
                            onChange={e => setNewPw(e.target.value)}
                            required
                            minLength={8}
                            autoComplete="new-password"
                        />
                        <PasswordStrength password={newPw} />
                    </div>
                    <div>
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Confirm new password
                        </label>
                        <input
                            type="password"
                            className={`${inputClass} ${confirmPw && confirmPw !== newPw ? "border-red-400 focus:border-red-500 focus:ring-red-400" : ""}`}
                            value={confirmPw}
                            onChange={e => setConfirmPw(e.target.value)}
                            required
                            autoComplete="new-password"
                        />
                        {confirmPw && confirmPw !== newPw && (
                            <p className="mt-1 text-xs text-red-500">Passwords do not match</p>
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
                        {pwSaving ? "Saving…" : "Update Password"}
                    </button>
                </form>
            </div>
        </div>
    );
}

// ── Tab: User Management ──────────────────────────────────────────────────────

function UsersTab({ currentUserId, toast }: { currentUserId: number; toast: (msg: string, v?: any) => void }) {
    const [users, setUsers] = useState<UserRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [saving, setSaving] = useState(false);
    const [actionId, setActionId] = useState<number | null>(null);

    const [form, setForm] = useState({
        username: "",
        email: "",
        password: "",
        role: "viewer" as UserRole,
    });

    async function fetchUsers() {
        try {
            const res = await apiFetch("/users");
            if (res.ok) setUsers(await res.json());
        } catch {
            toast("Error loading users", "error");
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => { fetchUsers(); }, []);

    async function handleCreate(e: React.FormEvent) {
        e.preventDefault();
        if (form.password.length < 8) {
            toast("Password must be at least 8 characters", "error");
            return;
        }
        setSaving(true);
        try {
            const res = await apiFetch("/users", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(form),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Failed to create user");
            }
            toast(`User "${form.username}" created`, "success");
            setForm({ username: "", email: "", password: "", role: "viewer" });
            setShowForm(false);
            fetchUsers();
        } catch (err: any) {
            toast(err.message || "Error creating user", "error");
        } finally {
            setSaving(false);
        }
    }

    async function handleRoleChange(userId: number, newRole: UserRole) {
        setActionId(userId);
        try {
            const res = await apiFetch(`/users/${userId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ role: newRole }),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Failed to update role");
            }
            setUsers(prev => prev.map(u => u.id === userId ? { ...u, role: newRole } : u));
            toast("Role updated", "success");
        } catch (err: any) {
            toast(err.message || "Error updating role", "error");
        } finally {
            setActionId(null);
        }
    }

    async function handleDeactivate(userId: number, username: string) {
        if (!confirm(`Deactivate user "${username}"?`)) return;
        setActionId(userId);
        try {
            const res = await apiFetch(`/users/${userId}`, { method: "DELETE" });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Failed to deactivate");
            }
            setUsers(prev => prev.map(u => u.id === userId ? { ...u, is_active: false } : u));
            toast(`User "${username}" deactivated`, "warning");
        } catch (err: any) {
            toast(err.message || "Error deactivating user", "error");
        } finally {
            setActionId(null);
        }
    }

    const inputClass = "h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white";

    return (
        <div className="space-y-4">
            {/* Header row */}
            <div className="flex items-center justify-between">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                    {users.filter(u => u.is_active).length} active · {users.filter(u => !u.is_active).length} inactive
                </p>
                <button
                    onClick={() => setShowForm(f => !f)}
                    className="flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-blue-700"
                >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={showForm ? "M6 18L18 6M6 6l12 12" : "M12 4v16m8-8H4"} />
                    </svg>
                    {showForm ? "Cancel" : "New User"}
                </button>
            </div>

            {/* Create form */}
            {showForm && (
                <div className="rounded-2xl border border-blue-100 bg-blue-50/50 p-6 shadow-sm dark:border-blue-500/20 dark:bg-blue-500/5 toast-enter">
                    <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">Create New User</h3>
                    <form onSubmit={handleCreate} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                        <div>
                            <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">Username *</label>
                            <input
                                className={inputClass}
                                value={form.username}
                                onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                                required
                                minLength={1}
                                maxLength={50}
                                placeholder="johndoe"
                            />
                        </div>
                        <div>
                            <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">Email</label>
                            <input
                                type="email"
                                className={inputClass}
                                value={form.email}
                                onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                                placeholder="john@example.com"
                            />
                        </div>
                        <div>
                            <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">Password * <span className="font-normal text-gray-400">(min. 8)</span></label>
                            <input
                                type="password"
                                className={inputClass}
                                value={form.password}
                                onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                                required
                                minLength={8}
                                autoComplete="new-password"
                            />
                        </div>
                        <div>
                            <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">Role *</label>
                            <select
                                className={inputClass}
                                value={form.role}
                                onChange={e => setForm(f => ({ ...f, role: e.target.value as UserRole }))}
                            >
                                <option value="viewer">Viewer</option>
                                <option value="editor">Editor</option>
                                <option value="admin">Admin</option>
                                <option value="super_admin">Super Admin</option>
                            </select>
                        </div>
                        <div className="sm:col-span-2 flex justify-end gap-2 pt-1">
                            <button
                                type="button"
                                onClick={() => setShowForm(false)}
                                className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                            >
                                Cancel
                            </button>
                            <button
                                type="submit"
                                disabled={saving}
                                className="flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                            >
                                {saving && (
                                    <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                    </svg>
                                )}
                                Create User
                            </button>
                        </div>
                    </form>
                </div>
            )}

            {/* Users table */}
            <div className="overflow-x-auto rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
                {loading ? (
                    <div className="flex items-center justify-center py-12">
                        <svg className="h-6 w-6 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                    </div>
                ) : (
                    <table className="w-full text-left text-sm">
                        <thead>
                            <tr className="border-b border-gray-200 dark:border-gray-800">
                                {["User", "Email", "Role", "Status", "Actions"].map(h => (
                                    <th key={h} className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                                        {h}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                            {users.map(u => (
                                <tr key={u.id} className={`${!u.is_active ? "opacity-50" : ""} hover:bg-gray-50 dark:hover:bg-gray-800/50`}>
                                    <td className="px-5 py-3.5">
                                        <div className="flex items-center gap-2.5">
                                            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-100 text-xs font-bold text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                                                {u.username.slice(0, 2).toUpperCase()}
                                            </span>
                                            <div>
                                                <p className="font-medium text-gray-900 dark:text-white">{u.username}</p>
                                                {u.id === currentUserId && (
                                                    <p className="text-[10px] text-blue-500">you</p>
                                                )}
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-5 py-3.5 text-gray-500 dark:text-gray-400">{u.email || "—"}</td>
                                    <td className="px-5 py-3.5">
                                        {u.id === currentUserId ? (
                                            <Badge variant={ROLE_VARIANTS[u.role] ?? "default"}>
                                                {ROLE_LABELS[u.role] ?? u.role}
                                            </Badge>
                                        ) : (
                                            <select
                                                value={u.role}
                                                onChange={e => handleRoleChange(u.id, e.target.value as UserRole)}
                                                disabled={actionId === u.id || !u.is_active}
                                                className="h-8 rounded-lg border border-gray-200 bg-white px-2 text-xs font-medium text-gray-700 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
                                            >
                                                <option value="viewer">Viewer</option>
                                                <option value="editor">Editor</option>
                                                <option value="admin">Admin</option>
                                                <option value="super_admin">Super Admin</option>
                                            </select>
                                        )}
                                    </td>
                                    <td className="px-5 py-3.5">
                                        <Badge variant={u.is_active ? "success" : "default"} dot>
                                            {u.is_active ? "Active" : "Inactive"}
                                        </Badge>
                                    </td>
                                    <td className="px-5 py-3.5">
                                        {u.id !== currentUserId && u.is_active && (
                                            <button
                                                onClick={() => handleDeactivate(u.id, u.username)}
                                                disabled={actionId === u.id}
                                                className="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-40 dark:hover:bg-red-500/10 dark:hover:text-red-400"
                                                title="Deactivate user"
                                            >
                                                {actionId === u.id ? (
                                                    <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                                    </svg>
                                                ) : (
                                                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                                                    </svg>
                                                )}
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
}

// ── Tab: Webhooks ─────────────────────────────────────────────────────────────

const ALL_EVENTS = [
    "upload",
    "entity.update",
    "entity.delete",
    "entity.bulk_delete",
    "harmonization.apply",
    "authority.confirm",
    "authority.reject",
];

interface WebhookRecord {
    id: number;
    url: string;
    events: string[];
    is_active: boolean;
    created_at: string | null;
    last_triggered_at: string | null;
    last_status: number | null;
}

function WebhooksTab({ toast }: { toast: (msg: string, v?: "success" | "error" | "warning" | "info") => void }) {
    const [hooks, setHooks] = useState<WebhookRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState<number | null>(null);
    const [form, setForm] = useState({ url: "", secret: "", events: [] as string[] });

    const load = async () => {
        setLoading(true);
        try {
            const res = await apiFetch("/webhooks");
            if (res.ok) setHooks(await res.json());
        } finally { setLoading(false); }
    };

    useEffect(() => { load(); }, []);

    const toggleEvent = (ev: string) =>
        setForm(f => ({
            ...f,
            events: f.events.includes(ev) ? f.events.filter(e => e !== ev) : [...f.events, ev],
        }));

    const handleCreate = async () => {
        if (!form.url || form.events.length === 0) {
            toast("URL and at least one event are required", "warning"); return;
        }
        setSaving(true);
        try {
            const res = await apiFetch("/webhooks", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url: form.url, events: form.events, secret: form.secret || null }),
            });
            if (!res.ok) throw new Error(await res.text());
            toast("Webhook created", "success");
            setForm({ url: "", secret: "", events: [] });
            setShowForm(false);
            load();
        } catch { toast("Failed to create webhook", "error"); }
        finally { setSaving(false); }
    };

    const handleToggle = async (hook: WebhookRecord) => {
        const res = await apiFetch(`/webhooks/${hook.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_active: !hook.is_active }),
        });
        if (res.ok) { toast(hook.is_active ? "Webhook disabled" : "Webhook enabled", "success"); load(); }
        else toast("Update failed", "error");
    };

    const handleDelete = async (id: number) => {
        const res = await apiFetch(`/webhooks/${id}`, { method: "DELETE" });
        if (res.ok) { toast("Webhook deleted", "success"); load(); }
        else toast("Delete failed", "error");
    };

    const handleTest = async (id: number) => {
        setTesting(id);
        try {
            const res = await apiFetch(`/webhooks/${id}/test`, { method: "POST" });
            if (res.ok) toast("Test ping sent", "info");
            else toast("Test failed", "error");
        } finally { setTesting(null); }
    };

    const statusColor = (s: number | null) => {
        if (!s) return "text-gray-400";
        if (s >= 200 && s < 300) return "text-emerald-600 dark:text-emerald-400";
        return "text-red-600 dark:text-red-400";
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                    Outbound HTTP callbacks fired when platform events occur.
                </p>
                <button
                    onClick={() => setShowForm(s => !s)}
                    className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                    {showForm ? "Cancel" : "+ New Webhook"}
                </button>
            </div>

            {showForm && (
                <div className="rounded-2xl border border-blue-200 bg-blue-50 p-5 dark:border-blue-500/20 dark:bg-blue-500/5">
                    <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">New Webhook</h3>
                    <div className="space-y-3">
                        <div>
                            <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Endpoint URL *</label>
                            <input
                                type="url"
                                value={form.url}
                                onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
                                placeholder="https://your-app.com/hook"
                                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                            />
                        </div>
                        <div>
                            <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Secret (HMAC-SHA256 key, optional)</label>
                            <input
                                type="text"
                                value={form.secret}
                                onChange={e => setForm(f => ({ ...f, secret: e.target.value }))}
                                placeholder="my-secret-key"
                                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                            />
                        </div>
                        <div>
                            <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">Events *</label>
                            <div className="flex flex-wrap gap-2">
                                {ALL_EVENTS.map(ev => (
                                    <button
                                        key={ev}
                                        onClick={() => toggleEvent(ev)}
                                        className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                                            form.events.includes(ev)
                                                ? "bg-blue-600 text-white"
                                                : "border border-gray-300 bg-white text-gray-700 hover:border-blue-400 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300"
                                        }`}
                                    >
                                        {ev}
                                    </button>
                                ))}
                            </div>
                        </div>
                        <button
                            onClick={handleCreate}
                            disabled={saving}
                            className="rounded-xl bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                        >
                            {saving ? "Saving…" : "Create Webhook"}
                        </button>
                    </div>
                </div>
            )}

            <div className="overflow-x-auto rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900">
                {loading ? (
                    <div className="flex justify-center py-10">
                        <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
                    </div>
                ) : hooks.length === 0 ? (
                    <p className="py-10 text-center text-sm text-gray-400 dark:text-gray-500">No webhooks configured yet</p>
                ) : (
                    <table className="w-full min-w-[560px] text-sm">
                        <thead className="border-b border-gray-200 dark:border-gray-700">
                            <tr className="text-left text-xs font-medium text-gray-500 dark:text-gray-400">
                                <th className="px-5 py-3.5">URL</th>
                                <th className="px-5 py-3.5">Events</th>
                                <th className="px-5 py-3.5">Last status</th>
                                <th className="px-5 py-3.5">Active</th>
                                <th className="px-5 py-3.5" />
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                            {hooks.map(hook => (
                                <tr key={hook.id} className="group">
                                    <td className="max-w-xs truncate px-5 py-3.5 font-mono text-xs text-gray-700 dark:text-gray-300">{hook.url}</td>
                                    <td className="px-5 py-3.5">
                                        <div className="flex flex-wrap gap-1">
                                            {hook.events.map(ev => (
                                                <span key={ev} className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-400">{ev}</span>
                                            ))}
                                        </div>
                                    </td>
                                    <td className={`px-5 py-3.5 font-mono text-xs ${statusColor(hook.last_status)}`}>
                                        {hook.last_status ?? "—"}
                                    </td>
                                    <td className="px-5 py-3.5">
                                        <button
                                            onClick={() => handleToggle(hook)}
                                            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${hook.is_active ? "bg-blue-600" : "bg-gray-300 dark:bg-gray-600"}`}
                                        >
                                            <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${hook.is_active ? "translate-x-4" : "translate-x-1"}`} />
                                        </button>
                                    </td>
                                    <td className="px-5 py-3.5">
                                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100">
                                            <button
                                                onClick={() => handleTest(hook.id)}
                                                disabled={testing === hook.id}
                                                className="rounded-lg px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 disabled:opacity-40 dark:hover:bg-blue-500/10"
                                            >
                                                {testing === hook.id ? "…" : "Test"}
                                            </button>
                                            <button
                                                onClick={() => handleDelete(hook.id)}
                                                className="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10 dark:hover:text-red-400"
                                            >
                                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                                                </svg>
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
}

// ── Tab: Notifications ────────────────────────────────────────────────────────

function NotificationsTab({ toast }: { toast: (msg: string, v?: any) => void }) {
    const inputClass = "h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white";

    const [form, setForm] = useState({
        smtp_host: "", smtp_port: 587, smtp_user: "", smtp_password: "",
        from_email: "", recipient_email: "", enabled: false,
        notify_on_enrichment_batch: true, notify_on_authority_confirm: true,
    });
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState(false);

    useEffect(() => {
        apiFetch("/notifications/settings").then(async r => {
            if (r.ok) {
                const d = await r.json();
                setForm(f => ({ ...f, ...d, smtp_password: "" }));
            }
        }).finally(() => setLoading(false));
    }, []);

    const handleSave = async () => {
        setSaving(true);
        try {
            const payload: Record<string, any> = { ...form };
            if (!payload.smtp_password) delete payload.smtp_password;
            const r = await apiFetch("/notifications/settings", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!r.ok) throw new Error((await r.json()).detail);
            toast("Notification settings saved", "success");
        } catch (e: any) {
            toast(e.message || "Save failed", "error");
        } finally { setSaving(false); }
    };

    const handleTest = async () => {
        setTesting(true);
        try {
            const r = await apiFetch("/notifications/test", { method: "POST" });
            const d = await r.json();
            if (d.sent) toast("Test email sent successfully", "success");
            else toast("Email not sent — check settings and ensure alerts are enabled", "warning");
        } catch { toast("Test failed", "error"); }
        finally { setTesting(false); }
    };

    const setField = (k: keyof typeof form, v: any) => setForm(prev => ({ ...prev, [k]: v }));

    if (loading) return <div className="py-10 text-center text-sm text-gray-400">Loading…</div>;

    return (
        <div className="space-y-4">
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h3 className="mb-4 text-base font-semibold text-gray-900 dark:text-white">SMTP Configuration</h3>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {([
                        { label: "SMTP Host", key: "smtp_host", type: "text", placeholder: "smtp.gmail.com" },
                        { label: "SMTP Port", key: "smtp_port", type: "number", placeholder: "587" },
                        { label: "SMTP User", key: "smtp_user", type: "text", placeholder: "user@example.com" },
                        { label: "SMTP Password", key: "smtp_password", type: "password", placeholder: "Leave blank to keep existing" },
                        { label: "From Email", key: "from_email", type: "email", placeholder: "noreply@example.com" },
                        { label: "Recipient Email", key: "recipient_email", type: "email", placeholder: "admin@example.com" },
                    ] as const).map(({ label, key, type, placeholder }) => (
                        <div key={key}>
                            <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">{label}</label>
                            <input
                                type={type}
                                className={inputClass}
                                value={String(form[key])}
                                onChange={e => setField(key, type === "number" ? Number(e.target.value) : e.target.value)}
                                placeholder={placeholder}
                            />
                        </div>
                    ))}
                </div>
            </div>

            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h3 className="mb-4 text-base font-semibold text-gray-900 dark:text-white">Alert Preferences</h3>
                <div className="space-y-3">
                    {([
                        { label: "Enable email alerts", key: "enabled" },
                        { label: "Notify on enrichment batch complete", key: "notify_on_enrichment_batch" },
                        { label: "Notify on authority record confirmed", key: "notify_on_authority_confirm" },
                    ] as const).map(({ label, key }) => (
                        <label key={key} className="flex cursor-pointer items-center gap-3">
                            <div
                                onClick={() => setField(key, !form[key])}
                                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${form[key] ? "bg-indigo-600" : "bg-gray-300 dark:bg-gray-600"}`}
                            >
                                <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${form[key] ? "translate-x-4" : "translate-x-1"}`} />
                            </div>
                            <span className="text-sm text-gray-700 dark:text-gray-300">{label}</span>
                        </label>
                    ))}
                </div>
            </div>

            <div className="flex items-center gap-3">
                <button
                    onClick={handleSave}
                    disabled={saving}
                    className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                    {saving ? "Saving…" : "Save Settings"}
                </button>
                <button
                    onClick={handleTest}
                    disabled={testing}
                    className="rounded-xl border border-gray-200 px-5 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                    {testing ? "Sending…" : "Send Test Email"}
                </button>
            </div>
        </div>
    );
}

// ── Tab: Branding ─────────────────────────────────────────────────────────────

function BrandingTab({ toast }: { toast: (msg: string, v?: any) => void }) {
    const { branding, refreshBranding } = useBranding();
    const inputClass = "h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white";

    const [form, setForm] = useState({
        platform_name: branding.platform_name,
        logo_url:      branding.logo_url,
        accent_color:  branding.accent_color,
        footer_text:   branding.footer_text,
    });
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        setForm({
            platform_name: branding.platform_name,
            logo_url:      branding.logo_url,
            accent_color:  branding.accent_color,
            footer_text:   branding.footer_text,
        });
    }, [branding]);

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
                throw new Error(err.detail || "Save failed");
            }
            await refreshBranding();
            toast("Branding updated", "success");
        } catch (e: any) {
            toast(e.message || "Save failed", "error");
        } finally { setSaving(false); }
    };

    const fld = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
        setForm(prev => ({ ...prev, [k]: e.target.value }));

    return (
        <div className="space-y-4">
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h3 className="mb-4 text-base font-semibold text-gray-900 dark:text-white">Platform Identity</h3>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div>
                        <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">Platform Name</label>
                        <input className={inputClass} value={form.platform_name} onChange={fld("platform_name")} placeholder="UKIP" />
                    </div>
                    <div>
                        <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">Accent Color</label>
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
                        <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">Logo URL <span className="font-normal text-gray-400">(optional)</span></label>
                        <input className={inputClass} value={form.logo_url} onChange={fld("logo_url")} placeholder="https://example.com/logo.png" />
                        {form.logo_url && (
                            <img src={form.logo_url} alt="Logo preview" className="mt-2 h-10 w-auto rounded object-contain" onError={e => (e.currentTarget.hidden = true)} />
                        )}
                    </div>
                    <div className="sm:col-span-2">
                        <label className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-400">Footer Text</label>
                        <input className={inputClass} value={form.footer_text} onChange={fld("footer_text")} placeholder="Universal Knowledge Intelligence Platform" />
                    </div>
                </div>
            </div>

            {/* Live preview */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Preview</h3>
                <div className="flex items-center gap-3 rounded-xl border border-gray-100 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-gray-800/50">
                    <div
                        className="flex h-8 w-8 items-center justify-center rounded-lg"
                        style={{ backgroundColor: form.accent_color }}
                    >
                        {form.logo_url ? (
                            <img src={form.logo_url} alt="" className="h-5 w-5 object-contain" onError={e => (e.currentTarget.hidden = true)} />
                        ) : (
                            <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                            </svg>
                        )}
                    </div>
                    <div>
                        <p className="text-sm font-semibold text-gray-900 dark:text-white">{form.platform_name || "UKIP"}</p>
                        <p className="text-xs text-gray-400">{form.footer_text}</p>
                    </div>
                </div>
            </div>

            <button
                onClick={handleSave}
                disabled={saving}
                className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
            >
                {saving ? "Saving…" : "Save Branding"}
            </button>
        </div>
    );
}

