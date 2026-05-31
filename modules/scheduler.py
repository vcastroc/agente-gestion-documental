"""Scheduling system for autonomous tasks."""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("AARI_Scheduler")


def setup_scheduler(app, db):
    """Initialize background scheduler for autonomous tasks."""
    from .automation import process_pending_invitations, generate_daily_report

    scheduler = BackgroundScheduler()

    # Task 1: Check and send pending invitations every 30 minutes
    scheduler.add_job(
        func=process_pending_invitations,
        args=[db],
        trigger=IntervalTrigger(minutes=30),
        id="send_invitations",
        name="Send pending invitations to qualified candidates",
        replace_existing=True,
    )
    logger.info("✅ Scheduled: Send invitations every 30 minutes")

    # Task 2: Generate daily report at 8 AM
    scheduler.add_job(
        func=generate_daily_report,
        args=[db],
        trigger=CronTrigger(hour=8, minute=0),
        id="daily_report",
        name="Generate daily performance report",
        replace_existing=True,
    )
    logger.info("✅ Scheduled: Daily report at 8:00 AM")

    # Task 3: Clean up old uploads older than 90 days (optional)
    scheduler.add_job(
        func=cleanup_old_uploads,
        args=[app.config.get("UPLOADS_DIR", "uploads")],
        trigger=CronTrigger(day_of_week="mon", hour=3, minute=0),
        id="cleanup_uploads",
        name="Clean up old CV files",
        replace_existing=True,
    )
    logger.info("✅ Scheduled: Weekly cleanup on Mondays at 3:00 AM")

    scheduler.start()
    logger.info("🚀 Background scheduler started")
    return scheduler


def cleanup_old_uploads(uploads_dir: str, days: int = 90):
    """Remove CV files older than specified days."""
    import os
    from pathlib import Path
    from datetime import datetime, timedelta

    try:
        uploads = Path(uploads_dir)
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0

        for file in uploads.glob("*"):
            if file.is_file():
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if mtime < cutoff:
                    file.unlink()
                    removed += 1
                    logger.info(f"🗑️ Deleted old file: {file.name}")

        logger.info(f"✅ Cleanup completed: {removed} files removed")

    except Exception as exc:
        logger.error(f"❌ Error during cleanup: {exc}")
