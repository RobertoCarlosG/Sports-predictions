export type SportId = 'mlb' | 'soccer' | 'nba';

export interface SportOption {
  id: SportId;
  /** Etiqueta corta en el selector */
  label: string;
  /** Descripción para pantallas “próximamente” */
  description: string;
  /** Si el dashboard de datos ya está implementado */
  implemented: boolean;
  /** Icono de Material Icons */
  icon: string;
}

export const SPORT_OPTIONS: readonly SportOption[] = [
  {
    id: 'mlb',
    label: 'MLB',
    description: 'Major League Baseball — statsapi.mlb.com',
    implemented: true,
    icon: 'sports_baseball',
  },
  {
    id: 'soccer',
    label: 'Fútbol',
    description: 'Soccer — API-Sports (planificado)',
    implemented: false,
    icon: 'sports_soccer',
  },
  {
    id: 'nba',
    label: 'NBA',
    description: 'NBA — API-Sports (planificado)',
    implemented: false,
    icon: 'sports_basketball',
  },
] as const;

export function sportIdFromUrl(path: string): SportId {
  const p = path.split('?')[0] ?? '';
  if (p.startsWith('/soccer')) {
    return 'soccer';
  }
  if (p.startsWith('/nba')) {
    return 'nba';
  }
  return 'mlb';
}

/** Deporte resaltado en la barra superior; en `/operations` ninguno. */
export function activeSportIdFromUrl(path: string): SportId | null {
  const p = path.split('?')[0] ?? '';
  if (p.startsWith('/operations')) {
    return null;
  }
  return sportIdFromUrl(path);
}
