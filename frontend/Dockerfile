# ── Stage 1: deps ────────────────────────────────────────────────────────────
FROM node:22-alpine AS deps
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline

# ── Stage 2: builder ─────────────────────────────────────────────────────────
FROM node:22-alpine AS builder
WORKDIR /app

# Build-time env (injected by docker-compose args)
ARG NEXT_PUBLIC_API_URL=https://api.ukip.inbounduxd.com
ARG BACKEND_INTERNAL_URL=http://ukip-backend:8000
ARG NEXT_PUBLIC_APP_VERSION=local
ARG APP_VERSION=local
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV BACKEND_INTERNAL_URL=$BACKEND_INTERNAL_URL
ENV NEXT_PUBLIC_APP_VERSION=$NEXT_PUBLIC_APP_VERSION
ENV UKIP_APP_VERSION=$APP_VERSION
LABEL org.opencontainers.image.revision=$APP_VERSION

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build

# ── Stage 3: runner ──────────────────────────────────────────────────────────
FROM node:22-alpine AS runner
WORKDIR /app

ARG NEXT_PUBLIC_APP_VERSION=local
ARG APP_VERSION=local
ENV NODE_ENV=production
ENV PORT=3004
ENV HOSTNAME=0.0.0.0
ENV NEXT_PUBLIC_APP_VERSION=$NEXT_PUBLIC_APP_VERSION
ENV UKIP_APP_VERSION=$APP_VERSION
LABEL org.opencontainers.image.revision=$APP_VERSION

# Non-root user for security
RUN addgroup --system --gid 1001 nodejs \
 && adduser  --system --uid 1001 nextjs

# Copy only what Next.js needs at runtime
COPY --from=builder /app/public       ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3004

CMD ["node", "server.js"]
