/** Patrones del anillo de 24 LEDs. Devuelven colores RGB de 0 a 1 por LED. */
import type { Luz } from './lenguaje'

export const N_LEDS = 24
export type RGB = [number, number, number]

export function hex(c: string): RGB {
  const n = parseInt(c.replace('#', ''), 16)
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]
}

function hsl(h: number, s: number, l: number): RGB {
  const k = (n: number) => (n + h * 12) % 12
  const a = s * Math.min(l, 1 - l)
  const f = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))
  return [f(0), f(8), f(4)]
}

const CORRE: RGB[] = ['#ff2d55', '#ffcc00', '#34c759', '#5ac8fa'].map(hex)

/**
 * @param t segundos desde que empezó el estado
 * @param lado ángulo (rad) del lado que se enciende en el patrón "lado"; 0 = arriba, positivo = hacia la derecha
 */
export function anillo(luz: Luz, t: number, lado = 0): RGB[] {
  const c = hex(luz.color)
  const b = luz.brillo ?? 1
  const P = luz.periodo ?? 1
  const out: RGB[] = []
  for (let i = 0; i < N_LEDS; i++) {
    // ángulo del LED: 0 arriba, sentido horario visto de frente
    const ang = (i / N_LEDS) * Math.PI * 2
    let k = 0
    let col = c
    switch (luz.patron) {
      case 'fijo':
        k = b
        break
      case 'respira':
        k = b * (0.18 + 0.82 * (0.5 - 0.5 * Math.cos((2 * Math.PI * t) / P)))
        break
      case 'gira': {
        const cabeza = ((t / P) * N_LEDS) % N_LEDS
        const d = (cabeza - i + N_LEDS) % N_LEDS
        k = b * (d < 9 ? (1 - d / 9) ** 2 : 0.04)
        break
      }
      case 'parpadea':
        k = t % P < P / 2 ? b : 0.04
        break
      case 'destello':
        k = b * (0.3 + 0.7 * Math.exp(-t * 2.5))
        break
      case 'llena': {
        const p = (t % P) / P
        const x = p * N_LEDS
        k = b * (i < Math.floor(x) ? 1 : i === Math.floor(x) ? x % 1 : 0.05)
        break
      }
      case 'corre': {
        const paso = Math.floor((t / P) * N_LEDS)
        col = CORRE[Math.floor(((i + paso) % N_LEDS) / 3) % CORRE.length]
        k = b * ((i + paso) % 3 === 0 ? 1 : 0.35)
        break
      }
      case 'arcoiris':
        col = hsl((i / N_LEDS + t / P) % 1, 1, 0.5)
        k = b
        break
      case 'faro': {
        const haz = Math.cos(ang - (2 * Math.PI * t) / P)
        k = b * (0.06 + Math.max(0, haz) ** 10)
        break
      }
      case 'lado': {
        const d = Math.cos(ang - lado)
        k = b * (0.08 + Math.max(0, d) ** 3)
        break
      }
      case 'apagando':
        k = b * Math.max(0, 1 - t / P)
        break
      case 'sectores': {
        const s = Math.floor(i / 4)
        const r = Math.sin((s + 1) * 12.9898 + Math.floor(t / P) * 78.233) * 43758.5453
        k = b * (r - Math.floor(r) > 0.45 ? 1 : 0.05)
        break
      }
    }
    out.push([col[0] * k, col[1] * k, col[2] * k])
  }
  return out
}

/** Brillo promedio del anillo (0 a 1), para la luz que proyecta y la pantalla del pecho. */
export function brillo(leds: RGB[]) {
  let s = 0
  for (const [r, g, b] of leds) s += Math.max(r, g, b)
  return s / leds.length
}

export function promedio(leds: RGB[]): RGB {
  const s: RGB = [0, 0, 0]
  for (const l of leds) for (let j = 0; j < 3; j++) s[j] += l[j]
  return s.map((v) => v / leds.length) as RGB
}
