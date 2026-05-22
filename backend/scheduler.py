"""
Background scheduler for all automated Sauce jobs.
Uses APScheduler's AsyncIOScheduler so jobs share the FastAPI event loop.
"""
from __future__ import annotations
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from nhl.sync_players import sync_all_players
from nhl.sync_games import sync_schedule, has_live_games
from nhl.sync_stats import poll_active_games
from scoring.streaks import update_streaks
from league.waiver import process_waiver_claims
from news.fetcher import refresh_rss
from league.trades import process_auto_approvals

log = logging.getLogger(__name__)


async def _stats_poll_job():
    """
    Runs every 30 seconds. Polls boxscores when games are live;
    exits immediately otherwise so we don't hammer the API unnecessarily.
    """
    try:
        live = await has_live_games()
        if live:
            await poll_active_games()
        else:
            # Outside game windows: just keep game statuses/scores updated
            await poll_active_games()
    except Exception:
        log.exception("Stats poll job failed")


async def _schedule_sync_job():
    try:
        await sync_schedule(days_ahead=14)
    except Exception:
        log.exception("Schedule sync job failed")


async def _player_sync_job():
    try:
        await sync_all_players()
    except Exception:
        log.exception("Player sync job failed")


async def _news_refresh_job():
    try:
        await refresh_rss()
    except Exception:
        log.exception("News refresh job failed")


async def _waiver_process_job(league_id: str):
    try:
        await process_waiver_claims(league_id)
    except Exception:
        log.exception("Waiver processing job failed")


async def _trade_auto_approval_job(league_id: str):
    try:
        await process_auto_approvals(league_id)
    except Exception:
        log.exception("Trade auto-approval job failed")


async def _streak_snapshot_job(league_id: str):
    """Runs nightly after midnight once all games are final."""
    try:
        await update_streaks(league_id)
    except Exception:
        log.exception("Streak snapshot job failed")


def build_scheduler(league_id: str | None = None) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    # Stat polling — every 30 seconds (cheap noop when no games are live)
    scheduler.add_job(
        _stats_poll_job,
        trigger=IntervalTrigger(seconds=30),
        id="stats_poll",
        name="NHL stat polling",
        max_instances=1,
        coalesce=True,
    )

    # Game schedule refresh — every 6 hours and on startup
    scheduler.add_job(
        _schedule_sync_job,
        trigger=IntervalTrigger(hours=6),
        id="schedule_sync",
        name="NHL schedule sync",
        max_instances=1,
        coalesce=True,
    )

    # Player/roster refresh — every 6 hours (catches trades, injuries, AHL recalls)
    scheduler.add_job(
        _player_sync_job,
        trigger=IntervalTrigger(hours=6),
        id="player_sync",
        name="NHL player sync",
        max_instances=1,
        coalesce=True,
    )

    # News feed refresh — every 20 minutes
    scheduler.add_job(
        _news_refresh_job,
        trigger=IntervalTrigger(minutes=20),
        id="news_refresh",
        name="RSS news refresh",
        max_instances=1,
        coalesce=True,
    )

    # Waiver processing — every 30 minutes (processes claims once the 24-hour window passes)
    if league_id:
        scheduler.add_job(
            _waiver_process_job,
            trigger=IntervalTrigger(minutes=30),
            id="waiver_process",
            name="Waiver claim processing",
            max_instances=1,
            coalesce=True,
            kwargs={"league_id": league_id},
        )

    # Trade auto-approvals — every 15 minutes
    if league_id:
        scheduler.add_job(
            _trade_auto_approval_job,
            trigger=IntervalTrigger(minutes=15),
            id="trade_auto_approve",
            name="Trade auto-approval",
            max_instances=1,
            coalesce=True,
            kwargs={"league_id": league_id},
        )

    # Hot/cold streak snapshot — nightly at 02:00 UTC (after all games are final)
    if league_id:
        scheduler.add_job(
            _streak_snapshot_job,
            trigger=CronTrigger(hour=2, minute=0),
            id="streak_snapshot",
            name="Player streak snapshot",
            max_instances=1,
            coalesce=True,
            kwargs={"league_id": league_id},
        )

    return scheduler
