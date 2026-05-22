"""Matchup and scoring endpoints."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from api.deps import get_current_user, get_my_team, get_league_id
from scoring.weekly_totals import get_team_week_totals
from scoring.category_engine import score_categories, tally_record
from db import get_db

router = APIRouter(prefix="/matchups", tags=["matchups"])


@router.get("/current")
async def current_matchup(
    team: dict = Depends(get_my_team),
    league_id: str = Depends(get_league_id),
    _: dict = Depends(get_current_user),
):
    db = get_db()
    league = await db.table("league").select("current_week, season_year").eq("id", league_id).single().execute()
    week = league.data["current_week"]
    season_year = league.data["season_year"]

    matchup = await (
        db.table("weekly_matchups")
        .select("id, week_number, is_playoff, status, home_team_id, away_team_id")
        .eq("league_id", league_id)
        .eq("week_number", week)
        .or_(f"home_team_id.eq.{team['id']},away_team_id.eq.{team['id']}")
        .single()
        .execute()
    )
    if not matchup.data:
        raise HTTPException(404, "No matchup found for current week")

    return await _build_matchup_detail(matchup.data, season_year)


@router.get("/week/{week_number}")
async def week_matchups(
    week_number: int,
    league_id: str = Depends(get_league_id),
    _: dict = Depends(get_current_user),
):
    db = get_db()
    league = await db.table("league").select("season_year").eq("id", league_id).single().execute()
    season_year = league.data["season_year"]

    result = await (
        db.table("weekly_matchups")
        .select("id, week_number, is_playoff, status, home_team_id, away_team_id")
        .eq("league_id", league_id)
        .eq("week_number", week_number)
        .execute()
    )
    matchups = []
    for m in (result.data or []):
        matchups.append(await _build_matchup_detail(m, season_year))
    return matchups


@router.get("/{matchup_id}")
async def get_matchup(matchup_id: str, _: dict = Depends(get_current_user)):
    db = get_db()
    matchup = await (
        db.table("weekly_matchups")
        .select("id, week_number, is_playoff, status, home_team_id, away_team_id, league_id")
        .eq("id", matchup_id)
        .single()
        .execute()
    )
    if not matchup.data:
        raise HTTPException(404, "Matchup not found")
    m = matchup.data
    league = await db.table("league").select("season_year").eq("id", m["league_id"]).single().execute()
    return await _build_matchup_detail(m, league.data["season_year"])


async def _build_matchup_detail(matchup: dict, season_year: int) -> dict:
    db = get_db()
    home_id = matchup["home_team_id"]
    away_id = matchup["away_team_id"]
    week = matchup["week_number"]

    # Team info
    home_team = await db.table("teams").select("id, name, wins, losses, ties").eq("id", home_id).single().execute()
    away_team = await db.table("teams").select("id, name, wins, losses, ties").eq("id", away_id).single().execute()

    # If matchup is complete, return stored results
    if matchup["status"] == "complete":
        cat_results = await (
            db.table("weekly_category_results")
            .select("category, home_value, away_value, winner")
            .eq("matchup_id", matchup["id"])
            .execute()
        )
        records = await (
            db.table("weekly_matchup_record")
            .select("team_id, wins, losses, ties")
            .eq("matchup_id", matchup["id"])
            .execute()
        )
        record_map = {r["team_id"]: r for r in (records.data or [])}
        return {
            "matchup_id": matchup["id"],
            "week_number": week,
            "is_playoff": matchup["is_playoff"],
            "status": matchup["status"],
            "home_team": home_team.data,
            "away_team": away_team.data,
            "home_record": record_map.get(home_id, {}),
            "away_record": record_map.get(away_id, {}),
            "categories": cat_results.data or [],
        }

    # Live/in-progress: compute totals on the fly
    import asyncio
    home_totals, away_totals = await asyncio.gather(
        get_team_week_totals(home_id, week, season_year),
        get_team_week_totals(away_id, week, season_year),
    )
    cat_results = score_categories(home_totals, away_totals)
    home_rec, away_rec = tally_record(cat_results)

    return {
        "matchup_id": matchup["id"],
        "week_number": week,
        "is_playoff": matchup["is_playoff"],
        "status": matchup["status"],
        "home_team": home_team.data,
        "away_team": away_team.data,
        "home_totals": home_totals,
        "away_totals": away_totals,
        "home_record": home_rec,
        "away_record": away_rec,
        "categories": cat_results,
    }
