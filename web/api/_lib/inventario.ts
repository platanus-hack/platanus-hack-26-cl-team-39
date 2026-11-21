// Lógica del inventario, compartida por la API REST (/api/inventario), el servidor MCP (/api/mcp)
// y la búsqueda con Claude (/api/preguntar). Archivos con "_" no se publican como funciones en Vercel.
import { neon } from '@neondatabase/serverless'
import { z } from 'zod'

export const ESTADOS = ['Listo', 'En uso', 'Por verificar', 'Sin identificar', 'Prestado', 'Dañado'] as const

/** Campos que se pueden escribir. Todo es opcional al editar; `nombre` es obligatorio al crear. */
export const CamposItem = z.object({
  nombre: z.string().trim().min(1).max(300),
  cantidad: z.number().int().min(0).nullable(),
  categoria: z.string().trim().min(1).max(80),
  origen: z.string().trim().max(120).nullable(),
  estado: z.string().trim().min(1).max(40),
  uso_bicho: z.string().trim().max(1000).nullable(),
  ubicacion: z.string().trim().max(200).nullable(),
  notas: z.string().trim().max(4000).nullable(),
})
export const NuevoItem = CamposItem.partial().required({ nombre: true })
export const CambiosItem = CamposItem.partial()
export type Campos = z.infer<typeof CamposItem>

export type Item = Campos & {
  id: number
  uso_lampara: string | null
  fuente: string | null
  creado: string
  actualizado: string
  actualizado_por: string | null
}

export type Cambio = {
  id: number
  item_id: number | null
  accion: 'crear' | 'editar' | 'borrar'
  antes: Partial<Item> | null
  despues: Partial<Item> | null
  autor: string | null
  fecha: string
}

const COLS = 'id, nombre, cantidad, categoria, origen, estado, uso_bicho, ubicacion, notas, uso_lampara, fuente, creado, actualizado, actualizado_por'

let _sql: ReturnType<typeof neon> | null = null
function db() {
  const url = process.env.DATABASE_URL
  if (!url) throw new ErrorHttp(503, 'El servidor no tiene DATABASE_URL configurada.')
  return (_sql ??= neon(url))
}

export class ErrorHttp extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

/** Texto vacío → null, para que "" no quede guardado como valor. */
function limpiar<T extends Record<string, unknown>>(o: T): T {
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(o)) out[k] = typeof v === 'string' && v.trim() === '' && k !== 'nombre' ? null : v
  return out as T
}

export async function listar(opts: { q?: string; categoria?: string; estado?: string; origen?: string } = {}): Promise<Item[]> {
  const sql = db()
  const q = opts.q?.trim() ? `%${opts.q.trim()}%` : null
  const rows = await sql.query(
    `select ${COLS} from items
     where ($1::text is null or unaccent(concat_ws(' ', nombre, categoria, origen, estado, uso_bicho, ubicacion, notas, uso_lampara)) ilike unaccent($1))
       and ($2::text is null or categoria ilike $2)
       and ($3::text is null or estado ilike $3)
       and ($4::text is null or origen ilike $4)
     order by categoria, nombre, id`,
    [q, opts.categoria?.trim() || null, opts.estado?.trim() || null, opts.origen?.trim() ? `%${opts.origen.trim()}%` : null],
  )
  return rows as Item[]
}

export async function obtener(id: number): Promise<Item | null> {
  const rows = (await db().query(`select ${COLS} from items where id = $1`, [id])) as Item[]
  return rows[0] ?? null
}

export async function crear(datos: unknown[], autor: string): Promise<Item[]> {
  const sql = db()
  const items = datos.map((d, i) => {
    const r = NuevoItem.safeParse(d)
    if (!r.success) throw new ErrorHttp(400, `Ítem ${i + 1}: ${r.error.issues.map((x) => `${x.path.join('.') || 'ítem'}: ${x.message}`).join('; ')}`)
    return limpiar(r.data)
  })
  const creados: Item[] = []
  for (const it of items) {
    const rows = (await sql.query(
      `insert into items (nombre, cantidad, categoria, origen, estado, uso_bicho, ubicacion, notas, actualizado_por)
       values ($1, $2, coalesce($3, 'Otros'), $4, coalesce($5, 'Listo'), $6, $7, $8, $9)
       returning ${COLS}`,
      [it.nombre, it.cantidad ?? null, it.categoria ?? null, it.origen ?? null, it.estado ?? null, it.uso_bicho ?? null, it.ubicacion ?? null, it.notas ?? null, autor],
    )) as Item[]
    const row = rows[0]
    await sql.query(`insert into cambios (item_id, accion, despues, autor) values ($1, 'crear', $2::jsonb, $3)`, [row.id, JSON.stringify(row), autor])
    creados.push(row)
  }
  return creados
}

const EDITABLES = ['nombre', 'cantidad', 'categoria', 'origen', 'estado', 'uso_bicho', 'ubicacion', 'notas'] as const

export async function editar(id: number, cambios: unknown, autor: string): Promise<Item> {
  const r = CambiosItem.safeParse(cambios)
  if (!r.success) throw new ErrorHttp(400, r.error.issues.map((x) => `${x.path.join('.')}: ${x.message}`).join('; '))
  const c = limpiar(r.data) as Partial<Campos>
  const keys = EDITABLES.filter((k) => k in c)
  if (!keys.length) throw new ErrorHttp(400, `No hay campos para cambiar. Campos válidos: ${EDITABLES.join(', ')}.`)
  const antes = await obtener(id)
  if (!antes) throw new ErrorHttp(404, `No existe el ítem ${id}.`)
  const sets = keys.map((k, i) => `${k} = $${i + 2}`).join(', ')
  const vals = keys.map((k) => c[k] ?? null)
  const sql = db()
  const rows = (await sql.query(
    `update items set ${sets}, actualizado = now(), actualizado_por = $${keys.length + 2} where id = $1 returning ${COLS}`,
    [id, ...vals, autor],
  )) as Item[]
  const despues = rows[0]
  const diffAntes: Record<string, unknown> = {}
  const diffDespues: Record<string, unknown> = {}
  for (const k of keys) {
    if (antes[k] !== despues[k]) {
      diffAntes[k] = antes[k]
      diffDespues[k] = despues[k]
    }
  }
  if (Object.keys(diffDespues).length) {
    await sql.query(`insert into cambios (item_id, accion, antes, despues, autor) values ($1, 'editar', $2::jsonb, $3::jsonb, $4)`, [
      id,
      JSON.stringify({ nombre: antes.nombre, ...diffAntes }),
      JSON.stringify({ nombre: despues.nombre, ...diffDespues }),
      autor,
    ])
  }
  return despues
}

export async function borrar(id: number, autor: string): Promise<Item> {
  const sql = db()
  const rows = (await sql.query(`delete from items where id = $1 returning ${COLS}`, [id])) as Item[]
  if (!rows[0]) throw new ErrorHttp(404, `No existe el ítem ${id}.`)
  await sql.query(`insert into cambios (item_id, accion, antes, autor) values ($1, 'borrar', $2::jsonb, $3)`, [id, JSON.stringify(rows[0]), autor])
  return rows[0]
}

export async function historial(limite = 50, itemId?: number): Promise<Cambio[]> {
  const n = Math.min(Math.max(Math.trunc(limite) || 50, 1), 500)
  return (await db().query(
    `select id, item_id, accion, antes, despues, autor, fecha from cambios
     where ($2::int is null or item_id = $2) order by fecha desc, id desc limit $1`,
    [n, itemId ?? null],
  )) as Cambio[]
}
