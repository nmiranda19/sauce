# Sauce

## Overview
Sauce is a personal fantasy hockey platform blending features from ESPN, Yahoo Fantasy, and Sleeper. Head-to-head category scoring league using NHL regular season data. Commissioner-controlled with full waiver wire, trade, and roster management systems.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python |
| Database | PostgreSQL (via Supabase) |
| API Layer | FastAPI |
| Mobile Frontend | React Native (Expo) |
| Data Source | NHL API (api-web.nhle.com + api.nhle.com/stats/rest) |
| Hosting | Railway (always-on Python backend, free tier) |
| Code Repository | GitHub (source control + Railway auto-deploy trigger) |

---

## Hosting & Deployment

- All Python backend code lives in a **GitHub repository**
- **Railway** connects directly to the GitHub repo and runs the backend 24/7
- Any code update pushed to GitHub automatically triggers a redeploy on Railway
- This ensures all automated jobs (stat polling, lineup locks, waiver processing, etc.) run continuously without manual intervention
- Railway free tier ($5 credit/month) is sufficient for Sauce's scale of 10 users

### What runs automatically on Railway (no manual action required):
- NHL API polling every 30 seconds during active game windows
- Lineup locks at first puck drop each day
- Waiver wire processing (24-hour claim window)
- Trade auto-approval at 48-hour mark
- Midnight stat calculations for hot/cold streaks
- RSS and X feed refreshes every 15-30 minutes
- Weekly matchup scoring and record updates

---

## League Structure

- 10 teams total
- Head-to-head category scoring (not points-based)
- Weekly matchups — each week produces a Wins-Losses-Ties record per team
- Season follows the NHL regular season schedule
- Standings determined by wins first, ties as tiebreaker

---

## Roster Structure

| Slot | Quantity | Eligible Positions |
|---|---|---|
| Forward (C/LW/RW) | 9 | C, LW, RW |
| Defenseman | 5 | D |
| Goalie | 2 | G |
| Utility | 1 | Forward or Defenseman |
| Bench | 5 | Forward, Defenseman, or Goalie |
| Injury Reserve (IR) | 3 | Any position (see IR rules) |
| **Total** | **25** | |

### Goalie Limits
- Maximum **4 goalies** on active roster (including bench) at any time
- IR slots are **separate** and do **not** count toward the 4 goalie limit
- A team could theoretically hold 4 active goalies + up to 3 goalies on IR

---

## Lineup Rules

- Managers can change their lineup **daily**
- Lineups **lock at the start of the first NHL game of each day**
- Must start a minimum of **3 goalies in a week** for GAA and Save % categories to count
- If fewer than 3 goalies started: both GAA and Save % are recorded as **losses** for that manager regardless of opponent's numbers

---

## Scoring Categories

### Skaters (counting stats — higher total wins the category)

| Category | How It's Counted |
|---|---|
| Goals | 1 per goal scored |
| Assists | 1 per assist |
| Plus/Minus | +1 per positive, -1 per negative |
| Shots on Goal | 1 per shot on goal |
| Defenseman Points | 1 per goal or assist scored by a player with position = D (stacks with Goals/Assists) |
| Special Teams Points | 1 per power play or shorthanded point (stacks with Goals/Assists) |
| Average TOI | Average minutes per game across the week — higher average wins category |

### Goalies (rate stats — best value wins the category)

| Category | How It's Counted |
|---|---|
| Wins | 1 per goalie win |
| GAA | Weekly average — **lower** value wins category |
| Save % | Weekly average — **higher** value wins category |

### Derived Stats (calculated server-side, not fetched directly)
- **Defenseman Points** — flagged when a player with position = D records a goal or assist
- **Special Teams Points** — pulled from NHL API power play / shorthanded flags per game
- **TOI** — converted from MM:SS to decimal minutes, averaged across all games in the week
- **GAA** — calculated from raw goals against and minutes played for the week only (not season cumulative)
- **Save %** — calculated from weekly saves and shots against only (not season cumulative)

---

## Weekly Matchup Scoring

- 10 categories per matchup
- Each category produces one of: Win / Loss / Tie
- Weekly record format: **W-L-T** (e.g. 5-4-1 or 4-4-2)
- Season standings accumulate weekly records across all matchups

---

## Playoff Structure

- **Top 4 teams** make the playoffs based on regular season record
- Playoffs use the **last 4 weeks of the NHL regular season, excluding the final week**
  - Example: if regular season is 26 weeks, playoffs use weeks 22–25
- Playoff matchups are **2 weeks long**
- **Two rounds:**
  - Semifinals: Seed 1 vs Seed 4, Seed 2 vs Seed 3
  - Finals: Winners of each semifinal
- Same category scoring system applies during playoffs

---

## League Homepage

A league-wide dashboard visible to all managers when they open the app. This is the first screen users see — it should surface the most relevant live and recent information across the whole league at a glance.

### News Feed
A unified feed combining two sources, sorted by timestamp (newest first):

