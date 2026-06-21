# Dark Mode — Bases y Plan de Implementación

> **Estado:** ✅ Implementado (2026-06-21).
> Se implementó con el mecanismo `data-theme` descrito abajo, pero **usando la paleta Slate + Azul original** (la que el usuario prefería) en lugar de los valores de tablas de este documento. Archivos: `_tokens.scss` (`[data-theme="dark"]`), `styles.scss` (overrides Material dark + blobs), `services/theme.service.ts`, script anti-FOUC en `index.html`, toggle en sidebar y topbar móvil. Este documento se conserva como referencia histórica del plan.

---

## Estrategia de theming

El sistema de diseño ya usa CSS custom properties en `_tokens.scss` bajo `:root`. Esto hace que el theming alternativo sea **sólo una sobrescritura de variables** — no requiere duplicar selectores ni crear archivos de componentes nuevos.

### Mecanismo propuesto: `data-theme` attribute

```html
<!-- index.html o app.component.html -->
<html data-theme="dark"> ... </html>
```

```scss
// _tokens.scss — añadir debajo de :root { ... }
[data-theme="dark"] {
  --bg-base:         #0F172A;
  --bg-elevated:     #1E293B;
  --bg-raised:       #293548;
  // ... resto de variables sobrescritas
}
```

**Ventajas sobre `prefers-color-scheme` media query:**
- Control explícito del usuario (toggle)
- Persiste en `localStorage`
- Puede coexistir con el respeto a `prefers-color-scheme` (ver más abajo)

---

## Paletas de color propuestas

### Paleta 1 — Oscuro Marino (recomendada)

Basada en Slate (Tailwind) con acento azul eléctrico. Mantiene el lenguaje visual actual.

| Token | Valor actual (light) | Valor propuesto (dark) |
|---|---|---|
| `--bg-base` | `#EEF2F7` | `#0F172A` |
| `--bg-elevated` | `#F5F8FC` | `#1E293B` |
| `--bg-raised` | `#FFFFFF` | `#293548` |
| `--glass-bg` | `rgba(255,255,255,.60)` | `rgba(30,41,59,.70)` |
| `--glass-bg-raised` | `rgba(255,255,255,.78)` | `rgba(41,53,72,.85)` |
| `--glass-bg-hover` | `rgba(255,255,255,.90)` | `rgba(41,53,72,.95)` |
| `--glass-border` | `rgba(59,130,246,.14)` | `rgba(99,160,255,.15)` |
| `--glass-border-hi` | `rgba(59,130,246,.28)` | `rgba(99,160,255,.28)` |
| `--accent` | `#2563EB` | `#3B82F6` |
| `--accent-strong` | `#1D4ED8` | `#60A5FA` |
| `--accent-soft` | `rgba(37,99,235,.10)` | `rgba(59,130,246,.18)` |
| `--accent-text` | `#1D4ED8` | `#93C5FD` |
| `--text-primary` | `#0F172A` | `#F1F5F9` |
| `--text-secondary` | `rgba(15,23,42,.65)` | `rgba(241,245,249,.65)` |
| `--text-tertiary` | `rgba(15,23,42,.42)` | `rgba(241,245,249,.40)` |
| `--text-disabled` | `rgba(15,23,42,.28)` | `rgba(241,245,249,.25)` |
| `--success` | `#16A34A` | `#4ADE80` |
| `--success-bg` | `rgba(22,163,74,.12)` | `rgba(74,222,128,.14)` |
| `--danger` | `#DC2626` | `#F87171` |
| `--danger-bg` | `rgba(220,38,38,.10)` | `rgba(248,113,113,.14)` |
| `--warning` | `#D97706` | `#FCD34D` |
| `--warning-bg` | `rgba(217,119,6,.12)` | `rgba(252,211,77,.14)` |
| `--info` | `#0284C7` | `#38BDF8` |
| `--info-bg` | `rgba(2,132,199,.10)` | `rgba(56,189,248,.14)` |
| `--shadow-sm` | `0 1px 4px rgba(15,23,42,.08)...` | `0 1px 4px rgba(0,0,0,.25)...` |
| `--shadow-md` | `0 4px 16px rgba(15,23,42,.10)...` | `0 4px 16px rgba(0,0,0,.35)...` |
| `--shadow-lg` | `0 8px 32px rgba(15,23,42,.14)...` | `0 8px 32px rgba(0,0,0,.50)...` |
| `--shadow-inset-top` | `inset 0 1px 0 rgba(255,255,255,.80)` | `inset 0 1px 0 rgba(255,255,255,.06)` |

---

### Paleta 2 — Carbono (alternativa, alto contraste)

Fondo casi negro, ideal para entornos oscuros extremos.

