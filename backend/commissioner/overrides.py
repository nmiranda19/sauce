"""
Commissioner override tools.

Covers:
- Waiver wire overrides (force a claim through, bypass timing and priority)
- Roster edits (force add/drop any player on any team)
- IR overrides (bypass eligibility designation check)
- Trade approval and veto (delegates to league/trades.py)
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta

from db import get_db
from commissioner.auth import require_commissioner
from commissioner.log import log_action
from league.roster import add_player, drop_player, RosterError
from league.ir_rules import IRError
from league.trades import commissioner_approve, commissioner_veto
from league.moves_log import log_move

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Waiver override
# ------------------------------------------------------------------ #

async def waiver_override(
    commissioner_id: str,
    team_id: str,
    player_id: str,
    slot: str,
    player_to_drop_id: str | None = None,
    notes: str | None = None,
) -> None:
    """
    Force a player onto a team's roster, bypassing priority order and 24-hour window.
    If player_to_drop_id is provided, that player is dropped to waivers first.
    """
    await require_commissioner(commissioner_id)
    db = get_db()

    # Drop a player first if requested
    if player_to_drop_id:
        try:
            await drop_player(team_id, player_to_drop_id)
        except RosterError as exc:
            raise RosterError(f"Could not drop {player_to_drop_id}: {exc}")

    # Add the player with commissioner bypass (skips add limit)
    await add_player(team_id, player_id, slot, source="waiver", commissioner_override=True)

    # Mark waiver entry as claimed if it exists
    await (
        db.table("waiver_wire")
        .update({"status": "claimed"})
        .eq("player_id", player_id)
        .execute()
    )

    # Fail any pending claims for this player from other teams
    await (
        db.table("waiver_claims")
        .update({
            "status": "failed",
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "override_by_commissioner": True,
        })
        .eq("player_to_add_id", player_id)
        .eq("status", "pending")
        .execute()
    )

    team = await db.table("teams").select("league_id").eq("id", team_id).single().execute()
    league_id = team.data["league_id"]
    await log_action(
        commissioner_id,
        "waiver_override",
        target_team_id=team_id,
        target_player_id=player_id,
        notes=notes,
    )
    log.info("Waiver override: team=%s player=%s slot=%s", team_id, player_id, slot)


# ------------------------------------------------------------------ #
# Roster edits
# ------------------------------------------------------------------ #

async def force_add_player(
    commissioner_id: str,
    team_id: str,
    player_id: str,
    slot: str,
    notes: str | None = None,
) -> None:
    """Add any player to any team, bypassing all limits."""
    await require_commissioner(commissioner_id)
    await add_player(team_id, player_id, slot, source="free_agent", commissioner_override=True)
    await log_action(
        commissioner_id, "roster_edit",
        target_team_id=team_id, target_player_id=player_id,
        notes=notes or f"Force-added to {slot}",
    )


async def force_drop_player(
    commissioner_id: str,
    team_id: str,
    player_id: str,
    notes: str | None = None,
) -> None:
    """Drop any player from any team."""
    await require_commissioner(commissioner_id)
    await drop_player(team_id, player_id)
    await log_action(
        commissioner_id, "roster_edit",
        target_team_id=team_id, target_player_id=player_id,
        notes=notes or "Force-dropped",
    )


async def force_move_player(
    commissioner_id: str,
    from_team_id: str,
    to_team_id: str,
    player_id: str,
    target_slot: str,
    notes: str | None = None,
) -> None:
    """Move a player directly between teams (outside of the trade system)."""
    await require_commissioner(commissioner_id)
    db = get_db()

    existing = await (
        db.table("rosters").select("slot")
        .eq("team_id", from_team_id).eq("player_id", player_id).single().execute()
    )
    if not existing.data:
        raise RosterError(f"Player is not on team {from_team_id}")

    await (
        db.table("rosters")
        .update({"team_id": to_team_id, "slot": target_slot})
        .eq("team_id", from_team_id).eq("player_id", player_id)
        .execute()
    )

    team = await db.table("teams").select("league_id").eq("id", to_team_id).single().execute()
    league_id = team.data["league_id"]
    await log_move(league_id, to_team_id, "add_free_agent", player_id)
    await log_action(
        commissioner_id, "roster_edit",
        target_team_id=to_team_id, target_player_id=player_id,
        notes=notes or f"Moved from team {from_team_id} to {to_team_id} ({target_slot})",
    )


# ------------------------------------------------------------------ #
# IR override
# ------------------------------------------------------------------ #

async def force_ir_place(
    commissioner_id: str,
    team_id: str,
    player_id: str,
    notes: str | None = None,
) -> None:
    """
    Place a player on IR regardless of their NHL injury designation.
    Useful when the API hasn't updated yet or for manual corrections.
    """
    await require_commissioner(commissioner_id)
    db = get_db()

    existing = await (
        db.table("rosters").select("slot")
        .eq("team_id", team_id).eq("player_id", player_id).single().execute()
    )
    if not existing.data:
        raise IRError("Player is not on this team")
    if existing.data["slot"] == "IR":
        raise IRError("Player is already in an IR slot")

    # Count IR slots
    ir_count = await (
        db.table("rosters").select("id")
        .eq("team_id", team_id).eq("slot", "IR").execute()
    )
    if len(ir_count.data or []) >= 3:
        raise IRError("Team already has 3 players on IR")

    await (
        db.table("rosters").update({"slot": "IR"})
        .eq("team_id", team_id).eq("player_id", player_id).execute()
    )

    team = await db.table("teams").select("league_id").eq("id", team_id).single().execute()
    league_id = team.data["league_id"]
    await log_move(league_id, team_id, "ir_place", player_id)
    await log_action(
        commissioner_id, "ir_override",
        target_team_id=team_id, target_player_id=player_id,
        notes=notes or "Force IR placement (bypassed eligibility check)",
    )


# ------------------------------------------------------------------ #
# Trade approval / veto (thin wrappers that add commissioner logging)
# ------------------------------------------------------------------ #

async def approve_trade(
    commissioner_id: str,
    trade_id: str,
    notes: str | None = None,
) -> None:
    await require_commissioner(commissioner_id)
    await commissioner_approve(trade_id, commissioner_id, notes)
    await log_action(
        commissioner_id, "trade_approved",
        target_trade_id=trade_id,
        notes=notes,
    )
    log.info("Trade %s approved by commissioner %s", trade_id, commissioner_id)


async def veto_trade(
    commissioner_id: str,
    trade_id: str,
    notes: str | None = None,
) -> None:
    await require_commissioner(commissioner_id)
    await commissioner_veto(trade_id, commissioner_id, notes)
    await log_action(
        commissioner_id, "trade_vetoed",
        target_trade_id=trade_id,
        notes=notes,
    )
    log.info("Trade %s vetoed by commissioner %s", trade_id, commissioner_id)
