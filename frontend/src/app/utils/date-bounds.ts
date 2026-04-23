/** Fechas ISO `YYYY-MM-DD` desde `start` hasta `end` (inclusive). Requiere `start <= end`. */
export function eachIsoDateInRange(start: string, end: string): string[] {
  if (start > end) {
    return [];
  }
  const out: string[] = [];
  const cur = new Date(`${start}T12:00:00`);
  const last = new Date(`${end}T12:00:00`);
  while (cur <= last) {
    const y = cur.getFullYear();
    const m = String(cur.getMonth() + 1).padStart(2, '0');
    const d = String(cur.getDate()).padStart(2, '0');
    out.push(`${y}-${m}-${d}`);
    cur.setDate(cur.getDate() + 1);
  }
  return out;
}

/** Límites de fecha para temporada en curso (solo año civil actual, sin futuro). */
export function currentSeasonDateBounds(): { min: string; max: string; year: number } {
  const today = new Date();
  const y = today.getFullYear();
  const m = String(today.getMonth() + 1).padStart(2, '0');
  const d = String(today.getDate()).padStart(2, '0');
  return {
    year: y,
    min: `${y}-01-01`,
    max: `${y}-${m}-${d}`,
  };
}

/** `YYYY-MM-DD` a partir de una fecha local. */
export function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** Suma días a una fecha ISO (mediodía local para evitar DST raros). */
export function addDaysIso(iso: string, days: number): string {
  const cur = new Date(`${iso}T12:00:00`);
  cur.setDate(cur.getDate() + days);
  return toIsoDate(cur);
}

/** Lista de fechas desde `startIso` (inclusive), `count` días, recortada a `maxIso` si hace falta. */
export function consecutiveIsoDatesClamped(startIso: string, count: number, maxIso: string): string[] {
  const out: string[] = [];
  let cur = startIso;
  for (let i = 0; i < count; i++) {
    if (cur > maxIso) {
      break;
    }
    out.push(cur);
    cur = addDaysIso(cur, 1);
  }
  return out;
}
