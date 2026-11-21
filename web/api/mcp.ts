// /api/mcp — servidor MCP (Streamable HTTP, sin estado) para que el Claude de cada uno use el inventario como herramientas.
//
//   Claude Code:  claude mcp add --transport http inventario https://<deploy>/api/mcp --header "Authorization: Bearer <clave>"
//   claude.ai:    conector personalizado con la URL https://<deploy>/api/mcp?clave=<clave>
//
// Implementa lo mínimo del protocolo: initialize, ping, tools/list y tools/call, con respuestas JSON (sin SSE).
import { ESTADOS, borrar, crear, editar, historial, listar, obtener, ErrorHttp, type Item } from './_lib/inventario.js'
import { preguntar } from './_lib/ia.js'
import { json, opciones } from './_lib/http.js'

export const OPTIONS = opciones

const VERSIONES = ['2025-06-18', '2025-03-26', '2024-11-05']

const campos = {
  nombre: { type: 'string', description: 'Nombre del ítem, con modelo si se sabe. Ej: "Sensor ultrasónico HC-SR04".' },
  cantidad: { type: ['integer', 'null'], minimum: 0, description: 'Cuántos hay. null si no se sabe.' },
  categoria: { type: 'string', description: 'Usa una existente: Placas y módulos, Sensores, Motores, Alimentación, Cables y conectores, Luz y pantallas, Estructura, Prototipado, Herramientas, Consumibles, Control.' },
  origen: { type: ['string', 'null'], description: 'De quién es o de dónde salió. Ej: "Inventario de Carlos", "Compra AFEL", "Caja de herramientas".' },
  estado: { type: 'string', description: `Uno de: ${ESTADOS.join(', ')}.` },
  uso_bicho: { type: ['string', 'null'], description: 'Para qué se usa en el robot (el bicho).' },
  ubicacion: { type: ['string', 'null'], description: 'Dónde está físicamente. Ej: "caja azul", "mochila de Renate".' },
  notas: { type: ['string', 'null'], description: 'Detalles: specs, voltaje, si falta algo, etc.' },
}
const autor = { type: 'string', description: 'Quién hace el cambio, con tu humano y que eres Claude. Ej: "Carlos (Claude)".' }

const TOOLS = [
  {
    name: 'buscar_items',
    description:
      'Lista ítems del inventario de hardware del equipo. Sin filtros devuelve todo (~130 ítems). "q" busca texto en todos los campos sin importar tildes. Para preguntas abiertas ("¿qué podemos usar para X?") usa preguntar_inventario.',
    inputSchema: {
      type: 'object',
      properties: {
        q: { type: 'string', description: 'Texto a buscar. Ej: "servo", "batería", "HC-SR04".' },
        categoria: { type: 'string' },
        estado: { type: 'string' },
        origen: { type: 'string', description: 'Parte del origen. Ej: "Carlos".' },
      },
      additionalProperties: false,
    },
  },
  {
    name: 'ver_item',
    description: 'Muestra un ítem por su id, con todos sus campos.',
    inputSchema: { type: 'object', properties: { id: { type: 'integer' } }, required: ['id'], additionalProperties: false },
  },
  {
    name: 'preguntar_inventario',
    description: 'Pregunta en lenguaje natural sobre el inventario; responde Claude con los ítems relevantes. Ej: "¿tenemos algo para medir distancia?".',
    inputSchema: { type: 'object', properties: { pregunta: { type: 'string' } }, required: ['pregunta'], additionalProperties: false },
  },
  {
    name: 'agregar_items',
    description: 'Agrega uno o más ítems nuevos. Antes busca con buscar_items que no exista ya; si existe, usa editar_item para cambiar la cantidad.',
    inputSchema: {
      type: 'object',
      properties: {
        items: { type: 'array', minItems: 1, maxItems: 200, items: { type: 'object', properties: campos, required: ['nombre'], additionalProperties: false } },
        autor,
      },
      required: ['items', 'autor'],
      additionalProperties: false,
    },
  },
  {
    name: 'editar_item',
    description: 'Cambia campos de un ítem existente (solo los que mandes). Ej: bajar la cantidad, marcarlo "En uso", anotar dónde está o para qué se usa en el bicho.',
    inputSchema: {
      type: 'object',
      properties: { id: { type: 'integer' }, cambios: { type: 'object', properties: campos, additionalProperties: false, minProperties: 1 }, autor },
      required: ['id', 'cambios', 'autor'],
      additionalProperties: false,
    },
  },
  {
    name: 'borrar_item',
    description: 'Borra un ítem. Úsalo solo si está duplicado o se agregó por error; si se rompió o se perdió, mejor edita su estado. Queda en el historial.',
    inputSchema: { type: 'object', properties: { id: { type: 'integer' }, autor }, required: ['id', 'autor'], additionalProperties: false },
  },
  {
    name: 'ver_historial',
    description: 'Últimos cambios del inventario: quién cambió qué y cuándo. Con "id", solo los de ese ítem.',
    inputSchema: { type: 'object', properties: { limite: { type: 'integer', minimum: 1, maximum: 200 }, id: { type: 'integer' } }, additionalProperties: false },
  },
]

const INSTRUCCIONES =
  'Inventario de hardware del equipo CRBRC (Platanus Hack 26), en Neon. Todo el equipo lo ve en bicho·dev. Antes de agregar algo, busca si ya existe. En cada cambio pon en "autor" a tu humano y que eres Claude, ej: "Renate (Claude)".'

