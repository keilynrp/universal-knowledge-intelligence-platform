import type { NextConfig } from "next";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
// Server-side rewrite target: use Docker-internal URL in production to avoid
// hairpin NAT issues when the Next.js container tries to reach the public URL.
const BACKEND_INTERNAL = process.env.BACKEND_INTERNAL_URL ?? BACKEND_URL;

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  compress: true,

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options",           value: "DENY" },
          { key: "X-Content-Type-Options",     value: "nosniff" },
          { key: "X-XSS-Protection",           value: "1; mode=block" },
          { key: "Referrer-Policy",            value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy",         value: "camera=(), microphone=(), geolocation=()" },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.googletagmanager.com",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob: https:",
              "font-src 'self'",
              `connect-src 'self' ${BACKEND_URL} ${BACKEND_URL.replace(/^http/, "ws")}`,
              "frame-ancestors 'none'",
            ].join("; "),
          },
        ],
      },
    ];
  },

  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${BACKEND_INTERNAL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
