/** Resumen legible del payload de boxscore de statsapi.mlb.com */

export interface BoxscoreTeamLine {
  label: string;
  runs: number | null;
  hits: number | null;
  errors: number | null;
}

export interface BoxscoreInningRow {
  inning: number;
  awayRuns: number | null;
  homeRuns: number | null;
}

export interface BoxscoreSummary {
  away: BoxscoreTeamLine | null;
  home: BoxscoreTeamLine | null;
  innings: BoxscoreInningRow[];
}

function num(x: unknown): number | null {
  if (x === null || x === undefined) {
    return null;
  }
  if (typeof x === 'number' && !Number.isNaN(x)) {
    return x;
  }
  if (typeof x === 'string' && x.trim() !== '') {
    const n = Number(x);
    return Number.isNaN(n) ? null : n;
  }
  return null;
}

function parseTeamSide(side: unknown): BoxscoreTeamLine | null {
  if (!side || typeof side !== 'object') {
    return null;
  }
  const s = side as Record<string, unknown>;
  const team = s['team'] as Record<string, unknown> | undefined;
  const label =
    (team?.['abbreviation'] as string | undefined)?.trim() ||
    (team?.['teamName'] as string | undefined)?.trim() ||
    (team?.['name'] as string | undefined)?.trim() ||
    '—';
  const teamStats = s['teamStats'] as Record<string, unknown> | undefined;
  const batting = teamStats?.['batting'] as Record<string, unknown> | undefined;
  const fielding = teamStats?.['fielding'] as Record<string, unknown> | undefined;
  const err = num(fielding?.['errors']) ?? num(batting?.['errors']);
  return {
    label,
    runs: num(batting?.['runs']),
    hits: num(batting?.['hits']),
    errors: err,
  };
}

function inningRunsFromSide(side: unknown): (number | null)[] {
  if (!side || typeof side !== 'object') {
    return [];
  }
  const s = side as Record<string, unknown>;
  const innings = s['innings'];
  if (!Array.isArray(innings)) {
    return [];
  }
  return innings.map((inn) => {
    if (!inn || typeof inn !== 'object') {
      return null;
    }
    const o = inn as Record<string, unknown>;
    return num(o['runs'] ?? o['r']);
  });
}

/** Extrae R/H/E y, si existe, línea por inning desde el JSON de boxscore. */
export function parseBoxscoreSummary(raw: Record<string, unknown> | null): BoxscoreSummary | null {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const teams = raw['teams'] as Record<string, unknown> | undefined;
  if (!teams) {
    return null;
  }
  const away = parseTeamSide(teams['away']);
  const home = parseTeamSide(teams['home']);
  const awayInn = inningRunsFromSide(teams['away']);
  const homeInn = inningRunsFromSide(teams['home']);
  const maxLen = Math.max(awayInn.length, homeInn.length);
  const innings: BoxscoreInningRow[] = [];
  for (let i = 0; i < maxLen; i++) {
    innings.push({
      inning: i + 1,
      awayRuns: awayInn[i] ?? null,
      homeRuns: homeInn[i] ?? null,
    });
  }
  if (!away && !home && innings.length === 0) {
    return null;
  }
  return { away, home, innings };
}
