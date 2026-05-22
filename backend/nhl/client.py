from __future__ import annotations
import logging
import asyncio
import httpx
from config import NHL_API_BASE, NHL_STATS_BASE, SEASON_YEAR, NHL_REGULAR_SEASON

log = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(15.0)
_MAX_RETRIES = 3
_RETRY_DELAY = 2.0  # seconds


class NHLClient:
    """Async HTTP client for the unofficial NHL API."""

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "Sauce-Fantasy-Hockey/1.0"},
        )

    async def close(self):
        await self._client.aclose()

    async def _get(self, url: str) -> dict:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = await self._client.get(url)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                log.warning("NHL API %s returned %s (attempt %d/%d)", url, exc.response.status_code, attempt, _MAX_RETRIES)
            except httpx.RequestError as exc:
                log.warning("NHL API request error for %s: %s (attempt %d/%d)", url, exc, attempt, _MAX_RETRIES)
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_DELAY * attempt)
        raise RuntimeError(f"NHL API unreachable after {_MAX_RETRIES} attempts: {url}")

    # ------------------------------------------------------------------ #
    # Endpoints
    # ------------------------------------------------------------------ #

    async def get_standings(self) -> dict:
        return await self._get(f"{NHL_API_BASE}/v1/standings/now")

    async def get_team_roster(self, team_abbrev: str) -> dict:
        return await self._get(f"{NHL_API_BASE}/v1/roster/{team_abbrev}/current")

    async def get_player_landing(self, player_id: int) -> dict:
        return await self._get(f"{NHL_API_BASE}/v1/player/{player_id}/landing")

    async def get_schedule(self, date_str: str) -> dict:
        """date_str: YYYY-MM-DD"""
        return await self._get(f"{NHL_API_BASE}/v1/schedule/{date_str}")

    async def get_boxscore(self, game_id: int) -> dict:
        return await self._get(f"{NHL_API_BASE}/v1/gamecenter/{game_id}/boxscore")

    async def get_player_game_log(self, player_id: int) -> dict:
        return await self._get(
            f"{NHL_API_BASE}/v1/player/{player_id}/game-log/{SEASON_YEAR}/{NHL_REGULAR_SEASON}"
        )


# Singleton used across sync jobs
_nhl: "NHLClient | None" = None


def get_nhl() -> NHLClient:
    global _nhl
    if _nhl is None:
        _nhl = NHLClient()
    return _nhl