/** Versión compacta de un ítem para no llenar el contexto del modelo. */
function corto(i: Item) {
  const o: Record<string, unknown> = { id: i.id, nombre: i.nombre, cantidad: i.cantidad, categoria: i.categoria, origen: i.origen, estado: i.estado }
  for (const k of ['uso_bicho', 'ubicacion', 'notas'] as const) if (i[k]) o[k] = i[k]
  return o
}

function claveOk(req: Request) {
  const clave = process.env.INVENTARIO_TOKEN
  if (!clave) return true
  const h = (req.headers.get('authorization') ?? '').replace(/^Bearer\s+/i, '').trim()
  return h === clave || new URL(req.url).searchParams.get('clave') === clave
}

type Args = Record<string, unknown>
const int = (v: unknown, nombre: string) => {
  if (typeof v !== 'number' || !Number.isInteger(v)) throw new ErrorHttp(400, `"${nombre}" debe ser un número entero.`)
  return v
}
const quien = (a: Args, req: Request) => (typeof a.autor === 'string' && a.autor.trim() ? a.autor.trim().slice(0, 80) : req.headers.get('x-autor') || 'Claude (MCP)')

async function llamar(nombre: string, a: Args, req: Request): Promise<unknown> {
  switch (nombre) {
    case 'buscar_items': {
      const s = (k: string) => (typeof a[k] === 'string' ? (a[k] as string) : undefined)
      const items = await listar({ q: s('q'), categoria: s('categoria'), estado: s('estado'), origen: s('origen') })
      return { total: items.length, items: items.map(corto) }
    }
    case 'ver_item': {
      const item = await obtener(int(a.id, 'id'))
      if (!item) throw new ErrorHttp(404, `No existe el ítem ${a.id}.`)
      return item
    }
    case 'preguntar_inventario':
      if (typeof a.pregunta !== 'string' || !a.pregunta.trim()) throw new ErrorHttp(400, 'Falta "pregunta".')
      return preguntar(a.pregunta.trim().slice(0, 2000))
    case 'agregar_items':
      if (!Array.isArray(a.items) || !a.items.length) throw new ErrorHttp(400, 'Falta "items" (lista).')
      return { creados: (await crear(a.items.slice(0, 200), quien(a, req))).map(corto) }
    case 'editar_item':
      return corto(await editar(int(a.id, 'id'), a.cambios ?? {}, quien(a, req)))
    case 'borrar_item':
      return { borrado: corto(await borrar(int(a.id, 'id'), quien(a, req))) }
    case 'ver_historial':
      return historial(typeof a.limite === 'number' ? a.limite : 30, typeof a.id === 'number' ? a.id : undefined)
    default:
      throw new ErrorHttp(404, `No existe la herramienta "${nombre}".`)
  }
}

type Rpc = { jsonrpc?: string; id?: string | number | null; method?: string; params?: Record<string, unknown> }

async function responder(m: Rpc, req: Request) {
  const ok = (result: unknown) => ({ jsonrpc: '2.0', id: m.id, result })
  const err = (code: number, message: string) => ({ jsonrpc: '2.0', id: m.id ?? null, error: { code, message } })
  switch (m.method) {
    case 'initialize': {
      const pedida = String(m.params?.protocolVersion ?? '')
      return ok({
        protocolVersion: VERSIONES.includes(pedida) ? pedida : VERSIONES[0],
        capabilities: { tools: { listChanged: false } },
        serverInfo: { name: 'inventario-crbrc', title: 'Inventario CRBRC', version: '1.0.0' },
        instructions: INSTRUCCIONES,
      })
    }
    case 'ping':
      return ok({})
    case 'tools/list':
      return ok({ tools: TOOLS })
    case 'tools/call': {
      const nombre = String(m.params?.name ?? '')
      const args = (m.params?.arguments ?? {}) as Args
      try {
        const r = await llamar(nombre, args, req)
        return ok({ content: [{ type: 'text', text: JSON.stringify(r, null, 1) }] })
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e)
        return ok({ content: [{ type: 'text', text: `Error: ${msg}` }], isError: true })
      }
    }
    default:
      return err(-32601, `Método no soportado: ${m.method}`)
  }
}

export async function POST(req: Request) {
  if (!claveOk(req)) return json({ jsonrpc: '2.0', id: null, error: { code: -32001, message: 'Falta la clave del equipo (Authorization: Bearer <clave> o ?clave=).' } }, 401)
  let body: Rpc | Rpc[]
  try {
    body = await req.json()
  } catch {
    return json({ jsonrpc: '2.0', id: null, error: { code: -32700, message: 'JSON inválido.' } }, 400)
  }
  const lista = Array.isArray(body) ? body : [body]
  const conId = lista.filter((m) => m.id !== undefined && m.id !== null)
  // Notificaciones y respuestas del cliente no llevan respuesta.
  if (!conId.length) return new Response(null, { status: 202, headers: { 'access-control-allow-origin': '*' } })
  const out = await Promise.all(conId.map((m) => responder(m, req)))
  return json(Array.isArray(body) ? out : out[0])
}

export function GET() {
  return json({ error: 'Este servidor MCP no abre streams SSE: usa POST.' }, 405, { allow: 'POST, OPTIONS' })
}

export function DELETE() {
  return new Response(null, { status: 405, headers: { allow: 'POST, OPTIONS' } })
}
