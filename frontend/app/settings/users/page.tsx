"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../components/ui";
import { apiFetch } from "../../../lib/api";
import UserAvatar from "../../components/UserAvatar";
import PasswordStrength from "../../components/PasswordStrength";

// ── Types ─────────────────────────────────────────────────────────────────────

type UserRole = "super_admin" | "admin" | "editor" | "viewer";

interface UserRecord {
  id: number;
  username: string;
  email: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string | null;
  avatar_url?: string | null;
}

interface UserStats {
  total: number;
  active: number;
  inactive: number;
  by_role: Record<string, number>;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const ROLE_LABELS: Record<UserRole, string> = {
  super_admin: "Super Admin",
  admin:       "Admin",
  editor:      "Editor",
  viewer:      "Viewer",
};

const ROLE_COLORS: Record<UserRole, string> = {
  super_admin: "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400",
  admin:       "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400",
  editor:      "bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400",
  viewer:      "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300",
};

const ROLE_AVATAR_BG: Record<UserRole, string> = {
  super_admin: "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400",
  admin:       "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400",
  editor:      "bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400",
  viewer:      "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
};

const inputCls = "h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white";

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: number; sub?: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">{label}</span>
      <span className="text-2xl font-bold text-gray-900 dark:text-white">{value}</span>
      {sub && <span className="text-xs text-gray-400">{sub}</span>}
    </div>
  );
}

// ── New / Edit user slide-over ─────────────────────────────────────────────────

interface UserFormProps {
  initial?: Partial<UserRecord>;
  onClose: () => void;
  onSaved: () => void;
  toast: (msg: string, v?: any) => void;
}

