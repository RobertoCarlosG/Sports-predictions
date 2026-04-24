export interface TeamOut {
  id: number;
  name: string;
  abbreviation: string;
}

export interface GameDetail {
  game_pk: number;
  season: string;
  game_date: string;
  status: string;
  home_team: TeamOut;
  away_team: TeamOut;
  home_score?: number | null;
  away_score?: number | null;
  venue_id: number | null;
  venue_name: string | null;
  lineups: Record<string, unknown> | null;
  boxscore: Record<string, unknown> | null;
  weather: Record<string, unknown> | null;
  /** Presente en GET /games?include_predictions=true; null = sin estimación. */
  prediction?: PredictionOut | null;
}

export interface PredictionOut {
  game_pk: number;
  home_win_probability: number;
  total_runs_estimate: number;
  over_under_line: number;
  model_version: string;
}
