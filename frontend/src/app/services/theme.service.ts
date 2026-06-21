import { Injectable, signal } from '@angular/core';

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'theme';

/**
 * Gestiona el tema claro/oscuro. El atributo `data-theme` se fija en `index.html`
 * antes de renderizar (anti-FOUC); este servicio sincroniza la señal con ese
 * estado inicial y persiste los cambios del usuario en localStorage.
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly theme = signal<Theme>(this.readInitial());

  /** Aplica el tema guardado al <html>. Llamar una vez al arrancar la app. */
  init(): void {
    this.apply(this.theme());
  }

  toggle(): void {
    this.set(this.theme() === 'dark' ? 'light' : 'dark');
  }

  set(theme: Theme): void {
    this.theme.set(theme);
    this.apply(theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* localStorage no disponible (modo privado) — el tema sigue activo en memoria */
    }
  }

  private apply(theme: Theme): void {
    document.documentElement.setAttribute('data-theme', theme);
  }

  private readInitial(): Theme {
    // Confía en lo que el script inline ya fijó en <html data-theme>.
    const current = document.documentElement.getAttribute('data-theme');
    if (current === 'dark' || current === 'light') return current;

    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === 'dark' || saved === 'light') return saved;
    } catch {
      /* ignore */
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
}
