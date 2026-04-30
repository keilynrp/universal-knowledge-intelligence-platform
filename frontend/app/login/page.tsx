"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "../contexts/AuthContext";
import { API_BASE } from "../../lib/api";

function LoginPageContent() {
  const { login, isAuthenticated } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Handle SSO redirect token
  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      localStorage.setItem("ukip_token", token);
      // Wait a moment for context to catch up or just reload
      window.location.href = "/";
    }
  }, [searchParams]);

  // Already authenticated → go straight to dashboard
  useEffect(() => {
    if (isAuthenticated) router.replace("/");
  }, [isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(username, password);
      router.push("/");
    } catch {
      setError("Invalid username or password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--ukip-bg)] px-4 text-[var(--ukip-text)]">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute left-[-8rem] top-[-8rem] h-96 w-96 rounded-full bg-violet-500/15 blur-3xl" />
        <div className="absolute right-[-10rem] top-24 h-96 w-96 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="absolute bottom-[-10rem] left-1/2 h-80 w-80 -translate-x-1/2 rounded-full bg-emerald-500/10 blur-3xl" />
      </div>

      <div className="ukip-panel relative w-full max-w-md p-8">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-violet-400/25 bg-violet-500/15 text-sm font-black tracking-[0.16em] text-violet-700 shadow-[var(--ukip-glow-violet)] dark:text-violet-100">
            UK
          </div>
          <p className="ukip-kicker">Semantic Intelligence</p>
          <h1 className="mt-2 text-3xl font-bold text-[var(--ukip-text-strong)]">UKIP</h1>
          <p className="mt-2 text-sm text-[var(--ukip-muted)]">
            Universal Knowledge Intelligence Platform
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-semibold text-[var(--ukip-text)]">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
              className="ukip-focus mt-1 w-full rounded-[var(--ukip-radius-md)] border border-[var(--ukip-border)] bg-[var(--ukip-panel-strong)] px-3 py-2 text-sm text-[var(--ukip-text)] outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-[var(--ukip-text)]">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="ukip-focus mt-1 w-full rounded-[var(--ukip-radius-md)] border border-[var(--ukip-border)] bg-[var(--ukip-panel-strong)] px-3 py-2 text-sm text-[var(--ukip-text)] outline-none"
            />
          </div>

          {error && (
            <p className="rounded-lg border border-red-400/20 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="ukip-focus w-full rounded-[var(--ukip-radius-md)] border border-transparent bg-[var(--ukip-primary)] px-4 py-2 text-sm font-semibold text-white shadow-[var(--ukip-glow-violet)] transition-colors hover:bg-[var(--ukip-primary-strong)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="mt-6 flex items-center justify-center">
            <span className="bg-[var(--ukip-panel)] px-2 text-sm text-[var(--ukip-muted)]">
                or
            </span>
        </div>

        <button
            onClick={() => window.location.href = `${API_BASE}/sso/login`}
            className="ukip-focus mt-6 flex w-full items-center justify-center gap-2 rounded-[var(--ukip-radius-md)] border border-[var(--ukip-border)] bg-[var(--ukip-panel-strong)] px-4 py-2 text-sm font-semibold text-[var(--ukip-text)] shadow-sm transition-colors hover:border-violet-400/40 hover:bg-violet-500/10"
        >
            <svg className="h-4 w-4" aria-hidden="true" focusable="false" data-prefix="fab" data-icon="google" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 488 512">
            <path fill="currentColor" d="M488 261.8C488 403.3 391.1 504 248 504 110.8 504 0 393.2 0 256S110.8 8 248 8c66.8 0 123 24.5 166.3 64.9l-67.5 64.9C258.5 52.6 94.3 116.6 94.3 256c0 86.5 69.1 156.6 153.7 156.6 98.2 0 135-70.4 140.8-106.9H248v-85.3h236.1c2.3 12.7 3.9 24.9 3.9 41.4z"></path>
            </svg>
            Sign in with SSO
        </button>      
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginPageContent />
    </Suspense>
  );
}
