"""
Background scheduler for daily playlist auto-sync.

Uses APScheduler with AsyncIOScheduler so it runs inside the same
event loop as FastAPI — no separate process needed.

Job: every day at YOUTUBE_SYNC_HOUR_UTC UTC, find all PlaylistImports
     with next_sync_at <= now and auto_sync_enabled = true, and sync them.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.core.config import settings
from src.db.session import AsyncSessionLocal
from src.services.playlist_sync import run_due_syncs

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler(timezone="UTC")


async def _daily_sync_job() -> None:
    """
    Scheduled job: sync all playlists due for an update.
    Runs inside its own DB session — isolated from request sessions.
    """
    logger.info("Daily sync job starting")
    async with AsyncSessionLocal() as db:
        try:
            results = await run_due_syncs(db)
            total = len(results)
            completed = sum(1 for r in results if r.status == "completed")
            failed = sum(1 for r in results if r.status == "failed")
            logger.info(
                "Daily sync done: %d processed, %d completed, %d failed",
                total, completed, failed,
            )
        except Exception:
            logger.exception("Daily sync job crashed unexpectedly")


def start_scheduler() -> AsyncIOScheduler:
    """
    Register all scheduled jobs and start the scheduler.
    Call this from FastAPI lifespan startup.
    """
    _scheduler.add_job(
        _daily_sync_job,
        trigger=CronTrigger(hour=settings.YOUTUBE_SYNC_HOUR_UTC, minute=0),
        id="daily_playlist_sync",
        name="Daily YouTube Playlist Auto-Sync",
        replace_existing=True,
        misfire_grace_time=3600,  # allow up to 1h late if server was down
    )
    _scheduler.start()
    logger.info(
        "Scheduler started — daily sync at %02d:00 UTC",
        settings.YOUTUBE_SYNC_HOUR_UTC,
    )
    return _scheduler


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")