| Token | Valor propuesto (carbon) |
|---|---|
| `--bg-base` | `#09090B` |
| `--bg-elevated` | `#111113` |
| `--bg-raised` | `#18181B` |
| `--glass-bg` | `rgba(24,24,27,.80)` |
| `--glass-bg-raised` | `rgba(24,24,27,.92)` |
| `--accent` | `#60A5FA` |
| `--text-primary` | `#FAFAFA` |

---

### Paleta 3 — Ambar Oscuro (experimental)

Para un look distinto; cambia el acento de azul a ámbar.

| Token | Valor propuesto (amber-dark) |
|---|---|
| `--bg-base` | `#1C1410` |
| `--bg-elevated` | `#241C14` |
| `--bg-raised` | `#2E2318` |
| `--glass-border` | `rgba(251,191,36,.15)` |
| `--accent` | `#F59E0B` |
| `--accent-strong` | `#D97706` |
| `--accent-soft` | `rgba(245,158,11,.15)` |
| `--accent-text` | `#FCD34D` |
| `--text-primary` | `#FEF3C7` |

---

## Ajustes de Material M3 para modo oscuro

El theme de Angular Material también necesita ajustarse. En `styles.scss` se definen paletas M3 con `define-theme`. Para dark mode:

```scss
// styles.scss — añadir bloque para dark
[data-theme="dark"] {
  @include mat.all-component-colors(
    mat.define-theme((
      color: (
        theme-type: dark,
        primary: mat.$azure-palette,
        tertiary: mat.$blue-palette,
      ),
    ))
  );
}
```

Y actualizar todos los overrides de tokens de Material (cards, chips, snackbars, etc.) para que usen las variables de `_tokens.scss` en lugar de valores hardcodeados — la mayoría ya lo hacen mediante `var(--*)`.

---

## Body decorations en modo oscuro

Los blobs de fondo en `styles.scss` (gradientes azul en `body::before` y `body::after`) funcionan en oscuro sólo ajustando la opacidad:

```scss
[data-theme="dark"] {
  body::before,
  body::after {
    opacity: 0.15; // reducir de 0.30 a 0.15 para no saturar
  }
}
```

---

## Glass morphism en modo oscuro

El mixin `glass()` usa `--glass-bg` y `--glass-blur`. En modo oscuro, el blur sobre fondos oscuros produce menos efecto visual. Considerar aumentar la opacidad del fondo:

```scss
// Opción A: usar glass-bg más opaco para dark (ya cubierto en tokens arriba)
// Opción B: reducir --glass-blur a 12px en dark para evitar artefactos
[data-theme="dark"] {
  --glass-blur: 12px;
}
```

---

## Toggle de tema — ThemeService

Cuando se implemente, crear un servicio Angular sencillo:

```typescript
// theme.service.ts
import { Injectable, signal } from '@angular/core';

export type Theme = 'light' | 'dark';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly theme = signal<Theme>(this.loadSaved());

  toggle(): void {
    const next: Theme = this.theme() === 'light' ? 'dark' : 'light';
    this.theme.set(next);
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
  }

  init(): void {
    const saved = this.loadSaved();
    document.documentElement.setAttribute('data-theme', saved);
  }

  private loadSaved(): Theme {
    const saved = localStorage.getItem('theme') as Theme | null;
    if (saved === 'dark' || saved === 'light') return saved;
    // Respetar preferencia del sistema si no hay preferencia guardada
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
}
```

Llamar `themeService.init()` en `AppComponent.ngOnInit()`.  
El toggle puede vivir en el sidebar (desktop) o en el mobile topbar.

---

## Orden de implementación recomendado

1. Añadir la Paleta 1 (Marino) a `_tokens.scss` bajo `[data-theme="dark"]`
2. Verificar visualmente cada vista con `data-theme="dark"` en el `<html>`
3. Ajustar los overrides de Material en `styles.scss` para dark
4. Crear `ThemeService` y conectar toggle en sidebar/topbar
5. Evaluar paletas 2 y 3 como extras opcionales

---

## Paletas de color alternativas (light)

El usuario mencionó paletas que no fueron implementadas. Dado que el sistema ya está en `_tokens.scss` con CSS custom properties, añadir una paleta light alternativa es trivial:

```scss
// Ejemplo: paleta "Verde Bosque" (acento verde en lugar de azul)
[data-theme="forest"] {
  --accent:          #15803D;
  --accent-strong:   #166534;
  --accent-soft:     rgba(21,128,61,.10);
  --accent-text:     #166534;
  --glass-border:    rgba(21,128,61,.14);
  --glass-border-hi: rgba(21,128,61,.28);
}
```

No requiere modificar ningún componente — sólo añadir el bloque de tokens y el selector `data-theme` correspondiente.
