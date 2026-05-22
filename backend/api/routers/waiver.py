"""Waiver wire endpoints."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.deps import get_current_user, get_my_team, get_league_id
from league.waiver import submit_claim, WaiverError
from league.roster import drop_player, add_player, validate_adds_remaining, RosterError
from db import get_db

router = APIRouter(prefix="/waiver", tags=["waiver"])


class ClaimRequest(BaseModel):
    player_to_add_id: str
    player_to_drop_id: Optional[str] = None
    target_slot: str


class FreeAgentAdd(BaseModel):
    player_id: str
    slot: str
    player_to_drop_id: Optional[str] = None


@router.get("/priority")
async def waiver_priority(league_id: str = Depends(get_league_id), _: dict = Depends(get_current_user)):
    db = get_db()
    result = await (
        db.table("teams")
        .select("id, name, waiver_priority, users(name)")
        .eq("league_id", league_id)
        .order("waiver_priority")
        .execute()
    )
    return result.data or []


@router.get("/claims/mine")
async def my_claims(team: dict = Depends(get_my_team), _: dict = Depends(get_current_user)):
    db = get_db()
    result = await (
        db.table("waiver_claims")
        .select(
            "id, status, priority_at_claim, created_at, processed_at, "
            "nhl_players!player_to_add_id(full_name, position, nhl_team_abbrev)"
        )
        .eq("team_id", team["id"])
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return result.data or []


@router.post("/claim", status_code=201)
async def submit_waiver_claim(
    body: ClaimRequest,
    team: dict = Depends(get_my_team),
    league_id: str = Depends(get_league_id),
    _: dict = Depends(get_current_user),
):
    try:
        claim_id = await submit_claim(
            team_id=team["id"],
            player_to_add_id=body.player_to_add_id,
            player_to_drop_id=body.player_to_drop_id,
            target_slot=body.target_slot,
            league_id=league_id,
        )
    except WaiverError as exc:
        raise HTTPException(400, str(exc))
    return {"claim_id": claim_id}


@router.post("/add", status_code=201)
async def add_free_agent(
    body: FreeAgentAdd,
    team: dict = Depends(get_my_team),
    league_id: str = Depends(get_league_id),
    _: dict = Depends(get_current_user),
):
    """Add a free agent directly (not on waivers, available immediately)."""
    try:
        await validate_adds_remaining(team["id"], league_id)
        if body.player_to_drop_id:
            await drop_player(team["id"], body.player_to_drop_id)
        await add_player(team["id"], body.player_id, body.slot, source="free_agent")
    except RosterError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@router.post("/drop", status_code=200)
async def drop_player_endpoint(
    player_id: str,
    team: dict = Depends(get_my_team),
    _: dict = Depends(get_current_user),
):
    try:
        await drop_player(team["id"], player_id)
    except RosterError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}
