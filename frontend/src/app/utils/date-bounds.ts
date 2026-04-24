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

/** Límites de fecha para temporada en curso (año civil actual con margen futuro de 30 días). */
export function currentSeasonDateBounds(): { min: string; max: string; year: number } {
  const today = new Date();
  const y = today.getFullYear();
  const futureDate = new Date(today);
  futureDate.setDate(futureDate.getDate() + 30);
  const maxY = futureDate.getFullYear();
  const maxM = String(futureDate.getMonth() + 1).padStart(2, '0');
  const maxD = String(futureDate.getDate()).padStart(2, '0');
  return {
    year: y,
    min: `${y}-01-01`,
    max: `${maxY}-${maxM}-${maxD}`,
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

/** Lunes de la semana calendario que contiene `iso` (lunes–domingo, locale del navegador). */
export function mondayOfIsoWeek(iso: string): string {
  const cur = new Date(`${iso}T12:00:00`);
  const dow = cur.getDay(); // 0 = domingo, 1 = lunes, …
  const offset = dow === 0 ? -6 : 1 - dow;
  cur.setDate(cur.getDate() + offset);
  return toIsoDate(cur);
}

/**
 * Días de la semana actual (lun → dom) que caen en [minIso, maxIso] (p. ej. max = hoy).
 * Así «Esta semana» no se confunde con «solo hoy» cuando maxIso es hoy y antes se avanzaba al futuro.
 */
export function calendarWeekRangeClamped(iso: string, minIso: string, maxIso: string): string[] {
  const mon = mondayOfIsoWeek(iso);
  const sun = addDaysIso(mon, 6);
  const start = mon < minIso ? minIso : mon;
  const end = sun > maxIso ? maxIso : sun;
  if (start > end) {
    return [];
  }
  return eachIsoDateInRange(start, end);
}
