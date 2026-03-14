/**
 * Centralized API configuration for UKIP frontend.
 *
 * In the browser all requests go through the Next.js proxy at /api/backend/*
 * so they stay on the same origin (no CORS / Private-Network-Access issues).
 * Server-side (SSR / API routes) hits the backend directly via NEXT_PUBLIC_API_URL.
 */
const DIRECT_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export const API_BASE =
  typeof window === "undefined"
    ? DIRECT_URL          // server-side: call backend directly
    : "/api/backend";     // browser: route through Next.js proxy (same-origin)

/**
 * Authenticated fetch wrapper.
 * - Reads the Bearer token from localStorage (key: "ukip_token") and attaches it.
 * - On HTTP 401, clears the stored token and redirects to /login.
 */
export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = typeof window !== "undefined" ? localStorage.getItem("ukip_token") : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error(`Cannot connect to backend at ${API_BASE}. Is the server running?`);
  }

  if (response.status === 401 && typeof window !== "undefined") {
    localStorage.removeItem("ukip_token");
    // Avoid redirect loop if already on /login
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }

  return response;
}
