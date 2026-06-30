# Contributing to PATHS

Thank you for contributing!  This document covers branching, PR etiquette,
and code conventions so reviews stay fast and the codebase stays clean.

---

## Branching strategy

```
main          ← production; protected (no direct push)
develop       ← integration branch; all PRs target develop
feature/<id>  ← feature work tied to a PATHS-NNN task ID
fix/<id>      ← bug fixes
chore/<desc>  ← non-functional changes (deps, tooling, docs)
```

Example: `git checkout -b feature/PATHS-185-status-page`

---

## Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body]

[optional footer — e.g. Fixes PATHS-185]
```

Types: `feat` · `fix` · `chore` · `docs` · `test` · `refactor` · `perf`

Examples:
```
feat(billing): add Stripe proration preview endpoint
fix(auth): clear rate-limit counter on successful login
docs(runbooks): add billing incident procedure
```

---

## Pull requests

1. **One concern per PR** — mix of features + refactors is hard to review.
2. **Title = commit message format** (same Conventional Commits convention).
3. **Fill in the PR template** — Summary, Test plan, Screenshots if UI changed.
4. **No direct pushes to `main`** — the pre-commit hook enforces this.
5. **At least one approving review** before merging.
6. **CI must be green** — secrets scan, lint, tests, build all pass.

---

## Code conventions

### Backend (Python)

- Formatter / linter: **ruff** (`ruff format`, `ruff check --fix`)
- Type checking: **mypy** (informational; hard failure planned)
- All new settings in `app/core/config.py` as typed `pydantic-settings` fields
- New DB columns → new Alembic migration (`alembic revision --autogenerate`)
- New API routes → register the router in `app/main.py`
- Agent nodes → log `{run_id, type, org_id, status, node, duration_ms}`
- Raise `HTTPException` with explicit `status_code`; never return `None` where
  a 404 is correct.

### Frontend (TypeScript / React)

- Formatter: **Prettier** (via `eslint-config-next`)
- No `any` — use proper types or `unknown` + narrowing
- All API calls go through `lib/api/` → `lib/hooks/` — never `fetch()` in
  components
- Server Components by default; add `"use client"` only when required
  (event handlers, hooks, browser APIs)
- `tailwind-merge` + `cva` for conditional class names — no string
  interpolation of class names
- Icons: `lucide-react` only — do not import from other icon libraries

---

## Pre-commit hooks

Install once after cloning:

```bash
pip install pre-commit
pre-commit install
```

Hooks run automatically on `git commit`:
- **gitleaks** — blocks commits containing secrets
- **ruff** — Python lint + format check
- **trailing-whitespace**, **end-of-file-fixer**, **check-yaml**, etc.

Run manually against all files: `pre-commit run --all-files`

---

## Testing

```bash
# Backend — must pass with ≥ 60 % coverage
cd backend && pytest tests/ --cov=app --cov-fail-under=60

# Frontend — run when tests exist
cd frontend && pnpm --filter @paths/web test
```

Add tests for:
- Every new API endpoint (at least a smoke test)
- Every new service function with business logic
- Any security-sensitive path (auth, rate limiting, tenant isolation)
