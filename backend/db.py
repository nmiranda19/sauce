from __future__ import annotations
from typing import Optional
from supabase import AsyncClient, acreate_client
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

_db: Optional[AsyncClient] = None


async def init_db() -> None:
    global _db
    _db = await acreate_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_db() -> AsyncClient:
    if _db is None:
        raise RuntimeError("Database client not initialized — call init_db() first")
    return _db
