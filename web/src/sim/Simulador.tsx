import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react'
import { Simulacion } from './escena'
import { ESCENAS, ESTADOS, GRUPOS, ICONOS, PIEZAS, REPOSO, describir, duracion, estado as porId, textoApp, type Escena, type Estado, type Visita } from './lenguaje'
import { audio, callar, decir, tocar } from './sonido'
import './sim.css'

const VISITAS: { id: Visita; label: string }[] = [
  { id: 'ninguna', label: 'Nadie' },
  { id: 'perro', label: 'Perro' },
  { id: 'persona', label: 'Persona' },
]

const NOMBRE_PIEZA = new Map(PIEZAS.map((p) => [p.id, p]))

function Icono8({ id, color }: { id: string; color: string }) {
  const filas = ICONOS[id] ?? ICONOS.sonrisa
  return (
    <span className="m8" aria-hidden style={{ '--c': color } as CSSProperties}>
      {filas.flatMap((f, i) => [...f].map((b, j) => <i key={`${i}-${j}`} className={b === '1' ? 'on' : ''} />))}
    </span>
  )
}

export function Simulador() {
  const lienzo = useRef<HTMLCanvasElement>(null)
  const sim = useRef<Simulacion | null>(null)
  const [actual, setActual] = useState<Estado>(REPOSO)
  const [vez, setVez] = useState(0)
  const [visita, setVisita] = useState<Visita>('ninguna')
  const [conSonido, setConSonido] = useState(true)
  const [sensores, setSensores] = useState(true)
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null)
  const [piezaLista, setPiezaLista] = useState<string | null>(null)
  const [foto, setFoto] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [escena, setEscena] = useState<string | null>(null)
  const pasos = useRef<number[]>([])
  const otros = useRef<number[]>([])
  const visitaRef = useRef(visita)
  visitaRef.current = visita
  const sonidoRef = useRef(conSonido)
  sonidoRef.current = conSonido

  useEffect(() => {
    const s = new Simulacion(lienzo.current!, {
      hover: (id, x, y) => setHover(id ? { id, x, y } : null),
      visitaSeFue: () => setVisita('ninguna'),
    })
    sim.current = s
    return () => {
      s.dispose()
      sim.current = null
      callar()
      pasos.current.forEach(clearTimeout)
      otros.current.forEach(clearTimeout)
    }
  }, [])

  useEffect(() => sim.current?.setVisita(visita), [visita])
  useEffect(() => sim.current?.setSensores(sensores), [sensores])
  useEffect(() => sim.current?.resaltar(piezaLista ?? hover?.id ?? null), [piezaLista, hover?.id])

  // sonidos que se repiten mientras dura el estado (espera tu decisión, cargando…)
  useEffect(() => {
    if (!actual.repetir || !conSonido) return
    const iv = setInterval(() => {
      tocar(actual.sonido)
      sim.current?.hablar(duracion(actual.sonido))
    }, actual.repetir * 1000)
    return () => clearInterval(iv)
  }, [actual, vez, conSonido])

  const despues = (ms: number, fn: () => void) => otros.current.push(window.setTimeout(fn, ms))

  const aplicar = useCallback((e: Estado) => {
    let final = e
    let nota: string | null = null
    if (e.solo_animales && e.si_persona && visitaRef.current === 'persona') {
      final = porId(e.si_persona)
      nota = 'A una persona no la mojo: le hablo y te aviso.'
    }
    otros.current.forEach(clearTimeout)
    otros.current = []
    callar()
    setActual(final)
    setVez((v) => v + 1)
    setAviso(nota)
    setFoto(null)
    sim.current?.setEstado(final)
    const dur = duracion(final.sonido)
    sim.current?.hablar(dur + (final.voz ? 3.2 : 0))
    if (sonidoRef.current) {
      tocar(final.sonido)
      if (final.voz) despues(dur * 1000 + 150, () => decir(final.voz!))
    }
    if (final.foto) despues(1100, () => setFoto(sim.current?.foto() ?? null))
  }, [])

  const parar = () => {
    pasos.current.forEach(clearTimeout)
    pasos.current = []
    setEscena(null)
  }

  const elegir = (e: Estado) => {
    if (conSonido) audio()
    parar()
    aplicar(e)
  }

  const correr = (esc: Escena, conVisita = true) => {
    if (conSonido) audio()
    parar()
    setEscena(esc.id)
    if (conVisita) {
      visitaRef.current = esc.visita
      setVisita(esc.visita)
      sim.current?.setVisita(esc.visita)
    }
    let t = 0
    for (const [id, s] of esc.pasos) {
      const e = porId(id)
      pasos.current.push(window.setTimeout(() => aplicar(e), t * 1000))
      t += s
    }
    pasos.current.push(window.setTimeout(() => setEscena(null), t * 1000))
  }

  /** En la app, tocar el círculo es hablarle. */
  const tocarCirculo = () =>
    correr({ id: 'circulo', nombre: 'Le hablas', visita, pasos: [['escucha', 2.4], ['piensa', 1.6], ['si', 2]] }, false)

  const d = describir(actual)
  const texto = aviso ?? textoApp(actual, visita)
  const pieza = hover ? NOMBRE_PIEZA.get(hover.id) : null
  const orbe = { '--c': actual.luz.color, '--per': `${actual.luz.periodo ?? 1.6}s`, '--b': actual.luz.brillo ?? 1 } as CSSProperties

  return (
    <div className="sim">
      <header className="toolbar">
        <div className="tb-title">
          <h1>Simulador</h1>
          <p>El bicho con las piezas del inventario y su idioma de {ESTADOS.length} estados</p>
        </div>
        <div className="tb-actions">
          <button type="button" className="capsule" aria-pressed={conSonido} onClick={() => setConSonido((v) => !v)} title="Sonidos y voz del bicho">
            Sonido <b>{conSonido ? 'sí' : 'no'}</b>
          </button>
          <button type="button" className="capsule" aria-pressed={sensores} onClick={() => setSensores((v) => !v)} title="Puntos del LiDAR y cono del ultrasonido">
            Sensores <b>{sensores ? 'sí' : 'no'}</b>
          </button>
          <button type="button" className="capsule" onClick={() => sim.current?.encuadrar()}>
            Encuadrar
          </button>
        </div>
      </header>

      <div className="sim-top">
        <section className="card glass sim-stage" aria-label="El bicho en 3D">
          <canvas ref={lienzo} />
          <div className="sim-now">
            <i style={{ background: actual.luz.color }} />
            <span>{actual.nombre}</span>
            {escena && <small>escena</small>}
          </div>
          <div className="seg sim-visita" role="group" aria-label="Visita en el patio">
            {VISITAS.map((v) => (
              <button key={v.id} type="button" aria-pressed={visita === v.id} onClick={() => setVisita(v.id)}>
                {v.label}
              </button>
            ))}
          </div>
          <p className="sim-hint">Arrastra para girar · rueda para acercar · clic en el pasto para mover la visita · pasa el mouse por una pieza</p>
          <span className="sim-pip" aria-hidden>
            <b>Cámara del bicho</b>
          </span>
          {pieza && hover && (
            <div className="sim-tip" style={{ left: hover.x + 14, top: hover.y + 14 }}>
              <b>{pieza.nombre}</b>
              <span>{pieza.uso}</span>
            </div>
          )}
        </section>

        <aside className="card glass sim-app" aria-label="La app del dueño">
          <p className="eyebrow">App del dueño</p>
          <div className="phone">
            <div className="phone-bar">
              <span>bicho</span>
              <span className="phone-dot" style={{ background: actual.luz.color }} />
            </div>
            <button type="button" className="orb-btn" onClick={tocarCirculo} title="Tocar para hablarle">
              <span key={vez} className={`orb p-${actual.luz.patron}`} style={orbe} />
            </button>
            <p className={`phone-text ${texto ? '' : 'muted'}`}>{texto ?? 'El bicho no dice nada: solo lo muestra con su cuerpo.'}</p>
            {foto && (
              <figure className="phone-foto">
                <img src={foto} alt="Foto de la cámara del bicho" />
                <figcaption>Foto de la cámara</figcaption>
              </figure>
            )}
            <p className="phone-hint">Toca el círculo para hablarle</p>
          </div>
        </aside>
      </div>

      <section className="card glass sim-detalle" aria-label="Estado actual">
        <div className="det-head">
          <Icono8 id={actual.matriz} color={actual.luz.color} />
          <div>
            <p className="eyebrow">{actual.grupo}</p>
            <h2>{actual.nombre}</h2>
          </div>
        </div>
        <dl className="det-grid">
          <div>
            <dt>Sonido</dt>
            <dd>{actual.sonido.length ? `${actual.sonido.length} notas · ${duracion(actual.sonido).toFixed(1)} s${actual.repetir ? ` · se repite cada ${actual.repetir} s` : ''}` : 'silencio'}</dd>
          </div>
          <div>
            <dt>Luz</dt>
            <dd>
              <i className="dot" style={{ background: actual.luz.color }} /> {d.luz}
            </dd>
          </div>
          <div>
            <dt>Brazo y cabeza</dt>
            <dd>{d.cabeza}</dd>
          </div>
          <div>
            <dt>Ruedas</dt>
            <dd>{d.cuerpo}</dd>
          </div>
          {actual.voz && (
            <div>
              <dt>Voz</dt>
              <dd>“{actual.voz}”</dd>
            </div>
          )}
          {(actual.foco || actual.agua) && (
            <div>
              <dt>Extra</dt>
              <dd>{[actual.foco && 'prende el foco', actual.agua && 'tira agua (solo animales)'].filter(Boolean).join(' · ')}</dd>
            </div>
          )}
        </dl>
      </section>

      <section className="card glass sim-estados" aria-label="Estados">
        <div className="card-head">
          <div>
            <h2>Idioma del bicho</h2>
            <p>Toca un estado para verlo y oírlo. Se edita en bicho/lenguaje.json.</p>
          </div>
        </div>
        {GRUPOS.map((g) => (
          <div key={g} className="est-grupo">
            <p className="est-label">{g}</p>
            <div className="est-chips">
              {ESTADOS.filter((e) => e.grupo === g).map((e) => (
                <button key={e.id} type="button" className="est-chip" aria-pressed={actual.id === e.id} onClick={() => elegir(e)}>
                  <i style={{ background: e.luz.color }} />
                  {e.nombre}
                </button>
              ))}
            </div>
          </div>
        ))}
      </section>

      <div className="sim-bottom">
        <section className="card glass" aria-label="Escenas">
          <div className="card-head">
            <div>
              <h2>Escenas</h2>
              <p>Historias completas para ensayar la demo.</p>
            </div>
            {escena && (
              <button type="button" className="capsule" onClick={parar}>
                Parar
              </button>
            )}
          </div>
          <div className="esc-list">
            {ESCENAS.map((esc) => (
              <button key={esc.id} type="button" className="esc" aria-pressed={escena === esc.id} onClick={() => correr(esc)}>
                <b>{esc.nombre}</b>
                <span>{esc.pasos.map(([id]) => porId(id).nombre).join(' → ')}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="card glass" aria-label="Piezas montadas">
          <div className="card-head">
            <div>
              <h2>Piezas montadas</h2>
              <p>Sacadas del inventario. Pasa el mouse para verlas en el robot.</p>
            </div>
          </div>
          <ul className="pz-list">
            {PIEZAS.map((p) => (
              <li key={p.id} onMouseEnter={() => setPiezaLista(p.id)} onMouseLeave={() => setPiezaLista(null)} className={hover?.id === p.id ? 'on' : ''}>
                <b>
                  {p.cantidad && p.cantidad > 1 ? `${p.cantidad}× ` : ''}
                  {p.nombre}
                </b>
                <span>{p.uso}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
