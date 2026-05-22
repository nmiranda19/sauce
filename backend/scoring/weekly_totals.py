"""
Aggregate per-team weekly fantasy stats from player_stats and goalie_stats.
Returns the raw numbers that feed into category comparison.

Scoring uses the current roster slot to determine who counts.
Active slots: C, LW, RW, D, UTIL  → skater stats count
Active slot:  G                    → goalie stats count
Bench (BN) and IR slots are excluded.
"""
from __future__ import annotations
from db import get_db

_ACTIVE_SKATER_SLOTS = ("C", "LW", "RW", "D", "UTIL")
_ACTIVE_GOALIE_SLOTS = ("G",)


async def _get_active_player_ids(team_id: str, slots: tuple) -> list[str]:
    db = get_db()
    result = await (
        db.table("rosters")
        .select("player_id")
        .eq("team_id", team_id)
        .in_("slot", list(slots))
        .execute()
    )
    return [r["player_id"] for r in (result.data or [])]


async def get_skater_week_totals(team_id: str, week_number: int, season_year: int) -> dict:
    """
    Returns dict with keys:
      goals, assists, plus_minus, shots_on_goal,
      defenseman_points, special_teams_points, average_toi
    All zero if no active skaters or no stats for the week.
    """
    player_ids = await _get_active_player_ids(team_id, _ACTIVE_SKATER_SLOTS)
    if not player_ids:
        return _zero_skater_totals()

    db = get_db()
    result = await (
        db.table("player_stats")
        .select(
            "goals, assists, plus_minus, shots_on_goal, "
            "toi_seconds, pp_points, sh_points, is_defenseman_point"
        )
        .in_("player_id", player_ids)
        .eq("week_number", week_number)
        .eq("season_year", season_year)
        .execute()
    )
    rows = result.data or []
    if not rows:
        return _zero_skater_totals()

    goals = sum(r["goals"] for r in rows)
    assists = sum(r["assists"] for r in rows)
    plus_minus = sum(r["plus_minus"] for r in rows)
    shots = sum(r["shots_on_goal"] for r in rows)
    pp_pts = sum(r["pp_points"] for r in rows)
    sh_pts = sum(r["sh_points"] for r in rows)

    # Defenseman points: goals + assists for rows flagged as defenseman
    d_pts = sum(
        r["goals"] + r["assists"]
        for r in rows
        if r["is_defenseman_point"]
    )

    # Average TOI: total seconds / game-appearances, converted to minutes
    total_toi = sum(r["toi_seconds"] for r in rows)
    game_count = len(rows)
    avg_toi = round((total_toi / game_count) / 60, 4) if game_count else 0.0

    return {
        "goals": goals,
        "assists": assists,
        "plus_minus": plus_minus,
        "shots_on_goal": shots,
        "defenseman_points": d_pts,
        "special_teams_points": pp_pts + sh_pts,
        "average_toi": avg_toi,
    }


async def get_goalie_week_totals(team_id: str, week_number: int, season_year: int) -> dict:
    """
    Returns dict with keys:
      goalie_wins, gaa, save_pct, goalies_started
    GAA and save_pct are None if no games were played (forces auto-loss when < 3 started).
    """
    player_ids = await _get_active_player_ids(team_id, _ACTIVE_GOALIE_SLOTS)
    if not player_ids:
        return _zero_goalie_totals()

    db = get_db()
    result = await (
        db.table("goalie_stats")
        .select("player_id, won, goals_against, shots_against, saves, toi_seconds")
        .in_("player_id", player_ids)
        .eq("week_number", week_number)
        .eq("season_year", season_year)
        .execute()
    )
    rows = result.data or []
    if not rows:
        return _zero_goalie_totals()

    wins = sum(1 for r in rows if r["won"])
    total_ga = sum(r["goals_against"] for r in rows)
    total_shots = sum(r["shots_against"] for r in rows)
    total_saves = sum(r["saves"] for r in rows)
    total_toi_secs = sum(r["toi_seconds"] for r in rows)

    # Count distinct goalies who played (toi > 0)
    started_ids = {r["player_id"] for r in rows if r["toi_seconds"] > 0}
    goalies_started = len(started_ids)

    # GAA = goals against per 60 minutes
    total_toi_mins = total_toi_secs / 60
    gaa = round((total_ga / total_toi_mins) * 60, 4) if total_toi_mins > 0 else None

    # SV% = saves / shots against
    save_pct = round(total_saves / total_shots, 4) if total_shots > 0 else None

    return {
        "goalie_wins": wins,
        "gaa": gaa,
        "save_pct": save_pct,
        "goalies_started": goalies_started,
    }


async def get_team_week_totals(team_id: str, week_number: int, season_year: int) -> dict:
    """All 10 categories plus goalies_started for the 3-goalie rule check."""
    skater = await get_skater_week_totals(team_id, week_number, season_year)
    goalie = await get_goalie_week_totals(team_id, week_number, season_year)
    return {**skater, **goalie}


def _zero_skater_totals() -> dict:
    return {
        "goals": 0,
        "assists": 0,
        "plus_minus": 0,
        "shots_on_goal": 0,
        "defenseman_points": 0,
        "special_teams_points": 0,
        "average_toi": 0.0,
    }


def _zero_goalie_totals() -> dict:
    return {
        "goalie_wins": 0,
        "gaa": None,
        "save_pct": None,
        "goalies_started": 0,
    }
