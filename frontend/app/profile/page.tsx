"use client";

import { useState, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../components/ui";
import UserAvatar from "../components/UserAvatar";
import AvatarUpload from "../components/AvatarUpload";
import { apiFetch } from "@/lib/api";
import PasswordStrength from "../components/PasswordStrength";

const ROLE_META: Record<string, { label: string; pill: string }> = {
    super_admin: { label: "Super Admin", pill: "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400" },
    admin:       { label: "Admin",       pill: "bg-orange-100 text-orange-700 dark:bg-orange-500/20 dark:text-orange-400" },
    editor:      { label: "Editor",      pill: "bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400" },
    viewer:      { label: "Viewer",      pill: "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400" },
};

const inputCls =
    "h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white";

function formatJoined(iso: string | null | undefined) {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

// ── Section wrapper ──────────────────────────────────────────────────────────

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <div className="mb-5">
                <h2 className="text-base font-semibold text-gray-900 dark:text-white">{title}</h2>
                {description && <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">{description}</p>}
            </div>
            {children}
        </div>
    );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ProfilePage() {
    const { user, refreshUser, updateAvatarUrl } = useAuth();
    const { toast } = useToast();

    const role     = user?.role ?? "viewer";
    const roleMeta = ROLE_META[role] ?? ROLE_META.viewer;

    // ── Profile edit ──────────────────────────────────────────────────────────
    const [displayName, setDisplayName] = useState(user?.display_name ?? "");
    const [email, setEmail]             = useState(user?.email ?? "");
    const [bio, setBio]                 = useState(user?.bio ?? "");
    const [profileSaving, setProfileSaving] = useState(false);

    useEffect(() => {
        setDisplayName(user?.display_name ?? "");
        setEmail(user?.email ?? "");
        setBio(user?.bio ?? "");
    }, [user?.display_name, user?.email, user?.bio]);

    async function handleSaveProfile(e: React.FormEvent) {
        e.preventDefault();
        const body: Record<string, string> = {};
        if (displayName !== (user?.display_name ?? "")) body.display_name = displayName;
        if (email       !== (user?.email ?? ""))        body.email        = email;
        if (bio         !== (user?.bio ?? ""))           body.bio          = bio;
        if (Object.keys(body).length === 0) { toast("No changes to save", "info"); return; }
        setProfileSaving(true);
        try {
            const res = await apiFetch("/users/me/profile", {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (!res.ok) { const err = await res.json(); throw new Error(err.detail || "Failed to save profile"); }
            await refreshUser();
            toast("Profile updated successfully", "success");
        } catch (err: any) {
            toast(err.message || "Error saving profile", "error");
        } finally {
            setProfileSaving(false);
        }
    }

    // ── Password change ───────────────────────────────────────────────────────
    const [currentPw, setCurrentPw] = useState("");
    const [newPw, setNewPw]         = useState("");
    const [confirmPw, setConfirmPw] = useState("");
    const [pwSaving, setPwSaving]   = useState(false);

    async function handleChangePassword(e: React.FormEvent) {
        e.preventDefault();
        if (newPw.length < 8)    { toast("New password must be at least 8 characters", "error"); return; }
        if (newPw !== confirmPw) { toast("Passwords do not match", "error"); return; }
        setPwSaving(true);
        try {
            const res = await apiFetch("/users/me/password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
            });
            if (!res.ok) { const err = await res.json(); throw new Error(err.detail || "Failed to change password"); }
            toast("Password updated successfully", "success");
            setCurrentPw(""); setNewPw(""); setConfirmPw("");
        } catch (err: any) {
            toast(err.message || "Error changing password", "error");
        } finally {
            setPwSaving(false);
        }
    }

    // ── Spinner helper ────────────────────────────────────────────────────────
    function Spinner() {
        return (
            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
        );
    }

    return (
        <div className="mx-auto max-w-2xl space-y-6">

            {/* ── Hero card ── */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <div className="flex items-center gap-5">
                    <UserAvatar
                        username={user?.username ?? "?"}
                        role={role}
                        avatarUrl={user?.avatar_url}
                        size="lg"
                    />
                    <div className="min-w-0">
                        <h1 className="truncate text-xl font-bold text-gray-900 dark:text-white">
                            {user?.display_name || user?.username || "—"}
                        </h1>
                        {user?.display_name && (
                            <p className="text-sm text-gray-400 dark:text-gray-500">@{user.username}</p>
                        )}
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                            <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${roleMeta.pill}`}>
                                {roleMeta.label}
                            </span>
                            {user?.email && (
                                <span className="truncate text-xs text-gray-500 dark:text-gray-400">{user.email}</span>
                            )}
                        </div>
                        {user?.bio && (
                            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300 line-clamp-2">{user.bio}</p>
                        )}
                        <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">
                            Member since {formatJoined(user?.created_at as string | null)}
                        </p>
                    </div>
                </div>
            </div>

            {/* ── Profile Picture ── */}
            <Section title="Profile Picture" description="Upload a custom avatar — drag & drop or click to browse.">
                <AvatarUpload
                    username={user?.username ?? ""}
                    role={role}
                    currentAvatarUrl={user?.avatar_url}
                    onUpdated={updateAvatarUrl}
                    toast={toast}
                />
            </Section>

            {/* ── Edit Profile ── */}
            <Section title="Personal Information" description="Update your display name, email address, and bio.">
                <form onSubmit={handleSaveProfile} className="space-y-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                        {/* Read-only */}
                        <div>
                            <label className="mb-1.5 block text-sm font-medium text-gray-500 dark:text-gray-400">
                                Username
                            </label>
                            <div className="flex h-10 items-center rounded-lg border border-dashed border-gray-200 bg-gray-50 px-3 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-800/50 dark:text-gray-400">
                                {user?.username}
                            </div>
                        </div>
                        <div>
                            <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                                Display name <span className="text-gray-400 font-normal">(optional)</span>
                            </label>
                            <input
                                type="text"
                                className={inputCls}
                                value={displayName}
                                onChange={e => setDisplayName(e.target.value)}
                                maxLength={100}
                                placeholder="Your full name or nickname"
                                autoComplete="name"
                            />
                        </div>
                    </div>
                    <div>
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Email address
                        </label>
                        <input
                            type="email"
                            className={inputCls}
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
                    <div className="flex justify-end">
                        <button
                            type="submit"
                            disabled={profileSaving}
                            className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                        >
                            {profileSaving && <Spinner />}
                            {profileSaving ? "Saving…" : "Save changes"}
                        </button>
                    </div>
                </form>
            </Section>

            {/* ── Security ── */}
            <Section title="Security" description="Change your login password.">
                <form onSubmit={handleChangePassword} className="space-y-4">
                    <div>
                        <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Current password
                        </label>
                        <input
                            type="password"
                            className={inputCls}
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
                            className={inputCls}
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
                            className={`${inputCls} ${confirmPw && confirmPw !== newPw ? "border-red-400 focus:border-red-500 focus:ring-red-400" : ""}`}
                            value={confirmPw}
                            onChange={e => setConfirmPw(e.target.value)}
                            required
                            autoComplete="new-password"
                        />
                        {confirmPw && confirmPw !== newPw && (
                            <p className="mt-1 text-xs text-red-500">Passwords do not match</p>
                        )}
                    </div>
                    <div className="flex justify-end">
                        <button
                            type="submit"
                            disabled={pwSaving || !currentPw || !newPw || newPw !== confirmPw}
                            className="flex items-center gap-2 rounded-xl bg-gray-900 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-gray-700 disabled:opacity-50 dark:bg-gray-700 dark:hover:bg-gray-600"
                        >
                            {pwSaving && <Spinner />}
                            {pwSaving ? "Saving…" : "Update password"}
                        </button>
                    </div>
                </form>
            </Section>
        </div>
    );
}
