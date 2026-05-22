"""
Orchestrates weekly matchup scoring.

score_matchup(matchup_id)  — score one matchup, write category results + W-L-T records
score_week(league_id, week_number) — score all matchups for a week
finalize_season_records(league_id)  — rebuild team.wins/losses/ties from all matchup records
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from db import get_db
from scoring.weekly_totals import get_team_week_totals
from scoring.category_engine import score_categories, tally_record

log = logging.getLogger(__name__)


async def score_matchup(matchup_id: str) -> None:
    db = get_db()

    # Load matchup
    m_result = await (
        db.table("weekly_matchups")
        .select("id, home_team_id, away_team_id, week_number, league_id, status")
        .eq("id", matchup_id)
        .single()
        .execute()
    )
    if not m_result.data:
        log.error("Matchup %s not found", matchup_id)
        return
    m = m_result.data

    # Get season_year from league
    league = await db.table("league").select("season_year").eq("id", m["league_id"]).single().execute()
    season_year = league.data["season_year"]

    week = m["week_number"]
    home_id = m["home_team_id"]
    away_id = m["away_team_id"]

    log.info("Scoring matchup %s  week=%d  home=%s  away=%s", matchup_id, week, home_id, away_id)

    # Compute totals for both teams concurrently
    import asyncio
    home_totals, away_totals = await asyncio.gather(
        get_team_week_totals(home_id, week, season_year),
        get_team_week_totals(away_id, week, season_year),
    )

    # Compare all 10 categories
    cat_results = score_categories(home_totals, away_totals)
    home_record, away_record = tally_record(cat_results)

    now = datetime.now(timezone.utc).isoformat()

    # Upsert category results
    cat_rows = [
        {
            "matchup_id": matchup_id,
            "category": r["category"],
            "home_value": r["home_value"],
            "away_value": r["away_value"],
            "winner": r["winner"],
        }
        for r in cat_results
    ]
    await db.table("weekly_category_results").upsert(
        cat_rows, on_conflict="matchup_id,category"
    ).execute()

    # Upsert matchup records for home and away
    record_rows = [
        {
            "matchup_id": matchup_id,
            "team_id": home_id,
            "week_number": week,
            "wins": home_record["wins"],
            "losses": home_record["losses"],
            "ties": home_record["ties"],
        },
        {
            "matchup_id": matchup_id,
            "team_id": away_id,
            "week_number": week,
            "wins": away_record["wins"],
            "losses": away_record["losses"],
            "ties": away_record["ties"],
        },
    ]
    await db.table("weekly_matchup_record").upsert(
        record_rows, on_conflict="matchup_id,team_id"
    ).execute()

    # Mark matchup complete
    await (
        db.table("weekly_matchups")
        .update({"status": "complete"})
        .eq("id", matchup_id)
        .execute()
    )

    log.info(
        "Matchup %s complete — home %d-%d-%d  away %d-%d-%d",
        matchup_id,
        home_record["wins"], home_record["losses"], home_record["ties"],
        away_record["wins"], away_record["losses"], away_record["ties"],
    )


async def score_week(league_id: str, week_number: int) -> None:
    """Score all scheduled/in-progress matchups for the given week."""
    db = get_db()
    result = await (
        db.table("weekly_matchups")
        .select("id")
        .eq("league_id", league_id)
        .eq("week_number", week_number)
        .in_("status", ["scheduled", "in_progress"])
        .execute()
    )
    matchup_ids = [r["id"] for r in (result.data or [])]
    if not matchup_ids:
        log.info("No matchups to score for league=%s week=%d", league_id, week_number)
        return

    log.info("Scoring %d matchups for week %d", len(matchup_ids), week_number)
    for mid in matchup_ids:
        await score_matchup(mid)

    # Rebuild season records after all matchups are scored
    await finalize_season_records(league_id)


async def finalize_season_records(league_id: str) -> None:
    """
    Recompute each team's season wins/losses/ties by summing all weekly_matchup_record rows.
    More reliable than maintaining running counters.
    """
    db = get_db()

    # Get all teams in the league
    teams_result = await db.table("teams").select("id").eq("league_id", league_id).execute()
    team_ids = [t["id"] for t in (teams_result.data or [])]

    for team_id in team_ids:
        records = await (
            db.table("weekly_matchup_record")
            .select("wins, losses, ties")
            .eq("team_id", team_id)
            .execute()
        )
        rows = records.data or []
        totals = {
            "wins":   sum(r["wins"]   for r in rows),
            "losses": sum(r["losses"] for r in rows),
            "ties":   sum(r["ties"]   for r in rows),
        }
        await db.table("teams").update(totals).eq("id", team_id).execute()

    log.info("Season records updated for %d teams", len(team_ids))
