"""
Polls live and recently-completed NHL games and stores per-game player stats.
Called every 30 seconds during active game windows.
"""
from __future__ import annotations
import logging
from datetime import date, datetime, timezone

from db import get_db
from nhl.client import get_nhl
from nhl.sync_games import get_todays_game_ids, has_live_games

log = logging.getLogger(__name__)

_STATE_MAP = {
    "FUT": "scheduled",
    "PRE": "scheduled",
    "LIVE": "live",
    "CRIT": "live",
    "FINAL": "final",
    "OFF": "final",
    "OVER": "final",
    "PPRD": "postponed",
}


def _toi_to_seconds(toi_str: str | None) -> int:
    """Convert 'MM:SS' → total seconds. Returns 0 on bad input."""
    if not toi_str:
        return 0
    try:
        parts = toi_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return 0


async def _load_player_uuid_map(nhl_ids: list[int]) -> dict[int, str]:
    """Bulk-fetch nhl_player_id → internal UUID from DB."""
    if not nhl_ids:
        return {}
    db = get_db()
    result = await (
        db.table("nhl_players")
        .select("id, nhl_player_id")
        .in_("nhl_player_id", nhl_ids)
        .execute()
    )
    return {r["nhl_player_id"]: r["id"] for r in (result.data or [])}


async def _load_game_uuid(nhl_game_id: int) -> str | None:
    """Fetch internal UUID for a game by nhl_game_id."""
    db = get_db()
    result = await (
        db.table("games")
        .select("id")
        .eq("nhl_game_id", nhl_game_id)
        .single()
        .execute()
    )
    return result.data["id"] if result.data else None


async def _update_game_status(nhl_game_id: int, state: str) -> None:
    db = get_db()
    status = _STATE_MAP.get(state, "scheduled")
    await (
        db.table("games")
        .update({"status": status, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("nhl_game_id", nhl_game_id)
        .execute()
    )


async def sync_game_stats(nhl_game_id: int) -> None:
    """Fetch boxscore for one game and upsert all player stats."""
    nhl = get_nhl()
    try:
        boxscore = await nhl.get_boxscore(nhl_game_id)
    except RuntimeError as exc:
        log.warning("Boxscore fetch failed for game %d: %s", nhl_game_id, exc)
        return

    state = boxscore.get("gameState", "FUT")
    await _update_game_status(nhl_game_id, state)

    # Don't parse stats for games that haven't started
    if state in ("FUT", "PRE"):
        return

    game_date_str = boxscore.get("gameDate", date.today().isoformat())
    try:
        game_date = date.fromisoformat(game_date_str)
    except ValueError:
        game_date = date.today()

    game_uuid = await _load_game_uuid(nhl_game_id)
    if not game_uuid:
        log.warning("Game %d not in DB — run schedule sync first", nhl_game_id)
        return

    # Determine week_number from games table
    db = get_db()
    g_row = await db.table("games").select("week_number, season_year").eq("nhl_game_id", nhl_game_id).single().execute()
    week_number = g_row.data["week_number"] if g_row.data else None
    season_year = g_row.data["season_year"] if g_row.data else None

    by_game_stats = boxscore.get("playerByGameStats", {})
    skater_rows: list[dict] = []
    goalie_rows: list[dict] = []

    # Collect all NHL player IDs first so we can bulk-resolve UUIDs
    all_nhl_ids: list[int] = []
    for side in ("homeTeam", "awayTeam"):
        side_stats = by_game_stats.get(side, {})
        for group in ("forwards", "defense", "goalies"):
            for p in side_stats.get(group, []):
                pid = p.get("playerId")
                if pid:
                    all_nhl_ids.append(pid)

    uuid_map = await _load_player_uuid_map(all_nhl_ids)

    for side in ("homeTeam", "awayTeam"):
        side_stats = by_game_stats.get(side, {})

        # Skaters
        for group, is_d in (("forwards", False), ("defense", True)):
            for p in side_stats.get(group, []):
                pid = p.get("playerId")
                player_uuid = uuid_map.get(pid)
                if not player_uuid:
                    continue

                goals = p.get("goals", 0) or 0
                assists = p.get("assists", 0) or 0
                pp_pts = p.get("powerPlayPoints", 0) or 0
                sh_pts = p.get("shorthandedPoints", 0) or 0

                skater_rows.append({
                    "player_id": player_uuid,
                    "game_id": game_uuid,
                    "game_date": game_date_str,
                    "week_number": week_number,
                    "season_year": season_year,
                    "goals": goals,
                    "assists": assists,
                    "plus_minus": p.get("plusMinus", 0) or 0,
                    "shots_on_goal": p.get("shots", 0) or 0,
                    "toi_seconds": _toi_to_seconds(p.get("toi")),
                    "pp_points": pp_pts,
                    "sh_points": sh_pts,
                    "is_defenseman_point": is_d and (goals + assists) > 0,
                })

        # Goalies
        for p in side_stats.get("goalies", []):
            pid = p.get("playerId")
            player_uuid = uuid_map.get(pid)
            if not player_uuid:
                continue

            decision = (p.get("decision") or "").upper()
            shots = p.get("shotsAgainst", 0) or 0
            saves = p.get("saves", 0) or 0

            goalie_rows.append({
                "player_id": player_uuid,
                "game_id": game_uuid,
                "game_date": game_date_str,
                "week_number": week_number,
                "season_year": season_year,
                "won": decision == "W",
                "goals_against": shots - saves,
                "shots_against": shots,
                "saves": saves,
                "toi_seconds": _toi_to_seconds(p.get("toi")),
            })

    if skater_rows:
        await db.table("player_stats").upsert(skater_rows, on_conflict="player_id,game_id").execute()
    if goalie_rows:
        await db.table("goalie_stats").upsert(goalie_rows, on_conflict="player_id,game_id").execute()

    log.debug(
        "Game %d: %d skater rows, %d goalie rows (state=%s)",
        nhl_game_id, len(skater_rows), len(goalie_rows), state,
    )


async def poll_active_games() -> None:
    """
    Main polling job. Checks whether games are live and fetches stats accordingly.
    If no games are active today, exits quickly (cheap check).
    """
    today_ids = await get_todays_game_ids()
    if not today_ids:
        return  # No games today — nothing to poll

    log.debug("Polling stats for %d games scheduled today", len(today_ids))

    for nhl_game_id in today_ids:
        await sync_game_stats(nhl_game_id)
