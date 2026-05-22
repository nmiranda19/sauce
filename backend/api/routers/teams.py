"""Team and roster endpoints."""
from __future__ import annotations
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from api.deps import get_current_user, get_my_team, get_league_id
from db import get_db
from config import SEASON_START_DATE

router = APIRouter(prefix="/teams", tags=["teams"])


def _games_remaining_in_week(week_number: int, today: date) -> tuple[date, date]:
    """Return (week_start, week_end) for the given week number."""
    week_start = SEASON_START_DATE + timedelta(weeks=week_number - 1)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


async def _attach_games_remaining(players: list[dict], week_number: int) -> list[dict]:
    """Add games_remaining_this_week to each player dict."""
    db = get_db()
    today = date.today()
    _, week_end = _games_remaining_in_week(week_number, today)
    today_str = today.isoformat()
    week_end_str = week_end.isoformat()

    # Batch fetch remaining game counts per team abbreviation
    abbrevs = list({p["nhl_players"]["nhl_team_abbrev"] for p in players if p.get("nhl_players")})
    if not abbrevs:
        for p in players:
            p["games_remaining_this_week"] = 0
        return players

    games = await (
        db.table("games")
        .select("home_team_abbrev, away_team_abbrev")
        .eq("week_number", week_number)
        .in_("status", ["scheduled", "live"])
        .gte("game_date", today_str)
        .lte("game_date", week_end_str)
        .execute()
    )
    counts: dict[str, int] = {}
    for g in (games.data or []):
        for abbrev in (g["home_team_abbrev"], g["away_team_abbrev"]):
            counts[abbrev] = counts.get(abbrev, 0) + 1

    for p in players:
        abbrev = (p.get("nhl_players") or {}).get("nhl_team_abbrev", "")
        p["games_remaining_this_week"] = counts.get(abbrev, 0)
    return players


@router.get("/me")
async def my_team(team: dict = Depends(get_my_team)):
    return team


@router.get("/me/roster")
async def my_roster(
    team: dict = Depends(get_my_team),
    league_id: str = Depends(get_league_id),
):
    db = get_db()
    league = await db.table("league").select("current_week").eq("id", league_id).single().execute()
    week = league.data["current_week"]

    result = await (
        db.table("rosters")
        .select(
            "slot, assigned_at, "
            "nhl_players(id, full_name, position, nhl_team_abbrev, jersey_number, status, headshot_url)"
        )
        .eq("team_id", team["id"])
        .execute()
    )
    players = result.data or []
    return await _attach_games_remaining(players, week)


@router.get("/{team_id}")
async def get_team(team_id: str, _: dict = Depends(get_current_user)):
    db = get_db()
    result = await (
        db.table("teams")
        .select("id, name, wins, losses, ties, waiver_priority, users(name)")
        .eq("id", team_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Team not found")
    return result.data


@router.get("/{team_id}/roster")
async def get_team_roster(
    team_id: str,
    league_id: str = Depends(get_league_id),
    _: dict = Depends(get_current_user),
):
    db = get_db()
    league = await db.table("league").select("current_week").eq("id", league_id).single().execute()
    week = league.data["current_week"]

    result = await (
        db.table("rosters")
        .select(
            "slot, "
            "nhl_players(id, full_name, position, nhl_team_abbrev, jersey_number, status, headshot_url)"
        )
        .eq("team_id", team_id)
        .execute()
    )
    players = result.data or []
    return await _attach_games_remaining(players, week)
