"""
Syncs NHL players from all active teams into the nhl_players table.
Run on startup and every few hours to catch trades/roster moves.
"""
from __future__ import annotations
import logging
import asyncio
from datetime import datetime, timezone

from db import get_db
from nhl.client import get_nhl

log = logging.getLogger(__name__)

# NHL API positionCode → our schema position
_POS_MAP = {"C": "C", "L": "LW", "R": "RW", "D": "D", "G": "G"}

# Injury designations the NHL landing page may return
_IR_STATUSES = {"IR", "IR-LT", "OUT"}
_DTD_STATUSES = {"DAY-TO-DAY", "DTD"}


def _map_status(designation: str | None) -> str:
    if not designation:
        return "active"
    upper = designation.upper().strip()
    if upper in _IR_STATUSES:
        return upper  # "IR", "IR-LT", "OUT"
    if upper in _DTD_STATUSES:
        return "DTD"
    return "active"


async def _upsert_players(players_raw: list[dict], team_abbrev: str) -> int:
    db = get_db()
    rows = []
    for p in players_raw:
        pos_code = p.get("positionCode", "")
        position = _POS_MAP.get(pos_code)
        if not position:
            continue
        rows.append({
            "nhl_player_id": p["id"],
            "full_name": f"{p['firstName']['default']} {p['lastName']['default']}",
            "position": position,
            "nhl_team_abbrev": team_abbrev,
            "jersey_number": p.get("sweaterNumber"),
            "headshot_url": p.get("headshot"),
            "status": "active",  # roster players are active; IR handled separately
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    if not rows:
        return 0
    await db.table("nhl_players").upsert(rows, on_conflict="nhl_player_id").execute()
    return len(rows)


async def sync_all_players() -> None:
    """
    Fetch every active NHL team's roster and upsert into nhl_players.
    Then update injury statuses for any player with an active IR designation.
    """
    nhl = get_nhl()
    log.info("Starting full player sync")

    # Get all active teams from standings
    try:
        standings = await nhl.get_standings()
    except RuntimeError as exc:
        log.error("Cannot fetch standings: %s", exc)
        return

    teams = [t["teamAbbrev"]["default"] for t in standings.get("standings", [])]
    log.info("Syncing rosters for %d teams", len(teams))

    total = 0
    _all_roster_ids: set[int] = set()
    for abbrev in teams:
        try:
            roster = await nhl.get_team_roster(abbrev)
        except RuntimeError as exc:
            log.warning("Skipping %s roster: %s", abbrev, exc)
            continue

        players = (
            roster.get("forwards", [])
            + roster.get("defensemen", [])
            + roster.get("goalies", [])
        )
        for p in players:
            if p.get("id"):
                _all_roster_ids.add(p["id"])
        count = await _upsert_players(players, abbrev)
        total += count
        log.debug("%s: %d players synced", abbrev, count)

    log.info("Player sync complete — %d players upserted", total)

    # Mark players no longer on any roster as inactive.
    # Precise IR/OUT designations are set by the commissioner via admin tools
    # since the NHL API doesn't expose structured injury data in roster endpoints.
    await _mark_unlisted_players_inactive(rostered_nhl_ids=_all_roster_ids)


async def _mark_unlisted_players_inactive(rostered_nhl_ids: set[int]) -> None:
    """
    Set status='OUT' for any player in our DB that isn't on a current NHL roster.
    These are players who were traded down to the AHL, bought out, or are long-term injured.
    """
    if not rostered_nhl_ids:
        return
    db = get_db()
    result = await db.table("nhl_players").select("id, nhl_player_id, status").execute()
    all_players = result.data or []

    unlisted = [
        p for p in all_players
        if p["nhl_player_id"] not in rostered_nhl_ids and p["status"] == "active"
    ]
    if not unlisted:
        return

    ids_to_update = [p["id"] for p in unlisted]
    await (
        db.table("nhl_players")
        .update({"status": "OUT", "updated_at": datetime.now(timezone.utc).isoformat()})
        .in_("id", ids_to_update)
        .execute()
    )
    log.info("%d players marked OUT (not on any current NHL roster)", len(unlisted))