**RSS Feed (official media — reliable, always on)**
- Pulls from TSN, Sportsnet, and NHL.com news endpoints
- Fetched and parsed every 15-30 minutes on a background schedule
- Provides headlines, source, and timestamp

**X (Twitter) Aggregator (insider breaking news)**
- Pulls recent posts from the following curated accounts via a third-party aggregator (e.g. Nitter or RapidAPI scraper):
  - @DFOFantasy
  - @FriedgeHNIC
  - @reporterchris
  - @frank_seravalli
  - @PierreVLeBrun
  - @emilymkaplan
  - @NHLPR
- Fetched every 15-30 minutes
- If the X aggregator goes down, the RSS feed keeps the section live
- Displays account handle, post text, and timestamp

> ⚠️ X's official API requires a paid subscription ($100+/month). This feed relies on a third-party aggregator which may occasionally be disrupted by X platform changes. Build with a fallback so the news section degrades gracefully to RSS-only if the aggregator fails.

### Hot & Cold Streaks
Calculated from league scoring categories over the **last 7 days** across all rostered players.

- **🔥 Hot Streak — Top 5**: the 5 highest-scoring rostered players in the league by combined fantasy category output over the last 7 days; includes all rostered players regardless of slot (active, bench, or IR)
- **🥶 Cold Streak — Bottom 5**: the 5 lowest-scoring rostered players in the league by combined fantasy category output over the last 7 days; **excludes players currently in an IR slot** since they are not actionable
- Refreshes daily via a **background job that runs after midnight once all games are final**, calculating 7-day rolling totals for every rostered player

### Recent Moves
A chronological feed of all roster activity across all 10 teams, showing:
- Player adds and drops (with waiver or free agent label)
- Trades (once approved)
- IR placements and activations
- Displays team name, move type, player name, and timestamp

---

## Waiver Wire System

- When a player is dropped, they hit waivers **immediately**
- Player becomes **claimable after 24 hours**
- Waiver priority is **rolling** — a successful claim sends that team to **last priority**
- Teams are limited to **2 player adds per week** (drops do not count against this limit)
- Claims are processed in waiver priority order

---

## Trade System

- Any manager can propose a trade to another manager
- Both teams must **accept** the trade before it goes to commissioner review
- Commissioner (admin user) **approves or rejects** all accepted trades
- If commissioner takes no action within **48 hours**, trade **auto-approves**
- Trades can involve any number of players between two teams

---

## Injury Reserve (IR) Rules

- Each team has **3 IR slots** in addition to the standard 25-man roster
- IR eligibility is determined by the player's **current NHL designation**
- Eligible designations: **IR, IR-LT, OUT**
- **Not eligible:** Day-to-Day
- Eligibility is checked in real time — if a player's designation changes, their IR eligibility changes accordingly
- Managers can keep a recovered player in an IR slot until they choose to move them
- If a player gets re-injured and re-designated as IR/OUT, they can be placed back on IR

---

## Draft System

- Draft is conducted **offline** (in person or via separate tool)
- Commissioner manually assigns players to teams via an **admin roster population tool**
- No live in-app draft functionality required

---

## Commissioner Powers

- Manually assign players to teams after offline draft
- Approve or reject accepted trades
- Override waiver wire decisions
- Edit league settings
- All commissioner actions are logged with timestamp and notes

---

## Database Tables

| Table | Purpose |
|---|---|
| users | Manager accounts (name, email, hashed password, is_commissioner flag) |
| league | League settings (season year, current week, status) |
| teams | Team records (wins, losses, ties, linked to user and league) |
| nhl_players | NHL player data synced from API (name, position, NHL team, active/injury status) |
| rosters | Active roster assignments (team, player, slot, date) |
| games | NHL game schedule and results (home/away team, date, status) |
| player_stats | Per-game skater stats (goals, assists, plus_minus, toi, shots, pp_point, sh_point, position) |
| goalie_stats | Per-game goalie stats (win, goals_against, shots_against, saves, calculated GAA/SV%) |
| weekly_matchups | Scheduled head-to-head matchups (teams, week, playoff flag, status) |
| weekly_category_results | Per-category result for each matchup (home value, away value, winner) |
| weekly_matchup_record | Final W-L-T record per matchup per team |
| weekly_team_settings | Per-team weekly counters (adds used, goalies started) |
| waiver_wire | Player availability and waiver status |
| waiver_claims | Individual claim requests (player to add, player to drop, priority, status) |
| trade_proposals | Trade records (proposing team, receiving team, status, timestamps) |
| trade_assets | Individual players in each trade (direction, player ID) |
| commissioner_log | Audit trail of all commissioner actions |
| news_feed | Cached news items from RSS and X aggregator (source, handle, headline/text, url, timestamp) |
| league_moves | Log of all roster moves across all teams (add, drop, trade, IR — used for Recent Moves feed) |
| player_streaks | Daily snapshot of 7-day fantasy scoring totals per rostered player (used for hot/cold streak calculations) |

---

## Build Order

