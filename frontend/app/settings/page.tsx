"use client";

import { useState, useEffect } from "react";
import { useLanguage } from "../contexts/LanguageContext";
import { useTheme } from "../contexts/ThemeContext";
import type { Language } from "../i18n/translations";
type Theme = "light" | "dark";
import { useAuth } from "../contexts/AuthContext";
import { PageHeader, TabNav, Badge, useToast } from "../components/ui";
import { apiFetch } from "@/lib/api";

// ── Types ───────────────────────────────────────────────────────────────────

type Tab = "preferences" | "account" | "users";

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
    const { user } = useAuth();
    const { toast } = useToast();

    const isSuperAdmin = user?.role === "super_admin";

    const tabs = [
        { id: "preferences", label: "Preferences" },
        { id: "account",     label: "Account" },
        ...(isSuperAdmin ? [{ id: "users", label: "User Management" }] : []),
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
            {tab === "account" && <AccountTab user={user} toast={toast} />}
            {tab === "users"   && isSuperAdmin && <UsersTab currentUserId={user?.id ?? 0} toast={toast} />}
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

function AccountTab({ user, toast }: { user: any; toast: (msg: string, v?: any) => void }) {
    const [currentPw, setCurrentPw] = useState("");
    const [newPw, setNewPw] = useState("");
    const [confirmPw, setConfirmPw] = useState("");
    const [saving, setSaving] = useState(false);

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
        setSaving(true);
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
            setSaving(false);
        }
    }

    const inputClass = "h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white";

    return (
        <div className="space-y-4">
            {/* Profile info */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h3 className="mb-4 text-base font-semibold text-gray-900 dark:text-white">Profile</h3>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                    {[
                        { label: "Username", value: user?.username },
                        { label: "Email", value: user?.email || "—" },
                        { label: "Role", value: user?.role },
                    ].map(({ label, value }) => (
                        <div key={label} className="flex flex-col gap-1 rounded-xl border border-gray-100 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-800/50">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{label}</span>
                            {label === "Role" ? (
                                <Badge variant={ROLE_VARIANTS[value as UserRole] ?? "default"}>
                                    {ROLE_LABELS[value as UserRole] ?? value}
                                </Badge>
                            ) : (
                                <span className="text-sm font-medium text-gray-800 dark:text-gray-200">{value}</span>
                            )}
                        </div>
                    ))}
                </div>
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
                            New password <span className="text-gray-400 font-normal">(min. 8 chars)</span>
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
                        disabled={saving || !currentPw || !newPw || newPw !== confirmPw}
                        className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                    >
                        {saving && (
                            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                        )}
                        {saving ? "Saving…" : "Update Password"}
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
            <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
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
