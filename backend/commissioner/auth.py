"""Commissioner authorization check."""
from __future__ import annotations
from db import get_db


class NotCommissionerError(Exception):
    pass


async def require_commissioner(user_id: str) -> dict:
    """
    Verify user is a commissioner. Returns the user record.
    Raises NotCommissionerError if not authorized.
    """
    db = get_db()
    result = await db.table("users").select("id, name, is_commissioner").eq("id", user_id).single().execute()
    if not result.data:
        raise NotCommissionerError("User not found")
    if not result.data["is_commissioner"]:
        raise NotCommissionerError("Commissioner access required")
    return result.data
