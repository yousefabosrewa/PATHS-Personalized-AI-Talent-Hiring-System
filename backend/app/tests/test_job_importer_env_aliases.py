"""JOB_IMPORTER_* and LINKEDIN_JOBS_PER_RUN map into JOB_SCRAPER_* without DB changes."""

from app.core.config import Settings


def test_job_importer_env_aliases_merge_into_scraper_fields(monkeypatch):
    monkeypatch.setenv("JOB_IMPORTER_ENABLED", "true")
    monkeypatch.setenv("JOB_IMPORTER_INTERVAL_MINUTES", "10")
    monkeypatch.setenv("JOB_IMPORTER_JOBS_PER_RUN", "5")
    s = Settings()
    assert s.job_scraper_enabled is True
    assert s.job_scraper_interval_minutes == 10
    assert s.job_scraper_batch_size == 5


def test_linkedin_jobs_per_run_caps_batch(monkeypatch):
    monkeypatch.setenv("LINKEDIN_JOBS_PER_RUN", "5")
    s = Settings()
    assert s.job_scraper_batch_size == 5
