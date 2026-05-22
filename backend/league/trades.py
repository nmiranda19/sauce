"""
Trade system.

Flow:
  1. proposing_team proposes trade (players to send/receive)
  2. receiving_team accepts or rejects
  3. Commissioner approves or vetoes within 48 hours
  4. If commissioner takes no action by the deadline → auto-approved
  5. Trade execution swaps players between rosters

Commissioner can also veto at any point before execution.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta

from db import get_db
from league.moves_log import log_move

log = logging.getLogger(__name__)

_COMMISSIONER_WINDOW_HOURS = 48


class TradeError(Exception):
    pass


# ------------------------------------------------------------------ #
# Proposal
# ------------------------------------------------------------------ #

async def propose_trade(
    proposing_team_id: str,
    receiving_team_id: str,
    players_from_proposer: list[str],   # player UUIDs moving TO receiving team
    players_from_receiver: list[str],   # player UUIDs moving TO proposing team
    league_id: str,
) -> str:
    """Create a trade proposal. Returns the trade ID."""
    if not players_from_proposer and not players_from_receiver:
        raise TradeError("A trade must include at least one player from each side")
    if proposing_team_id == receiving_team_id:
        raise TradeError("Cannot trade with yourself")

    db = get_db()

    # Verify all players are actually on the expected teams
    await _verify_players_on_team(proposing_team_id, players_from_proposer)
    await _verify_players_on_team(receiving_team_id, players_from_receiver)

    now = datetime.now(timezone.utc)
    trade = await db.table("trade_proposals").insert({
        "proposing_team_id": proposing_team_id,
        "receiving_team_id": receiving_team_id,
        "status": "pending",
        "proposed_at": now.isoformat(),
    }).execute()
    trade_id = trade.data[0]["id"]

    # Insert trade assets
    asset_rows = []
    for pid in players_from_proposer:
        asset_rows.append({
            "trade_id": trade_id,
            "player_id": pid,
            "from_team_id": proposing_team_id,
            "to_team_id": receiving_team_id,
        })
    for pid in players_from_receiver:
        asset_rows.append({
            "trade_id": trade_id,
            "player_id": pid,
            "from_team_id": receiving_team_id,
            "to_team_id": proposing_team_id,
        })
    await db.table("trade_assets").insert(asset_rows).execute()

    log.info("Trade proposed: %s  proposer=%s  receiver=%s", trade_id, proposing_team_id, receiving_team_id)
    return trade_id


# ------------------------------------------------------------------ #
# Response
# ------------------------------------------------------------------ #

async def respond_to_trade(trade_id: str, accepting_team_id: str, accept: bool) -> None:
    """Receiving team accepts or rejects the trade."""
    db = get_db()
    trade = await _get_trade(trade_id)

    if trade["receiving_team_id"] != accepting_team_id:
        raise TradeError("Only the receiving team can respond to this trade")
    if trade["status"] != "pending":
        raise TradeError(f"Trade is already {trade['status']}")

    if not accept:
        await db.table("trade_proposals").update({
            "status": "rejected",
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", trade_id).execute()
        log.info("Trade %s rejected by receiving team", trade_id)
        return

    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=_COMMISSIONER_WINDOW_HOURS)
    await db.table("trade_proposals").update({
        "status": "accepted",
        "accepted_at": now.isoformat(),
        "commissioner_deadline": deadline.isoformat(),
    }).eq("id", trade_id).execute()
    log.info("Trade %s accepted — commissioner deadline %s", trade_id, deadline.isoformat())


async def withdraw_trade(trade_id: str, proposing_team_id: str) -> None:
    """Proposing team withdraws a pending trade."""
    db = get_db()
    trade = await _get_trade(trade_id)
    if trade["proposing_team_id"] != proposing_team_id:
        raise TradeError("Only the proposing team can withdraw this trade")
    if trade["status"] not in ("pending",):
        raise TradeError(f"Cannot withdraw a trade with status '{trade['status']}'")
    await db.table("trade_proposals").update({
        "status": "withdrawn",
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", trade_id).execute()


# ------------------------------------------------------------------ #
# Commissioner actions
# ------------------------------------------------------------------ #

async def commissioner_approve(trade_id: str, commissioner_id: str, notes: str | None = None) -> None:
    trade = await _get_trade(trade_id)
    if trade["status"] != "accepted":
        raise TradeError(f"Can only approve an accepted trade (current status: {trade['status']})")
    await _execute_trade(trade_id, status="approved", notes=notes)


async def commissioner_veto(trade_id: str, commissioner_id: str, notes: str | None = None) -> None:
    db = get_db()
    trade = await _get_trade(trade_id)
    if trade["status"] not in ("pending", "accepted"):
        raise TradeError(f"Cannot veto a trade with status '{trade['status']}'")
    await db.table("trade_proposals").update({
        "status": "vetoed",
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "commissioner_notes": notes,
    }).eq("id", trade_id).execute()
    log.info("Trade %s vetoed by commissioner", trade_id)


# ------------------------------------------------------------------ #
# Auto-approval job (scheduled)
# ------------------------------------------------------------------ #

async def process_auto_approvals(league_id: str) -> None:
    """
    Auto-approve any accepted trades where the commissioner_deadline has passed.
    Run every 15–30 minutes.
    """
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    overdue = await (
        db.table("trade_proposals")
        .select("id")
        .eq("status", "accepted")
        .lte("commissioner_deadline", now)
        .execute()
    )
    for row in (overdue.data or []):
        log.info("Auto-approving trade %s (commissioner window expired)", row["id"])
        await _execute_trade(row["id"], status="auto_approved", notes="Auto-approved: 48-hour commissioner window expired")


# ------------------------------------------------------------------ #
# Trade execution
# ------------------------------------------------------------------ #

async def _execute_trade(trade_id: str, status: str, notes: str | None) -> None:
    db = get_db()
    assets = await db.table("trade_assets").select("player_id, from_team_id, to_team_id").eq("trade_id", trade_id).execute()

    for asset in (assets.data or []):
        # Move player: update roster row's team_id
        await (
            db.table("rosters")
            .update({"team_id": asset["to_team_id"]})
            .eq("team_id", asset["from_team_id"])
            .eq("player_id", asset["player_id"])
            .execute()
        )

    # Get league_id for move logging
    trade = await _get_trade(trade_id)
    proposing_league = await db.table("teams").select("league_id").eq("id", trade["proposing_team_id"]).single().execute()
    league_id = proposing_league.data["league_id"]

    for asset in (assets.data or []):
        await log_move(
            league_id,
            asset["to_team_id"],
            "trade",
            asset["player_id"],
            related_trade_id=trade_id,
        )

    await db.table("trade_proposals").update({
        "status": status,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "commissioner_notes": notes,
    }).eq("id", trade_id).execute()

    log.info("Trade %s executed (status=%s) — %d assets moved", trade_id, status, len(assets.data or []))


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

async def _get_trade(trade_id: str) -> dict:
    db = get_db()
    result = await db.table("trade_proposals").select("*").eq("id", trade_id).single().execute()
    if not result.data:
        raise TradeError("Trade not found")
    return result.data


async def _verify_players_on_team(team_id: str, player_ids: list[str]) -> None:
    if not player_ids:
        return
    db = get_db()
    rostered = await (
        db.table("rosters")
        .select("player_id")
        .eq("team_id", team_id)
        .in_("player_id", player_ids)
        .execute()
    )
    found = {r["player_id"] for r in (rostered.data or [])}
    missing = set(player_ids) - found
    if missing:
        raise TradeError(f"Player(s) not on the expected team roster: {missing}")
