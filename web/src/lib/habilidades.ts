// Habilidades del bicho: qué sabe hacer, quién se lo enseñó y cuándo.
//
// Se arman juntando tres fuentes:
//  1. bicho/habilidades.json: la lista que mantiene el equipo (lo que le programó y lo que ya aprendió).
//  2. Lo que aprende en vivo: los eventos del cerebro ({"t":"cerebro","tipo":"paso"|"aprendido"|...}) que reparte
//     el relé. Cada aprendizaje se guarda en este navegador, para no perderlo al recargar.
//  3. Su propia copia de habilidades.json, que llega con {"t":"fuente"} (su código) cuando su cerebro la escribe.
// Con el código que corre (fuente) además se cuenta cuánto escribió él y cuánto el equipo.
import catalogo from '../../../bicho/habilidades.json'
import type { Evento } from '../components/Cerebro'
import { cmpSemver, type Release } from './firmware'

export type Origen = 'equipo' | 'solo'
export type Canal = 'oido' | 'web' | 'app'

export type Habilidad = {
  id: string
  icono: string
  nombre: string
  que_hace?: string
  pidele?: string
  comandos: string[]
  origen: Origen
  version?: string
  /** Cuándo la tuvo (ms). */
  cuando?: number
  /** `cuando` es "a más tardar": no quedó registro de la hora exacta. */
  aprox?: boolean
  /** Cuándo se la pidieron (ms), si la aprendió solo. */
  inicio?: number
  pedido?: string
  canal?: Canal
  /** Archivos que escribió y cuántas líneas quedaron en cada uno. */
  archivos: Record<string, number>
  intentos?: number
  pruebas: string[]
  resumen?: string
  /** La tiene ahora, según la versión que corre el bicho (false: volvió a una versión anterior). */
  presente: boolean
}

type EntradaCatalogo = {
  id?: string
  icono?: string
  nombre?: string
  que_hace?: string
  pidele?: string
  comandos?: string[]
  origen?: string
  version?: string
  cuando?: string
  a_mas_tardar?: string
  inicio?: string
  pedido?: string
  canal?: string
  archivos?: Record<string, number>
  intentos?: number
}

/* ------------------------------------------------------------------ */
/* Aprendizajes: lo que se ve en los eventos del cerebro                */
/* ------------------------------------------------------------------ */

export type Aprendizaje = {
  trabajo: string
  estado: 'aprendiendo' | 'aprendido' | 'fallo'
  que?: string
  pedido?: string
  canal?: Canal
  inicio?: number
  fin?: number
  /** Último evento que se vio de este aprendizaje. */
  ultimo: number
  version?: string
  notas?: string
  intentos: number
  rechazos: number
  vueltas: number
  archivos: Record<string, number>
  pruebas: string[]
  hardware?: string
  resumen?: string
  /** Los últimos pasos, para mostrar en vivo lo que está haciendo. */
  pasos: { ts: number; texto: string }[]
  /** Lo que manda el cerebro nuevo al terminar: nombre corto, cómo pedírsela y sus comandos. */
  habilidad?: { nombre?: string; pidele?: string; comandos?: string[] }
}

const CLAVE_LS = 'bicho.aprendizajes'
// Si un aprendizaje no da señales en 10 minutos, se cortó (el cerebro se reinició o se cayó).
const SE_CORTO_MS = 10 * 60_000

export function cargarAprendizajes(): Record<string, Aprendizaje> {
  try {
    const x = JSON.parse(localStorage.getItem(CLAVE_LS) || '{}')
    return x && typeof x === 'object' ? x : {}
  } catch {
    return {}
  }
}

export function guardarAprendizajes(m: Record<string, Aprendizaje>) {
  try {
    const lista = Object.values(m)
      .sort((a, b) => b.ultimo - a.ultimo)
      .slice(0, 60)
    localStorage.setItem(CLAVE_LS, JSON.stringify(Object.fromEntries(lista.map((a) => [a.trabajo, { ...a, pasos: a.estado === 'aprendiendo' ? a.pasos : [] }]))))
  } catch {
    /* sin localStorage: solo se ve lo de esta sesión */
  }
}

