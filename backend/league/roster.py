"""
Roster management: add/drop players, slot assignment, lineup swaps, validation.

Business rules enforced here:
- Max 4 goalies on active roster (any non-IR slot)
- Max 2 player adds per week (drops are free)
- Slot must be eligible for player's position
- Players can only be on one team at a time
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from db import get_db
from league.moves_log import log_move

log = logging.getLogger(__name__)

# Which positions are allowed in each slot
SLOT_ELIGIBLE_POSITIONS: dict[str, set[str]] = {
    "C":    {"C"},
    "LW":   {"LW"},
    "RW":   {"RW"},
    "D":    {"D"},
    "G":    {"G"},
    "UTIL": {"C", "LW", "RW", "D"},
    "BN":   {"C", "LW", "RW", "D", "G"},
    "IR":   {"C", "LW", "RW", "D", "G"},  # eligibility checked separately
}

_MAX_ADDS_PER_WEEK = 2
_MAX_ACTIVE_GOALIES = 4  # non-IR slots only
_IR_SLOT = "IR"
_ACTIVE_SLOTS = {"C", "LW", "RW", "D", "G", "UTIL", "BN"}  # everything except IR


class RosterError(Exception):
    """Raised for any invalid roster operation. Message is user-facing."""


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

async def _get_player(player_id: str) -> dict:
    db = get_db()
    result = await db.table("nhl_players").select("id, full_name, position, status").eq("id", player_id).single().execute()
    if not result.data:
        raise RosterError("Player not found")
    return result.data


async def _get_roster(team_id: str) -> list[dict]:
    db = get_db()
    result = await db.table("rosters").select("player_id, slot").eq("team_id", team_id).execute()
    return result.data or []


async def _get_team_league(team_id: str) -> dict:
    db = get_db()
    result = await (
        db.table("teams")
        .select("id, league_id, waiver_priority")
        .eq("id", team_id)
        .single()
        .execute()
    )
    if not result.data:
        raise RosterError("Team not found")
    return result.data


async def _get_current_week(league_id: str) -> int:
    db = get_db()
    result = await db.table("league").select("current_week").eq("id", league_id).single().execute()
    return result.data["current_week"]


async def _count_active_goalies(team_id: str) -> int:
    """Count goalies in non-IR slots (active + bench)."""
    roster = await _get_roster(team_id)
    db = get_db()
    goalie_player_ids = []
    for r in roster:
        if r["slot"] in _ACTIVE_SLOTS:
            goalie_player_ids.append(r["player_id"])
    if not goalie_player_ids:
        return 0
    result = await (
        db.table("nhl_players")
        .select("id")
        .in_("id", goalie_player_ids)
        .eq("position", "G")
        .execute()
    )
    return len(result.data or [])


async def _get_adds_used(team_id: str, week_number: int) -> int:
    db = get_db()
    result = await (
        db.table("weekly_team_settings")
        .select("adds_used")
        .eq("team_id", team_id)
        .eq("week_number", week_number)
        .execute()
    )
    return result.data[0]["adds_used"] if result.data else 0


async def _increment_adds_used(team_id: str, week_number: int) -> None:
    db = get_db()
    current = await _get_adds_used(team_id, week_number)
    await db.table("weekly_team_settings").upsert(
        {"team_id": team_id, "week_number": week_number, "adds_used": current + 1},
        on_conflict="team_id,week_number",
    ).execute()


# ------------------------------------------------------------------ #
# Validation
# ------------------------------------------------------------------ #

async def validate_slot(team_id: str, player_id: str, slot: str) -> None:
    """Raise RosterError if the slot is not valid for this player and team state."""
    player = await _get_player(player_id)
    eligible = SLOT_ELIGIBLE_POSITIONS.get(slot, set())
    if player["position"] not in eligible:
        raise RosterError(
            f"{player['full_name']} ({player['position']}) cannot be placed in a {slot} slot"
        )
    # Goalie limit check (only for non-IR adds)
    if player["position"] == "G" and slot != _IR_SLOT:
        current_g = await _count_active_goalies(team_id)
        if current_g >= _MAX_ACTIVE_GOALIES:
            raise RosterError(
                f"Cannot add {player['full_name']}: team already has {_MAX_ACTIVE_GOALIES} active goalies (IR slots are separate)"
            )


async def validate_adds_remaining(team_id: str, league_id: str) -> None:
    week = await _get_current_week(league_id)
    used = await _get_adds_used(team_id, week)
    if used >= _MAX_ADDS_PER_WEEK:
        raise RosterError(f"Team has used all {_MAX_ADDS_PER_WEEK} adds for this week")


# ------------------------------------------------------------------ #
# Core operations
# ------------------------------------------------------------------ #

async def add_player(
    team_id: str,
    player_id: str,
    slot: str,
    source: str = "free_agent",   # "free_agent" or "waiver"
    commissioner_override: bool = False,
) -> None:
    """
    Place a player onto a team's roster.
    Validates slot eligibility, goalie limit, and (unless override) weekly add limit.
    """
    team = await _get_team_league(team_id)
    league_id = team["league_id"]

    # Check add limit (commissioner overrides bypass this)
    if not commissioner_override:
        await validate_adds_remaining(team_id, league_id)

    await validate_slot(team_id, player_id, slot)

    db = get_db()
    # Ensure player isn't already rostered somewhere
    existing = await db.table("rosters").select("team_id").eq("player_id", player_id).execute()
    if existing.data:
        raise RosterError("Player is already on a roster")

    await db.table("rosters").insert({
        "team_id": team_id,
        "player_id": player_id,
        "slot": slot,
        "assigned_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    if not commissioner_override:
        week = await _get_current_week(league_id)
        await _increment_adds_used(team_id, week)

    move_type = "add_waiver" if source == "waiver" else "add_free_agent"
    await log_move(league_id, team_id, move_type, player_id)
    log.info("add_player  team=%s  player=%s  slot=%s  source=%s", team_id, player_id, slot, source)


async def drop_player(team_id: str, player_id: str) -> None:
    """
    Remove a player from a team's roster and place them on waivers.
    The player becomes claimable after 24 hours.
    """
    from datetime import timedelta
    from league.ir_rules import is_ir_eligible  # avoid circular import

    db = get_db()
    team = await _get_team_league(team_id)
    league_id = team["league_id"]

    # Confirm player is on this team
    existing = await (
        db.table("rosters")
        .select("slot")
        .eq("team_id", team_id)
        .eq("player_id", player_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise RosterError("Player is not on this team's roster")

    # Remove from roster
    await db.table("rosters").delete().eq("team_id", team_id).eq("player_id", player_id).execute()

    # Place on waivers
    now = datetime.now(timezone.utc)
    claimable = now + timedelta(hours=24)
    await db.table("waiver_wire").upsert(
        {
            "player_id": player_id,
            "dropped_by_team_id": team_id,
            "dropped_at": now.isoformat(),
            "claimable_at": claimable.isoformat(),
            "status": "on_waivers",
        },
        on_conflict="player_id",
    ).execute()

    await log_move(league_id, team_id, "drop", player_id)
    log.info("drop_player  team=%s  player=%s", team_id, player_id)


async def swap_slot(team_id: str, player_id: str, new_slot: str) -> None:
    """
    Move a rostered player to a different slot (lineup management, not an add/drop).
    No add counter change. Subject to lineup lock.
    """
    from league.lineup import is_lineup_locked  # avoid circular import

    db = get_db()
    if await is_lineup_locked():
        raise RosterError("Lineup is locked — cannot make changes after today's first puck drop")

    existing = await (
        db.table("rosters")
        .select("slot")
        .eq("team_id", team_id)
        .eq("player_id", player_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise RosterError("Player is not on this team's roster")

    await validate_slot(team_id, player_id, new_slot)

    await (
        db.table("rosters")
        .update({"slot": new_slot})
        .eq("team_id", team_id)
        .eq("player_id", player_id)
        .execute()
    )
    log.info("swap_slot  team=%s  player=%s  slot=%s", team_id, player_id, new_slot)
