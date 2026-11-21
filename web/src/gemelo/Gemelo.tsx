import { useEffect, useMemo, useRef, useState } from 'react'
import type { SensorStore } from '../lib/sensors'
import type { Articulacion } from '../brazo/visor'
import { Gemelo3D, type Pieza, type Vivo } from './escena'
import './gemelo.css'

/* Vista «Gemelo»: el bicho completo en 3D (chasis impreso + brazo v4) con sus sensores en vivo encima.
   Todo en una pantalla, como la vista Brazo: visor a la izquierda, sensores y brazo a la derecha. */

type Imagen = { nombre: string; url: string; ts: number }

// Dónde vive cada sensor en el robot: la fila se ilumina en el gemelo al tocarla.
const SENSORES: { re: RegExp; nombre: string; unidad?: string; nodo: string }[] = [
  { re: /^temp_cpu$/, nombre: 'Temperatura de la Pi', unidad: '°C', nodo: 'G_pi' },
  { re: /^carga/, nombre: 'Carga de la CPU', nodo: 'G_pi' },
  { re: /^wifi/, nombre: 'Señal WiFi', unidad: 'dBm', nodo: 'G_pi' },
  { re: /^luz$/, nombre: 'Luz de prueba · GPIO 17', nodo: 'LED_luz' },
  { re: /^verde$/, nombre: 'Luz verde · GPIO 27', nodo: 'LED_verde' },
  { re: /^rojo$/, nombre: 'Luz roja · GPIO 22', nodo: 'LED_rojo' },
  { re: /^camara/, nombre: 'Cámara CSI ov5647', nodo: 'G_esp1' },
  { re: /^oido\.angulo/, nombre: 'Oído · ángulo de la voz', unidad: '°', nodo: 'G_parlante' },
  { re: /^oido/, nombre: 'Oído · ReSpeaker', nodo: 'G_parlante' },
  { re: /^flujo2/, nombre: 'Flujo óptico #2 · ADNS-3080', nodo: 'G_flujo2' },
  { re: /^flujo/, nombre: 'Flujo óptico #1 · ADNS-3080', nodo: 'G_flujo1' },
  { re: /^(imu|pitch|roll|mpu)/, nombre: 'Orientación · MPU-6050', unidad: '°', nodo: 'G_imu' },
  { re: /^(dist|tof|ultra)/, nombre: 'Distancia · parachoques', unidad: 'cm', nodo: 'G_parachoques' },
  { re: /^servo/, nombre: 'Servo del brazo', unidad: '°', nodo: 'G_brazo' },
  { re: /^(bat|volt)/, nombre: 'Batería · ADS1115', unidad: 'V', nodo: 'G_ads' },
]
const queEs = (k: string) => SENSORES.find((s) => s.re.test(k))

type Pose = { nombre: string; angulos?: Record<string, number>; secuencia?: Record<string, number>[] }
const POSES: Pose[] = [
  // en el brazo v4 el hombro va hacia adelante bajo 90° y el codo en 90° deja el eslabón 2 horizontal
  { nombre: 'Al frente', angulos: { J_giro: 90, J_hombro: 90, J_codo: 90, J_pinza_a: 84 } },
  { nombre: 'Mirar arriba', angulos: { J_giro: 90, J_hombro: 100, J_codo: 160 } },
  { nombre: 'Recoger del suelo', angulos: { J_giro: 90, J_hombro: 35, J_codo: 70, J_pinza_a: 108 } },
  { nombre: 'Plegado', angulos: { J_giro: 90, J_hombro: 112, J_codo: 55, J_pinza_a: 60 } },
  { nombre: 'Saludar', secuencia: [{ J_giro: 90, J_hombro: 100, J_codo: 160 }, { J_giro: 65 }, { J_giro: 115 }, { J_giro: 65 }, { J_giro: 115 }, { J_giro: 90 }] },
  { nombre: 'Escanear', secuencia: [{ J_hombro: 80, J_codo: 110 }, { J_giro: 15 }, { J_giro: 165 }, { J_giro: 90 }] },
  { nombre: 'Abrir pinza', angulos: { J_pinza_a: 108 } },
  { nombre: 'Cerrar pinza', angulos: { J_pinza_a: 60 } },
]

const espera = (ms: number) => new Promise((r) => setTimeout(r, ms))

