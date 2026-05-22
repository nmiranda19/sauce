"""Write entries to league_moves (the Recent Moves feed)."""
from __future__ import annotations
from datetime import datetime, timezone
from db import get_db


async def log_move(
    league_id: str,
    team_id: str,
    move_type: str,
    player_id: str,
    related_trade_id: str | None = None,
    notes: str | None = None,
) -> None:
    db = get_db()
    await db.table("league_moves").insert({
        "league_id": league_id,
        "team_id": team_id,
        "move_type": move_type,
        "player_id": player_id,
        "related_trade_id": related_trade_id,
        "notes": notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
