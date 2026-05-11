# Frontend — Sports-Predictions

SPA **Angular** (Material) que consume el API de Sports-Predictions: listado por fecha, historial MLB, detalle con clima, predicción, box score y sincronización de datos MLB.

## Desarrollo

```bash
npm install
npm start
```

Abre `http://localhost:4200/`. La URL del API se configura en `src/environments/environment.ts` (`apiUrl`); en producción, [environment.prod.ts](src/environments/environment.prod.ts).

## Build

```bash
npm run build
```

Salida en **`dist/browser`** (Vercel típico: *Output Directory* `dist/browser`). Asegura `apiUrl` en `environment.prod.ts` apunta al backend desplegado.

## Tests

```bash
ng test
```

## Documentación específica del frontend

Los documentos dentro de **`frontend/docs/`** (esta carpeta sí se puede versionar) describen patrones locales, p. ej.:
- [docs/CACHE-HTTP-FRONTEND.md](docs/CACHE-HTTP-FRONTEND.md) — caché HTTP con `shareReplay(1)`, botón «Actualizar» y diagramas Mermaid del flujo Hoy → Mañana → Hoy, decisión interna de `RequestCache.get`, force refresh y mutaciones.

## Origen del proyecto

Generado con [Angular CLI](https://github.com/angular/angular-cli); versiones concretas en `package.json` y `angular.json`.
