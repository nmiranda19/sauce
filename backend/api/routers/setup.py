"""One-time league and team creation (commissioner-only after first user)."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_current_commissioner
from commissioner.settings import create_league, create_team, set_waiver_priority_order, schedule_matchups

router = APIRouter(prefix="/setup", tags=["setup"])


class LeagueCreate(BaseModel):
    name: str
    season_year: int
    total_weeks: int = 26


class TeamCreate(BaseModel):
    league_id: str
    user_id: str
    team_name: str
    waiver_priority: int


class WaiverPrioritySet(BaseModel):
    league_id: str
    priority_map: dict  # {team_id: priority_number}


class MatchupSchedule(BaseModel):
    league_id: str
    matchups: list[dict]


@router.post("/league", status_code=201)
async def create_league_endpoint(body: LeagueCreate, user: dict = Depends(get_current_commissioner)):
    league_id = await create_league(body.name, body.season_year, body.total_weeks)
    return {"league_id": league_id}


@router.post("/team", status_code=201)
async def create_team_endpoint(body: TeamCreate, user: dict = Depends(get_current_commissioner)):
    team_id = await create_team(body.league_id, body.user_id, body.team_name, body.waiver_priority)
    return {"team_id": team_id}


@router.post("/waiver-priority")
async def set_waiver_priority(body: WaiverPrioritySet, user: dict = Depends(get_current_commissioner)):
    await set_waiver_priority_order(user["id"], body.league_id, body.priority_map)
    return {"ok": True}


@router.post("/matchups", status_code=201)
async def create_matchup_schedule(body: MatchupSchedule, user: dict = Depends(get_current_commissioner)):
    count = await schedule_matchups(user["id"], body.league_id, body.matchups)
    return {"matchups_created": count}
