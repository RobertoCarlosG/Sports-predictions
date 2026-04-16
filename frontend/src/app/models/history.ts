import type { TeamOut } from './game';

export interface HistoryGame {
  sport_code: string;
  game_pk: number;
  season: string;
  game_date: string;
  status: string;
  home_team: TeamOut;
  away_team: TeamOut;
  home_score: number | null;
  away_score: number | null;
  winner_team_id: number | null;
}

export interface MlbSyncRangeResult {
  start_date: string;
  end_date: string;
  days_synced: number;
}
