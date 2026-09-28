"use client";

import { createContext, useContext, useState, useEffect, useCallback, useSyncExternalStore } from "react";
import { API_BASE } from "@/lib/api";

interface User {
  id: number;
  username: string;
  role: string;
  email: string | null;
  is_active: boolean;
  avatar_url?: string | null;
  display_name?: string | null;
  bio?: string | null;
  created_at?: string | null;
}

interface AuthContextType {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  hydrated: boolean;
  login: (username: string, password: string) => Promise<void>;
  loginWithSsoCode: (code: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  updateAvatarUrl: (url: string | null) => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

const AUTH_EVENT = "ukip-auth-change";

function subscribeAuth(onStoreChange: () => void): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }
  const handleChange = () => onStoreChange();
  window.addEventListener("storage", handleChange);
  window.addEventListener(AUTH_EVENT, handleChange);
  return () => {
    window.removeEventListener("storage", handleChange);
    window.removeEventListener(AUTH_EVENT, handleChange);
  };
}

function getTokenSnapshot(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return localStorage.getItem("ukip_token");
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const token: string | null = useSyncExternalStore<string | null>(
    subscribeAuth,
    getTokenSnapshot,
    () => null,
  );
  const hydrated = useSyncExternalStore<boolean>(
    () => () => {},
    () => true,
    () => false,
  );
  const [user, setUser]   = useState<User | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }

    let cancelled = false;
    fetch(`${API_BASE}/users/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data) {
          setUser(data);
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [token]);

  const refreshUser = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/users/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setUser(await res.json());
    } catch { /* non-critical */ }
  }, [token]);

  const updateAvatarUrl = useCallback((url: string | null) => {
    setUser(prev => prev ? { ...prev, avatar_url: url } : prev);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const body = new URLSearchParams({ username, password });
    const res = await fetch(`${API_BASE}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    });
    if (!res.ok) {
      throw new Error("Invalid credentials");
    }
    const data = await res.json();
    localStorage.setItem("ukip_token", data.access_token);
    window.dispatchEvent(new Event(AUTH_EVENT));
  }, []);

  // The SSO callback redirects with a single-use code, never a token (issue 408).
  const loginWithSsoCode = useCallback(async (code: string) => {
    const res = await fetch(`${API_BASE}/sso/exchange`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    if (!res.ok) {
      throw new Error("Invalid or expired SSO code");
    }
    const data = await res.json();
    localStorage.setItem("ukip_token", data.access_token);
    window.dispatchEvent(new Event(AUTH_EVENT));
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("ukip_token");
    setUser(null);
    window.dispatchEvent(new Event(AUTH_EVENT));
  }, []);

  const resolvedUser = token ? user : null;

  return (
    <AuthContext.Provider value={{ token, user: resolvedUser, isAuthenticated: !!token, hydrated, login, loginWithSsoCode, logout, refreshUser, updateAvatarUrl }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
