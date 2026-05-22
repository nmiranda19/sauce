"""
RSS news feed fetcher.
Pulls from TSN, Sportsnet, and NHL.com and upserts into news_feed table.
X (Twitter) support is best-effort via a third-party aggregator.
"""
from __future__ import annotations
import logging
import asyncio
from datetime import datetime, timezone

import feedparser
import httpx

from db import get_db

log = logging.getLogger(__name__)

RSS_SOURCES = [
    {"name": "TSN",       "url": "https://www.tsn.ca/rss/news.xml"},
    {"name": "Sportsnet", "url": "https://www.sportsnet.ca/feed/"},
    {"name": "NHL.com",   "url": "https://www.nhl.com/rss/news.xml"},
]

# X (Twitter) accounts to monitor via RapidAPI or Nitter aggregator.
# Set TWITTER_AGGREGATOR_URL in env to enable; falls back gracefully if unset or unavailable.
X_ACCOUNTS = [
    "@DFOFantasy", "@FriedgeHNIC", "@reporterchris",
    "@frank_seravalli", "@PierreVLeBrun", "@emilymkaplan", "@NHLPR",
]


async def fetch_rss_feed(name: str, url: str) -> list[dict]:
    """Fetch and parse one RSS feed. Returns normalized rows for news_feed table."""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Sauce-Fantasy/1.0"})
            resp.raise_for_status()
            raw = resp.text
    except Exception as exc:
        log.warning("RSS fetch failed for %s (%s): %s", name, url, exc)
        return []

    feed = feedparser.parse(raw)
    rows = []
    for entry in feed.entries[:20]:  # cap at 20 per source
        link = entry.get("link", "")
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if published:
            pub_dt = datetime(*published[:6], tzinfo=timezone.utc).isoformat()
        else:
            pub_dt = datetime.now(timezone.utc).isoformat()

        rows.append({
            "source_type": "rss",
            "source_name": name,
            "headline": entry.get("title", "")[:500],
            "body": entry.get("summary", "")[:2000],
            "url": link,
            "published_at": pub_dt,
            "external_id": link or entry.get("id", ""),
        })
    return rows


async def refresh_rss() -> None:
    """Fetch all RSS sources and upsert into news_feed."""
    db = get_db()
    tasks = [fetch_rss_feed(s["name"], s["url"]) for s in RSS_SOURCES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    rows = []
    for result in results:
        if isinstance(result, list):
            rows.extend(result)

    if rows:
        # Upsert; (source_type, external_id) is the unique key
        await db.table("news_feed").upsert(rows, on_conflict="source_type,external_id").execute()
        log.info("RSS refresh: %d items upserted", len(rows))

    # Prune old items (keep latest 500)
    await _prune_old_news()


async def _prune_old_news() -> None:
    """Keep only the 500 most recent news items to prevent unbounded table growth."""
    db = get_db()
    result = await (
        db.table("news_feed")
        .select("id")
        .order("published_at", desc=True)
        .limit(501)
        .execute()
    )
    rows = result.data or []
    if len(rows) <= 500:
        return
    keep_ids = [r["id"] for r in rows[:500]]
    oldest_kept = rows[499]["id"]
    # Delete everything older than the 500th item
    await (
        db.table("news_feed")
        .delete()
        .not_.in_("id", keep_ids)
        .execute()
    )
