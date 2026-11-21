// Ayudas HTTP comunes a las funciones de /api (Web Request/Response: corren igual en Vercel y en el dev server de Vite).
import { ErrorHttp } from './inventario.js'

const CORS = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET, POST, PATCH, DELETE, OPTIONS',
  'access-control-allow-headers': 'content-type, authorization, x-autor, mcp-protocol-version, mcp-session-id',
}

export function json(data: unknown, status = 200, extra: Record<string, string> = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...CORS, ...extra },
  })
}

export const opciones = () => new Response(null, { status: 204, headers: CORS })

/** Clave del equipo: `Authorization: Bearer <clave>`. Sin INVENTARIO_TOKEN en el servidor (desarrollo local) no se pide. */
export function autorizado(req: Request) {
  const clave = process.env.INVENTARIO_TOKEN
  if (!clave) return true
  const h = req.headers.get('authorization') ?? ''
  return h.replace(/^Bearer\s+/i, '').trim() === clave
}

export function exigirClave(req: Request) {
  if (!autorizado(req))
    throw new ErrorHttp(401, 'Falta la clave del equipo o no es correcta. Mándala como "Authorization: Bearer <clave>". Pídesela al equipo si no la tienes.')
}

/** Quién hace el cambio: header `x-autor` o campo `autor` del cuerpo. Ej: "Carlos (Claude)". */
export function autorDe(req: Request, cuerpo?: { autor?: unknown }) {
  const a = (typeof cuerpo?.autor === 'string' ? cuerpo.autor : req.headers.get('x-autor')) ?? ''
  return decodeURIComponent(a).trim().slice(0, 80) || 'sin nombre'
}

export async function leerJson(req: Request): Promise<Record<string, unknown>> {
  const t = await req.text()
  if (!t.trim()) return {}
  try {
    const v = JSON.parse(t)
    if (v && typeof v === 'object') return v
  } catch {
    /* cae abajo */
  }
  throw new ErrorHttp(400, 'El cuerpo no es JSON válido.')
}

export function idDe(url: URL) {
  const id = Number(url.searchParams.get('id'))
  if (!Number.isInteger(id) || id <= 0) throw new ErrorHttp(400, 'Falta ?id=<número> en la URL.')
  return id
}

export function manejar(fn: (req: Request) => Promise<Response>) {
  return async (req: Request) => {
    try {
      return await fn(req)
    } catch (e) {
      if (e instanceof ErrorHttp) return json({ error: e.message }, e.status)
      console.error(e)
      return json({ error: 'Error interno del servidor.', detalle: e instanceof Error ? e.message : String(e) }, 500)
    }
  }
}
