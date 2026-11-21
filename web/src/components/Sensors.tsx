import { useEffect, useState, type CSSProperties } from 'react'
import type { SensorStore, Series } from '../lib/sensors'
import { Icon, Sparkline } from './ui'

/** Nombres y unidades para las claves conocidas. Las demás se muestran tal cual llegan del firmware. */
const KNOWN: Record<string, [string, string]> = {
  mic: ['Micrófono', ''],
  'imu.pitch': ['Inclinación', '°'],
  'imu.roll': ['Giro', '°'],
  dist_cm: ['Distancia', 'cm'],
  'servo[0]': ['Servo 1', '°'],
  'servo[1]': ['Servo 2', '°'],
  'servo[2]': ['Servo 3', '°'],
  temp_c: ['Temperatura', '°C'],
  temp_cpu: ['Temp. CPU', '°C'],
  carga: ['Carga CPU', ''],
  wifi_dbm: ['Señal WiFi', 'dBm'],
  boton: ['Botón', ''],
  'imu.ax': ['Acel. X', 'g'],
  'imu.ay': ['Acel. Y', 'g'],
  'imu.az': ['Acel. Z', 'g'],
}

function fmt(v: unknown) {
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return v.toString()
    const a = Math.abs(v)
    return v.toFixed(a >= 100 ? 1 : a >= 1 ? 2 : 3)
  }
  if (typeof v === 'boolean') return v ? 'ON' : 'OFF'
  if (v === null || v === undefined) return '—'
  return String(v)
}

function Tile({ s, stale, wide, onToggle }: { s: Series; stale: boolean; wide: boolean; onToggle: () => void }) {
  const [label, unit] = KNOWN[s.key] ?? [s.key, '']
  const isBool = typeof s.last === 'boolean'
  const isNum = typeof s.last === 'number' || isBool
  const n = typeof s.last === 'boolean' ? (s.last ? 1 : 0) : typeof s.last === 'number' ? s.last : NaN
  const span = s.max - s.min
  const v = isBool ? n : Number.isFinite(n) && span > 0 ? (n - s.min) / span : 0
  const avg = isNum && !isBool && s.hist.length ? s.hist.reduce((a, b) => a + b, 0) / s.hist.length : NaN
  return (
    <article
      className={`sensor ${stale ? 'stale' : ''} ${wide ? 'wide' : ''}`}
      data-on={s.last === true ? '' : undefined}
      style={{ '--v': v } as CSSProperties}
      role="button"
      tabIndex={0}
      aria-expanded={wide}
      title={wide ? 'Clic para achicar' : 'Clic para ampliar'}
      onClick={onToggle}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onToggle())}
    >
      <div className="s-top">
        <span className="s-label" title={s.key}>
          {label}
        </span>
        {label !== s.key && <span className="s-key">{s.key}</span>}
      </div>
      <div className="s-read">
        <b>{fmt(s.last)}</b>
        {unit && <i>{unit}</i>}
        {wide && Number.isFinite(avg) && (
          <span className="s-avg">
            promedio <b>{fmt(+avg.toFixed(3))}</b>
          </span>
        )}
      </div>
      <div className="chart">{isNum ? <Sparkline data={s.hist} stepped={isBool} /> : <svg viewBox="0 0 120 36" aria-hidden />}</div>
      <div className="s-foot">
        <small>{isNum && !isBool && s.hist.length ? fmt(s.min) : '—'}</small>
        <span className="meter">
          <span />
        </span>
        <small>{isNum && !isBool && s.hist.length ? fmt(s.max) : '—'}</small>
      </div>
    </article>
  )
}

export function Sensors({ store, connected, onRate }: { store: SensorStore; connected: boolean; onRate: (hz: number) => void }) {
  const [, setTick] = useState(0)
  const [paused, setPaused] = useState(false)
  const [wide, setWide] = useState<string | null>(null)

  useEffect(() => {
    if (paused) return
    const iv = setInterval(() => setTick((t) => t + 1), 100)
    return () => clearInterval(iv)
  }, [paused])

  const now = performance.now()
  const list = [...store.series.values()]
  const live = connected && now - store.lastAt < 1500

  return (
    <section className="sec" id="sensores" aria-label="Sensores">
      <article className="card glass sensors">
        <header className="card-head">
          <div>
            <h2>Sensores</h2>
            <p>Lecturas en tiempo real del bicho · clic en uno para ampliarlo</p>
          </div>
          <div className="head-actions">
            <span className={`live ${live ? '' : 'idle'}`}>
              <i className="live-dot" aria-hidden />
              {live ? store.hz.toFixed(1) : '0.0'} Hz <span className="sep">·</span> {store.frames.toLocaleString('es-CL')} lecturas
            </span>
            <select
              className="btn-secondary"
              defaultValue=""
              disabled={!connected}
              onChange={(e) => onRate(Number(e.target.value))}
              title="Pedirle al bicho otra frecuencia de envío"
              aria-label="Frecuencia de envío"
            >
              <option value="" disabled>
                Frecuencia
              </option>
              {[1, 5, 10, 20, 50].map((h) => (
                <option key={h} value={h}>
                  {h} Hz
                </option>
              ))}
            </select>
            <button type="button" className="btn-secondary" onClick={() => setPaused((p) => !p)}>
              {paused ? <Icon.Play /> : <Icon.Pause />}
              {paused ? 'Seguir' : 'Pausar'}
            </button>
          </div>
        </header>

        {list.length === 0 ? (
          <div className="empty">
            <p className="empty-t">{connected ? 'Esperando lecturas…' : 'Sin lecturas'}</p>
            <p className="empty-s">
              {connected ? (
                <>
                  El firmware tiene que mandar <code>{'{"t":"s","d":{…}}'}</code>. Cada campo nuevo aparece solo.
                </>
              ) : (
                'Conecta el bicho por WiFi o abre el simulador.'
              )}
            </p>
          </div>
        ) : (
          <div className="sensor-grid">
            {list.map((s) => (
              <Tile key={s.key} s={s} stale={now - s.updatedAt > 2000} wide={wide === s.key} onToggle={() => setWide((w) => (w === s.key ? null : s.key))} />
            ))}
          </div>
        )}
      </article>
    </section>
  )
}
