"""
LinkedIn-labeled job ingestion (facade).

PATHS does **not** bypass LinkedIn login, CAPTCHAs, paywalls, or anti-bot
controls. For production use of LinkedIn-hosted listings, prefer LinkedIn's
official APIs or partner programs where you are contractually authorized.

The running integration uses :class:`JobScraperAdapter`, which reads a curated
company list and discovers **public** career / ATS pages (Greenhouse, Lever,
Workday, etc.) via search — the same pipeline historically wired behind
``JOB_SCRAPER_SOURCE=linkedin``, which sets ``jobs.source_platform`` for
analytics and deduplication.

Replace this module's imports in your own deployment if you plug in a
different compliant provider; the database contract is unchanged.
"""

from app.services.job_scraper.job_import_service import JobImportService
from app.services.job_scraper.scraper_adapter import JobScraperAdapter

__all__ = ["JobImportService", "JobScraperAdapter"]