const nuevo = (trabajo: string, ts: number): Aprendizaje => ({
  trabajo,
  estado: 'aprendiendo',
  ultimo: ts,
  intentos: 0,
  rechazos: 0,
  vueltas: 0,
  archivos: {},
  pruebas: [],
  pasos: [],
})

/** Arma los aprendizajes que se ven en esta ventana de eventos (los del relé más los que llegan en vivo). */
export function derivar(eventos: Evento[]): Record<string, Aprendizaje> {
  const out: Record<string, Aprendizaje> = {}
  const dichos = new Map<string, Evento>() // lo que se le escribió, por id: de ahí sale el canal
  let pedido: Evento | null = null // el último "aprende": el "Empiezo a aprender" que sigue es el mismo

  for (const e of eventos) {
    const ts = e.ts ?? 0
    if (e.tipo === 'decir') {
      dichos.set(e.id, e)
      continue
    }
    if (e.tipo === 'aprende') {
      pedido = e
      continue
    }
    if (!e.trabajo) continue
    const a = (out[e.trabajo] ??= nuevo(e.trabajo, ts))
    a.ultimo = Math.max(a.ultimo, ts)
    const t = e.texto ?? ''

    if (e.tipo === 'paso') {
      a.pasos = [...a.pasos, { ts, texto: t }].slice(-8)
      let m: RegExpMatchArray | null
      if ((m = t.match(/^Empiezo a aprender: ([\s\S]+)$/))) {
        a.que = m[1].trim()
        a.inicio = ts
        if (pedido && Math.abs((pedido.ts ?? 0) - ts) < 15_000) {
          a.inicio = Math.min(ts, pedido.ts ?? ts)
          a.pedido = pedido.oido
          const dicho = pedido.frase ? dichos.get(pedido.frase) : undefined
          a.canal = typeof pedido.angulo === 'number' ? 'oido' : dicho?.canal === 'app' ? 'app' : 'web'
          pedido = null
        }
      } else if ((m = t.match(/^Escribo (\S+) \((\d+) líneas?\)/))) a.archivos = { ...a.archivos, [m[1]]: Number(m[2]) }
      else if ((m = t.match(/^Instalo la versión (\S+?):\s*([\s\S]*)$/))) {
        a.intentos++
        a.version = m[1]
        if (m[2].trim()) a.notas = m[2].trim()
      } else if (/^El Pi rechazó la versión/.test(t)) a.rechazos++
      else if (/no se reportó: el bicho volvió/.test(t)) a.vueltas++
      else if ((m = t.match(/^Pruebo (\{[\s\S]*\})$/))) a.pruebas = [...a.pruebas, m[1]].slice(-20)
      else if ((m = t.match(/^Encontré: ([\s\S]+)$/))) a.hardware = m[1].trim()
    } else if (e.tipo === 'aprendido') {
      a.estado = 'aprendido'
      a.fin = ts
      a.resumen = t
      if (e.version) a.version = e.version
      if (e.habilidad) a.habilidad = e.habilidad
    } else if (e.tipo === 'error') {
      a.estado = 'fallo'
      a.fin = ts
      a.resumen = t
    }
  }
  return out
}

/** Junta lo guardado con lo nuevo. La ventana del relé puede venir cortada: nunca se pierde lo que ya se sabía. */
export function juntar(previos: Record<string, Aprendizaje>, nuevos: Record<string, Aprendizaje>) {
  const out = { ...previos }
  let cambio = false
  for (const [k, n] of Object.entries(nuevos)) {
    const p = previos[k]
    const m: Aprendizaje = p
      ? {
          ...p,
          ...Object.fromEntries(Object.entries(n).filter(([, v]) => v !== undefined)),
          estado: p.estado !== 'aprendiendo' ? p.estado : n.estado,
          inicio: Math.min(p.inicio ?? Infinity, n.inicio ?? Infinity) === Infinity ? undefined : Math.min(p.inicio ?? Infinity, n.inicio ?? Infinity),
          ultimo: Math.max(p.ultimo, n.ultimo),
          intentos: Math.max(p.intentos, n.intentos),
          rechazos: Math.max(p.rechazos, n.rechazos),
          vueltas: Math.max(p.vueltas, n.vueltas),
          archivos: { ...p.archivos, ...n.archivos },
          pruebas: n.pruebas.length >= p.pruebas.length ? n.pruebas : p.pruebas,
          pasos: n.pasos.length >= p.pasos.length ? n.pasos : p.pasos,
          que: n.que ?? p.que,
          pedido: n.pedido ?? p.pedido,
          canal: n.canal ?? p.canal,
        }
      : n
    if (!p || JSON.stringify(p) !== JSON.stringify(m)) {
      out[k] = m
      cambio = true
    }
  }
  return cambio ? out : previos
}

