import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { VisorBrazo, type Articulacion, type Vista } from './visor'
import { Plano } from './Plano'
import './brazo.css'

/* Vista «Brazo»: árbol BIM, visor 3D y control del brazo en una sola pantalla. Lee web/public/bim/registro.json. */

type Revision = { rev: string; fecha?: string; commit?: string; cambio?: string }
type Pieza = {
  id: string
  nombre: string
  grupo?: string
  material?: string
  relleno?: string
  orientacion?: string
  rev?: string
  estado?: string
  stl?: string
  bandeja?: string
  gramos?: number
  historial?: Revision[]
}
type Componente = { id: string; nombre: string; modelo?: string; canal?: number; gramos?: number }
type Registro = { modelo?: string; version_modelo?: string; articulaciones: Articulacion[]; piezas: Pieza[]; componentes: Componente[]; calibracion?: string }

type Fila = { id: string; nombre: string; rev?: string; estado: Estado; estadoTxt: string; pieza?: Pieza; comp?: Componente }
type Estado = 'impresa' | 'imprimiendo' | 'confirmar' | 'diseno' | 'componente'

const TORQUE_SERVO = 1.0 // N·m, MG995 a 6 V (aprox.)

function clasificar(txt = ''): Estado {
  const t = txt.toLowerCase()
  if (/dise(ñ|n)o/.test(t)) return 'diseno'
  if (/por confirmar|confirmar/.test(t)) return 'confirmar'
  if (/imprimi(é|e)ndose|imprimiendo|en impresi(ó|o)n|en cola/.test(t)) return 'imprimiendo'
  if (/impres[ao]|lista|montad/.test(t)) return 'impresa'
  return 'confirmar'
}

const ESTADO_TXT: Record<Estado, string> = {
  impresa: 'Impresa',
  imprimiendo: 'Imprimiéndose',
  confirmar: 'Por confirmar',
  diseno: 'En diseño',
  componente: 'Componente',
}

const PRESETS: { id: string; label: string; titulo: string; pose: (a: Articulacion) => number }[] = [
  { id: 'montaje', label: 'Todos en 90°', titulo: 'Pose de montaje: cada servo en 90°', pose: () => 90 },
  { id: 'reposo', label: 'Reposo', titulo: 'La pose de inicio del registro', pose: (a) => a.inicio },
  {
    id: 'alcance',
    label: 'Alcance',
    titulo: 'Brazo estirado hacia adelante: el peor caso para el hombro',
    pose: (a) => ({ J_giro: 90, J_hombro: 0, J_codo: 180, J_pinza_a: 84 })[a.nodo] ?? a.inicio,
  },
]

const limitar = (a: Articulacion, d: number) => Math.min(a.max, Math.max(a.min, Math.round(d)))

