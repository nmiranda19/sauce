"""
League settings management and week advancement.

Also provides the initial league/team creation helpers used during setup.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any

from db import get_db
from commissioner.auth import require_commissioner
from commissioner.log import log_action

log = logging.getLogger(__name__)

_EDITABLE_LEAGUE_FIELDS = {
    "name", "season_year", "current_week", "total_weeks",
    "playoff_start_week", "status",
}

_VALID_STATUSES = {"pre_season", "in_season", "playoffs", "offseason"}


class SettingsError(Exception):
    pass


# ------------------------------------------------------------------ #
# League creation (one-time setup, not restricted to commissioner)
# ------------------------------------------------------------------ #

async def create_league(
    name: str,
    season_year: int,
    total_weeks: int = 26,
) -> str:
    """Create the league record. Returns the league ID."""
    db = get_db()
    playoff_start = total_weeks - 4  # last 4 weeks, excluding the final week
    result = await db.table("league").insert({
        "name": name,
        "season_year": season_year,
        "current_week": 1,
        "total_weeks": total_weeks,
        "playoff_start_week": playoff_start,
        "status": "pre_season",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    league_id = result.data[0]["id"]
    log.info("League created: %s (id=%s)", name, league_id)
    return league_id


async def create_team(
    league_id: str,
    user_id: str,
    team_name: str,
    waiver_priority: int,
) -> str:
    """Create a team record. Returns the team ID."""
    db = get_db()
    result = await db.table("teams").insert({
        "league_id": league_id,
        "user_id": user_id,
        "name": team_name,
        "waiver_priority": waiver_priority,
        "wins": 0,
        "losses": 0,
        "ties": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    team_id = result.data[0]["id"]
    log.info("Team created: %s (id=%s) priority=%d", team_name, team_id, waiver_priority)
    return team_id


# ------------------------------------------------------------------ #
# Settings updates
# ------------------------------------------------------------------ #

async def update_league_settings(
    commissioner_id: str,
    league_id: str,
    updates: dict[str, Any],
) -> None:
    """
    Update one or more league settings fields.
    Only fields in _EDITABLE_LEAGUE_FIELDS are accepted.
    """
    await require_commissioner(commissioner_id)

    invalid = set(updates.keys()) - _EDITABLE_LEAGUE_FIELDS
    if invalid:
        raise SettingsError(f"Unknown or non-editable fields: {invalid}")

    if "status" in updates and updates["status"] not in _VALID_STATUSES:
        raise SettingsError(f"Invalid status '{updates['status']}'. Must be one of {_VALID_STATUSES}")

    if not updates:
        return

    db = get_db()
    await db.table("league").update(updates).eq("id", league_id).execute()
    await log_action(
        commissioner_id,
        "settings_change",
        notes=f"Updated league settings: {updates}",
    )
    log.info("League settings updated: %s → %s", league_id, updates)


async def advance_week(commissioner_id: str, league_id: str) -> int:
    """
    Score the current week then increment current_week.
    Returns the new week number.
    Transitions league status to 'playoffs' if the new week is the playoff start.
    """
    from scoring.matchup import score_week  # avoid circular at module level

    await require_commissioner(commissioner_id)
    db = get_db()

    league = await db.table("league").select("current_week, playoff_start_week, total_weeks, status").eq("id", league_id).single().execute()
    if not league.data:
        raise SettingsError("League not found")

    current = league.data["current_week"]
    playoff_start = league.data["playoff_start_week"]
    total = league.data["total_weeks"]

    if current >= total:
        raise SettingsError(f"Season is already at week {current} of {total} — cannot advance further")

    # Score the week that just ended
    log.info("Scoring week %d before advancing", current)
    await score_week(league_id, current)

    new_week = current + 1
    updates: dict[str, Any] = {"current_week": new_week}

    # Transition to playoffs if applicable
    if playoff_start and new_week == playoff_start and league.data["status"] == "in_season":
        updates["status"] = "playoffs"
        log.info("League transitioning to playoffs at week %d", new_week)

    # Transition to offseason after the final week
    if new_week > total:
        updates["status"] = "offseason"

    await db.table("league").update(updates).eq("id", league_id).execute()
    await log_action(
        commissioner_id,
        "settings_change",
        notes=f"Advanced league to week {new_week}",
    )
    log.info("League advanced to week %d", new_week)
    return new_week


async def set_waiver_priority_order(
    commissioner_id: str,
    league_id: str,
    priority_map: dict[str, int],
) -> None:
    """
    Manually set waiver priorities for all teams.
    priority_map = {team_id: priority_number, ...}
    Useful for setting up the initial snake draft order at season start.
    """
    await require_commissioner(commissioner_id)
    db = get_db()
    for team_id, priority in priority_map.items():
        await db.table("teams").update({"waiver_priority": priority}).eq("id", team_id).execute()
    await log_action(
        commissioner_id,
        "settings_change",
        notes=f"Set waiver priority order for {len(priority_map)} teams",
    )
    log.info("Waiver priorities set for %d teams", len(priority_map))


async def schedule_matchups(
    commissioner_id: str,
    league_id: str,
    matchups: list[dict],
) -> int:
    """
    Create the weekly matchup schedule for the season.

    matchups = [
        {"week_number": 1, "home_team_id": "...", "away_team_id": "...", "is_playoff": False},
        ...
    ]
    Returns number of matchups created.
    """
    await require_commissioner(commissioner_id)
    db = get_db()

    rows = [
        {
            "league_id": league_id,
            "week_number": m["week_number"],
            "home_team_id": m["home_team_id"],
            "away_team_id": m["away_team_id"],
            "is_playoff": m.get("is_playoff", False),
            "status": "scheduled",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        for m in matchups
    ]
    await db.table("weekly_matchups").insert(rows).execute()
    await log_action(
        commissioner_id,
        "settings_change",
        notes=f"Scheduled {len(rows)} matchups for league {league_id}",
    )
    log.info("Scheduled %d matchups", len(rows))
    return len(rows)
