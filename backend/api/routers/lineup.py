"""Lineup management: swap slots, lock status."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.deps import get_current_user, get_my_team, get_league_id
from league.roster import swap_slot, RosterError
from league.lineup import is_lineup_locked, get_lineup_lock_time

router = APIRouter(prefix="/lineup", tags=["lineup"])


class SlotSwap(BaseModel):
    player_id: str
    new_slot: str


@router.get("/lock")
async def lineup_lock_status():
    locked = await is_lineup_locked()
    lock_time = await get_lineup_lock_time()
    return {"locked": locked, "lock_time": lock_time}


@router.put("/slot")
async def swap_player_slot(
    body: SlotSwap,
    team: dict = Depends(get_my_team),
    _: dict = Depends(get_current_user),
):
    try:
        await swap_slot(team["id"], body.player_id, body.new_slot)
    except RosterError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "player_id": body.player_id, "new_slot": body.new_slot}
