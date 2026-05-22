"""
Commissioner draft population tool.

After the offline draft, the commissioner assigns players to teams one at a time
or in bulk. All normal checks (add limits, availability) are bypassed.
Players must exist in nhl_players (run sync_all_players first).
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from db import get_db
from commissioner.auth import require_commissioner
from commissioner.log import log_action
from league.roster import validate_slot

log = logging.getLogger(__name__)


class DraftError(Exception):
    pass


async def assign_player(
    commissioner_id: str,
    team_id: str,
    player_id: str,
    slot: str,
    notes: str | None = None,
) -> None:
    """
    Assign a single player to a team in the specified slot.
    Bypasses add limits and waiver wire. Validates slot/position eligibility.
    """
    await require_commissioner(commissioner_id)

    db = get_db()

    # Ensure player exists
    player = await db.table("nhl_players").select("id, full_name").eq("id", player_id).single().execute()
    if not player.data:
        raise DraftError(f"Player {player_id} not found — run NHL player sync first")

    # Ensure team exists
    team = await db.table("teams").select("id, league_id, name").eq("id", team_id).single().execute()
    if not team.data:
        raise DraftError(f"Team {team_id} not found")

    # Check not already rostered
    existing = await db.table("rosters").select("team_id").eq("player_id", player_id).execute()
    if existing.data:
        raise DraftError(f"{player.data['full_name']} is already rostered")

    # Validate slot eligibility (goalie limit still enforced for draft)
    await validate_slot(team_id, player_id, slot)

    await db.table("rosters").insert({
        "team_id": team_id,
        "player_id": player_id,
        "slot": slot,
        "assigned_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    await log_action(
        commissioner_id,
        action_type="player_assign",
        target_team_id=team_id,
        target_player_id=player_id,
        notes=notes or f"Draft assignment to {team.data['name']} ({slot})",
    )
    log.info("Draft assign: %s → team=%s slot=%s", player.data["full_name"], team_id, slot)


async def bulk_assign(
    commissioner_id: str,
    assignments: list[dict],
) -> dict:
    """
    Assign multiple players in one call.

    assignments = [
        {"team_id": "...", "player_id": "...", "slot": "C"},
        ...
    ]

    Returns {"success": [...], "errors": [...]}.
    """
    await require_commissioner(commissioner_id)

    success = []
    errors = []
    for a in assignments:
        try:
            await assign_player(
                commissioner_id,
                team_id=a["team_id"],
                player_id=a["player_id"],
                slot=a["slot"],
                notes=a.get("notes"),
            )
            success.append(a["player_id"])
        except Exception as exc:
            errors.append({"player_id": a.get("player_id"), "error": str(exc)})

    log.info("Bulk draft assign: %d success, %d errors", len(success), len(errors))
    return {"success": success, "errors": errors}


async def clear_team_roster(commissioner_id: str, team_id: str) -> int:
    """Remove all players from a team's roster (use to redo a draft assignment)."""
    await require_commissioner(commissioner_id)
    db = get_db()
    result = await db.table("rosters").delete().eq("team_id", team_id).execute()
    count = len(result.data or [])
    await log_action(commissioner_id, "roster_edit", target_team_id=team_id, notes=f"Cleared roster ({count} players removed)")
    log.info("Cleared roster for team=%s (%d players)", team_id, count)
    return count
