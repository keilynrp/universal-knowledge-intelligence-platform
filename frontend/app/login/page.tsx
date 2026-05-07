"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "../contexts/AuthContext";
import { useBranding } from "../contexts/BrandingContext";
import { BrandLockup } from "../components/ukip";
import { API_BASE } from "../../lib/api";

function LoginPageContent() {
  const { login, isAuthenticated } = useAuth();
  const { branding } = useBranding();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [activeSlide, setActiveSlide] = useState(0);

  const stakeholderSlides = [
    {
      eyebrow: "Universidades",
      title: "Convierte producción académica en inteligencia institucional.",
      body: "Unifica publicaciones, autores, afiliaciones y citas para tomar decisiones con trazabilidad y menos trabajo manual.",
      metricLabel: "Cobertura institucional",
      metricValue: "74%",
      metricDelta: "+12pp",
      insightLabel: "Registros armonizados",
      insightValue: "1,580",
      accent: "from-violet-500 to-cyan-400",
    },
    {
      eyebrow: "Centros de investigación",
      title: "Detecta capacidades, brechas y colaboración científica.",
      body: "UKIP transforma ingestas dispersas en portafolios consultables, enriquecidos y listos para análisis por dominio.",
      metricLabel: "Enriquecimiento",
      metricValue: "61%",
      metricDelta: "+8.1%",
      insightLabel: "Aristas de conocimiento",
      insightValue: "12.4K",
      accent: "from-cyan-400 to-emerald-300",
    },
    {
      eyebrow: "Bibliotecas y repositorios",
      title: "Publica portales de catálogo limpios para consulta real.",
      body: "Crea experiencias tipo OPAC con facetas, registros verticales y fichas completas sin duplicar la data de ingesta.",
      metricLabel: "Calidad promedio",
      metricValue: "0.73",
      metricDelta: "+0.03",
      insightLabel: "Portales activos",
      insightValue: "08",
      accent: "from-violet-500 to-fuchsia-400",
    },
  ];
  const currentSlide = stakeholderSlides[activeSlide];

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

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveSlide((current) => (current + 1) % stakeholderSlides.length);
    }, 6500);

    return () => window.clearInterval(timer);
  }, [stakeholderSlides.length]);

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
              <p className="ukip-kicker text-violet-700 dark:text-violet-300">Semantic Intelligence</p>
              <h1 className="mt-3 text-3xl font-semibold tracking-[-0.025em] text-slate-950 dark:text-[var(--ukip-text-strong)]">
                Iniciar sesión
              </h1>
              <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-[var(--ukip-muted)]">
                Accede a {branding.platform_name || "UKIP"} para gestionar catálogos, enriquecimiento y portafolios de investigación.
              </p>
            </div>

            <button
              onClick={() => window.location.href = `${API_BASE}/sso/login`}
              className="ukip-focus flex h-12 w-full items-center justify-center gap-3 rounded-full border border-slate-200 bg-white px-4 text-sm font-bold text-slate-700 shadow-sm transition hover:border-violet-200 hover:bg-violet-50 dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-text)] dark:hover:bg-violet-500/10"
            >
              <svg className="h-4 w-4 text-violet-600" aria-hidden="true" focusable="false" data-prefix="fab" data-icon="google" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 488 512">
                <path fill="currentColor" d="M488 261.8C488 403.3 391.1 504 248 504 110.8 504 0 393.2 0 256S110.8 8 248 8c66.8 0 123 24.5 166.3 64.9l-67.5 64.9C258.5 52.6 94.3 116.6 94.3 256c0 86.5 69.1 156.6 153.7 156.6 98.2 0 135-70.4 140.8-106.9H248v-85.3h236.1c2.3 12.7 3.9 24.9 3.9 41.4z" />
              </svg>
              Continuar con SSO
            </button>

            <div className="my-6 flex items-center gap-3">
              <div className="h-px flex-1 bg-slate-200 dark:bg-white/10" />
              <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">
                o usar credenciales
              </span>
              <div className="h-px flex-1 bg-slate-200 dark:bg-white/10" />
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-[0.12em] text-slate-700 dark:text-[var(--ukip-text)]">
                  Usuario
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
                    Contraseña
                  </label>
                  <span className="text-xs font-semibold text-violet-600 dark:text-violet-300">Acceso seguro</span>
                </div>
                <div className="relative mt-2">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoComplete="current-password"
                    placeholder="Min. 8 caracteres"
                    className="ukip-focus h-12 w-full rounded-full border border-slate-200 bg-slate-50 px-5 pr-12 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-violet-300 focus:bg-white dark:border-white/10 dark:bg-white/5 dark:text-[var(--ukip-text)] dark:focus:bg-white/10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1.5 text-slate-400 transition hover:text-violet-600 dark:text-white/40 dark:hover:text-violet-300"
                    aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
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
                  Recordarme
                </label>
                <span className="font-semibold text-violet-600 dark:text-violet-300">¿Olvidaste tu contraseña?</span>
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
                {loading ? "Ingresando..." : `Entrar a ${branding.platform_name || "UKIP"}`}
              </button>
            </form>

            <p className="mt-8 text-center text-xs text-slate-400 dark:text-[var(--ukip-muted)]">
              © 2026 {branding.platform_name || "UKIP"}. {branding.footer_text || "Research Intelligence Platform"}.
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
                <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-white/60">UKIP Narrative</p>
                <p className="mt-1 text-sm font-semibold text-white/80">Research intelligence by stakeholder</p>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setActiveSlide((current) => (current - 1 + stakeholderSlides.length) % stakeholderSlides.length)}
                  className="flex h-9 w-9 items-center justify-center rounded-full border border-white/15 bg-white/10 text-white transition hover:bg-white/20"
                  aria-label="Slide anterior"
                >
                  ←
                </button>
                <button
                  type="button"
                  onClick={() => setActiveSlide((current) => (current + 1) % stakeholderSlides.length)}
                  className="flex h-9 w-9 items-center justify-center rounded-full border border-white/15 bg-white/10 text-white transition hover:bg-white/20"
                  aria-label="Slide siguiente"
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
                  aria-label={`Ir al slide ${index + 1}`}
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
