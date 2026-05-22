"""
Syncs the NHL game schedule into the games table.
Assigns week_number relative to SEASON_START_DATE.
Runs daily and on startup to keep the forward schedule populated.
"""
from __future__ import annotations
import logging
import math
from datetime import date, timedelta, datetime, timezone

from db import get_db
from nhl.client import get_nhl
from config import SEASON_START_DATE, SEASON_YEAR

log = logging.getLogger(__name__)

# Map NHL API gameState → our schema status
_STATE_MAP = {
    "FUT": "scheduled",
    "PRE": "scheduled",
    "LIVE": "live",
    "CRIT": "live",
    "FINAL": "final",
    "OFF": "final",
    "OVER": "final",
    "PPRD": "postponed",
}


def date_to_week(game_date: date) -> int | None:
    """Return the 1-based fantasy week number for a game date, or None if before season start."""
    delta = (game_date - SEASON_START_DATE).days
    if delta < 0:
        return None
    return math.floor(delta / 7) + 1


async def sync_schedule(days_ahead: int = 14) -> None:
    """
    Fetch schedule for today through days_ahead and upsert into games table.
    Fetches one date at a time (NHL API groups by week but we request by day).
    """
    nhl = get_nhl()
    db = get_db()

    today = date.today()
    # Also look back 2 days to catch status updates on recent games
    start = today - timedelta(days=2)

    log.info("Syncing schedule from %s (+%d days ahead)", start, days_ahead)

    fetched_game_ids: set[int] = set()
    rows: list[dict] = []

    for offset in range(-2, days_ahead + 1):
        target = start + timedelta(days=offset)
        date_str = target.isoformat()
        try:
            data = await nhl.get_schedule(date_str)
        except RuntimeError as exc:
            log.warning("Schedule fetch failed for %s: %s", date_str, exc)
            continue

        for game_week in data.get("gameWeek", []):
            for g in game_week.get("games", []):
                game_id = g.get("id")
                if not game_id or game_id in fetched_game_ids:
                    continue
                # Only sync regular season games
                if g.get("gameType") != 2:
                    continue
                fetched_game_ids.add(game_id)

                game_date_str = g.get("gameDate", date_str)
                try:
                    game_date = date.fromisoformat(game_date_str)
                except ValueError:
                    game_date = target

                season_raw = g.get("season", str(SEASON_YEAR))
                season_int = int(str(season_raw)[:4])  # e.g. 20252026 → 2025

                state = g.get("gameState", "FUT")
                status = _STATE_MAP.get(state, "scheduled")

                home = g.get("homeTeam", {})
                away = g.get("awayTeam", {})

                rows.append({
                    "nhl_game_id": game_id,
                    "home_team_abbrev": home.get("abbrev", ""),
                    "away_team_abbrev": away.get("abbrev", ""),
                    "game_date": game_date_str,
                    "start_time": g.get("startTimeUTC"),
                    "status": status,
                    "home_score": home.get("score"),
                    "away_score": away.get("score"),
                    "season_year": season_int,
                    "week_number": date_to_week(game_date),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })

    if rows:
        await db.table("games").upsert(rows, on_conflict="nhl_game_id").execute()
        log.info("Schedule sync complete — %d games upserted", len(rows))
    else:
        log.info("Schedule sync found no games to upsert")


async def get_todays_game_ids() -> list[int]:
    """Return nhl_game_ids for all non-postponed games scheduled today."""
    db = get_db()
    today = date.today().isoformat()
    result = await (
        db.table("games")
        .select("nhl_game_id")
        .eq("game_date", today)
        .neq("status", "postponed")
        .execute()
    )
    return [r["nhl_game_id"] for r in (result.data or [])]


async def has_live_games() -> bool:
    """True if any game in the DB currently has status='live'."""
    db = get_db()
    result = await (
        db.table("games")
        .select("id")
        .eq("status", "live")
        .limit(1)
        .execute()
    )
    return bool(result.data)
