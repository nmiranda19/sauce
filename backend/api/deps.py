"""FastAPI dependencies: current_user and commissioner guard."""
from __future__ import annotations
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from api.auth import decode_token, oauth2_scheme
from db import get_db

_401 = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
_403 = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Commissioner access required")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise _401
    db = get_db()
    result = await db.table("users").select("id, name, email, is_commissioner").eq("id", user_id).single().execute()
    if not result.data:
        raise _401
    return result.data


async def get_current_commissioner(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_commissioner"):
        raise _403
    return user


async def get_league_id() -> str:
    """Fetch the single active league ID."""
    db = get_db()
    result = await db.table("league").select("id").limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="No league configured yet")
    return result.data[0]["id"]


async def get_my_team(
    current_user: dict = Depends(get_current_user),
    league_id: str = Depends(get_league_id),
) -> dict:
    """Return the current user's team in the active league."""
    db = get_db()
    result = await (
        db.table("teams")
        .select("*")
        .eq("user_id", current_user["id"])
        .eq("league_id", league_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="You don't have a team in this league")
    return result.data
