// Cronograma de Platanus Hack 26: qué está pasando, qué viene y cuándo es la próxima comida.
import data from './cronograma.json'

export type Evento = {
  inicio: Date
  fin: Date
  icono: string
  titulo: string
  tipo: 'comida' | 'actividad' | 'hito'
  para: string[]
  detalle?: string
}

export const EVENTOS: Evento[] = data.eventos
  .map((e) => ({ ...e, tipo: e.tipo as Evento['tipo'], inicio: new Date(e.inicio), fin: new Date(e.fin) }))
  .sort((a, b) => a.inicio.getTime() - b.inicio.getTime())

export function agenda(now: number) {
  const ahora = EVENTOS.filter((e) => e.inicio.getTime() <= now && now < e.fin.getTime())
  const proximo = EVENTOS.find((e) => e.inicio.getTime() > now) ?? null
  const comida = EVENTOS.find((e) => e.tipo === 'comida' && e.inicio.getTime() > now) ?? null
  return { ahora, proximo, comida }
}

const partes = (d: Date) =>
  Object.fromEntries(
    new Intl.DateTimeFormat('es-CL', { weekday: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hourCycle: 'h23', timeZone: 'America/Santiago' })
      .formatToParts(d)
      .map((x) => [x.type, x.value]),
  )

/** "8:30", o "dom 8:00" si no es hoy (hora de Santiago). */
export function hora(d: Date, now: number) {
  const p = partes(d)
  const hoy = partes(new Date(now))
  const hhmm = `${Number(p.hour)}:${p.minute}`
  return p.day === hoy.day ? hhmm : `${p.weekday.replace('.', '')} ${hhmm}`
}

/** "en 25 min", "en 4 h 5 min". */
export function falta(d: Date, now: number) {
  const min = Math.max(0, Math.round((d.getTime() - now) / 60_000))
  if (min < 1) return 'ya'
  if (min < 60) return `en ${min} min`
  const h = Math.floor(min / 60)
  const m = min % 60
  return m ? `en ${h} h ${m} min` : `en ${h} h`
}
