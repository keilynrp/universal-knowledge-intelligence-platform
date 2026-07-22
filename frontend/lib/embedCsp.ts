/**
 * Per-widget Content-Security-Policy for the public embed page.
 *
 * The global next.config.ts policy forbids framing everywhere
 * (`frame-ancestors 'none'`), which is right for the app and fatal for
 * /embed/[token] — a page whose entire purpose is to be iframed by customer
 * sites. Embed routes are excluded from the global rule and receive their
 * policy from middleware instead, derived per widget from `allowed_origins`.
 *
 * Fail-closed: when the widget's origins cannot be determined (fetch failed,
 * empty value, malformed content), nobody may frame it. A restricted widget
 * must never become open because of an error.
 */

/**
 * Widget tokens are UUID4s minted server-side (`str(uuid.uuid4())`).
 *
 * The token arrives from the URL path and is interpolated into a *server-side*
 * fetch of the widget config, so an unvalidated value lets a caller steer that
 * request at other backend paths — including ones reachable only from inside
 * the network (CodeQL `js/request-forgery`). Matching the exact minted format
 * removes the class entirely rather than escaping around it.
 */
const UUID_V4 =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isWidgetToken(value: string): boolean {
  return UUID_V4.test(value);
}

/** True for values safe to place in a response header as an origin. */
function isHeaderSafeOrigin(value: string): boolean {
  return /^https?:\/\/[^\s;,]+$/.test(value);
}

export function buildFrameAncestors(allowedOrigins: string | null): string {
  const raw = (allowedOrigins ?? "").trim();
  if (raw === "*") return "frame-ancestors *";

  // Header-splitting control characters poison the whole value, not just one
  // segment — we cannot trust any part of a string that tried.
  if (/[\r\n\0]/.test(raw)) return "frame-ancestors 'none'";

  const origins = raw
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0 && isHeaderSafeOrigin(part));

  if (origins.length === 0) return "frame-ancestors 'none'";
  return `frame-ancestors ${origins.join(" ")}`;
}

/**
 * Full CSP for an embed response: the app's baseline directives with the
 * widget's frame-ancestors. Mirrors next.config.ts — if a directive changes
 * there, change it here too (asserted by embedCsp.test.ts on the stable parts).
 */
export function buildEmbedCsp(
  allowedOrigins: string | null,
  apiBase: string,
): string {
  const wsBase = apiBase.replace(/^http/, "ws");
  return [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https:",
    "font-src 'self'",
    `connect-src 'self' ${apiBase} ${wsBase}`,
    buildFrameAncestors(allowedOrigins),
  ].join("; ");
}
