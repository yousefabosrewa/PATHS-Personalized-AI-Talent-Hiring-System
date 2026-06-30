# PATHS Backend

FastAPI service providing the hiring-platform API, LangGraph agents,
PostgreSQL/AGE persistence, Qdrant vector search, and Stripe billing.

---

## Environment variables

Copy `.env.example` to `.env` and fill in the values.

### Required

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://...` | Full async PostgreSQL DSN |
| `SECRET_KEY` | `CHANGE-ME-...` | JWT signing key — **must be changed in production** |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant server |

### Important optional

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | `development` \| `staging` \| `production` |
| `DEBUG` | `true` | Set to `false` in production |
| `OPENROUTER_API_KEY` | `""` | LLM inference (scoring, DSS, sourcing agents) |
| `STRIPE_SECRET_KEY` | `""` | Billing |
| `STRIPE_WEBHOOK_SECRET` | `""` | Stripe webhook signature verification |
| `SENTRY_DSN` | `""` | Error monitoring |
| `PROMETHEUS_ENABLED` | `true` | Expose `/metrics` endpoint |
| `OTEL_ENABLED` | `false` | OpenTelemetry tracing |
| `OTEL_ENDPOINT` | `""` | OTLP gRPC collector (e.g. `http://localhost:4317`) |
| `ENABLE_SCHEDULER` | `true` | APScheduler (job scraper + GDPR cron) |

See `app/core/config.py` for the full list of settings with types and defaults.

---

## Apache AGE setup

PATHS uses Apache AGE for candidate–job relationship graphs.

1. Install AGE alongside PostgreSQL 16:
   ```sql
   CREATE EXTENSION age;
   LOAD 'age';
   SET search_path = ag_catalog, "$user", public;
   SELECT create_graph('paths_graph');
   ```

2. The Alembic migrations include AGE graph operations — they rely on the
   `ag_catalog` schema being available.

---

## Alembic workflow

```bash
# Apply all migrations to head
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "describe_the_change"

# Roll back one step
alembic downgrade -1

# Show migration history
alembic history --verbose
```

> **Production rule**: always run `alembic upgrade head` *before* deploying
> the new backend image. See `docs/runbooks/01_db_migration_safely.md`.

---

## Agent topology

```
CV Upload
  └── cv_ingestion_agent (8 nodes)
        parse → chunk → embed → store_qdrant → extract_entities
        → store_age_graph → generate_summary → update_candidate_record

Job Post
  └── scoring_agent
        fetch_candidates → score_each (LLM + vector hybrid) → rank → persist

Sourcing
  └── sourcing_agent (5 nodes)
        plan_search → fetch_open_to_work → score → deduplicate → enrich

Interview
  └── interview_agent (runtime)
        per_turn: generate_question → evaluate_answer → update_transcript

Decision Support
  └── decision_support_agent (4 nodes)
        aggregate_evidence → build_rubric → llm_score → write_recommendation

Post-Hire
  └── growth_plan_agent
        assess_gaps → identify_resources → generate_roadmap → persist
```

Each agent run creates an `AgentRun` DB row, streams node updates via SSE,
and logs `{run_id, type, org_id, status, node, duration_ms}` at every node.

---

## API structure

All routes live under `/api/v1/`.  Key prefixes:

| Prefix | Purpose |
|---|---|
| `/auth` | Login, register, password reset, GDPR export/delete |
| `/organizations` | Org management |
| `/jobs` | Job posts CRUD + pipeline board |
| `/candidates` | Candidate profiles + CV management |
| `/applications` | Applications + status transitions |
| `/interviews` | Interview scheduling + runtime |
| `/decision-support` | DSS recommendations |
| `/billing` | Stripe subscriptions + invoices |
| `/admin` | Org-level admin panel |
| `/platform-admin` | Platform-wide admin (superuser) |
| `/owner` | Business intelligence for the platform owner |
| `/analytics` | Reports + bias/fairness dashboards |
| `/agent-runs` | Agent run status + SSE stream |

Interactive docs: **http://localhost:8001/docs**

---

## Observability

| Surface | Endpoint / Detail |
|---|---|
| Prometheus metrics | `GET /metrics` |
| Health check | `GET /api/v1/health` |
| DB health | `GET /api/v1/health/databases` |
| Correlation ID | `X-Correlation-ID` request/response header |
| Structured logs | JSON in production; human-readable in development |

---

## Running in production (Fly.io)

```bash
# Build + deploy
fly deploy --app paths-backend

# Tail logs
fly logs --app paths-backend

# Open a console
fly ssh console --app paths-backend

# Run migrations against production
fly ssh console --app paths-backend -C "alembic upgrade head"
```
