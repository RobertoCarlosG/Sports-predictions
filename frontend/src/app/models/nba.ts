export interface NbaTeamOut {
  id: number;
  name: string;
  abbreviation: string;
  conference?: string | null;
  division?: string | null;
}

export interface NbaPredictionOut {
  game_id: string;
  home_win_probability: number;
  margin_estimate: number;
  total_points_estimate: number;
  spread_line: number;
  over_under_line: number;
  over_probability?: number | null;
  model_version: string;
  defaults_injected?: boolean;
  predicted_winner?: 'home' | 'away' | null;
  actual_winner?: 'home' | 'away' | null;
  is_correct?: boolean | null;
  evaluated_at?: string | null;
}

export interface NbaGameDetail {
  game_id: string;
  season: string;
  game_date: string;
  status: string;
  home_team: NbaTeamOut;
  away_team: NbaTeamOut;
  home_score?: number | null;
  away_score?: number | null;
  arena?: string | null;
  boxscore?: Record<string, unknown> | null;
  prediction?: NbaPredictionOut | null;
}

export interface NbaGamesListMeta {
  warnings: string[];
  info: string[];
  missing_snapshot_count: number;
}

export interface NbaGamesListResponse {
  games: NbaGameDetail[];
  meta: NbaGamesListMeta;
}

export type NbaModelKind = 'xgb' | 'lgbm' | 'catboost' | 'ensemble';
