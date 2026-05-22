"""
Injury Reserve rules.

Eligible designations: IR, IR-LT, OUT
Not eligible: DTD (Day-to-Day), active

IR slots are separate from the 25-man roster and do not count toward the 4-goalie limit.
A team has 3 IR slots.

Managers can keep a recovered player in an IR slot until they choose to move them.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from db import get_db
from league.moves_log import log_move

log = logging.getLogger(__name__)

_IR_ELIGIBLE_STATUSES = {"IR", "IR-LT", "OUT"}
_MAX_IR_SLOTS = 3


class IRError(Exception):
    pass


async def is_ir_eligible(player_id: str) -> bool:
    db = get_db()
    result = await db.table("nhl_players").select("status").eq("id", player_id).single().execute()
    if not result.data:
        return False
    return result.data["status"] in _IR_ELIGIBLE_STATUSES


async def _count_ir_slots_used(team_id: str) -> int:
    db = get_db()
    result = await (
        db.table("rosters")
        .select("id")
        .eq("team_id", team_id)
        .eq("slot", "IR")
        .execute()
    )
    return len(result.data or [])


async def place_on_ir(team_id: str, player_id: str) -> None:
    """
    Move a player from any active/bench slot to an IR slot.
    Player must have an IR-eligible NHL designation.
    """
    db = get_db()

    if not await is_ir_eligible(player_id):
        player = await db.table("nhl_players").select("full_name, status").eq("id", player_id).single().execute()
        name = player.data["full_name"] if player.data else "Player"
        status = player.data["status"] if player.data else "unknown"
        raise IRError(
            f"{name} is not IR eligible (current designation: {status}). "
            "Only IR, IR-LT, and OUT are eligible."
        )

    existing = await (
        db.table("rosters")
        .select("slot")
        .eq("team_id", team_id)
        .eq("player_id", player_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise IRError("Player is not on this team's roster")
    if existing.data["slot"] == "IR":
        raise IRError("Player is already in an IR slot")

    ir_used = await _count_ir_slots_used(team_id)
    if ir_used >= _MAX_IR_SLOTS:
        raise IRError(f"Team has no open IR slots ({_MAX_IR_SLOTS} slots are full)")

    await (
        db.table("rosters")
        .update({"slot": "IR"})
        .eq("team_id", team_id)
        .eq("player_id", player_id)
        .execute()
    )

    # Get league_id for move log
    team = await db.table("teams").select("league_id").eq("id", team_id).single().execute()
    league_id = team.data["league_id"]
    await log_move(league_id, team_id, "ir_place", player_id)
    log.info("ir_place  team=%s  player=%s", team_id, player_id)


async def activate_from_ir(team_id: str, player_id: str, target_slot: str) -> None:
    """
    Move a player from an IR slot to an active or bench slot.
    The player does NOT need to be IR-eligible to be activated
    (managers can hold recovered players in IR until they choose to move them).
    Target slot is validated for position eligibility and goalie limits.
    """
    from league.roster import validate_slot  # avoid circular at module level

    db = get_db()
    existing = await (
        db.table("rosters")
        .select("slot")
        .eq("team_id", team_id)
        .eq("player_id", player_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise IRError("Player is not on this team's roster")
    if existing.data["slot"] != "IR":
        raise IRError("Player is not in an IR slot")

    await validate_slot(team_id, player_id, target_slot)

    await (
        db.table("rosters")
        .update({"slot": target_slot})
        .eq("team_id", team_id)
        .eq("player_id", player_id)
        .execute()
    )

    team = await db.table("teams").select("league_id").eq("id", team_id).single().execute()
    league_id = team.data["league_id"]
    await log_move(league_id, team_id, "ir_activate", player_id)
    log.info("ir_activate  team=%s  player=%s  slot=%s", team_id, player_id, target_slot)
