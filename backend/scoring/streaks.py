"""
Daily snapshot job: compute 7-day rolling fantasy totals for every rostered player.
Writes to player_streaks table. Used by the Hot/Cold streak feed on the homepage.

Hot (Top 5): highest fantasy_score_7d across all rostered players (any slot)
Cold (Bottom 5): lowest fantasy_score_7d, EXCLUDING players in IR slots
"""
from __future__ import annotations
import logging
from datetime import date, timedelta

from db import get_db

log = logging.getLogger(__name__)


async def update_streaks(league_id: str, snapshot_date: date | None = None) -> None:
    """
    Compute 7-day rolling totals for all rostered players and upsert into player_streaks.
    snapshot_date defaults to today.
    """
    if snapshot_date is None:
        snapshot_date = date.today()

    db = get_db()
    window_start = snapshot_date - timedelta(days=6)  # inclusive 7-day window

    log.info("Updating streaks for league=%s  window=%s to %s", league_id, window_start, snapshot_date)

    # Get all teams in the league
    teams = await db.table("teams").select("id").eq("league_id", league_id).execute()
    team_ids = [t["id"] for t in (teams.data or [])]

    streak_rows = []
    for team_id in team_ids:
        # All rostered players on this team, in any slot (including bench; excluding nothing here)
        roster = await (
            db.table("rosters")
            .select("player_id, slot")
            .eq("team_id", team_id)
            .execute()
        )
        for r in (roster.data or []):
            player_id = r["player_id"]
            row = await _compute_player_streak(player_id, team_id, window_start, snapshot_date)
            streak_rows.append(row)

    if streak_rows:
        await db.table("player_streaks").upsert(
            streak_rows, on_conflict="player_id,snapshot_date"
        ).execute()

    log.info("Streak snapshot complete — %d player rows upserted", len(streak_rows))


async def _compute_player_streak(
    player_id: str,
    team_id: str,
    window_start: date,
    snapshot_date: date,
) -> dict:
    db = get_db()
    start_str = window_start.isoformat()
    end_str = snapshot_date.isoformat()

    # Fetch skater stats in window
    skater = await (
        db.table("player_stats")
        .select("goals, assists, plus_minus, shots_on_goal, toi_seconds, pp_points, sh_points, is_defenseman_point")
        .eq("player_id", player_id)
        .gte("game_date", start_str)
        .lte("game_date", end_str)
        .execute()
    )
    skater_rows = skater.data or []

    # Fetch goalie stats in window
    goalie = await (
        db.table("goalie_stats")
        .select("won, goals_against, saves, shots_against, toi_seconds")
        .eq("player_id", player_id)
        .gte("game_date", start_str)
        .lte("game_date", end_str)
        .execute()
    )
    goalie_rows = goalie.data or []

    return {
        "player_id": player_id,
        "team_id": team_id,
        "snapshot_date": end_str,
        # Skater rolling totals
        "goals_7d":             sum(r["goals"]   for r in skater_rows),
        "assists_7d":           sum(r["assists"]  for r in skater_rows),
        "plus_minus_7d":        sum(r["plus_minus"] for r in skater_rows),
        "shots_7d":             sum(r["shots_on_goal"] for r in skater_rows),
        "pp_points_7d":         sum(r["pp_points"] for r in skater_rows),
        "sh_points_7d":         sum(r["sh_points"] for r in skater_rows),
        "defenseman_points_7d": sum(
            r["goals"] + r["assists"] for r in skater_rows if r["is_defenseman_point"]
        ),
        "toi_seconds_7d":       sum(r["toi_seconds"] for r in skater_rows),
        # Goalie rolling totals
        "goalie_wins_7d":    sum(1 for r in goalie_rows if r["won"]),
        "goals_against_7d":  sum(r["goals_against"] for r in goalie_rows),
        "saves_7d":          sum(r["saves"] for r in goalie_rows),
        "shots_against_7d":  sum(r["shots_against"] for r in goalie_rows),
        "goalie_toi_7d":     sum(r["toi_seconds"] for r in goalie_rows),
    }
