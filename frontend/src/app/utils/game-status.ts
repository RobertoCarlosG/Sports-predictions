/** Clasificación de estado de partido para UI (sin exponer códigos crudos de la API). */
export type MatchStatusKind = 'live' | 'upcoming' | 'final';

export function matchStatusKind(status: string): MatchStatusKind {
  const s = status.toLowerCase();
  if (s.includes('live') || s.includes('in progress') || (s.includes('delayed') && s.includes('game'))) {
    return 'live';
  }
  if (
    s.includes('final') ||
    s.includes('completed') ||
    s.includes('game over') ||
    s.includes('cancelled') ||
    s.includes('postponed')
  ) {
    return 'final';
  }
  return 'upcoming';
}

export function matchStatusLabel(kind: MatchStatusKind): string {
  switch (kind) {
    case 'live':
      return 'En vivo';
    case 'final':
      return 'Final';
    default:
      return 'Próximo';
  }
}
