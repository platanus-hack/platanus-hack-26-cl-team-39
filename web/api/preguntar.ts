// /api/preguntar — pregúntale a Claude por el inventario en lenguaje natural.
//   POST /api/preguntar  { "pregunta": "¿tenemos algo para medir distancia?" }
//   → { respuesta, ids: [ítems relevantes], modelo }
// Pide la clave del equipo (cada pregunta gasta tokens).
import { preguntar } from './_lib/ia.js'
import { ErrorHttp } from './_lib/inventario.js'
import { exigirClave, json, leerJson, manejar, opciones } from './_lib/http.js'

export const OPTIONS = opciones

export const POST = manejar(async (req) => {
  exigirClave(req)
  const b = await leerJson(req)
  const pregunta = typeof b.pregunta === 'string' ? b.pregunta.trim() : ''
  if (!pregunta) throw new ErrorHttp(400, 'Manda { "pregunta": "…" }.')
  if (pregunta.length > 2000) throw new ErrorHttp(400, 'La pregunta es muy larga (máximo 2000 caracteres).')
  return json(await preguntar(pregunta))
})
