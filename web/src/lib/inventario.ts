// Cliente de la API del inventario (/api/inventario, /api/historial, /api/preguntar).
export type Item = {
  id: number
  nombre: string
  cantidad: number | null
  categoria: string
  origen: string | null
  estado: string
  uso_bicho: string | null
  ubicacion: string | null
  notas: string | null
  uso_lampara: string | null
  fuente: string | null
  creado: string
  actualizado: string
  actualizado_por: string | null
}

export type Cambio = {
  id: number | string
  item_id: number | null
  accion: 'crear' | 'editar' | 'borrar'
  antes: Partial<Item> | null
  despues: Partial<Item> | null
  autor: string | null
  fecha: string
}

export type Campos = Pick<Item, 'nombre' | 'cantidad' | 'categoria' | 'origen' | 'estado' | 'uso_bicho' | 'ubicacion' | 'notas'>

export const ESTADOS = ['Listo', 'En uso', 'Por verificar', 'Sin identificar', 'Prestado', 'Dañado']
export const EQUIPO = ['Guty', 'Carlos', 'Cristian', 'Renate', 'Walls']

const store = {
  get: (k: string) => {
    try {
      return localStorage.getItem(k) ?? ''
    } catch {
      return ''
    }
  },
  set: (k: string, v: string) => {
    try {
      if (v) localStorage.setItem(k, v)
      else localStorage.removeItem(k)
    } catch {
      /* sin storage: queda solo en memoria */
    }
  },
}
export const clave = { get: () => store.get('inventario.clave'), set: (v: string) => store.set('inventario.clave', v.trim()) }
export const autor = { get: () => store.get('inventario.autor'), set: (v: string) => store.set('inventario.autor', v.trim()) }

export class ErrorApi extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body) headers.set('content-type', 'application/json')
  const k = clave.get()
  if (k) headers.set('authorization', `Bearer ${k}`)
  const a = autor.get()
  if (a) headers.set('x-autor', encodeURIComponent(a))
  let res: Response
  try {
    res = await fetch(path, { ...init, headers })
  } catch {
    throw new ErrorApi(0, 'No hay conexión con la API del inventario.')
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new ErrorApi(res.status, (data as { error?: string }).error ?? `Error ${res.status}`)
  return data as T
}

export const inventario = {
  listar: () => api<{ items: Item[] }>('/api/inventario').then((r) => r.items),
  crear: (item: Partial<Campos>) => api<{ items: Item[] }>('/api/inventario', { method: 'POST', body: JSON.stringify({ item }) }).then((r) => r.items[0]),
  editar: (id: number, cambios: Partial<Campos>) => api<{ item: Item }>(`/api/inventario?id=${id}`, { method: 'PATCH', body: JSON.stringify(cambios) }).then((r) => r.item),
  borrar: (id: number) => api<{ item: Item }>(`/api/inventario?id=${id}`, { method: 'DELETE' }).then((r) => r.item),
  historial: (limite = 40, id?: number) => api<{ cambios: Cambio[] }>(`/api/historial?limite=${limite}${id ? `&id=${id}` : ''}`).then((r) => r.cambios),
  preguntar: (pregunta: string) => api<{ respuesta: string; ids: number[]; modelo: string }>('/api/preguntar', { method: 'POST', body: JSON.stringify({ pregunta }) }),
}

/** Para buscar sin importar tildes ni mayúsculas. */
export const plano = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
