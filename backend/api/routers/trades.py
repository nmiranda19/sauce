"""Trade endpoints including category impact preview."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.deps import get_current_user, get_my_team, get_league_id
from league.trades import (
    propose_trade, respond_to_trade, withdraw_trade, TradeError
)
from db import get_db

router = APIRouter(prefix="/trades", tags=["trades"])


class TradeProposal(BaseModel):
    receiving_team_id: str
    players_from_me: list[str]      # player UUIDs I'm sending
    players_from_them: list[str]    # player UUIDs I'm receiving


class TradeResponse(BaseModel):
    accept: bool


@router.get("/")
async def list_trades(
    league_id: str = Depends(get_league_id),
    _: dict = Depends(get_current_user),
):
    db = get_db()
    # Get all teams in league to filter trades
    teams = await db.table("teams").select("id").eq("league_id", league_id).execute()
    team_ids = [t["id"] for t in (teams.data or [])]
    if not team_ids:
        return []
    result = await (
        db.table("trade_proposals")
        .select(
            "id, status, proposed_at, accepted_at, resolved_at, commissioner_notes, commissioner_deadline, "
            "proposing_team:teams!proposing_team_id(id, name), "
            "receiving_team:teams!receiving_team_id(id, name)"
        )
        .in_("proposing_team_id", team_ids)
        .order("proposed_at", desc=True)
        .limit(100)
        .execute()
    )
    return result.data or []


@router.get("/{trade_id}")
async def get_trade(trade_id: str, _: dict = Depends(get_current_user)):
    db = get_db()
    trade = await db.table("trade_proposals").select("*").eq("id", trade_id).single().execute()
    if not trade.data:
        raise HTTPException(404, "Trade not found")

    assets = await (
        db.table("trade_assets")
        .select(
            "player_id, from_team_id, to_team_id, "
            "nhl_players(full_name, position, nhl_team_abbrev)"
        )
        .eq("trade_id", trade_id)
        .execute()
    )
    return {**trade.data, "assets": assets.data or []}


@router.get("/{trade_id}/impact")
async def trade_category_impact(
    trade_id: str,
    league_id: str = Depends(get_league_id),
    _: dict = Depends(get_current_user),
):
    """
    Preview how this trade affects each team's category totals
    based on season-to-date stats.
    """
    db = get_db()
    trade = await db.table("trade_proposals").select("*").eq("id", trade_id).single().execute()
    if not trade.data:
        raise HTTPException(404, "Trade not found")
    t = trade.data

    assets = await db.table("trade_assets").select("player_id, from_team_id, to_team_id").eq("trade_id", trade_id).execute()
    league = await db.table("league").select("season_year").eq("id", league_id).single().execute()
    season_year = league.data["season_year"]

    impact = {}
    for asset in (assets.data or []):
        pid = asset["player_id"]
        # Sum season-to-date skater stats for this player
        stats = await (
            db.table("player_stats")
            .select("goals, assists, plus_minus, shots_on_goal, pp_points, sh_points")
            .eq("player_id", pid)
            .eq("season_year", season_year)
            .execute()
        )
        rows = stats.data or []
        totals = {
            "goals": sum(r["goals"] for r in rows),
            "assists": sum(r["assists"] for r in rows),
            "plus_minus": sum(r["plus_minus"] for r in rows),
            "shots_on_goal": sum(r["shots_on_goal"] for r in rows),
            "pp_points": sum(r["pp_points"] for r in rows),
            "sh_points": sum(r["sh_points"] for r in rows),
        }
        impact[pid] = {
            "from_team_id": asset["from_team_id"],
            "to_team_id": asset["to_team_id"],
            "season_totals": totals,
        }

    return {"trade_id": trade_id, "player_impact": impact}


@router.post("/", status_code=201)
async def create_trade(
    body: TradeProposal,
    team: dict = Depends(get_my_team),
    league_id: str = Depends(get_league_id),
    _: dict = Depends(get_current_user),
):
    try:
        trade_id = await propose_trade(
            proposing_team_id=team["id"],
            receiving_team_id=body.receiving_team_id,
            players_from_proposer=body.players_from_me,
            players_from_receiver=body.players_from_them,
            league_id=league_id,
        )
    except TradeError as exc:
        raise HTTPException(400, str(exc))
    return {"trade_id": trade_id}


@router.post("/{trade_id}/respond")
async def respond_trade(
    trade_id: str,
    body: TradeResponse,
    team: dict = Depends(get_my_team),
    _: dict = Depends(get_current_user),
):
    try:
        await respond_to_trade(trade_id, team["id"], body.accept)
    except TradeError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "accepted": body.accept}


@router.post("/{trade_id}/withdraw")
async def withdraw(
    trade_id: str,
    team: dict = Depends(get_my_team),
    _: dict = Depends(get_current_user),
):
    try:
        await withdraw_trade(trade_id, team["id"])
    except TradeError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}
