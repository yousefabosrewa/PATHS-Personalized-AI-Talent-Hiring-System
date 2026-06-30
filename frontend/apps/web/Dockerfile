# PATHS web (Next.js 16, standalone output) — multi-stage image.
#
# IMPORTANT: the build context MUST be the frontend *workspace root*
# (the dir containing pnpm-lock.yaml + pnpm-workspace.yaml), NOT apps/web,
# because pnpm needs the lockfile to do a --frozen-lockfile install.
# `frontend/docker-compose.yml` / the root compose set `context: ./frontend`
# (or `.`) with `dockerfile: apps/web/Dockerfile` accordingly.

FROM node:22-alpine AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

# ---- deps: install the whole workspace from the frozen lockfile ----
FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile

# ---- builder: compile @paths/web into .next/standalone ----
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/web/node_modules ./apps/web/node_modules
COPY . .

# NEXT_PUBLIC_* values are inlined into the client bundle at build time, so the
# browser-facing API URL has to be known here. The default targets a local
# docker-compose run where the backend is published on :8001.
ARG NEXT_PUBLIC_API_URL=http://localhost:8001
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1

RUN pnpm --filter @paths/web build

# ---- runner: minimal standalone server ----
FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nextjs

# In a monorepo the standalone bundle preserves the workspace layout, so
# server.js ends up at apps/web/server.js with node_modules hoisted to the root.
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/public ./apps/web/public

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "apps/web/server.js"]
