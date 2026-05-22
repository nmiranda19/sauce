"""
Lineup lock logic.

Lineups lock at the start of the first NHL game of each day.
Lock is determined in real-time by checking whether any game today
has already started (start_time <= now) or has status='live'.

No state stored — just a DB check. This means:
- Before the day's first puck drop: lineups are open
- After the day's first puck drop: lineups are locked for that day
- Managers can make changes again from midnight until the next day's first puck drop
"""
from __future__ import annotations
import logging
from datetime import date, datetime, timezone

from db import get_db

log = logging.getLogger(__name__)


async def is_lineup_locked() -> bool:
    """
    Returns True if today's lineup is locked (first puck has dropped).
    A lineup is locked when any game today is live or has a start_time in the past.
    """
    db = get_db()
    today = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()

    # Check for any live game today
    live = await (
        db.table("games")
        .select("id")
        .eq("game_date", today)
        .eq("status", "live")
        .limit(1)
        .execute()
    )
    if live.data:
        return True

    # Check for any final game today (covers games that have ended)
    final = await (
        db.table("games")
        .select("id")
        .eq("game_date", today)
        .eq("status", "final")
        .limit(1)
        .execute()
    )
    if final.data:
        return True

    # Check for any scheduled game whose start_time has passed
    started = await (
        db.table("games")
        .select("id")
        .eq("game_date", today)
        .eq("status", "scheduled")
        .lte("start_time", now)
        .limit(1)
        .execute()
    )
    return bool(started.data)


async def get_lineup_lock_time() -> str | None:
    """
    Returns the ISO timestamp of today's first puck drop, or None if no games today.
    Useful for displaying lock time to managers.
    """
    db = get_db()
    today = date.today().isoformat()
    result = await (
        db.table("games")
        .select("start_time")
        .eq("game_date", today)
        .neq("status", "postponed")
        .order("start_time")
        .limit(1)
        .execute()
    )
    if result.data and result.data[0]["start_time"]:
        return result.data[0]["start_time"]
    return None
