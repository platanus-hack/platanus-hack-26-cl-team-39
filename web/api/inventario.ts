// /api/inventario — leer (público) y modificar (con la clave del equipo) el inventario de hardware.
//
//   GET    /api/inventario                       → { items: [...] }  (?q= texto, ?categoria=, ?estado=, ?origen=, ?id=)
//   POST   /api/inventario   { item } | { items: [...] }            → { items: [creados] }
//   PATCH  /api/inventario?id=12   { cantidad: 3, estado: "En uso" } → { item }
//   DELETE /api/inventario?id=12                                     → { item: borrado }
//
// Escribir pide `Authorization: Bearer <clave>`. Manda `x-autor: Tu nombre (Claude)` para que quede en el historial.
import { borrar, crear, editar, ESTADOS, listar, obtener, ErrorHttp } from './_lib/inventario.js'
import { autorDe, exigirClave, idDe, json, leerJson, manejar, opciones } from './_lib/http.js'

export const OPTIONS = opciones

export const GET = manejar(async (req) => {
  const url = new URL(req.url)
  if (url.searchParams.has('id')) {
    const item = await obtener(idDe(url))
    if (!item) throw new ErrorHttp(404, 'No existe ese ítem.')
    return json({ item })
  }
  const p = url.searchParams
  const items = await listar({ q: p.get('q') ?? undefined, categoria: p.get('categoria') ?? undefined, estado: p.get('estado') ?? undefined, origen: p.get('origen') ?? undefined })
  return json({ total: items.length, estados: ESTADOS, items })
})

export const POST = manejar(async (req) => {
  exigirClave(req)
  const b = await leerJson(req)
  const lista = Array.isArray(b.items) ? b.items : b.item ? [b.item] : b.nombre ? [b] : null
  if (!lista?.length) throw new ErrorHttp(400, 'Manda { "item": {...} } o { "items": [...] }. El único campo obligatorio es "nombre".')
  if (lista.length > 200) throw new ErrorHttp(400, 'Máximo 200 ítems por llamada.')
  const items = await crear(lista, autorDe(req, b))
  return json({ items }, 201)
})

export const PATCH = manejar(async (req) => {
  exigirClave(req)
  const id = idDe(new URL(req.url))
  const b = await leerJson(req)
  const { autor: _autor, ...cambios } = b
  void _autor
  const item = await editar(id, cambios, autorDe(req, b))
  return json({ item })
})

export const DELETE = manejar(async (req) => {
  exigirClave(req)
  const item = await borrar(idDe(new URL(req.url)), autorDe(req))
  return json({ item })
})
