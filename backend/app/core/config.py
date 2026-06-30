"""
PATHS Backend — Application configuration.

All settings are loaded from environment variables via pydantic-settings.
"""

from functools import lru_cache
from typing import Self

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # tolerate forward-compat env vars (e.g. QDRANT_COLLECTION_CANDIDATES)
    )

    # ── Application ─────────────────────────────────────
    app_name: str = "PATHS Backend"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True
    # Comma-separated — Next.js (3000) and legacy Vite (5173) dev
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )

    # ── PostgreSQL ──────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "paths_db"
    postgres_user: str = "paths_user"
    postgres_password: str = "change_me"
    database_url: str = "postgresql+psycopg://paths_user:change_me@localhost:5432/paths_db"

    # ── Apache AGE ──────────────────────────────────────
    age_graph_name: str = "paths_graph"
    age_schema: str = "ag_catalog"

    # ── Qdrant ──────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    # Legacy chunked CV collection (kept for backward compatibility)
    qdrant_collection_cv: str = "candidate_cv_chunks"
    qdrant_collection_vector_size: int = 768  # nomic-embed-text dimension

    # ── Unified candidate / job vector collections (one-vector-per-entity rule)
    # These are the spec-compliant collections used by the new sync layer.
    qdrant_candidate_collection: str = "paths_candidates"
    qdrant_job_collection: str = "paths_jobs"

    # ── Ollama ──────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3.1:8b"
    ollama_embed_model: str = "nomic-embed-text"

    # ── Embedding (provider-agnostic aliases used by sync layer) ───────
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 768
    embedding_version: str = "v1"

    # ── Authentication / JWT ────────────────────────────
    secret_key: str = "CHANGE-ME-TO-A-RANDOM-SECRET"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── Ingestion ───────────────────────────────────────
    upload_dir: str = "./uploads"
    chunk_size: int = 900
    chunk_overlap: int = 120

    # ── Job Ingestion ───────────────────────────────────
    job_ingestion_enabled: bool = True
    enable_glassdoor_source: bool = False
    job_ingestion_max_pages: int = 20
    qdrant_collection_jobs: str = "job_description_chunks"

    # ── OpenRouter / Llama scoring agent ───────────────────────────────
    # Used by `app/services/scoring/*` for the candidate-job scoring service.
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "meta-llama/llama-3.2-3b-instruct:free"
    openrouter_referer: str = "https://paths.local"
    openrouter_app_title: str = "PATHS Scoring Agent"
    # Decision Support System (DSS) — spec: Llama 3.2 8B
    openrouter_dss_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    openrouter_development_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    openrouter_outreach_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    # PATHy in-app assistant — a SMALL/FAST model so the chat feels snappy
    # (the 70B free model is too slow for an interactive widget). Falls through
    # the free-model chain if rate-limited.
    assistant_model: str = "openai/gpt-oss-20b:free"
    # Free-model fallback chain — when the primary model is rate-limited (429)
    # the OpenRouter client falls through these, all :free tier, mixed providers.
    openrouter_free_fallback_models: str = (
        "meta-llama/llama-3.3-70b-instruct:free,openai/gpt-oss-120b:free,"
        "z-ai/glm-4.5-air:free,openai/gpt-oss-20b:free,"
        "qwen/qwen3-next-80b-a3b-instruct:free,google/gemma-4-31b-it:free,"
        "meta-llama/llama-3.2-3b-instruct:free"
    )
    decision_support_enabled: bool = True
    dss_openrouter_timeout_seconds: float = 120.0
    dss_max_json_retries: int = 1

    # ── Candidate-Job scoring service ──────────────────────────────────
    scoring_service_enabled: bool = True
    scoring_agent_weight: float = 0.65
    scoring_vector_weight: float = 0.35
    scoring_min_relevance_threshold: float = 0.45
    scoring_max_jobs_per_candidate: int = 20
    scoring_model_temperature: float = 0.1
    scoring_model_max_tokens: int = 1200
    scoring_request_timeout_seconds: float = 60.0
    scoring_prompt_version: str = "v1"
    # If true, the scoring service falls back to a deterministic local
    # heuristic when no OpenRouter API key is configured (handy for
    # local dev / CI). Set to false in production.
    scoring_allow_offline_fallback: bool = True

    # ── Organization-side candidate search & outreach ──────────────────
    org_matching_enabled: bool = True
    org_matching_default_top_k: int = 3
    org_matching_max_top_k: int = 20
    org_matching_max_candidates_per_run: int = 200
    org_matching_require_human_approval: bool = True
    org_scoring_agent_weight: float = 0.65
    org_scoring_vector_weight: float = 0.35
    org_scoring_min_relevance_threshold: float = 0.45

    # LLM provider abstraction (OpenRouter | ollama)
    llm_provider: str = "openrouter"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1500
    llm_streaming_enabled: bool = True
    llm_allow_fallback_to_ollama: bool = False
    ollama_model: str = "llama3.1:8b"

    # Brief-mandated unified env names for the Interview Intelligence Agent.
    local_llm_enabled: bool = False
    local_llm_provider: str = "ollama"
    local_llm_base_url: str = "http://localhost:11434"
    local_llm_model: str = "llama3.1:8b"

    # Interview runtime + reports
    interview_runtime_max_turns: int = 25
    interview_report_storage_dir: str = "./interview_reports"

    # CSV / CV download safety
    org_csv_max_rows: int = 500
    org_cv_download_timeout_seconds: int = 30
    org_cv_max_file_size_mb: int = 10
    org_cv_allowed_content_types: str = (
        "application/pdf,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "application/msword,"
        "text/plain"
    )
    # SSRF protection — block these CIDR ranges in CV download
    org_cv_block_private_networks: bool = True

    # Outreach
    outreach_enabled: bool = True
    outreach_require_approval: bool = True
    outreach_from_email: str = ""
    outreach_from_name: str = "PATHS Recruitment"
    outreach_reply_deadline_days: int = 3
    outreach_default_booking_link: str = ""
    outreach_provider: str = "smtp"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    # Optional MCP support
    mcp_enabled: bool = False
    mcp_google_calendar_enabled: bool = False
    mcp_gmail_enabled: bool = False

    # ── Interview intelligence module ───────────────────────────────────
    interview_intelligence_enabled: bool = True
    # Google Calendar + Meet (optional; service account JSON)
    google_application_credentials: str = ""
    google_calendar_service_account_file: str = ""
    google_calendar_id: str = "primary"
    google_workspace_impersonate_user: str = ""

    # ── Job Scraper (hourly LinkedIn / careers-page import) ────────────
    # Wraps the external `Job_Scraper-main` module. Hourly scheduler
    # imports at most JOB_SCRAPER_BATCH_SIZE jobs per run.
    job_scraper_enabled: bool = False  # opt-in; Playwright / Job_Scraper-main
    job_scraper_interval_minutes: int = 60
    job_scraper_batch_size: int = 10
    job_scraper_run_on_startup: bool = False
    # Default: compliant public RSS (no browser). Set ``linkedin`` + JOB_SCRAPER_ENABLED for Playwright.
    job_scraper_source: str = "remoteok_rss"
    public_job_feed_url: str = "https://remoteok.com/rss"
    weworkremotely_feed_url: str = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
    job_scraper_timeout_seconds: int = 120
    job_scraper_max_pages_per_run: int = 1
    job_scraper_log_level: str = "INFO"
    # Filesystem locations
    job_scraper_module_path: str = "../Job_Scraper-main"
    job_scraper_data_file: str = "../Job_Scraper-main/data/Data.xlsx"
    # Per-run company budget — how many companies the adapter is allowed
    # to visit (browser pages are expensive). Resets to 0 when the list ends.
    job_scraper_companies_per_run: int = 8
    # Headless browser flag, kept controlled and slow by default
    job_scraper_headless: bool = True
    # Optional: stub the scraper (return [] always) — handy in tests/CI.
    job_scraper_stub: bool = False
    # Distributed lock name for the hourly scheduler
    job_scraper_lock_name: str = "paths_job_scraper_hourly_import"

    # ── Outreach Agent (Google OAuth + Calendar + Gmail + LLM) ─────────
    outreach_agent_enabled: bool = True
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/google-integration/callback"
    google_scopes: str = (
        "https://www.googleapis.com/auth/gmail.send "
        "https://www.googleapis.com/auth/calendar.events "
        "https://www.googleapis.com/auth/calendar.freebusy "
        "https://www.googleapis.com/auth/userinfo.email "
        "openid"
    )
    google_oauth_state_secret: str = ""  # falls back to secret_key
    outreach_token_ttl_days: int = 14
    outreach_default_duration_minutes: int = 30
    outreach_default_buffer_minutes: int = 10
    outreach_default_timezone: str = "Africa/Cairo"
    outreach_public_base_url: str = "http://localhost:3000"
    outreach_agent_model: str = "meta-llama/llama-3.2-8b-instruct"
    outreach_agent_max_tokens: int = 700
    outreach_agent_temperature: float = 0.3
    outreach_send_rate_limit_per_minute: int = 10

    # ── Open-to-Work Candidate Sourcing ────────────────────────────────
    # New, additive module that mirrors the job scraper architecture.
    # Disabled by default. No DB schema changes — uses CandidateSource,
    # EvidenceItem.meta_json, Candidate.headline/summary/desired_*, etc.
    candidate_sourcing_enabled: bool = False
    candidate_sourcing_provider: str = "mock"  # mock | linkedin | openresume
    candidate_sourcing_max_per_run: int = 10
    candidate_sourcing_interval_minutes: int = 60
    candidate_sourcing_request_timeout_seconds: int = 90
    candidate_sourcing_lock_name: str = "paths_candidate_sourcing_run"
    candidate_sourcing_run_on_startup: bool = False
    # Provider-specific (compliant defaults).
    # LinkedIn provider is stub-by-default. It NEVER scrapes private pages,
    # bypasses CAPTCHA, or rotates proxies. Real connector requires an
    # approved API/export to be wired into ``linkedin_open_to_work_provider``.
    linkedin_candidate_provider_stub: bool = True
    linkedin_candidate_export_dir: str = "../linkedin_scraper-master/samples"
    candidate_sourcing_default_keywords: str = ""  # comma-separated
    candidate_sourcing_default_location: str = ""
    candidate_sourcing_min_match_score: float = 0.0
    # Reasoning agent (uses existing OpenRouter Llama config)
    candidate_sourcing_reasoning_enabled: bool = True
    candidate_sourcing_reasoning_model: str = "meta-llama/llama-3.1-8b-instruct"
    candidate_sourcing_reasoning_max_tokens: int = 600
    candidate_sourcing_reasoning_temperature: float = 0.2

    # ── Source Candidate (fix6.md) — recruiter preview/import workflow ──
    # Default provider used by the new POST /recruiter/source-candidate
    # /external/fetch endpoint. "linkedin_mcp" falls back to consented CSV
    # exports when no MCP server is reachable.
    source_candidate_default_provider: str = "linkedin_mcp"
    # Maximum candidates returned per Add-to-Process click (per the spec,
    # always 5; configurable so admins can dial it lower).
    source_candidate_fetch_count: int = 5
    # Days a pending member invite stays open. If the invitee never signs in
    # within this window, their membership is auto-expired to 'inactive'.
    member_invite_grace_days: int = 2
    # MCP endpoint — usually http://127.0.0.1:8080/mcp when the operator
    # is running the linkedin-mcp-server reference locally.
    linkedin_mcp_url: str = ""
    linkedin_mcp_timeout_seconds: float = 60.0

    # ── Skill Evidence MCP tools (CV / GitHub / LinkedIn) ────────────
    # Drives per-skill scoring on candidate profiles. The "MCP" framing
    # is per the brief: each source is a tool the evidence agent can
    # call, scoped behind a clean interface so a real MCP server URL
    # can be swapped in later without changing the agent code.
    github_api_base: str = "https://api.github.com"
    # Optional GitHub PAT — bumps the public REST rate-limit ceiling
    # from ~60 req/h to ~5000 req/h. Leave blank for unauthenticated
    # access (works but rate-limited).
    github_token: str = ""
    # The User-Agent string the LinkedIn best-effort fetcher uses. Some
    # LinkedIn endpoints block requests without a realistic UA.
    linkedin_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
    # Optional pointer at a hosted LinkedIn MCP server. When set, the
    # LinkedIn evidence tool prefers that endpoint over the public-HTML
    # fallback so operators with a real MCP can plug it in cleanly.
    linkedin_mcp_server_url: str = ""
    # Aggregator weights — must sum to 100. Override via JSON in env if
    # you want to retune per deployment without redeploying code.
    # Candidate.md §4 — skill rubric is CV 50% + GitHub 50% (LinkedIn removed).
    skill_evidence_weights_json: str = '{"cv": 50, "github": 50}'
    skill_evidence_llm_timeout_seconds: int = 45
    # Cap on simultaneous skill-evidence requests per refresh call to
    # keep one candidate from monopolising the LLM/HTTP budget.
    skill_evidence_max_parallel: int = 4

    # ── Recall.ai (Interview notetaker bots) ──────────────────────────
    # Sends a Recall.ai bot to a meeting URL (Zoom / Meet / Teams) and
    # pulls the post-meeting transcript OR streams it in real-time via
    # the transcript.data webhook. Disabled until an API key is set.
    recall_api_key: str = ""
    # Region tied to the Recall workspace — base URL is built as
    # https://{recall_region}.recall.ai/api/v1.  Valid values today are
    # us-west-2 | us-east-1 | eu-central-1 | ap-northeast-1.
    recall_region: str = "eu-central-1"
    # Shared secret used to verify the Svix signature on inbound webhooks.
    # Paste the value from the Recall webhook config screen here.
    recall_webhook_secret: str = ""
    # Publicly-reachable URL the backend is served from (e.g. ngrok /
    # cloudflared) — Recall posts events here. Local dev only needs this
    # if mode = real_time; the post-meeting path also works via polling.
    recall_public_webhook_url: str = ""
    # Friendly display name the bot uses inside the meeting UI.
    recall_bot_name: str = "PATHS Notetaker"
    # Polling fallback cadence when webhooks are unavailable, in seconds.
    recall_poll_interval_seconds: int = 10
    # On-disk transcript copy for offline analysis / audit.
    recall_transcripts_dir: str = "./uploads/transcripts"

    # ── Stripe Billing ─────────────────────────────────────────────────
    stripe_secret_key: str = ""          # sk_test_... / sk_live_...
    stripe_webhook_secret: str = ""      # whsec_...
    stripe_publishable_key: str = ""     # pk_test_... / pk_live_...
    # Frontend base URL used to build success/cancel redirect URLs
    app_frontend_url: str = "http://localhost:3000"

    # ── Email (password reset + notifications) ─────────────────────────
    # Already covered by smtp_* above — reuse those settings.

    # ── Observability (PATHS-177 / PATHS-178) ──────────────────────────────
    # Prometheus metrics endpoint (always on; set to false to disable)
    prometheus_enabled: bool = True
    # Sentry — leave dsn empty to disable
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    # Populated by CI from `git rev-parse --short HEAD`
    sentry_release: str = ""
    # OpenTelemetry — leave otel_endpoint empty to disable
    otel_enabled: bool = False
    otel_endpoint: str = ""   # e.g. http://localhost:4317 (gRPC)
    otel_service_name: str = "paths-backend"

    # Optional aliases (no schema impact) — LINKEDIN_* / ENABLE_SCHEDULER
    linkedin_scraper_enabled: bool | None = None
    linkedin_jobs_per_hour: int | None = None
    linkedin_jobs_per_run: int | None = None
    linkedin_scraper_interval_minutes: int | None = None
    enable_scheduler: bool = True
    # Friendly names for ops (map into JOB_SCRAPER_* — no new DB fields)
    job_importer_enabled: bool | None = None
    job_importer_interval_minutes: int | None = None
    job_importer_jobs_per_run: int | None = None

    @model_validator(mode="after")
    def _production_guard(self) -> Self:
        """Enforce production-safe configuration."""
        if self.app_env == "production":
            if self.secret_key == "CHANGE-ME-TO-A-RANDOM-SECRET":
                raise ValueError(
                    "SECRET_KEY must be changed from the default in production. "
                    "Generate a strong random secret and set it in your environment."
                )
            if self.candidate_sourcing_provider == "mock":
                raise ValueError(
                    "candidate_sourcing_provider must not be 'mock' in production. "
                    "Set a real provider (e.g. 'linkedin') or disable candidate sourcing."
                )
            if self.debug is True:
                object.__setattr__(self, "debug", False)
        return self

    @computed_field
    @property
    def mock_data_enabled(self) -> bool:
        """Returns True only if mock data is allowed (non-production)."""
        return self.app_env != "production" and self.candidate_sourcing_provider == "mock"

    @model_validator(mode="after")
    def _apply_linkedin_scheduler_aliases(self) -> Self:
        """Merge LINKEDIN_* / JOB_IMPORTER_* env vars into JOB_SCRAPER_* fields."""
        if self.job_importer_enabled is True:
            object.__setattr__(self, "job_scraper_enabled", True)
        if self.job_importer_interval_minutes is not None:
            object.__setattr__(
                self,
                "job_scraper_interval_minutes",
                max(1, int(self.job_importer_interval_minutes)),
            )
        if self.job_importer_jobs_per_run is not None:
            bounded = max(1, min(int(self.job_importer_jobs_per_run), 10))
            object.__setattr__(self, "job_scraper_batch_size", bounded)
        if self.linkedin_scraper_enabled is True:
            object.__setattr__(self, "job_scraper_enabled", True)
        if self.linkedin_jobs_per_hour is not None:
            # Hard cap: never more than 10 jobs per scheduled run (hourly cadence).
            bounded = max(1, min(int(self.linkedin_jobs_per_hour), 10))
            object.__setattr__(self, "job_scraper_batch_size", bounded)
        if self.linkedin_jobs_per_run is not None:
            bounded = max(1, min(int(self.linkedin_jobs_per_run), 10))
            object.__setattr__(self, "job_scraper_batch_size", bounded)
        if self.linkedin_scraper_interval_minutes is not None:
            object.__setattr__(
                self,
                "job_scraper_interval_minutes",
                max(1, int(self.linkedin_scraper_interval_minutes)),
            )
        return self

    @computed_field
    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