export function Gemelo({ store, conectado, imagenes, enviar }: { store: SensorStore; conectado: boolean; imagenes: Imagen[]; enviar: (l: string) => void }) {
  const host = useRef<HTMLDivElement>(null)
  const g = useRef<Gemelo3D | null>(null)
  const [arts, setArts] = useState<Articulacion[]>([])
  const [ang, setAng] = useState<Record<string, number>>({})
  const [pieza, setPieza] = useState<Pieza | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const [tick, setTick] = useState(0)
  const [real, setReal] = useState(false) // mandar los servos al bicho real
  const [odo, setOdo] = useState(false) // mover el gemelo con el flujo óptico
  const [sim, setSim] = useState(false) // sensores de mentira, para mostrarlo sin robot
  const [sel, setSel] = useState<string | null>(null)
  const realRef = useRef(real)
  realRef.current = real && conectado
  const ultimoEnvio = useRef<Record<number, number>>({})
  const flujoPrev = useRef<{ dx: number; dy: number } | null>(null)
  const poseRun = useRef(0)

  useEffect(() => {
    const v = new Gemelo3D(host.current!, { clic: (p) => { setPieza(p); setSel(p?.nodo ?? null) } })
    g.current = v
    fetch('/bim/registro.json')
      .then((r) => r.json())
      .then(async (reg) => {
        const a = (reg.articulaciones ?? []) as Articulacion[]
        a.forEach((x) => Gemelo3D.canalDe.set(x.nodo, x.canal))
        setArts(a)
        setAng(Object.fromEntries(a.map((x) => [x.nodo, x.inicio])))
        await v.cargar(a)
        setCargando(false)
      })
      .catch((e) => {
        setError(`No se pudo cargar el modelo: ${e.message}`)
        setCargando(false)
      })
    return () => v.destruir()
  }, [])

  // lectura de sensores a ~6 fps (fuera de React, igual que la sección Sensores)
  useEffect(() => {
    const iv = setInterval(() => setTick((t) => t + 1), 160)
    return () => clearInterval(iv)
  }, [])

  const camara = imagenes.find((i) => i.nombre === 'camara') ?? null
  const lista = useMemo(() => {
    void tick
    return [...store.series.values()].filter((s) => !/^_/.test(s.key)).sort((a, b) => a.key.localeCompare(b.key))
  }, [tick, store])

  useEffect(() => {
    const v = g.current
    if (!v) return
    const num = (k: string) => {
      const s = store.series.get(k)?.last
      return typeof s === 'number' ? s : undefined
    }
    const bool = (k: string) => {
      const s = store.series.get(k)?.last
      return typeof s === 'boolean' ? s : typeof s === 'number' ? s > 0 : undefined
    }
    let vivo: Vivo
    if (sim && !conectado) {
      const t = performance.now() / 1000
      vivo = {
        luz: Math.sin(t * 0.7) > 0.3,
        verde: Math.sin(t * 1.3) > 0.5,
        rojo: Math.sin(t * 0.9 + 2) > 0.6,
        tempCpu: 52 + 10 * Math.sin(t / 8),
        vozAngulo: (t * 25) % 360,
        vozActiva: Math.sin(t * 2) > 0,
      }
    } else {
      const servos: Record<number, number> = {}
      for (const s of store.series.values()) {
        const m = s.key.match(/^servo\[(\d+)\]$/)
        if (m && typeof s.last === 'number') servos[Number(m[1])] = s.last
      }
      vivo = {
        luz: bool('luz'),
        verde: bool('verde'),
        rojo: bool('rojo'),
        tempCpu: num('temp_cpu'),
        vozAngulo: num('oido.angulo'),
        vozActiva: bool('oido.voz'),
        servos: Object.keys(servos).length && !realRef.current ? servos : undefined,
      }
      // flujo óptico: el ADNS-3080 entrega dx/dy acumulados; se integra la diferencia (400 cpi ≈ 0,0635 mm por cuenta)
      const dx = num('flujo.dx'), dy = num('flujo.dy')
      if (odo && dx !== undefined && dy !== undefined) {
        const p = flujoPrev.current
        if (p) vivo.avance = { dx: (dy - p.dy) * 0.0000635, dy: (dx - p.dx) * 0.0000635 }
        flujoPrev.current = { dx, dy }
      } else flujoPrev.current = null
    }
    vivo.camara = camara?.url ?? null
    v.setVivo(vivo)
    if (vivo.servos) setAng((a) => ({ ...a, ...Object.fromEntries(arts.filter((x) => vivo.servos![x.canal] !== undefined).map((x) => [x.nodo, vivo.servos![x.canal]])) }))
  }, [tick, sim, conectado, odo, camara?.url, store, arts])

  const mover = (nodo: string, deg: number) => {
    g.current?.setAngulo(nodo, deg)
    setAng((a) => ({ ...a, [nodo]: deg }))
    const art = arts.find((x) => x.nodo === nodo)
    if (art && realRef.current) {
      const now = performance.now()
      if (now - (ultimoEnvio.current[art.canal] ?? 0) > 60) {
        ultimoEnvio.current[art.canal] = now
        enviar(JSON.stringify({ cmd: 'servo', i: art.canal, deg: Math.round(deg) }))
      }
    }
  }
  const aplicarPose = async (p: Pose) => {
    const run = ++poseRun.current
    const pasos = p.secuencia ?? [p.angulos!]
    for (const paso of pasos) {
      if (run !== poseRun.current) return
      for (const [n, d] of Object.entries(paso)) {
        const a = arts.find((x) => x.nodo === n)
        if (a) mover(n, Math.max(a.min, Math.min(a.max, d)))
      }
      if (p.secuencia) await espera(520)
    }
  }

  const hz = store.hz
  const edadCam = camara ? Math.round((Date.now() - camara.ts) / 1000) : null

  return (
    <div className="gm">
      <header className="toolbar">
        <div className="tb-title">
          <h1>Gemelo digital</h1>
          <p>Chasis impreso V1 + brazo v4 · cada pieza del inventario · sensores en vivo</p>
        </div>
        <div className="tb-actions">
          <span className={`capsule ${conectado ? '' : 'off'}`}>{conectado ? `${hz.toFixed(1)} Hz en vivo` : sim ? 'Sensores simulados' : 'Sin bicho conectado'}</span>
          {!conectado && (
            <button type="button" className="capsule" onClick={() => setSim((s) => !s)}>
              {sim ? 'Apagar simulación' : 'Simular sensores'}
            </button>
          )}
          <button type="button" className="capsule" onClick={() => g.current?.volverAlCentro()}>
            Volver al centro
          </button>
        </div>
      </header>

      <div className="gm-grid">
        <div className="card gm-visor">
          <div className="gm-canvas" ref={host} />
          {cargando && <p className="gm-carga">Armando el bicho pieza por pieza…</p>}
          {error && <p className="gm-carga err">{error}</p>}
          <div className="gm-leyenda">
            <span><i style={{ background: '#af52de' }} />de dónde viene la voz</span>
            <span><i style={{ background: '#007aff' }} />lo que ve la cámara</span>
            <span><i style={{ background: '#ff3b30' }} />la Pi se calienta</span>
          </div>
          {pieza && (
            <div className="gm-ficha">
              <button type="button" className="gm-x" aria-label="Cerrar" onClick={() => { setPieza(null); setSel(null); g.current?.resaltar(null) }}>×</button>
              <strong>{pieza.etiqueta}</strong>
              <span>
                {pieza.tipo === 'impreso' ? 'Pieza impresa' : pieza.tipo === 'chasis' ? 'Chasis' : 'Componente'}
                {pieza.item ? ` · ítem ${pieza.item} del inventario` : ''}
                {pieza.masa ? ` · ${Math.round(pieza.masa)} g` : ''}
              </span>
            </div>
          )}
          {camara && edadCam !== null && <span className="gm-cam">cámara del bicho · hace {edadCam} s</span>}
        </div>

        <aside className="gm-lado">
          <section className="card gm-sens">
            <div className="gm-h">
              <h2>Sensores en vivo</h2>
              <span>toca uno para verlo en el robot</span>
            </div>
            <div className="gm-lista">
              {lista.length === 0 && (
                <p className="gm-vacio">{conectado ? 'Esperando lecturas del bicho…' : 'Conecta el bicho (barra lateral) o usa «Simular sensores».'}</p>
              )}
              {lista.map((s) => {
                const q = queEs(s.key)
                const val = typeof s.last === 'boolean' ? (s.last ? 'encendida' : 'apagada') : typeof s.last === 'number' ? s.last.toFixed(Math.abs(s.last) < 10 ? 2 : 0) : String(s.last ?? '—')
                return (
                  <button type="button" key={s.key} className={`gm-fila ${q && sel === q.nodo ? 'sel' : ''}`} onClick={() => { if (q) { g.current?.resaltar(q.nodo); setSel(q.nodo) } }}>
                    <span className="gm-k">{q?.nombre ?? s.key}<small>{s.key}</small></span>
                    <span className={`gm-v ${typeof s.last === 'boolean' ? (s.last ? 'on' : 'offv') : ''}`}>{val}{q?.unidad && typeof s.last === 'number' ? ` ${q.unidad}` : ''}</span>
                  </button>
                )
              })}
            </div>
            <label className="gm-check">
              <input type="checkbox" checked={odo} onChange={(e) => setOdo(e.target.checked)} /> Mover el gemelo con el flujo óptico (experimental)
            </label>
          </section>

          <section className="card gm-brazo">
            <div className="gm-h">
              <h2>Brazo v4</h2>
              <span>{realRef.current ? 'mueve también el robot real' : 'solo el gemelo'}</span>
            </div>
            <div className="gm-poses">
              {POSES.map((p) => (
                <button key={p.nombre} type="button" onClick={() => void aplicarPose(p)} disabled={cargando}>
                  {p.nombre}
                </button>
              ))}
            </div>
            {arts.map((a) => (
              <label key={a.nodo} className="gm-sl">
                <span>
                  {a.servo.replace(/^S\d_/, '').replace('pinza', 'pinza')} <small>canal {a.canal}</small>
                  <b>{Math.round(ang[a.nodo] ?? a.inicio)}°</b>
                </span>
                <input type="range" min={a.min} max={a.max} value={ang[a.nodo] ?? a.inicio} onChange={(e) => mover(a.nodo, Number(e.target.value))} disabled={cargando} />
              </label>
            ))}
            <label className="gm-check">
              <input type="checkbox" checked={real} disabled={!conectado} onChange={(e) => setReal(e.target.checked)} /> Mover el robot real (manda <code>servo</code>)
            </label>
          </section>
        </aside>
      </div>
    </div>
  )
}
