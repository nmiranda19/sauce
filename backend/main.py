import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db import init_db, get_db
from scheduler import build_scheduler
from nhl.sync_players import sync_all_players
from nhl.sync_games import sync_schedule

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("Initializing Supabase client")
    await init_db()

    log.info("Running initial data sync")
    await sync_schedule(days_ahead=14)
    await sync_all_players()

    # Fetch the active league_id so the scheduler can target it
    db = get_db()
    league_result = await db.table("league").select("id").limit(1).execute()
    league_id = league_result.data[0]["id"] if league_result.data else None

    log.info("Starting background scheduler (league_id=%s)", league_id)
    scheduler = build_scheduler(league_id=league_id)
    scheduler.start()

    yield

    # Shutdown
    log.info("Shutting down scheduler")
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Sauce Fantasy Hockey API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the React Native app (Expo dev server + production builds)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Ensure CORS headers are present even on unhandled 500 errors
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.error("Unhandled exception on %s %s: %r", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"},
    )

# ------------------------------------------------------------------ #
# Routers
# ------------------------------------------------------------------ #
from api.auth import router as auth_router
from api.routers.setup import router as setup_router
from api.routers.league import router as league_router
from api.routers.teams import router as teams_router
from api.routers.lineup import router as lineup_router
from api.routers.players import router as players_router
from api.routers.waiver import router as waiver_router
from api.routers.trades import router as trades_router
from api.routers.matchups import router as matchups_router
from api.routers.commissioner import router as commissioner_router

app.include_router(auth_router)
app.include_router(setup_router)
app.include_router(league_router)
app.include_router(teams_router)
app.include_router(lineup_router)
app.include_router(players_router)
app.include_router(waiver_router)
app.include_router(trades_router)
app.include_router(matchups_router)
app.include_router(commissioner_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"message": "Sauce Fantasy Hockey API — see /docs for endpoints"}