function UserFormSlider({ initial, onClose, onSaved, toast }: UserFormProps) {
  const isEdit = !!initial?.id;
  const [form, setForm] = useState({
    username: initial?.username ?? "",
    email:    initial?.email ?? "",
    password: "",
    role:     (initial?.role ?? "viewer") as UserRole,
  });
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isEdit && form.password.length < 8) {
      toast("Password must be at least 8 characters", "error");
      return;
    }
    setSaving(true);
    try {
      const body: Record<string, unknown> = { role: form.role };
      if (form.email) body.email = form.email;
      if (!isEdit) {
        body.username = form.username;
        body.password = form.password;
      } else {
        if (form.password) body.password = form.password;
      }

      const res = await apiFetch(isEdit ? `/users/${initial!.id}` : "/users", {
        method: isEdit ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Request failed");
      }
      toast(isEdit ? "User updated" : `User "${form.username}" created`, "success");
      onSaved();
      onClose();
    } catch (err: any) {
      toast(err.message || "Error", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    /* Backdrop */
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative flex h-full w-full max-w-md flex-col bg-white shadow-2xl dark:bg-gray-900">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-800">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">
            {isEdit ? `Edit "${initial?.username}"` : "New User"}
          </h2>
          <button onClick={onClose} className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex flex-1 flex-col overflow-y-auto px-6 py-5">
          <div className="space-y-4 flex-1">
            {!isEdit && (
              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Username <span className="text-red-500">*</span>
                </label>
                <input
                  className={inputCls}
                  value={form.username}
                  onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                  required
                  minLength={3}
                  maxLength={50}
                  placeholder="johndoe"
                  autoComplete="username"
                />
              </div>
            )}

            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">Email</label>
              <input
                type="email"
                className={inputCls}
                value={form.email ?? ""}
                onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                placeholder="john@example.com"
                autoComplete="email"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                {isEdit ? "New password" : "Password"}{" "}
                <span className="font-normal text-gray-400">{isEdit ? "(leave blank to keep)" : "*"}</span>
              </label>
              <input
                type="password"
                className={inputCls}
                value={form.password}
                onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                {...(!isEdit && { required: true, minLength: 8 })}
                autoComplete="new-password"
                placeholder={isEdit ? "••••••••" : ""}
              />
              <PasswordStrength password={form.password} />
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
                Role <span className="text-red-500">*</span>
              </label>
              <select
                className={inputCls}
                value={form.role}
                onChange={e => setForm(f => ({ ...f, role: e.target.value as UserRole }))}
              >
                <option value="viewer">Viewer — read-only access</option>
                <option value="editor">Editor — can create and edit data</option>
                <option value="admin">Admin — full data + config access</option>
                <option value="super_admin">Super Admin — full platform access</option>
              </select>
            </div>

            {/* Role description */}
            <div className="rounded-xl border border-gray-100 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-800/50">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {form.role === "viewer"      && "Can browse entities, analytics, and reports. No write access."}
                {form.role === "editor"      && "Can upload, edit entities, apply harmonization, and manage rules."}
                {form.role === "admin"       && "All editor permissions + manage data connectors, AI integrations, and RAG index."}
                {form.role === "super_admin" && "Full platform access including user management and all admin settings."}
              </p>
            </div>
          </div>

          {/* Footer */}
          <div className="mt-6 flex justify-end gap-3 border-t border-gray-100 pt-4 dark:border-gray-800">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-1.5 rounded-xl bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving && (
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              )}
              {isEdit ? "Save changes" : "Create user"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function UsersManagementPage() {
  const { user: me } = useAuth();
  const { toast } = useToast();

  const [users,   setUsers]   = useState<UserRecord[]>([]);
  const [stats,   setStats]   = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<number | null>(null);

  // Filters
  const [search,     setSearch]     = useState("");
  const [roleFilter, setRoleFilter] = useState<UserRole | "">("");
  const [statusFilter, setStatusFilter] = useState<"active" | "inactive" | "">("");

  // Slide-over state
  const [slideOver, setSlideOver] = useState<{ mode: "create" | "edit"; user?: UserRecord } | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [uRes, sRes] = await Promise.all([
        apiFetch("/users"),
        apiFetch("/users/stats"),
      ]);
      if (uRes.ok) setUsers(await uRes.json());
      if (sRes.ok) setStats(await sRes.json());
    } catch {
      toast("Failed to load users", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // ── Filtered list ──────────────────────────────────────────────────────────

  const filtered = users.filter(u => {
    if (search) {
      const q = search.toLowerCase();
      if (!u.username.toLowerCase().includes(q) && !(u.email ?? "").toLowerCase().includes(q)) return false;
    }
    if (roleFilter && u.role !== roleFilter) return false;
    if (statusFilter === "active"   && !u.is_active) return false;
    if (statusFilter === "inactive" &&  u.is_active) return false;
    return true;
  });

  // ── Actions ────────────────────────────────────────────────────────────────

  async function handleRoleChange(userId: number, newRole: UserRole) {
    setActionId(userId);
    try {
      const res = await apiFetch(`/users/${userId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: newRole }),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail); }
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, role: newRole } : u));
      toast("Role updated", "success");
    } catch (err: any) {
      toast(err.message || "Failed to update role", "error");
    } finally {
      setActionId(null);
    }
  }

  async function handleToggleActive(u: UserRecord) {
    if (u.id === me?.id) { toast("Cannot change your own account status", "error"); return; }
    if (u.is_active && !confirm(`Deactivate "${u.username}"? They will lose access immediately.`)) return;
    setActionId(u.id);
    try {
      const res = u.is_active
        ? await apiFetch(`/users/${u.id}`, { method: "DELETE" })
        : await apiFetch(`/users/${u.id}/activate`, { method: "POST" });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail); }
      setUsers(prev => prev.map(x => x.id === u.id ? { ...x, is_active: !u.is_active } : x));
      setStats(prev => prev ? {
        ...prev,
        active:   prev.active   + (u.is_active ? -1 : 1),
        inactive: prev.inactive + (u.is_active ?  1 : -1),
      } : prev);
      toast(u.is_active ? `"${u.username}" deactivated` : `"${u.username}" reactivated`, u.is_active ? "warning" : "success");
    } catch (err: any) {
      toast(err.message || "Action failed", "error");
    } finally {
      setActionId(null);
    }
  }

  // ── Guard ──────────────────────────────────────────────────────────────────

  if (me && me.role !== "super_admin") {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-gray-400">
        <svg className="h-10 w-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
        <p className="mt-3 text-sm font-medium">Super Admin access required</p>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">User Management</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Manage accounts, roles, and access for your platform users
          </p>
        </div>
        <button
          onClick={() => setSlideOver({ mode: "create" })}
          className="flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-700"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New User
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Total"    value={stats.total} />
          <StatCard label="Active"   value={stats.active} />
          <StatCard label="Inactive" value={stats.inactive} />
          <StatCard
            label="Roles"
            value={Object.keys(stats.by_role).length}
            sub={Object.entries(stats.by_role)
              .sort((a, b) => b[1] - a[1])
              .map(([r, n]) => `${n} ${ROLE_LABELS[r as UserRole] ?? r}`)
              .join(" · ")}
          />
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Search */}
        <div className="relative flex-1 min-w-[180px] max-w-xs">
          <svg className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            className="h-9 w-full rounded-lg border border-gray-200 bg-white pl-8 pr-3 text-sm outline-none transition focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white"
            placeholder="Search users…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        {/* Role filter */}
        <select
          className="h-9 rounded-lg border border-gray-200 bg-white px-2.5 text-sm text-gray-700 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
          value={roleFilter}
          onChange={e => setRoleFilter(e.target.value as UserRole | "")}
        >
          <option value="">All roles</option>
          <option value="super_admin">Super Admin</option>
          <option value="admin">Admin</option>
          <option value="editor">Editor</option>
          <option value="viewer">Viewer</option>
        </select>

        {/* Status filter */}
        <select
          className="h-9 rounded-lg border border-gray-200 bg-white px-2.5 text-sm text-gray-700 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value as "active" | "inactive" | "")}
        >
          <option value="">All statuses</option>
          <option value="active">Active only</option>
          <option value="inactive">Inactive only</option>
        </select>

        {/* Clear filters */}
        {(search || roleFilter || statusFilter) && (
          <button
            onClick={() => { setSearch(""); setRoleFilter(""); setStatusFilter(""); }}
            className="text-xs text-blue-600 hover:underline dark:text-blue-400"
          >
            Clear filters
          </button>
        )}

        <span className="ml-auto text-xs text-gray-400">{filtered.length} user{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {/* Users table */}
      <div className="overflow-x-auto rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <svg className="h-6 w-6 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-gray-400">
            <svg className="h-10 w-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <p className="mt-2 text-sm">No users match your filters</p>
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-800">
                {["User", "Email", "Role", "Status", "Joined", "Actions"].map(h => (
                  <th key={h} className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {filtered.map(u => {
                const isMe = u.id === me?.id;
                const busy = actionId === u.id;
                return (
                  <tr
                    key={u.id}
                    className={`transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50 ${!u.is_active ? "opacity-60" : ""}`}
                  >
                    {/* User */}
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <UserAvatar username={u.username} role={u.role} avatarUrl={(u as any).avatar_url} size="md" />
                        <div>
                          <p className="font-medium text-gray-900 dark:text-white">{u.username}</p>
                          {isMe && <p className="text-[10px] font-semibold text-blue-500">you</p>}
                        </div>
                      </div>
                    </td>

                    {/* Email */}
                    <td className="px-5 py-3.5 text-gray-500 dark:text-gray-400">
                      {u.email || <span className="text-gray-300 dark:text-gray-600">—</span>}
                    </td>

                    {/* Role */}
                    <td className="px-5 py-3.5">
                      {isMe ? (
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${ROLE_COLORS[u.role]}`}>
                          {ROLE_LABELS[u.role]}
                        </span>
                      ) : (
                        <select
                          value={u.role}
                          onChange={e => handleRoleChange(u.id, e.target.value as UserRole)}
                          disabled={busy || !u.is_active}
                          className="h-7 rounded-lg border border-gray-200 bg-white px-2 text-xs font-medium text-gray-700 outline-none transition focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
                        >
                          <option value="viewer">Viewer</option>
                          <option value="editor">Editor</option>
                          <option value="admin">Admin</option>
                          <option value="super_admin">Super Admin</option>
                        </select>
                      )}
                    </td>

                    {/* Status */}
                    <td className="px-5 py-3.5">
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        u.is_active
                          ? "bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400"
                          : "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400"
                      }`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${u.is_active ? "bg-green-500" : "bg-gray-400"}`} />
                        {u.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>

                    {/* Joined */}
                    <td className="px-5 py-3.5 text-xs text-gray-400 dark:text-gray-500">
                      {formatDate(u.created_at)}
                    </td>

                    {/* Actions */}
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-1">
                        {/* Edit */}
                        {!isMe && (
                          <button
                            onClick={() => setSlideOver({ mode: "edit", user: u })}
                            disabled={busy}
                            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-40 dark:hover:bg-gray-700 dark:hover:text-gray-200"
                            title="Edit user"
                          >
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                            </svg>
                          </button>
                        )}

                        {/* Activate / Deactivate toggle */}
                        {!isMe && (
                          <button
                            onClick={() => handleToggleActive(u)}
                            disabled={busy}
                            className={`rounded-lg p-1.5 disabled:opacity-40 transition-colors ${
                              u.is_active
                                ? "text-gray-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10 dark:hover:text-red-400"
                                : "text-gray-400 hover:bg-green-50 hover:text-green-600 dark:hover:bg-green-500/10 dark:hover:text-green-400"
                            }`}
                            title={u.is_active ? "Deactivate user" : "Reactivate user"}
                          >
                            {busy ? (
                              <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                              </svg>
                            ) : u.is_active ? (
                              /* Ban icon */
                              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                              </svg>
                            ) : (
                              /* Check-circle icon */
                              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                            )}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Slide-over */}
      {slideOver && (
        <UserFormSlider
          initial={slideOver.mode === "edit" ? slideOver.user : undefined}
          onClose={() => setSlideOver(null)}
          onSaved={fetchAll}
          toast={toast}
        />
      )}
    </div>
  );
}
