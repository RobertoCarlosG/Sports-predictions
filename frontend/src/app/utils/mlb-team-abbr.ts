import type { TeamOut } from '../models/game';

/** Mismo mapa que el backend: evita HOME/AWAY si el API o la BD vienen mal tipados. */
const MLB_TEAM_ABBR: Readonly<Record<number, string>> = {
  108: 'LAA',
  109: 'AZ',
  110: 'BAL',
  111: 'BOS',
  112: 'CHC',
  113: 'CIN',
  114: 'CLE',
  115: 'COL',
  116: 'DET',
  117: 'HOU',
  118: 'KC',
  119: 'LAD',
  120: 'WSH',
  121: 'NYM',
  133: 'ATH',
  134: 'PIT',
  135: 'SD',
  136: 'SEA',
  137: 'SF',
  138: 'STL',
  139: 'TB',
  140: 'TEX',
  141: 'TOR',
  142: 'MIN',
  143: 'PHI',
  144: 'ATL',
  145: 'CWS',
  146: 'MIA',
  147: 'NYY',
  158: 'MIL',
};

function teamIdToInt(id: number): number {
  return Math.trunc(Number(id));
}

/** Abreviatura segura para listados (respeta id MLB aunque abbreviation sea HOME/AWAY). */
export function mlbDisplayAbbrev(team: TeamOut): string {
  const tid = teamIdToInt(team.id);
  const mapped = MLB_TEAM_ABBR[tid];
  if (mapped) {
    return mapped;
  }
  const a = (team.abbreviation ?? '').trim().toUpperCase();
  if (a && a !== 'HOME' && a !== 'AWAY') {
    return a.slice(0, 8);
  }
  const parts = (team.name ?? '').trim().split(/\s+/);
  if (parts.length > 0) {
    return parts[parts.length - 1]!.slice(0, 8).toUpperCase();
  }
  return '?';
}
