# PATHS Frontend

Next.js 16 (App Router) web application for the PATHS hiring platform.
Covers the recruiter dashboard, candidate portal, admin + owner portals,
and all public marketing pages.

---

## Tech stack

| Concern | Library |
|---|---|
| Framework | Next.js 16 (App Router, React Server Components) |
| Styling | Tailwind CSS v4 + shadcn/ui component primitives |
| Data fetching | TanStack Query v5 |
| Forms | React Hook Form + Zod |
| Animation | Framer Motion |
| Charts | Recharts |
| State | Zustand (client-only global state) |
| Error monitoring | Sentry (`@sentry/nextjs`) |
| Font loading | `next/font/google` (Inter, Plus Jakarta Sans, JetBrains Mono, Cormorant Garamond) |

---

## Environment variables

Create `apps/web/.env.local` (git-ignored):

```env
# Backend API base URL (no trailing slash)
NEXT_PUBLIC_API_URL=http://localhost:8001

# Sentry (leave blank to disable)
NEXT_PUBLIC_SENTRY_DSN=
NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE=0.1

# Git SHA injected by CI — used as Sentry release tag
NEXT_PUBLIC_APP_VERSION=local

# Sentry source-map upload (CI only)
SENTRY_AUTH_TOKEN=
SENTRY_ORG=
SENTRY_PROJECT=
```

---

## Scripts

Run all commands from the **monorepo root** (`frontend/`):

```bash
# Install all packages
pnpm install

# Start dev server for the web app (port 3000)
pnpm --filter @paths/web dev

# Production build
pnpm --filter @paths/web build

# Start production server
pnpm --filter @paths/web start

# Lint
pnpm --filter @paths/web lint

# TypeScript type-check
pnpm --filter @paths/web exec tsc --noEmit

# Lighthouse CI (requires a running server on port 3000)
npx lhci autorun
```

---

## Route groups

| Group | Path prefix | Purpose |
|---|---|---|
| `(marketing)` | `/` `/pricing` `/about` `/legal/*` | Public marketing + legal pages |
| `(auth)` | `/login` `/register` `/forgot-password` | Auth flows |
| `(dashboard)` | `/dashboard/*` | Recruiter workspace |
| `(candidate)` | `/candidate/*` | Candidate portal |
| `(admin)` | `/admin/*` | Platform admin panel (superuser) |
| `(owner)` | `/owner/*` | Business intelligence for the platform owner |

---

## 3-layer API pattern

```
lib/api/index.ts            ← raw fetch helpers (getJson, postJson, …)
lib/api/<domain>.api.ts     ← typed wrappers per domain (jobs.api.ts, etc.)
lib/hooks/index.ts          ← TanStack Query hooks (useJobs, useCreateJob, …)
components/**               ← consume hooks; never call fetch() directly
```

---

## Design system notes

- **Colours**: CSS custom properties defined in `globals.css`; dark-mode via
  `next-themes`. Primary = `--primary` (indigo-600 light / indigo-400 dark).
- **Typography**: `font-sans` → Inter; `font-heading` → Plus Jakarta Sans;
  `font-mono` → JetBrains Mono; `font-display` → Cormorant Garamond
  (PATHS wordmark only).
- **Components**: built on `@base-ui/react` primitives styled with `cva` +
  `tailwind-merge`.  Use the existing component library before adding new ones.
- **Icons**: `lucide-react` exclusively.

---

## Cookie consent

The `CookieConsent` component in `src/components/layout/` manages GDPR opt-in.
Analytics and marketing cookies are only activated after explicit user consent.
The state is persisted in `localStorage` under the key `paths-cookie-consent`.

---

## Sentry integration

Three config files in the project root:
- `sentry.client.config.ts` — browser (loaded by the webpack plugin)
- `sentry.server.config.ts` — Node.js SSR (loaded via `src/instrumentation.ts`)
- `sentry.edge.config.ts` — Edge runtime middleware

`next.config.ts` wraps the config with `withSentryConfig` for source-map uploads.
