"""Player search and detail endpoints."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from api.deps import get_current_user, get_league_id
from db import get_db

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/")
async def search_players(
    q: str = Query("", description="Name search"),
    position: str = Query("", description="C, LW, RW, D, or G"),
    nhl_team: str = Query("", description="Team abbreviation e.g. EDM"),
    limit: int = Query(25, le=100),
    _: dict = Depends(get_current_user),
):
    db = get_db()
    query = db.table("nhl_players").select(
        "id, full_name, position, nhl_team_abbrev, jersey_number, status, headshot_url"
    )
    if q:
        query = query.ilike("full_name", f"%{q}%")
    if position:
        query = query.eq("position", position.upper())
    if nhl_team:
        query = query.eq("nhl_team_abbrev", nhl_team.upper())
    result = await query.order("full_name").limit(limit).execute()
    return result.data or []


@router.get("/available")
async def available_players(
    league_id: str = Depends(get_league_id),
    q: str = Query(""),
    position: str = Query(""),
    limit: int = Query(50, le=200),
    _: dict = Depends(get_current_user),
):
    """Players currently on waivers or available as free agents (not on any roster)."""
    db = get_db()

    # Players on waivers with claimable status
    waiver_q = (
        db.table("waiver_wire")
        .select(
            "status, claimable_at, "
            "nhl_players(id, full_name, position, nhl_team_abbrev, jersey_number, status, headshot_url)"
        )
        .in_("status", ["on_waivers", "free_agent"])
    )
    waiver_result = await waiver_q.execute()
    waiver_rows = waiver_result.data or []

    # All rostered player IDs
    rostered = await db.table("rosters").select("player_id").execute()
    rostered_ids = {r["player_id"] for r in (rostered.data or [])}

    # On-waiver player IDs
    waiver_player_ids = {r["nhl_players"]["id"] for r in waiver_rows if r.get("nhl_players")}

    # Free agents: in nhl_players, not rostered, not on waivers
    fa_query = (
        db.table("nhl_players")
        .select("id, full_name, position, nhl_team_abbrev, jersey_number, status, headshot_url")
        .eq("status", "active")
    )
    if q:
        fa_query = fa_query.ilike("full_name", f"%{q}%")
    if position:
        fa_query = fa_query.eq("position", position.upper())
    fa_result = await fa_query.limit(200).execute()
    free_agents = [
        p for p in (fa_result.data or [])
        if p["id"] not in rostered_ids and p["id"] not in waiver_player_ids
    ]

    # Build response combining waivers and FAs
    response = []
    for w in waiver_rows:
        p = w.get("nhl_players", {})
        if not p:
            continue
        if q and q.lower() not in p.get("full_name", "").lower():
            continue
        if position and p.get("position", "").upper() != position.upper():
            continue
        response.append({**p, "availability": w["status"], "claimable_at": w.get("claimable_at")})

    for p in free_agents:
        response.append({**p, "availability": "free_agent", "claimable_at": None})

    return response[:limit]


@router.get("/{player_id}")
async def get_player(player_id: str, _: dict = Depends(get_current_user)):
    db = get_db()
    result = await (
        db.table("nhl_players")
        .select("*")
        .eq("id", player_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Player not found")
    return result.data