/** El aprendizaje que está corriendo ahora, si hay uno (y no se cortó). */
export function enCurso(lista: Aprendizaje[], ahora = Date.now()) {
  return lista.find((a) => a.estado === 'aprendiendo' && ahora - a.ultimo < SE_CORTO_MS) ?? null
}

/* ------------------------------------------------------------------ */
/* Habilidades: catálogo + lo que aprendió                              */
/* ------------------------------------------------------------------ */

const ms = (iso?: string) => {
  const t = iso ? Date.parse(iso) : NaN
  return Number.isFinite(t) ? t : undefined
}

/** Nombre corto a partir de las notas del cerebro, si no mandó uno. */
export function nombreCorto(texto?: string) {
  let s = (texto ?? '').trim()
  s = s.replace(/^(aprendió|aprendi|aprende|aprender|ahora sabe|sabe)\s+(a\s+)?/i, '')
  s = s.replace(/^(agrega|agregar|añade|añadir|suma|sumar|incorpora)\s+(el\s+|la\s+)?(soporte|manejo|lectura)\s+(para|de|del|a)\s+/i, '')
  s = s.replace(/^(agrega|agregar|añade|añadir)\s+/i, '')
  s = s.split(/\s*[(:;]|,\s|\.\s|\s[—–-]\s/)[0].replace(/\.$/, '').trim()
  if (s.length > 58) s = `${s.slice(0, 56).replace(/\s+\S*$/, '')}…`
  return s ? s[0].toUpperCase() + s.slice(1) : 'Algo nuevo'
}

const ICONOS: [RegExp, string][] = [
  [/c[aá]mara|foto|ve[rs]?\b|imagen|vista/i, '📷'],
  [/habla|voz|parlante|sonido|audio|aplay/i, '🔊'],
  [/luz|luces|led|verde|rojo|color/i, '💡'],
  [/motor|rueda|mover|avanz|gira|anda/i, '🛞'],
  [/servo|brazo|pinza/i, '🦾'],
  [/flujo|movimiento|desplaz/i, '🧭'],
  [/distancia|ultrason|l[aá]ser|lidar|tof/i, '📏'],
  [/temperatura|humedad|clima/i, '🌡️'],
  [/bot[oó]n|toque|tacto/i, '🔘'],
]
const iconoPara = (t: string) => ICONOS.find(([re]) => re.test(t))?.[1] ?? '✨'

/** Los comandos que probó, sin los de siempre. */
const comandosDe = (pruebas: string[]) =>
  [
    ...new Set(
      pruebas
        .map((p) => {
          try {
            return String(JSON.parse(p).cmd ?? '')
          } catch {
            return ''
          }
        })
        .filter((c) => c && !['hola', 'info', 'rate', 'reboot'].includes(c)),
    ),
  ]

function desdeCatalogo(e: EntradaCatalogo, releases: Release[]): Habilidad | null {
  if (!e.nombre) return null
  const rel = e.version ? releases.find((r) => r.version === e.version) : undefined
  const exacta = ms(e.cuando) ?? (e.origen !== 'solo' ? ms(rel?.date) : undefined)
  const aprox = exacta === undefined ? ms(e.a_mas_tardar) : undefined
  return {
    id: e.id ?? e.version ?? e.nombre,
    icono: e.icono ?? iconoPara(`${e.nombre} ${e.que_hace ?? ''}`),
    nombre: e.nombre,
    que_hace: e.que_hace,
    pidele: e.pidele,
    comandos: e.comandos ?? [],
    origen: e.origen === 'solo' ? 'solo' : 'equipo',
    version: e.version,
    cuando: exacta ?? aprox ?? ms(rel?.date),
    aprox: aprox !== undefined,
    inicio: ms(e.inicio),
    pedido: e.pedido,
    canal: e.canal === 'oido' || e.canal === 'app' || e.canal === 'web' ? e.canal : undefined,
    archivos: e.archivos ?? {},
    intentos: e.intentos,
    pruebas: [],
    presente: true,
  }
}

export function armarHabilidades({
  aprendizajes,
  releases,
  fw,
  delBicho,
}: {
  aprendizajes: Aprendizaje[]
  releases: Release[]
  /** Versión que corre el bicho ahora (null si no se sabe). */
  fw: string | null
  /** Su propia lista (habilidades.json en su código), si la tiene. */
  delBicho?: EntradaCatalogo[]
}): Habilidad[] {
  const lista: Habilidad[] = []
  const porVersion = new Map<string, Habilidad>()
  const agregar = (h: Habilidad | null) => {
    if (!h) return
    const ya = (h.version && h.origen === 'solo' && porVersion.get(h.version)) || lista.find((x) => x.id === h.id)
    if (ya) {
      // Lo curado por el equipo manda en el nombre; los datos del proceso se completan.
      for (const [k, v] of Object.entries(h) as [keyof Habilidad, unknown][]) {
        if (v === undefined || (Array.isArray(v) && !v.length) || (typeof v === 'object' && v && !Array.isArray(v) && !Object.keys(v).length)) continue
        if ((ya as Record<string, unknown>)[k] === undefined || (Array.isArray(ya[k]) && !(ya[k] as unknown[]).length) || (k === 'archivos' && !Object.keys(ya.archivos).length))
          (ya as Record<string, unknown>)[k] = v
      }
      return
    }
    lista.push(h)
    if (h.version && h.origen === 'solo') porVersion.set(h.version, h)
  }

  for (const e of (catalogo as { habilidades: EntradaCatalogo[] }).habilidades) agregar(desdeCatalogo(e, releases))
  for (const e of delBicho ?? []) agregar(desdeCatalogo({ ...e, origen: e.origen ?? 'solo' }, releases))

  for (const a of aprendizajes) {
    if (a.estado !== 'aprendido' || !a.version) continue
    const texto = `${a.habilidad?.nombre ?? ''} ${a.notas ?? ''} ${a.que ?? ''}`
    const ya = porVersion.get(a.version)
    const h: Habilidad = {
      id: ya?.id ?? `v${a.version}`,
      icono: iconoPara(texto),
      nombre: a.habilidad?.nombre || nombreCorto(a.notas ?? a.que),
      que_hace: a.notas ?? a.que,
      pidele: a.habilidad?.pidele,
      comandos: a.habilidad?.comandos?.length ? a.habilidad.comandos : comandosDe(a.pruebas),
      origen: 'solo',
      version: a.version,
      cuando: a.fin,
      aprox: false,
      inicio: a.inicio,
      pedido: a.pedido,
      canal: a.canal,
      archivos: a.archivos,
      intentos: a.intentos,
      pruebas: a.pruebas,
      resumen: a.resumen,
      presente: true,
    }
    if (ya) {
      // Los datos vistos en vivo son más exactos que lo anotado a mano (salvo el nombre y cómo pedírsela).
      Object.assign(ya, {
        cuando: h.cuando ?? ya.cuando,
        aprox: h.cuando ? false : ya.aprox,
        inicio: h.inicio ?? ya.inicio,
        pedido: h.pedido ?? ya.pedido,
        canal: h.canal ?? ya.canal,
        archivos: Object.keys(h.archivos).length ? h.archivos : ya.archivos,
        intentos: h.intentos || ya.intentos,
        pruebas: h.pruebas.length ? h.pruebas : ya.pruebas,
        resumen: h.resumen ?? ya.resumen,
      })
    } else agregar(h)
  }

  // ¿La tiene ahora? Si el bicho volvió a una versión anterior, lo aprendido después se le borró.
  const ultimaDelEquipo = releases[0]?.version
  if (fw)
    for (const h of lista) {
      if (h.version) h.presente = cmpSemver(fw, h.version) >= 0
      else if (h.origen === 'solo') h.presente = ultimaDelEquipo ? cmpSemver(fw, ultimaDelEquipo) > 0 : true
    }
  return lista
}

/* ------------------------------------------------------------------ */
/* Quién escribió su código                                             */
/* ------------------------------------------------------------------ */

// El código del equipo, tal como está en el repo (se carga solo cuando hace falta).
const BASE = import.meta.glob('../../../bicho/*.py', { query: '?raw', import: 'default' }) as Record<string, () => Promise<string>>
let base: Promise<Record<string, string>> | null = null
function codigoDelEquipo() {
  base ??= Promise.all(Object.entries(BASE).map(async ([ruta, cargar]) => [ruta.split('/').pop()!, await cargar()] as const)).then(Object.fromEntries)
  return base
}

export type Autoria = { equipo: number; solo: number; archivos: { nombre: string; equipo: number; solo: number }[] }

const lineas = (s: string) =>
  s
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith('#'))