1. **Database schema** — define and create all tables in PostgreSQL via Supabase
2. **NHL API data pipeline** — fetch and store players, games, and per-game stats on a schedule
3. **Scoring engine** — calculate weekly category totals, derived stats, and matchup W-L-T results
4. **League logic** — roster management, waiver wire, trades, IR rules, lineup locks
5. **Commissioner tools** — manual draft population, trade approval, waiver overrides
6. **FastAPI layer** — REST endpoints the mobile frontend will consume
7. **React Native frontend (Expo)** — mobile app for iOS and Android
8. **Railway deployment** — connect GitHub repo to Railway, configure environment variables, verify all background jobs run in production

---

## UX Improvements Over ESPN & Yahoo

These are intentional design decisions based on known pain points with existing fantasy hockey platforms. Each should be treated as a required feature, not a nice-to-have.

### Data & Scoring
- **Aggressive stat polling** — poll NHL API every **30 seconds during active game windows**; drop to every **10-15 minutes outside game windows** for roster and injury status updates (conditional polling — no need to hammer the API when no games are live); display a visible "last updated" timestamp on all live scoring screens so managers always know how fresh the data is
- **Weekly schedule context on every player** — show games remaining this week next to every player name in the lineup view (e.g. "3 GP left"); this is the single most useful piece of information for daily lineup decisions and ESPN/Yahoo bury it

### Lineup Management
- **Mobile-first lineup screen** — large tap targets, clear position slot labels, swipe-to-swap players; designed for phone use first, not a desktop UI compressed to mobile
- **Goalie start counter visible in lineup** — always show how many goalies have been started this week vs the 3-goalie minimum, directly on the lineup screen

### Waiver Wire
- **Waiver priority always visible** — every manager can see their current waiver priority rank and full claim history log at all times; no guessing why a claim failed
- **Injury context on player add screen** — when adding a player from waivers or free agency, show their current NHL injury designation and estimated return timeline directly on that screen

### Trades
- **Category impact preview before submitting** — when a manager builds a trade offer, show a side-by-side breakdown of how the trade affects each team's weekly category totals based on the current season's stats; answers "does this trade actually help me?" before it's sent
- **Trade history log** — full visible history of all proposed, accepted, rejected, and auto-approved trades for the entire season

### Commissioner
- **All commissioner tools fully functional on mobile** — trade approvals, waiver overrides, roster edits, and settings changes must all work in the mobile app; nothing commissioner-only on desktop

---

## NHL API Endpoints (Key References)

- Base URL 1: `https://api-web.nhle.com/v1/`
- Base URL 2: `https://api.nhle.com/stats/rest/`
- No API key required (unofficial public API)
- Key endpoints:
  - Player game log: `/v1/player/{playerId}/game-log/{season}/{gameType}`
  - Schedule: `/v1/schedule/{date}`
  - Team roster: `/v1/roster/{teamAbbrev}/current`
  - Player info: `/v1/player/{playerId}/landing`
  - Standings: `/v1/standings/{date}`

> ⚠️ The NHL API is unofficial and undocumented. Endpoints can change without notice. Build with error handling and monitoring for broken endpoints.

---

## Key Business Rules Summary

- Max 4 goalies on active roster at any time (IR separate)
- Must start 3+ goalies in a week for GAA and Save % to count
- 2 player adds per week maximum (drops free)
- IR eligible: OUT, IR, IR-LT (not Day-to-Day)
- Lineup locks at first puck drop of the day
- Trade auto-approves after 48 hours of commissioner inaction
- Waiver priority rolls after each successful claim
- Dropped players claimable after 24 hours on waivers
- Playoffs = last 4 weeks of regular season excluding final week
- Playoff rounds are 2 weeks each

---

## Pre-Build Checklist

### Accounts to create before starting Claude Code:
- [ ] Supabase — free account at supabase.com, create a new project, save Project URL, Anon key, Service Role key, and database password
- [ ] GitHub — free account at github.com, create a new empty repository named `sauce`
- [ ] Railway — free account at railway.app, connect to GitHub during setup

### Local environment:
- [ ] Python 3.11+ installed — verify with `python --version`
- [ ] pip installed — verify with `pip --version`
- [ ] VS Code installed from code.visualstudio.com
- [ ] Claude Code installed and working inside VS Code
- [ ] Node.js LTS installed from nodejs.org — verify with `node --version`
- [ ] Expo CLI installed — run `npm install -g expo-cli`, verify with `expo --version`
- [ ] Expo Go app installed on your phone (App Store or Google Play)

### Supabase MCP setup inside Claude Code:
- [ ] Generate a Supabase Personal Access Token (PAT) from Supabase account settings
- [ ] Run the following command in terminal: `claude mcp add supabase -s project -e SUPABASE_ACCESS_TOKEN=your_token -- npx -y @supabase/mcp-server-supabase@latest`
- [ ] Verify connection by asking Claude Code to list your Supabase tables

### Before first Claude Code session:
- [ ] Create a folder on your computer named `sauce` and open it in VS Code
- [ ] Have Supabase credentials ready to paste in
- [ ] Have the contents of this markdown file ready to paste as your first Claude Code prompt
