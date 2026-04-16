import { HttpErrorResponse } from '@angular/common/http';

/** Vista enriquecida para mostrar errores de API sin confundir CORS con el fallo real. */
export interface ApiErrorView {
  title: string;
  summary: string;
  hints: string[];
  httpStatus: number;
  code?: string;
  /** Solo si el backend envía `technical` o cuerpo en texto */
  technical?: string;
}

function readBodyMessage(body: unknown): { message: string; detail: string; technical?: string } {
  if (body === null || body === undefined) {
    return { message: '', detail: '' };
  }
  if (typeof body === 'string') {
    return { message: body, detail: '' };
  }
  if (typeof body === 'object') {
    const o = body as Record<string, unknown>;
    const message = typeof o['message'] === 'string' ? o['message'] : '';
    const detail = o['detail'] !== undefined ? String(o['detail']) : '';
    const technical = typeof o['technical'] === 'string' ? o['technical'] : undefined;
    return { message, detail, technical };
  }
  return { message: '', detail: '' };
}

export function parseApiError(err: unknown): ApiErrorView {
  if (err instanceof HttpErrorResponse) {
    const status = err.status;
    const { message, detail, technical } = readBodyMessage(err.error);

    if (status === 0) {
      return {
        title: 'Sin respuesta del servidor',
        summary:
          'El navegador no pudo leer la respuesta del API. A veces aparece un aviso de CORS ' +
          'cuando el servidor devolvió error 500 sin cabeceras CORS: el problema real suele ser el fallo en el backend, no la configuración de CORS.',
        hints: [
          'Abre los logs del servicio en Render y busca el stack trace (p. ej. base de datos).',
          'Si el error era `relation "teams" does not exist`, ejecuta `backend/sql/001_initial_schema.sql` en Supabase.',
          'En Render, variable CORS_ORIGINS debe incluir exactamente tu URL de Vercel (https://….vercel.app).',
        ],
        httpStatus: 0,
        code: detail || undefined,
        technical: err.message || technical,
      };
    }

    if (status === 503 && detail === 'database_schema_missing') {
      return {
        title: 'Base de datos sin tablas',
        summary:
          message ||
          'Las tablas no existen en PostgreSQL. El API no puede guardar ni leer partidos.',
        hints: [
          'En Supabase → SQL → pega y ejecuta el contenido de `backend/sql/001_initial_schema.sql`.',
          'Vuelve a cargar esta página cuando el script haya terminado sin error.',
        ],
        httpStatus: status,
        code: detail,
        technical,
      };
    }

    if (status >= 500) {
      return {
        title: 'Error del servidor',
        summary:
          message ||
          'El API devolvió un error interno. Revisa los logs en Render para el detalle exacto.',
        hints: [
          'Confirma DATABASE_URL en Render y que las tablas existen.',
          'Si ves CORS en consola pero el log muestra 500, el fallo es el 500; CORS en errores ya se corrige en versiones recientes del backend.',
        ],
        httpStatus: status,
        code: detail || undefined,
        technical: technical ?? (typeof err.error === 'string' ? err.error : JSON.stringify(err.error)),
      };
    }

    if (status === 404) {
      return {
        title: 'No encontrado',
        summary: message || 'El recurso no existe en el API.',
        hints: ['Comprueba la URL del API en environment.prod.ts.'],
        httpStatus: status,
        code: detail || undefined,
      };
    }

    return {
      title: `Error HTTP ${status}`,
      summary: message || err.statusText || err.message || 'Error al llamar al API.',
      hints: [],
      httpStatus: status,
      code: detail || undefined,
      technical,
    };
  }

  if (err instanceof Error) {
    return {
      title: 'Error',
      summary: err.message,
      hints: [],
      httpStatus: 0,
    };
  }

  return {
    title: 'Error desconocido',
    summary: 'No se pudo interpretar el error.',
    hints: [],
    httpStatus: 0,
  };
}
