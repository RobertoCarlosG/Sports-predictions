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
