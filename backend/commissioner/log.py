"""Write entries to the commissioner_log audit table."""
from __future__ import annotations
from datetime import datetime, timezone
from db import get_db

_VALID_ACTIONS = {
    "trade_approved", "trade_vetoed", "waiver_override",
    "roster_edit", "settings_change", "player_assign", "ir_override",
}


async def log_action(
    commissioner_id: str,
    action_type: str,
    target_team_id: str | None = None,
    target_player_id: str | None = None,
    target_trade_id: str | None = None,
    notes: str | None = None,
) -> None:
    db = get_db()
    await db.table("commissioner_log").insert({
        "commissioner_id": commissioner_id,
        "action_type": action_type,
        "target_team_id": target_team_id,
        "target_player_id": target_player_id,
        "target_trade_id": target_trade_id,
        "notes": notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
