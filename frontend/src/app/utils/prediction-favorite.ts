/**
 * A partir de P(local) en [0,1], obtiene P del favorito (≥ 0,5) y el bando con mayor
 * probabilidad de victoria, sin encajar la lectura en «local/visitante».
 */
export function favoriteFromHomeWinProbability(
  homeWin: number | null | undefined,
): { favorite: 'home' | 'away' | 'none'; favoriteWinProb: number | null; homeWin: number | null } {
  if (homeWin == null || Number.isNaN(homeWin)) {
    return { favorite: 'none', favoriteWinProb: null, homeWin: null };
  }
  const p = Math.min(1, Math.max(0, homeWin));
  if (p >= 0.5) {
    return { favorite: 'home', favoriteWinProb: p, homeWin: p };
  }
  return { favorite: 'away', favoriteWinProb: 1 - p, homeWin: p };
}
