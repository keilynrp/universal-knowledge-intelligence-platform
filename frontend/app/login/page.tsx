"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "../contexts/AuthContext";
import { useBranding } from "../contexts/BrandingContext";
import { useLanguage } from "../contexts/LanguageContext";
import { BrandLockup } from "../components/ukip";
import { API_BASE } from "../../lib/api";

type PublicSsoSettings = {
  sso_enabled: boolean;
  sso_login_button_visible: boolean;
  sso_provider_label: string;
  sso_provider_configured: boolean;
};

function LoginPageContent() {
  const { login, isAuthenticated } = useAuth();
  const { branding } = useBranding();
  const { t } = useLanguage();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [resetEmail, setResetEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [resetMode, setResetMode] = useState<"login" | "request" | "confirm">("login");
  const [showPassword, setShowPassword] = useState(false);
  const [activeSlide, setActiveSlide] = useState(0);
  const [ssoSettings, setSsoSettings] = useState<PublicSsoSettings | null>(null);

  const platformName = branding.platform_name || "UKIP";
  const footerText = branding.footer_text || t("auth.login.footer_fallback");

  const stakeholderSlides = useMemo(() => [
    {
      eyebrow: t("auth.login.slide.universities.eyebrow"),
      title: t("auth.login.slide.universities.title"),
      body: t("auth.login.slide.universities.body"),
      metricLabel: t("auth.login.slide.universities.metric_label"),
      metricValue: "74%",
      metricDelta: "+12pp",
      insightLabel: t("auth.login.slide.universities.insight_label"),
      insightValue: "1,580",
      accent: "from-violet-500 to-cyan-400",
    },
    {
      eyebrow: t("auth.login.slide.research_centers.eyebrow"),
      title: t("auth.login.slide.research_centers.title"),
      body: t("auth.login.slide.research_centers.body"),
      metricLabel: t("auth.login.slide.research_centers.metric_label"),
      metricValue: "61%",
      metricDelta: "+8.1%",
      insightLabel: t("auth.login.slide.research_centers.insight_label"),
      insightValue: "12.4K",
      accent: "from-cyan-400 to-emerald-300",
    },
    {
      eyebrow: t("auth.login.slide.libraries.eyebrow"),
      title: t("auth.login.slide.libraries.title"),
      body: t("auth.login.slide.libraries.body"),
      metricLabel: t("auth.login.slide.libraries.metric_label"),
      metricValue: "0.73",
      metricDelta: "+0.03",
      insightLabel: t("auth.login.slide.libraries.insight_label"),
      insightValue: "08",
      accent: "from-violet-500 to-fuchsia-400",
    },
  ], [t]);
  const currentSlide = stakeholderSlides[activeSlide];
  const showSsoButton = Boolean(
    ssoSettings?.sso_enabled &&
    ssoSettings.sso_login_button_visible &&
    ssoSettings.sso_provider_configured,
  );
  const ssoProviderLabel = ssoSettings?.sso_provider_label || "SSO";

  // Handle SSO redirect token
  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      localStorage.setItem("ukip_token", token);
      // Wait a moment for context to catch up or just reload
      window.location.href = "/";
    }
    if (searchParams.get("reset_token")) {
      setResetMode("confirm");
    }
  }, [searchParams]);

  // Already authenticated → go straight to dashboard
  useEffect(() => {
    if (isAuthenticated) router.replace("/");
  }, [isAuthenticated, router]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveSlide((current) => (current + 1) % stakeholderSlides.length);
    }, 6500);

    return () => window.clearInterval(timer);
  }, [stakeholderSlides.length]);

  useEffect(() => {
    let mounted = true;
    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/auth/sso/settings`);
        if (!response.ok) return;
        const data = await response.json() as PublicSsoSettings;
        if (mounted) setSsoSettings(data);
      } catch {
        if (mounted) setSsoSettings(null);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(username, password);
      router.push("/");
    } catch {
      setError(t("auth.login.error"));
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordResetRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`${API_BASE}/auth/password-reset/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: resetEmail }),
      });
      if (!response.ok) throw new Error("reset request failed");
      const data = await response.json();
      if (data.sent === false && data.reason === "smtp_not_configured") {
        setError(t("auth.login.reset_smtp_unavailable"));
        return;
      }
      setNotice(t("auth.login.reset_request_sent"));
    } catch {
      setError(t("auth.login.reset_request_error"));
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordResetConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`${API_BASE}/auth/password-reset/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: searchParams.get("reset_token") ?? "",
          new_password: newPassword,
        }),
      });
      if (!response.ok) throw new Error("reset confirm failed");
      setNotice(t("auth.login.reset_complete"));
      setNewPassword("");
      setResetMode("login");
      router.replace("/login");
    } catch {
      setError(t("auth.login.reset_confirm_error"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#deddfb] px-4 py-8 text-[var(--ukip-text)] dark:bg-[var(--ukip-bg)]">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-[-10rem] top-[-8rem] h-96 w-96 rounded-full bg-white/60 blur-3xl dark:bg-violet-500/10" />
        <div className="absolute right-[-8rem] top-20 h-[28rem] w-[28rem] rounded-full bg-violet-400/20 blur-3xl dark:bg-violet-500/20" />
        <div className="absolute bottom-[-12rem] left-1/3 h-96 w-96 rounded-full bg-cyan-300/30 blur-3xl dark:bg-cyan-500/10" />
      </div>

      <section className="relative grid min-h-[640px] w-full max-w-6xl overflow-hidden rounded-[2rem] border border-white/70 bg-white shadow-[0_30px_100px_rgb(79_70_229_/_0.22)] dark:border-white/10 dark:bg-[var(--ukip-panel)] lg:grid-cols-[0.95fr_1.05fr]">
        <div className="flex items-center justify-center px-6 py-10 sm:px-10 lg:px-16">
          <div className="w-full max-w-sm">
            <div className="mb-10">
              <BrandLockup branding={branding} size="md" className="mb-8" />
              <p className="ukip-kicker text-violet-700 dark:text-violet-300">{t("auth.login.kicker")}</p>
              <h1 className="mt-3 text-3xl font-semibold tracking-[-0.025em] text-slate-950 dark:text-[var(--ukip-text-strong)]">
                {t("auth.login.title")}
              </h1>
              <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-[var(--ukip-muted)]">
                {t("auth.login.description", { platform: platformName })}
              </p>
            </div>

            {showSsoButton && (
              <>
                <button
                  onClick={() => window.location.href = `${API_BASE}/sso/login`}
                  className="ukip-focus flex h-12 w-full items-center justify-center gap-3 rounded-full border border-slate-200 bg-white px-4 text-sm font-bold text-slate-700 shadow-sm transition hover:border-violet-200 hover:bg-violet-50 dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-text)] dark:hover:bg-violet-500/10"
                >
                  <svg className="h-4 w-4 text-violet-600" aria-hidden="true" focusable="false" data-prefix="fab" data-icon="google" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 488 512">
                    <path fill="currentColor" d="M488 261.8C488 403.3 391.1 504 248 504 110.8 504 0 393.2 0 256S110.8 8 248 8c66.8 0 123 24.5 166.3 64.9l-67.5 64.9C258.5 52.6 94.3 116.6 94.3 256c0 86.5 69.1 156.6 153.7 156.6 98.2 0 135-70.4 140.8-106.9H248v-85.3h236.1c2.3 12.7 3.9 24.9 3.9 41.4z" />
                  </svg>
                  {t("auth.login.sso_with_provider", { provider: ssoProviderLabel })}
                </button>

                <div className="my-6 flex items-center gap-3">
                  <div className="h-px flex-1 bg-slate-200 dark:bg-white/10" />
                  <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">
                    {t("auth.login.credentials_divider")}
                  </span>
                  <div className="h-px flex-1 bg-slate-200 dark:bg-white/10" />
                </div>
              </>
            )}

            {resetMode === "request" && (
              <form onSubmit={handlePasswordResetRequest} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-[0.12em] text-slate-700 dark:text-[var(--ukip-text)]">
                    {t("auth.login.reset_email")}
                  </label>
                  <input
                    type="email"
                    value={resetEmail}
                    onChange={(e) => setResetEmail(e.target.value)}
                    required
                    autoComplete="email"
                    placeholder={t("settings.account.email_placeholder")}
                    className="ukip-focus mt-2 h-12 w-full rounded-full border border-slate-200 bg-slate-50 px-5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-violet-300 focus:bg-white dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-text)] dark:focus:bg-white/10"
                  />
                </div>
                {error && (
                  <p className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
                    {error}
                  </p>
                )}
                {notice && (
                  <p className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-200">
                    {notice}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  className="ukip-focus h-12 w-full rounded-full border border-transparent bg-[var(--ukip-primary)] px-5 text-sm font-semibold text-white shadow-[var(--ukip-glow-violet)] transition hover:bg-[var(--ukip-primary-strong)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {loading ? t("auth.login.reset_sending") : t("auth.login.reset_send_link")}
                </button>
                <button
                  type="button"
                  onClick={() => { setResetMode("login"); setError(""); setNotice(""); }}
                  className="w-full text-center text-xs font-semibold text-violet-600 dark:text-violet-300"
                >
                  {t("auth.login.back_to_login")}
                </button>
              </form>
            )}

            {resetMode === "confirm" && (
              <form onSubmit={handlePasswordResetConfirm} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-[0.12em] text-slate-700 dark:text-[var(--ukip-text)]">
                    {t("auth.login.new_password")}
                  </label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    minLength={8}
                    autoComplete="new-password"
                    placeholder={t("auth.login.new_password_placeholder")}
                    className="ukip-focus mt-2 h-12 w-full rounded-full border border-slate-200 bg-slate-50 px-5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-violet-300 focus:bg-white dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-text)] dark:focus:bg-white/10"
                  />
                </div>
                {error && (
                  <p className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
                    {error}
                  </p>
                )}
                {notice && (
                  <p className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-200">
                    {notice}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  className="ukip-focus h-12 w-full rounded-full border border-transparent bg-[var(--ukip-primary)] px-5 text-sm font-semibold text-white shadow-[var(--ukip-glow-violet)] transition hover:bg-[var(--ukip-primary-strong)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {loading ? t("settings.account.saving") : t("auth.login.reset_password")}
                </button>
              </form>
            )}

            {resetMode === "login" && (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-[0.12em] text-slate-700 dark:text-[var(--ukip-text)]">
                  {t("auth.username")}
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoComplete="username"
                  placeholder="superadmin"
                  className="ukip-focus mt-2 h-12 w-full rounded-full border border-slate-200 bg-slate-50 px-5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-violet-300 focus:bg-white dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-text)] dark:focus:bg-white/10"
                />
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-bold uppercase tracking-[0.12em] text-slate-700 dark:text-[var(--ukip-text)]">
                    {t("auth.password")}
                  </label>
                  <span className="text-xs font-semibold text-violet-600 dark:text-violet-300">{t("auth.login.secure_access")}</span>
                </div>
                <div className="relative mt-2">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoComplete="current-password"
                    placeholder={t("auth.login.password_placeholder")}
                    className="ukip-focus h-12 w-full rounded-full border border-slate-200 bg-slate-50 px-5 pr-12 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-violet-300 focus:bg-white dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-text)] dark:focus:bg-white/10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1.5 text-slate-400 transition hover:text-violet-600 dark:text-white/40 dark:hover:text-violet-300"
                    aria-label={showPassword ? t("auth.login.hide_password") : t("auth.login.show_password")}
                  >
                    {showPassword ? (
                      <svg className="h-4.5 w-4.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                        <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                        <line x1="1" y1="1" x2="23" y2="23" />
                      </svg>
                    ) : (
                      <svg className="h-4.5 w-4.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs">
                <label className="flex items-center gap-2 font-semibold text-slate-600 dark:text-[var(--ukip-muted)]">
                  <input type="checkbox" defaultChecked className="h-4 w-4 rounded border-violet-300 accent-violet-600" />
                  {t("auth.login.remember_me")}
                </label>
                <button
                  type="button"
                  onClick={() => { setResetMode("request"); setError(""); setNotice(""); setResetEmail(username); }}
                  className="font-semibold text-violet-600 dark:text-violet-300"
                >
                  {t("auth.login.forgot_password")}
                </button>
              </div>

              {error && (
                <p className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="ukip-focus h-12 w-full rounded-full border border-transparent bg-[var(--ukip-primary)] px-5 text-sm font-semibold text-white shadow-[var(--ukip-glow-violet)] transition hover:bg-[var(--ukip-primary-strong)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? t("auth.login.loading") : t("auth.login.submit", { platform: platformName })}
              </button>
            </form>
            )}

            <p className="mt-8 text-center text-xs text-slate-400 dark:text-[var(--ukip-muted)]">
              © 2026 {platformName}. {footerText}.
            </p>
          </div>
        </div>

        <div className="relative hidden overflow-hidden bg-gradient-to-br from-[#4f25d8] via-[#5b2df0] to-[#2b1497] p-10 text-white lg:block">
          <div className="absolute inset-0 opacity-40 [background-image:radial-gradient(circle_at_1px_1px,rgba(255,255,255,.32)_1px,transparent_0)] [background-size:22px_22px]" />
          <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full border border-white/15" />
          <div className="absolute left-12 top-24 h-40 w-40 rounded-full border border-white/15" />
          <div className="absolute right-0 top-0 h-32 w-48 bg-[#2b1497] [clip-path:polygon(0_0,100%_0,100%_100%)] opacity-75" />
          <div className="absolute bottom-0 right-0 h-48 w-52 bg-[#2b1497] [clip-path:polygon(100%_0,100%_100%,0_100%)] opacity-75" />

          <div className="relative flex h-full min-h-[560px] flex-col">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-white/60">{t("auth.login.narrative_label")}</p>
                <p className="mt-1 text-sm font-semibold text-white/80">{t("auth.login.narrative_subtitle")}</p>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setActiveSlide((current) => (current - 1 + stakeholderSlides.length) % stakeholderSlides.length)}
                  className="flex h-9 w-9 items-center justify-center rounded-full border border-white/15 bg-white/10 text-white transition hover:bg-white/20"
                  aria-label={t("auth.login.previous_slide")}
                >
                  ←
                </button>
                <button
                  type="button"
                  onClick={() => setActiveSlide((current) => (current + 1) % stakeholderSlides.length)}
                  className="flex h-9 w-9 items-center justify-center rounded-full border border-white/15 bg-white/10 text-white transition hover:bg-white/20"
                  aria-label={t("auth.login.next_slide")}
                >
                  →
                </button>
              </div>
            </div>

            <div className="relative mt-10 flex flex-1 items-center">
              <div className="grid w-full items-center gap-8">
                <div className="relative mx-auto w-full max-w-[30rem]">
                  <div className={`absolute -inset-6 rounded-[2rem] bg-gradient-to-br ${currentSlide.accent} opacity-35 blur-2xl transition-all`} />
                  <div className="relative rounded-[1.75rem] border border-white/20 bg-white/95 p-6 text-slate-950 shadow-2xl">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">{currentSlide.metricLabel}</p>
                        <p className="mt-2 font-mono text-4xl font-semibold tracking-[-0.035em]">{currentSlide.metricValue}</p>
                      </div>
                      <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">{currentSlide.metricDelta}</span>
                    </div>

                    <div className="mt-8 grid grid-cols-[1fr_auto] items-end gap-5">
                      <svg className="h-28 w-full" viewBox="0 0 260 110" fill="none" aria-hidden="true">
                        <path d="M4 84C28 76 42 44 66 52C91 60 98 23 124 29C150 35 145 74 173 67C204 59 217 35 256 43" stroke="#6D4AFF" strokeWidth="4" fill="none" />
                        <path d="M4 84C28 76 42 44 66 52C91 60 98 23 124 29C150 35 145 74 173 67C204 59 217 35 256 43V110H4V84Z" fill="url(#loginSlideChart)" opacity=".2" />
                        <circle cx="173" cy="67" r="5" fill="#6D4AFF" />
                        <defs>
                          <linearGradient id="loginSlideChart" x1="130" y1="29" x2="130" y2="110">
                            <stop stopColor="#6D4AFF" />
                            <stop offset="1" stopColor="#6D4AFF" stopOpacity="0" />
                          </linearGradient>
                        </defs>
                      </svg>
                      <div className="rounded-2xl bg-slate-950 px-4 py-3 text-white shadow-xl">
                        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-white/50">{currentSlide.insightLabel}</p>
                        <p className="mt-1 font-mono text-2xl font-semibold">{currentSlide.insightValue}</p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mx-auto max-w-md text-center">
                  <span className="inline-flex rounded-full border border-white/15 bg-white/10 px-4 py-1.5 text-[11px] font-bold uppercase tracking-[0.18em] text-white/75">
                    {currentSlide.eyebrow}
                  </span>
                  <h2 className="mt-5 text-3xl font-semibold leading-tight tracking-[-0.025em]">
                    {currentSlide.title}
                  </h2>
                  <p className="mt-4 text-sm leading-6 text-white/75">
                    {currentSlide.body}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-8 flex items-center justify-center gap-2">
              {stakeholderSlides.map((slide, index) => (
                <button
                  key={slide.eyebrow}
                  type="button"
                  onClick={() => setActiveSlide(index)}
                  className={`h-2 rounded-full transition-all ${activeSlide === index ? "w-8 bg-white" : "w-2 bg-white/40 hover:bg-white/70"}`}
                  aria-label={t("auth.login.go_to_slide", { number: index + 1 })}
                />
              ))}
            </div>
          </div>
        </div>
      </section>
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
