/**
 * Embed-route middleware: per-widget framing policy.
 *
 * Matches only /embed/:token. Fetches the widget's public config (which
 * includes `allowed_origins`) and emits a Content-Security-Policy whose
 * `frame-ancestors` reflects it. next.config.ts deliberately excludes /embed
 * from the global security-header rule, so this middleware is the single
 * source of CSP for embeds — no merge-order ambiguity with static headers.
 *
 * Failure posture is closed: config unreachable or malformed → the standard
 * app policy (deny framing). See lib/embedCsp.ts.
 */
import { NextRequest, NextResponse } from "next/server";
import { buildEmbedCsp, isWidgetToken } from "./lib/embedCsp";

const API_BASE = (
  process.env.BACKEND_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

const PUBLIC_API = (process.env.NEXT_PUBLIC_API_URL ?? API_BASE).replace(/\/$/, "");

/** Tiny TTL cache so every iframe load does not hit the config endpoint. */
const CACHE_TTL_MS = 60_000;
const cache = new Map<string, { origins: string | null; expires: number }>();

async function allowedOriginsFor(token: string): Promise<string | null> {
  // Validate BEFORE the value reaches a URL. A token that is not the exact
  // minted format never becomes a server-side request, so a crafted path can
  // neither traverse to another backend route nor probe internal endpoints.
  if (!isWidgetToken(token)) return null;

  const hit = cache.get(token);
  if (hit && hit.expires > Date.now()) return hit.origins;

  let origins: string | null = null;
  try {
    const response = await fetch(`${API_BASE}/embed/${encodeURIComponent(token)}/config`, {
      signal: AbortSignal.timeout(2_000),
    });
    if (response.ok) {
      const body = (await response.json()) as { allowed_origins?: unknown };
      origins = typeof body.allowed_origins === "string" ? body.allowed_origins : null;
    }
  } catch {
    origins = null; // fail closed
  }

  cache.set(token, { origins, expires: Date.now() + CACHE_TTL_MS });
  return origins;
}

export async function middleware(request: NextRequest) {
  const token = request.nextUrl.pathname.split("/")[2] ?? "";
  const origins = await allowedOriginsFor(token);

  const response = NextResponse.next();
  response.headers.set("Content-Security-Policy", buildEmbedCsp(origins, PUBLIC_API));
  // Deliberately no X-Frame-Options here: it has no origin-list form, and its
  // presence would override the CSP in browsers that honour both.
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  return response;
}

export const config = {
  matcher: ["/embed/:token*"],
};
