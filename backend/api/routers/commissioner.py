"""All commissioner-only API endpoints. Fully mobile-compatible."""
from __future__ import annotations
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_current_commissioner, get_league_id
from commissioner.draft import assign_player, bulk_assign, clear_team_roster
from commissioner.overrides import (
    waiver_override, force_add_player, force_drop_player,
    force_move_player, force_ir_place, approve_trade, veto_trade,
)
from commissioner.settings import update_league_settings, advance_week
from league.ir_rules import place_on_ir, activate_from_ir, IRError
from db import get_db

router = APIRouter(prefix="/commissioner", tags=["commissioner"])


# ------------------------------------------------------------------ #
# Models
# ------------------------------------------------------------------ #

class DraftAssign(BaseModel):
    team_id: str
    player_id: str
    slot: str
    notes: Optional[str] = None


class BulkDraftAssign(BaseModel):
    assignments: list[dict]


class WaiverOverrideReq(BaseModel):
    team_id: str
    player_id: str
    slot: str
    player_to_drop_id: Optional[str] = None
    notes: Optional[str] = None


class ForceAddReq(BaseModel):
    team_id: str
    player_id: str
    slot: str
    notes: Optional[str] = None


class ForceDropReq(BaseModel):
    team_id: str
    player_id: str
    notes: Optional[str] = None


class ForceMoveReq(BaseModel):
    from_team_id: str
    to_team_id: str
    player_id: str
    target_slot: str
    notes: Optional[str] = None


class ForceIRReq(BaseModel):
    team_id: str
    player_id: str
    notes: Optional[str] = None


class TradeActionReq(BaseModel):
    trade_id: str
    notes: Optional[str] = None


class SettingsUpdate(BaseModel):
    updates: dict[str, Any]


# ------------------------------------------------------------------ #
# Draft tools
# ------------------------------------------------------------------ #

@router.post("/draft/assign", status_code=201)
async def draft_assign(body: DraftAssign, user: dict = Depends(get_current_commissioner)):
    try:
        await assign_player(user["id"], body.team_id, body.player_id, body.slot, body.notes)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@router.post("/draft/bulk", status_code=201)
async def draft_bulk(body: BulkDraftAssign, user: dict = Depends(get_current_commissioner)):
    result = await bulk_assign(user["id"], body.assignments)
    return result


@router.delete("/teams/{team_id}/roster")
async def clear_roster(team_id: str, user: dict = Depends(get_current_commissioner)):
    count = await clear_team_roster(user["id"], team_id)
    return {"players_removed": count}


# ------------------------------------------------------------------ #
# Waiver & roster overrides
# ------------------------------------------------------------------ #

@router.post("/waiver/override")
async def waiver_override_endpoint(body: WaiverOverrideReq, user: dict = Depends(get_current_commissioner)):
    try:
        await waiver_override(user["id"], body.team_id, body.player_id, body.slot, body.player_to_drop_id, body.notes)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@router.post("/roster/add")
async def force_add(body: ForceAddReq, user: dict = Depends(get_current_commissioner)):
    try:
        await force_add_player(user["id"], body.team_id, body.player_id, body.slot, body.notes)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@router.post("/roster/drop")
async def force_drop(body: ForceDropReq, user: dict = Depends(get_current_commissioner)):
    try:
        await force_drop_player(user["id"], body.team_id, body.player_id, body.notes)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@router.post("/roster/move")
async def force_move(body: ForceMoveReq, user: dict = Depends(get_current_commissioner)):
    try:
        await force_move_player(user["id"], body.from_team_id, body.to_team_id, body.player_id, body.target_slot, body.notes)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@router.post("/ir/place")
async def force_ir(body: ForceIRReq, user: dict = Depends(get_current_commissioner)):
    try:
        await force_ir_place(user["id"], body.team_id, body.player_id, body.notes)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


# ------------------------------------------------------------------ #
# Trade approval
# ------------------------------------------------------------------ #

@router.post("/trades/approve")
async def approve(body: TradeActionReq, user: dict = Depends(get_current_commissioner)):
    try:
        await approve_trade(user["id"], body.trade_id, body.notes)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@router.post("/trades/veto")
async def veto(body: TradeActionReq, user: dict = Depends(get_current_commissioner)):
    try:
        await veto_trade(user["id"], body.trade_id, body.notes)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@router.get("/trades/pending")
async def pending_trades(
    league_id: str = Depends(get_league_id),
    _: dict = Depends(get_current_commissioner),
):
    db = get_db()
    teams = await db.table("teams").select("id").eq("league_id", league_id).execute()
    team_ids = [t["id"] for t in (teams.data or [])]
    result = await (
        db.table("trade_proposals")
        .select("id, status, proposed_at, accepted_at, commissioner_deadline, "
                "proposing_team:teams!proposing_team_id(name), "
                "receiving_team:teams!receiving_team_id(name)")
        .in_("proposing_team_id", team_ids)
        .in_("status", ["pending", "accepted"])
        .order("proposed_at", desc=True)
        .execute()
    )
    return result.data or []


# ------------------------------------------------------------------ #
# Settings and week advancement
# ------------------------------------------------------------------ #

@router.put("/settings")
async def update_settings(
    body: SettingsUpdate,
    league_id: str = Depends(get_league_id),
    user: dict = Depends(get_current_commissioner),
):
    try:
        await update_league_settings(user["id"], league_id, body.updates)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@router.post("/advance-week")
async def advance_week_endpoint(
    league_id: str = Depends(get_league_id),
    user: dict = Depends(get_current_commissioner),
):
    try:
        new_week = await advance_week(user["id"], league_id)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"new_week": new_week}


# ------------------------------------------------------------------ #
# Commissioner audit log
# ------------------------------------------------------------------ #

@router.get("/log")
async def commissioner_log(_: dict = Depends(get_current_commissioner)):
    db = get_db()
    result = await (
        db.table("commissioner_log")
        .select("id, action_type, notes, created_at, "
                "users!commissioner_id(name), "
                "teams!target_team_id(name), "
                "nhl_players!target_player_id(full_name)")
        .order("created_at", desc=True)
        .limit(200)
        .execute()
    )
    return result.data or []
