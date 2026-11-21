import { flatten, type Scalar } from './protocol'

export const HISTORY = 240

export type Series = {
  key: string
  last: Scalar
  hist: number[]
  min: number
  max: number
  updatedAt: number
}

/** Guarda el historial de cada sensor fuera de React; la UI lo lee a ~10 fps. */
export class SensorStore {
  series = new Map<string, Series>()
  frames = 0
  private stamps: number[] = []

  push(d: Record<string, unknown>) {
    const now = performance.now()
    this.frames++
    this.stamps.push(now)
    while (this.stamps.length && now - this.stamps[0] > 2000) this.stamps.shift()
    for (const [key, v] of Object.entries(flatten(d))) {
      let s = this.series.get(key)
      if (!s) {
        s = { key, last: v, hist: [], min: Infinity, max: -Infinity, updatedAt: now }
        this.series.set(key, s)
      }
      s.last = v
      s.updatedAt = now
      const n = typeof v === 'boolean' ? (v ? 1 : 0) : typeof v === 'number' ? v : NaN
      if (Number.isFinite(n)) {
        s.hist.push(n)
        if (s.hist.length > HISTORY) s.hist.shift()
        if (n < s.min) s.min = n
        if (n > s.max) s.max = n
      }
    }
  }

  /** Frames por segundo de los últimos 2 s. */
  get hz() {
    if (this.stamps.length < 2) return 0
    const span = this.stamps[this.stamps.length - 1] - this.stamps[0]
    return span > 0 ? ((this.stamps.length - 1) * 1000) / span : 0
  }

  get lastAt() {
    return this.stamps[this.stamps.length - 1] ?? 0
  }

  resetMinMax() {
    for (const s of this.series.values()) {
      s.min = Math.min(...s.hist)
      s.max = Math.max(...s.hist)
    }
  }

  clear() {
    this.series.clear()
    this.frames = 0
    this.stamps = []
  }
}
