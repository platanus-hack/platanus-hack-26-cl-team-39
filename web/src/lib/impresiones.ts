// Piezas del bicho en las impresoras 3D: cuánto les falta y cuándo terminan.
import data from './impresiones.json'

export type Impresion = {
  pieza: string
  impresora: string
  inicio: Date
  fin: Date
  /** La hora de inicio es una suposición: se muestra con ≈. */
  aprox: boolean
}

type Fila = { pieza: string; impresora: string; inicio: string; minutos: number; aprox?: boolean }

export const IMPRESIONES: Impresion[] = (data.impresiones as Fila[])
  .map((i) => {
    const inicio = new Date(i.inicio)
    return { pieza: i.pieza, impresora: i.impresora, inicio, fin: new Date(inicio.getTime() + i.minutos * 60_000), aprox: !!i.aprox }
  })
  .sort((a, b) => a.fin.getTime() - b.fin.getTime())

/** Avance de 0 a 1 y si ya terminó. */
export function avance(i: Impresion, now: number) {
  const total = i.fin.getTime() - i.inicio.getTime()
  const p = Math.min(1, Math.max(0, (now - i.inicio.getTime()) / total))
  return { p, lista: now >= i.fin.getTime() }
}

/** "4:12:05" que falta, en horas, minutos y segundos. */
export function restante(i: Impresion, now: number) {
  const s = Math.max(0, Math.floor((i.fin.getTime() - now) / 1000))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${h}:${pad(m)}:${pad(s % 60)}`
}