/**
 * Cuántas líneas de Python escribió él y cuántas el equipo. Una línea es del equipo si está en la versión del
 * repo de ese archivo; las demás las escribió el bicho (los archivos que no existen en el repo, enteros).
 */
export async function autoria(archivos: Record<string, string>): Promise<Autoria> {
  const repo = await codigoDelEquipo()
  const out: Autoria = { equipo: 0, solo: 0, archivos: [] }
  for (const [nombre, texto] of Object.entries(archivos)) {
    if (!nombre.endsWith('.py')) continue
    const quedan = new Map<string, number>()
    for (const l of lineas(repo[nombre] ?? '')) quedan.set(l, (quedan.get(l) ?? 0) + 1)
    let equipo = 0
    let solo = 0
    for (const l of lineas(texto)) {
      const n = quedan.get(l) ?? 0
      if (n > 0) {
        equipo++
        quedan.set(l, n - 1)
      } else solo++
    }
    out.equipo += equipo
    out.solo += solo
    out.archivos.push({ nombre, equipo, solo })
  }
  out.archivos.sort((a, b) => b.solo - a.solo)
  return out
}

/** Su propia lista de habilidades, si su código la trae. */
export function habilidadesDelBicho(archivos?: Record<string, string> | null): EntradaCatalogo[] | undefined {
  try {
    const x = JSON.parse(archivos?.['habilidades.json'] ?? '')
    return Array.isArray(x?.habilidades) ? x.habilidades : undefined
  } catch {
    return undefined
  }
}

/* ------------------------------------------------------------------ */
/* Formato                                                              */
/* ------------------------------------------------------------------ */

export const hora = (t?: number) => (t ? new Date(t).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }) : '')

export function hace(t?: number, ahora = Date.now()) {
  if (!t) return ''
  const s = Math.max(0, (ahora - t) / 1000)
  if (s < 45) return 'recién'
  if (s < 3600) return `hace ${Math.round(s / 60)} min`
  const h = Math.floor(s / 3600)
  const m = Math.round((s % 3600) / 60)
  return m && h < 6 ? `hace ${h} h ${m} min` : `hace ${h} h`
}

export function duracion(msTotal?: number) {
  if (msTotal == null || !Number.isFinite(msTotal) || msTotal < 0) return ''
  const s = Math.round(msTotal / 1000)
  if (s < 60) return `${s} s`
  const m = Math.floor(s / 60)
  return s % 60 ? `${m} min ${s % 60} s` : `${m} min`
}

export const CANAL: Record<Canal, string> = { oido: 'se lo dijeron en voz alta', web: 'se lo escribieron en bicho·dev', app: 'se lo dijeron desde la app' }
