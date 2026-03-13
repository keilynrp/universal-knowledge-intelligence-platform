"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "../contexts/AuthContext";
import UserAvatar from "./UserAvatar";

const ROLE_COLORS: Record<string, { pill: string; label: string }> = {
  super_admin: { pill: "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400",    label: "Super Admin" },
  admin:       { pill: "bg-orange-100 text-orange-700 dark:bg-orange-500/20 dark:text-orange-400", label: "Admin" },
  editor:      { pill: "bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400", label: "Editor" },
  viewer:      { pill: "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400",    label: "Viewer" },
};

export default function UserMenu() {
  const [open, setOpen] = useState(false);
  const { user, logout }  = useAuth();
  const router = useRouter();
  const ref    = useRef<HTMLDivElement>(null);

  // Close on click-outside
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  function handleLogout() {
    setOpen(false);
    logout();
    router.push("/login");
  }

  const role     = user?.role ?? "viewer";
  const roleInfo = ROLE_COLORS[role] ?? ROLE_COLORS.viewer;

  return (
    <div ref={ref} className="relative">
      {/* Trigger */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2.5 rounded-full pl-1 pr-3 py-1 transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
        aria-label="User menu"
      >
        {/* Avatar */}
        <UserAvatar username={user?.username ?? "?"} role={role} avatarUrl={user?.avatar_url} size="sm" />
        {/* Name + role — hidden on small screens */}
        <div className="hidden flex-col items-start leading-tight sm:flex">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
            {user?.display_name || user?.username || "…"}
          </span>
          <span className="text-[11px] font-medium capitalize text-gray-400 dark:text-gray-500">
            {role.replace("_", " ")}
          </span>
        </div>
        {/* Chevron */}
        <svg
          className={`hidden h-4 w-4 text-gray-400 transition-transform duration-200 sm:block ${open ? "rotate-180" : ""}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-12 z-50 w-60 overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-xl dark:border-gray-700 dark:bg-gray-900">
          {/* User info card */}
          <div className="flex flex-col items-center gap-2 bg-gray-50 px-4 py-5 dark:bg-gray-800/60">
            <UserAvatar username={user?.username ?? "?"} role={role} avatarUrl={user?.avatar_url} size="lg" />
            <div className="text-center">
              <p className="text-sm font-semibold text-gray-900 dark:text-white">
                {user?.display_name || user?.username || "—"}
              </p>
              {user?.display_name && (
                <p className="text-xs text-gray-400 dark:text-gray-500">@{user.username}</p>
              )}
              {user?.email && (
                <p className="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">
                  {user.email}
                </p>
              )}
              <span className={`mt-1.5 inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${roleInfo.pill}`}>
                {roleInfo.label}
              </span>
            </div>
          </div>

          {/* Menu items */}
          <div className="p-1.5">
            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-gray-700 transition-colors hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-800">
                <svg className="h-4 w-4 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </span>
              Settings
            </Link>

            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-gray-700 transition-colors hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-800">
                <svg className="h-4 w-4 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                </svg>
              </span>
              My Profile
            </Link>

            <div className="my-1.5 border-t border-gray-100 dark:border-gray-800" />

            <button
              onClick={handleLogout}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-red-600 transition-colors hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-50 dark:bg-red-500/10">
                <svg className="h-4 w-4 text-red-500 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
                </svg>
              </span>
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
