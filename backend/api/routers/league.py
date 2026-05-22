"""League-wide endpoints: standings, news feed, hot/cold streaks, recent moves."""
from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Depends, Query
from api.deps import get_current_user, get_league_id
from db import get_db

router = APIRouter(prefix="/league", tags=["league"])


@router.get("/")
async def get_league(league_id: str = Depends(get_league_id)):
    db = get_db()
    result = await db.table("league").select("*").eq("id", league_id).single().execute()
    return result.data


@router.get("/standings")
async def get_standings(league_id: str = Depends(get_league_id)):
    db = get_db()
    result = await (
        db.table("teams")
        .select("id, name, wins, losses, ties, waiver_priority, users(name)")
        .eq("league_id", league_id)
        .order("wins", desc=True)
        .order("ties", desc=True)
        .execute()
    )
    return result.data or []


@router.get("/news")
async def get_news(limit: int = Query(50, le=100)):
    db = get_db()
    result = await (
        db.table("news_feed")
        .select("id, source_type, source_name, headline, body, url, published_at")
        .order("published_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


@router.get("/streaks")
async def get_streaks(league_id: str = Depends(get_league_id)):
    """
    Returns hot (top 5) and cold (bottom 5) players based on today's streak snapshot.
    Cold excludes players in IR slots.
    """
    db = get_db()
    today = date.today().isoformat()

    # Get team IDs in league
    teams = await db.table("teams").select("id").eq("league_id", league_id).execute()
    team_ids = [t["id"] for t in (teams.data or [])]
    if not team_ids:
        return {"hot": [], "cold": []}

    # Fetch today's snapshots for all rostered players
    snapshots = await (
        db.table("player_streaks")
        .select(
            "player_id, team_id, fantasy_score_7d, goals_7d, assists_7d, "
            "plus_minus_7d, shots_7d, goalie_wins_7d, "
            "nhl_players(full_name, position, nhl_team_abbrev, headshot_url), "
            "teams(name)"
        )
        .in_("team_id", team_ids)
        .eq("snapshot_date", today)
        .execute()
    )
    rows = snapshots.data or []

    # Find IR-slotted players to exclude from cold list
    ir_players = await (
        db.table("rosters")
        .select("player_id")
        .in_("team_id", team_ids)
        .eq("slot", "IR")
        .execute()
    )
    ir_ids = {r["player_id"] for r in (ir_players.data or [])}

    sorted_desc = sorted(rows, key=lambda r: r["fantasy_score_7d"] or 0, reverse=True)
    hot = sorted_desc[:5]
    cold_eligible = [r for r in sorted_desc if r["player_id"] not in ir_ids]
    cold = cold_eligible[-5:][::-1]  # lowest 5, ascending from worst

    return {"hot": hot, "cold": cold}


@router.get("/moves")
async def get_recent_moves(
    limit: int = Query(30, le=100),
    league_id: str = Depends(get_league_id),
):
    db = get_db()
    result = await (
        db.table("league_moves")
        .select(
            "id, move_type, created_at, "
            "teams(name), "
            "nhl_players(full_name, position, nhl_team_abbrev)"
        )
        .eq("league_id", league_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []
