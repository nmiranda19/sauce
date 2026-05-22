import { api } from './client';

// ── Auth ──────────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', new URLSearchParams({ username: email, password }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),
  register: (name: string, email: string, password: string) =>
    api.post('/auth/register', { name, email, password }),
  me: () => api.get('/auth/me'),
};

// ── League ────────────────────────────────────────────────────────
export const leagueApi = {
  get:        () => api.get('/league/'),
  standings:  () => api.get('/league/standings'),
  news:       (limit = 50) => api.get(`/league/news?limit=${limit}`),
  streaks:    () => api.get('/league/streaks'),
  moves:      (limit = 30) => api.get(`/league/moves?limit=${limit}`),
};

// ── My team ───────────────────────────────────────────────────────
export const teamApi = {
  me:        () => api.get('/teams/me'),
  myRoster:  () => api.get('/teams/me/roster'),
  get:       (id: string) => api.get(`/teams/${id}`),
  roster:    (id: string) => api.get(`/teams/${id}/roster`),
};

// ── Lineup ────────────────────────────────────────────────────────
export const lineupApi = {
  lockStatus: () => api.get('/lineup/lock'),
  swapSlot:  (playerId: string, newSlot: string) =>
    api.put('/lineup/slot', { player_id: playerId, new_slot: newSlot }),
};

// ── Players ───────────────────────────────────────────────────────
export const playerApi = {
  search:    (q: string, position = '', limit = 25) =>
    api.get(`/players/?q=${encodeURIComponent(q)}&position=${position}&limit=${limit}`),
  available: (q = '', position = '') =>
    api.get(`/players/available?q=${encodeURIComponent(q)}&position=${position}`),
  get:       (id: string) => api.get(`/players/${id}`),
};

// ── Waiver ────────────────────────────────────────────────────────
export const waiverApi = {
  priority:  () => api.get('/waiver/priority'),
  myClaims:  () => api.get('/waiver/claims/mine'),
  claim:     (playerToAddId: string, targetSlot: string, playerToDropId?: string) =>
    api.post('/waiver/claim', { player_to_add_id: playerToAddId, target_slot: targetSlot, player_to_drop_id: playerToDropId }),
  addFA:     (playerId: string, slot: string, playerToDropId?: string) =>
    api.post('/waiver/add', { player_id: playerId, slot, player_to_drop_id: playerToDropId }),
  drop:      (playerId: string) =>
    api.post('/waiver/drop', null, { params: { player_id: playerId } }),
};

// ── Trades ────────────────────────────────────────────────────────
export const tradeApi = {
  list:    () => api.get('/trades/'),
  get:     (id: string) => api.get(`/trades/${id}`),
  impact:  (id: string) => api.get(`/trades/${id}/impact`),
  propose: (receivingTeamId: string, myPlayers: string[], theirPlayers: string[]) =>
    api.post('/trades/', { receiving_team_id: receivingTeamId, players_from_me: myPlayers, players_from_them: theirPlayers }),
  respond: (id: string, accept: boolean) => api.post(`/trades/${id}/respond`, { accept }),
  withdraw:(id: string) => api.post(`/trades/${id}/withdraw`),
};

// ── Matchups ──────────────────────────────────────────────────────
export const matchupApi = {
  current:   () => api.get('/matchups/current'),
  week:      (n: number) => api.get(`/matchups/week/${n}`),
  get:       (id: string) => api.get(`/matchups/${id}`),
};

// ── Commissioner ──────────────────────────────────────────────────
export const commissionerApi = {
  pendingTrades:   () => api.get('/commissioner/trades/pending'),
  approveTrade:    (tradeId: string, notes?: string) => api.post('/commissioner/trades/approve', { trade_id: tradeId, notes }),
  vetoTrade:       (tradeId: string, notes?: string) => api.post('/commissioner/trades/veto', { trade_id: tradeId, notes }),
  draftAssign:     (teamId: string, playerId: string, slot: string) =>
    api.post('/commissioner/draft/assign', { team_id: teamId, player_id: playerId, slot }),
  waiverOverride:  (teamId: string, playerId: string, slot: string, dropId?: string, notes?: string) =>
    api.post('/commissioner/waiver/override', { team_id: teamId, player_id: playerId, slot, player_to_drop_id: dropId, notes }),
  advanceWeek:     () => api.post('/commissioner/advance-week'),
  log:             () => api.get('/commissioner/log'),
};
