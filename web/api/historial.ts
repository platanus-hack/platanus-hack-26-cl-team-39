// /api/historial — últimos cambios del inventario (quién cambió qué y cuándo).
//   GET /api/historial?limite=50&id=12
import { historial } from './_lib/inventario.js'
import { json, manejar, opciones } from './_lib/http.js'

export const OPTIONS = opciones

export const GET = manejar(async (req) => {
  const p = new URL(req.url).searchParams
  const id = Number(p.get('id'))
  const cambios = await historial(Number(p.get('limite')) || 50, Number.isInteger(id) && id > 0 ? id : undefined)
  return json({ cambios })
})