export function Brazo({ conectado, motivo, enviar }: { conectado: boolean; motivo?: string | null; enviar: (linea: string) => void }) {
  const lienzo = useRef<HTMLCanvasElement>(null)
  const capa = useRef<HTMLDivElement>(null)
  const visor = useRef<VisorBrazo | null>(null)
  const [reg, setReg] = useState<Registro | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [enModelo, setEnModelo] = useState<Set<string> | null>(null)
  const [angulos, setAngulos] = useState<Record<string, number>>({})
  const [hover, setHover] = useState<{ id: string; x: number; y: number; desdeLista?: boolean } | null>(null)
  const [sel, setSel] = useState<string | null>(null)
  const [vista, setVista] = useState<Vista>('3d')
  const [real, setReal] = useState(false)
  const [carga, setCarga] = useState(100)
  const [torque, setTorque] = useState<{ hombro: number | null; codo: number | null }>({ hombro: null, codo: null })
  const [plano, setPlano] = useState<{ id: string; rev: string } | null>(null)
  const [cajon, setCajon] = useState(false)

  /* ---------- registro + modelo ---------- */
  useEffect(() => {
    let vivo = true
    fetch('/bim/registro.json', { cache: 'no-cache' })
      .then((r) => {
        if (!r.ok) throw new Error(`registro.json respondió ${r.status}`)
        return r.json() as Promise<Registro>
      })
      .then((r) => {
        if (!vivo) return
        setReg(r)
        setAngulos(Object.fromEntries(r.articulaciones.map((a) => [a.nodo, a.inicio])))
      })
      .catch((e) => vivo && setError(`No pude leer el registro BIM: ${(e as Error).message}`))
    return () => {
      vivo = false
    }
  }, [])

  // pose → modelo → torque. Se aplica en el mismo evento que cambia la pose (no en un efecto): así un slider
  // arrastrado rápido no encadena decenas de renders.
  const angulosRef = useRef(angulos)
  angulosRef.current = angulos
  const cargaRef = useRef(carga)
  cargaRef.current = carga
  const aplicar = useCallback(
    (pose: Record<string, number>, cargaG: number) => {
      const v = visor.current
      if (!v || !reg) return
      for (const a of reg.articulaciones) v.setAngulo(a.nodo, pose[a.nodo] ?? a.inicio)
      setTorque(v.torques(cargaG))
    },
    [reg],
  )

  useEffect(() => {
    if (!reg || !lienzo.current || !capa.current) return
    const v = new VisorBrazo(lienzo.current, capa.current, {
      hover: (id, x, y) => setHover(id ? { id, x, y } : null),
      clic: (id) => {
        if (id) setSel(id)
      },
    })
    visor.current = v
    ;(window as unknown as { __brazo?: VisorBrazo }).__brazo = v
    v.cargar('/bim/brazo.glb', reg.articulaciones)
      .then((ids) => {
        setEnModelo(new Set(ids))
        aplicar(angulosRef.current, cargaRef.current)
      })
      .catch((e) => setError(`No pude cargar brazo.glb: ${(e as Error).message}`))
    return () => {
      v.dispose()
      visor.current = null
    }
  }, [reg, aplicar])

  const hoverId = hover?.id ?? null
  useEffect(() => visor.current?.resaltar(hoverId, sel), [hoverId, sel, enModelo])
  useEffect(() => visor.current?.vista(vista), [vista, enModelo])

  /* ---------- robot real: un comando por canal, con throttle de ~60 ms ---------- */
  const pendientes = useRef(new Map<number, number>())
  const timer = useRef<number | null>(null)
  const ultimo = useRef(0)
  const enviarRef = useRef(enviar)
  enviarRef.current = enviar
  const flush = useCallback(() => {
    timer.current = null
    ultimo.current = performance.now()
    for (const [i, deg] of pendientes.current) enviarRef.current(JSON.stringify({ cmd: 'servo', i, deg }))
    pendientes.current.clear()
  }, [])
  const puedeMover = conectado && !motivo
  const activo = real && puedeMover
  const mandar = useCallback(
    (cambios: { canal: number; deg: number }[]) => {
      if (!activo) return
      for (const c of cambios) pendientes.current.set(c.canal, c.deg)
      if (timer.current !== null) return
      const espera = Math.max(0, 60 - (performance.now() - ultimo.current))
      timer.current = window.setTimeout(flush, espera)
    },
    [activo, flush],
  )
  useEffect(() => () => {
    if (timer.current !== null) clearTimeout(timer.current)
  }, [])
  useEffect(() => {
    if (!puedeMover) setReal(false)
  }, [puedeMover])

  const mover = (a: Articulacion, deg: number) => {
    const d = limitar(a, deg)
    const pose = { ...angulosRef.current, [a.nodo]: d }
    angulosRef.current = pose
    setAngulos(pose)
    aplicar(pose, carga)
    mandar([{ canal: a.canal, deg: d }])
  }
  const preset = (p: (typeof PRESETS)[number]) => {
    if (!reg) return
    const pose = Object.fromEntries(reg.articulaciones.map((a) => [a.nodo, limitar(a, p.pose(a))]))
    angulosRef.current = pose
    setAngulos(pose)
    aplicar(pose, carga)
    mandar(reg.articulaciones.map((a) => ({ canal: a.canal, deg: pose[a.nodo] })))
  }

  /* ---------- árbol ---------- */
  const grupos = useMemo(() => {
    if (!reg) return []
    const g = new Map<string, Fila[]>()
    for (const p of reg.piezas) {
      const k = p.grupo ?? 'Otras piezas'
      if (!g.has(k)) g.set(k, [])
      const e = clasificar(p.estado)
      g.get(k)!.push({ id: p.id, nombre: p.nombre, rev: p.rev, estado: e, estadoTxt: p.estado ?? ESTADO_TXT[e], pieza: p })
    }
    g.set(
      'Componentes · servos',
      reg.componentes.map((c) => ({ id: c.id, nombre: c.nombre, estado: 'componente' as const, estadoTxt: c.modelo ?? 'Componente', comp: c })),
    )
    return [...g.entries()]
  }, [reg])
  const filas = useMemo(() => new Map(grupos.flatMap(([, fs]) => fs.map((f) => [f.id, f] as const))), [grupos])
  const elegida = sel ? filas.get(sel) : undefined
  const tip = hover && !hover.desdeLista ? filas.get(hover.id) : undefined

  const pct = (t: number | null) => (t === null ? null : Math.round((t / TORQUE_SERVO) * 100))

  return (
    <div className="bz">
      <header className="toolbar">
        <div className="tb-title">
          <h1>Brazo</h1>
          <p>
            {reg ? `${reg.modelo ?? 'Brazo'} ${reg.version_modelo ?? ''} · ${reg.piezas.length} piezas · ${reg.componentes.length} servos` : 'Cargando el registro BIM…'}
          </p>
        </div>
        <div className="tb-actions">
          <button type="button" className="capsule bz-cajon-btn" aria-pressed={cajon} onClick={() => setCajon((v) => !v)}>
            Piezas
          </button>
          <span className={`capsule bz-robot ${puedeMover ? 'on' : ''}`} title={motivo ?? undefined}>
            <i aria-hidden /> Robot <b>{puedeMover ? (activo ? 'moviéndose' : 'conectado') : 'sin conexión'}</b>
          </span>
        </div>
      </header>

      {error && <p className="notice">{error}</p>}

      <div className={`bz-grid ${cajon ? 'cajon-abierto' : ''}`}>
        {/* ── izquierda: árbol BIM ── */}
        <aside className="card glass bz-arbol" aria-label="Piezas del modelo BIM">
          <div className="bz-lista">
            {grupos.map(([g, fs]) => (
              <section key={g} className="bz-grupo">
                <p className="bz-grupo-t">{g}</p>
                <ul>
                  {fs.map((f) => (
                    <li key={f.id}>
                      <button
                        type="button"
                        className={`bz-fila ${sel === f.id ? 'sel' : ''} ${enModelo && !enModelo.has(f.id) ? 'fuera' : ''}`}
                        onMouseEnter={() => setHover({ id: f.id, x: 0, y: 0, desdeLista: true })}
                        onMouseLeave={() => setHover(null)}
                        onClick={() => setSel(sel === f.id ? null : f.id)}
                        title={enModelo && !enModelo.has(f.id) ? 'Todavía no está en el modelo 3D' : undefined}
                      >
                        <span className="bz-id">{f.id.replace(/_.*/, '')}</span>
                        <span className="bz-nom">{f.nombre}</span>
                        {f.rev && f.rev !== '-' && <span className="bz-rev">rev {f.rev}</span>}
                        <i className={`bz-est e-${f.estado}`} title={f.estadoTxt} />
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
          <div className="bz-leyenda" aria-label="Estados">
            {(['impresa', 'imprimiendo', 'confirmar', 'diseno'] as const).map((e) => (
              <span key={e}>
                <i className={`bz-est e-${e}`} /> {ESTADO_TXT[e]}
              </span>
            ))}
          </div>
          {elegida && (
            <div className="bz-ficha">
              <div className="bz-ficha-head">
                <div>
                  <p className="bz-ficha-id">{elegida.id}</p>
                  <h2>{elegida.nombre}</h2>
                </div>
                <button type="button" className="bz-x" onClick={() => setSel(null)} aria-label="Cerrar ficha">
                  ×
                </button>
              </div>
              <span className={`bz-chip e-${elegida.estado}`}>{elegida.estadoTxt}</span>
              <dl className="bz-dl">
                {(elegida.pieza
                  ? [
                      ['Material', elegida.pieza.material],
                      ['Relleno', elegida.pieza.relleno],
                      ['Orientación', elegida.pieza.orientacion],
                      ['Gramos', elegida.pieza.gramos != null ? `${elegida.pieza.gramos} g` : undefined],
                      ['Bandeja', elegida.pieza.bandeja],
                    ]
                  : [
                      ['Modelo', elegida.comp?.modelo],
                      ['Canal', elegida.comp?.canal != null ? String(elegida.comp.canal) : undefined],
                      ['Gramos', elegida.comp?.gramos != null ? `${elegida.comp.gramos} g` : undefined],
                    ]
                ).map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{v ?? '—'}</dd>
                  </div>
                ))}
              </dl>
              {elegida.pieza?.historial && elegida.pieza.historial.length > 0 && (
                <ol className="bz-hist">
                  {[...elegida.pieza.historial].reverse().map((h, i) => (
                    <li key={i}>
                      <b>rev {h.rev}</b>
                      {h.commit && <code>{h.commit}</code>}
                      <span>{h.cambio}</span>
                    </li>
                  ))}
                </ol>
              )}
              {elegida.pieza?.rev && elegida.pieza.rev !== '-' && (
                <button type="button" className="bz-plano-btn" onClick={() => setPlano({ id: elegida.id, rev: elegida.pieza!.rev! })}>
                  Plano rev {elegida.pieza.rev}
                </button>
              )}
            </div>
          )}
        </aside>

        {/* ── centro: visor ── */}
        <section className="card glass bz-visor" aria-label="El brazo en 3D">
          <canvas ref={lienzo} />
          <div ref={capa} className="bz-capa" aria-hidden />
          <div className="seg bz-vistas" role="group" aria-label="Vista">
            {(
              [
                ['3d', '3D'],
                ['lado', 'Lado'],
                ['frente', 'Frente'],
                ['arriba', 'Arriba'],
              ] as const
            ).map(([id, l]) => (
              <button key={id} type="button" aria-pressed={vista === id} onClick={() => (vista === id ? visor.current?.vista(id) : setVista(id))}>
                {l}
              </button>
            ))}
          </div>
          {!enModelo && !error && <p className="bz-cargando">Cargando brazo.glb…</p>}
          <p className="bz-hint">Arrastra para girar · rueda para acercar · clic en una pieza para ver su ficha</p>
          {tip && hover && (
            <div className="sim-tip" style={{ left: hover.x + 14, top: hover.y + 14 }}>
              <b>
                {tip.id} · {tip.nombre}
              </b>
              <span>{tip.estadoTxt}</span>
            </div>
          )}
          {plano && reg && (
            <Plano
              pieza={filas.get(plano.id)?.pieza ?? { id: plano.id, nombre: plano.id }}
              rev={plano.rev}
              onRev={(rev) => setPlano({ id: plano.id, rev })}
              onCerrar={() => setPlano(null)}
            />
          )}
        </section>

        {/* ── derecha: control ── */}
        <aside className="card glass bz-control" aria-label="Control del brazo">
          <label className={`bz-real ${activo ? 'on' : ''}`} title={puedeMover ? undefined : (motivo ?? 'Conecta el bicho para mover el robot real')}>
            <input type="checkbox" checked={activo} disabled={!puedeMover} onChange={(e) => setReal(e.target.checked)} />
            <span className="bz-switch" aria-hidden />
            <span>
              <b>Mover el robot real</b>
              <small>{puedeMover ? (activo ? 'Cada cambio se manda al bicho' : 'Apagado: solo se mueve el modelo') : (motivo ?? 'Sin bicho conectado: solo el modelo')}</small>
            </span>
          </label>

          <div className="bz-sliders">
            {reg?.articulaciones.map((a) => {
              const v = angulos[a.nodo] ?? a.inicio
              const sinNodo = enModelo !== null && !visor.current?.tieneNodo(a.nodo)
              return (
                <div key={a.nodo} className="bz-slider" title={a.que_hace}>
                  <div className="bz-slider-head">
                    <span className="bz-num">{a.servo.match(/^S(\d+)/)?.[1] ?? a.canal}</span>
                    <span className="bz-sl-nom">
                      {a.servo.replace(/^S\d+_/, '')}
                      <small>
                        canal {a.canal}
                        {sinNodo ? ' · aún no está en el 3D' : ''}
                      </small>
                    </span>
                    <input
                      className="bz-deg"
                      type="number"
                      min={a.min}
                      max={a.max}
                      value={v}
                      onChange={(e) => mover(a, Number(e.target.value))}
                      aria-label={`${a.servo} en grados`}
                    />
                    <span className="bz-unit">°</span>
                  </div>
                  <input type="range" min={a.min} max={a.max} step={1} value={v} onChange={(e) => mover(a, Number(e.target.value))} aria-label={a.servo} />
                </div>
              )
            })}
          </div>

          <div className="bz-presets">
            {PRESETS.map((p) => (
              <button key={p.id} type="button" className="capsule" onClick={() => preset(p)} title={p.titulo}>
                {p.label}
              </button>
            ))}
          </div>

          <div className="bz-torque">
            <div className="bz-torque-head">
              <p className="bz-eyebrow">Torque estático</p>
              <label className="bz-carga">
                carga en la pinza
                <input type="number" min={0} max={1000} step={10} value={carga} onChange={(e) => {
                    const g = Math.max(0, Number(e.target.value) || 0)
                    setCarga(g)
                    aplicar(angulosRef.current, g)
                  }} />g
              </label>
            </div>
            {(
              [
                ['Hombro', torque.hombro],
                ['Codo', torque.codo],
              ] as const
            ).map(([n, t]) => {
              const p = pct(t)
              return (
                <div key={n} className={`bz-tq ${p === null ? '' : p >= 100 ? 't-mal' : p >= 66 ? 't-ojo' : 't-ok'}`}>
                  <span className="bz-tq-n">{n}</span>
                  <span className="bz-tq-bar">
                    <i style={{ width: `${Math.min(100, p ?? 0)}%` }} />
                    <s style={{ left: '66.6%' }} title="⅔ del torque del servo: el máximo recomendado" />
                  </span>
                  <span className="bz-tq-v">{t === null ? '—' : `${t.toFixed(2)} N·m`}</span>
                  <b className="bz-tq-p">{p === null ? '' : `${p} %`}</b>
                </div>
              )
            })}
            <p className="bz-nota">Contra MG995 ≈ {TORQUE_SERVO.toFixed(1)} N·m a 6 V. Línea: ⅔, el máximo recomendado.</p>
          </div>
        </aside>
        {cajon && <button type="button" className="bz-velo" aria-label="Cerrar piezas" onClick={() => setCajon(false)} />}
      </div>
    </div>
  )
}
