import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Release } from '../lib/firmware'
import { cmpSemver } from '../lib/firmware'
import {
  CANAL,
  armarHabilidades,
  autoria,
  cargarAprendizajes,
  derivar,
  duracion,
  enCurso,
  guardarAprendizajes,
  habilidadesDelBicho,
  hace,
  hora,
  juntar,
  nombreCorto,
  type Aprendizaje,
  type Autoria,
  type Habilidad,
} from '../lib/habilidades'
import type { Evento } from './Cerebro'
import './habilidades.css'

/** Reloj que avanza solo: cada segundo mientras aprende (para el cronómetro), si no cada 20 s. */
function useAhora(rapido: boolean) {
  const [ahora, setAhora] = useState(Date.now())
  useEffect(() => {
    const iv = setInterval(() => setAhora(Date.now()), rapido ? 1000 : 20_000)
    return () => clearInterval(iv)
  }, [rapido])
  return ahora
}

/** Lo que aprende, a partir de los eventos del cerebro. Se guarda en este navegador para no perderlo al recargar. */
function useAprendizajes(eventos: Evento[]) {
  const [mapa, setMapa] = useState(cargarAprendizajes)
  useEffect(() => {
    setMapa((prev) => {
      const sig = juntar(prev, derivar(eventos))
      if (sig !== prev) guardarAprendizajes(sig)
      return sig
    })
  }, [eventos])
  return useMemo(() => Object.values(mapa).sort((a, b) => (b.inicio ?? b.ultimo) - (a.inicio ?? a.ultimo)), [mapa])
}

export function Habilidades({
  eventos,
  fw,
  releases,
  codigo,
}: {
  eventos: Evento[]
  /** Versión que corre el bicho (null si no se sabe). */
  fw: string | null
  releases: Release[]
  /** El código que corre el bicho ({"t":"fuente"}), si llegó. */
  codigo: Record<string, string> | null
}) {
  const aprendizajes = useAprendizajes(eventos)
  const ahoraLento = useAhora(false)
  const corriendo = enCurso(aprendizajes, ahoraLento)
  const ahora = useAhora(Boolean(corriendo))

  const habilidades = useMemo(
    () => armarHabilidades({ aprendizajes, releases, fw, delBicho: habilidadesDelBicho(codigo) }),
    [aprendizajes, releases, fw, codigo],
  )
  const tiene = habilidades.filter((h) => h.presente)
  const solas = tiene.filter((h) => h.origen === 'solo')
  const ultima = [...solas].filter((h) => h.cuando).sort((a, b) => (b.cuando ?? 0) - (a.cuando ?? 0))[0]
  // Si después de lo último que aprendió intentó otra cosa y no pudo, se cuenta igual.
  const fallo = aprendizajes.find((a) => a.estado === 'fallo' && (a.fin ?? 0) > (ultima?.cuando ?? 0))

  const [quien, setQuien] = useState<Autoria | null>(null)
  useEffect(() => {
    if (!codigo) return
    let vivo = true
    autoria(codigo)
      .then((a) => vivo && setQuien(a))
      .catch(() => {})
    return () => {
      vivo = false
    }
  }, [codigo])

  return (
    <section className="sec" id="habilidades" aria-label="Habilidades">
      <div className="hab-top">
        {corriendo ? <Aprendiendo a={corriendo} ahora={ahora} /> : <UltimoAprendido h={ultima} fallo={fallo} ahora={ahora} />}
        <Autonomia tiene={tiene} solas={solas} releases={releases} fw={fw} quien={quien} ahora={ahora} />
      </div>
      <Crecimiento habilidades={tiene} ahora={ahora} aprendiendo={corriendo} />
      <Lista habilidades={habilidades} ahora={ahora} fw={fw} />
    </section>
  )
}

/* ------------------------------------------------------------------ */
/* Lo último que aprendió                                               */
/* ------------------------------------------------------------------ */

/** "Hoy", "Ayer" o el día de la semana. */
function dia(t: number | undefined, ahora: number) {
  if (!t) return ''
  const a = new Date(ahora)
  const d = new Date(t)
  const dias = Math.round((new Date(a.getFullYear(), a.getMonth(), a.getDate()).getTime() - new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()) / 86_400_000)
  if (dias <= 0) return 'Hoy'
  if (dias === 1) return 'Ayer'
  const s = d.toLocaleDateString('es-CL', { weekday: 'long' })
  return s[0].toUpperCase() + s.slice(1)
}

function UltimoAprendido({ h, fallo, ahora }: { h?: Habilidad; fallo?: Aprendizaje; ahora: number }) {
  const [verMas, setVerMas] = useState(false)
  if (!h)
    return (
      <article className="card glass hab-hero">
        <p className="eyebrow">Lo último que aprendió</p>
        <div className="empty">
          <p className="empty-t">Todavía no aprende nada solo</p>
          <p className="empty-s">Pídele algo que no sepa hacer: «bicho, aprende a…». Acá aparece apenas lo aprenda.</p>
        </div>
      </article>
    )
  const lineas = Object.values(h.archivos).reduce((s, n) => s + n, 0)
  const nArchivos = Object.keys(h.archivos).length
  const tardo = h.inicio && h.cuando ? h.cuando - h.inicio : undefined
  const reciente = h.cuando && ahora - h.cuando < 15 * 60_000
  return (
    <article className={`card glass hab-hero${reciente ? ' hab-hero-nueva' : ''}`}>
      <span className="glow glow-y hab-glow" aria-hidden />
      <div className="hab-hero-top">
        <p className="eyebrow">Lo último que aprendió</p>
        <span className="hab-sello">
          <i aria-hidden />
          Lo aprendió solo
        </span>
      </div>

      <div className="hab-hero-nombre">
        <span className="hab-emoji" aria-hidden>
          {h.icono}
        </span>
        <div>
          <h2>{h.nombre}</h2>
          <p className="hab-cuando">
            {h.aprox ? `Antes de las ${hora(h.cuando)}` : `${dia(h.cuando, ahora)} a las ${hora(h.cuando)}`}
            <span className="sep">·</span>
            {hace(h.cuando, ahora)}
            {h.version && (
              <>
                <span className="sep">·</span>v{h.version}
              </>
            )}
          </p>
        </div>
      </div>

      {h.que_hace && <p className="hab-que">{h.que_hace}</p>}

      {h.pedido && (
        <blockquote className="hab-pedido">
          <p>«{h.pedido.length > 180 ? `${h.pedido.slice(0, 178)}…` : h.pedido}»</p>
          <footer>{h.canal ? CANAL[h.canal] : 'lo que le pidieron'}</footer>
        </blockquote>
      )}

      <dl className="hab-proceso">
        <div>
          <dt>Tardó</dt>
          <dd>{tardo ? duracion(tardo) : '—'}</dd>
        </div>
        <div>
          <dt>Escribió</dt>
          <dd title={Object.entries(h.archivos).map(([n, l]) => `${n}: ${l} líneas`).join('\n')}>
            {nArchivos ? (
              <>
                {lineas} líneas<small>en {nArchivos === 1 ? '1 archivo' : `${nArchivos} archivos`}</small>
              </>
            ) : (
              '—'
            )}
          </dd>
        </div>
        <div>
          <dt>Lo probó</dt>
          <dd>{h.pruebas.length ? `${h.pruebas.length} ${h.pruebas.length === 1 ? 'vez' : 'veces'}` : '—'}</dd>
        </div>
        <div>
          <dt>Intentos</dt>
          <dd>{h.intentos ?? '—'}</dd>
        </div>
      </dl>

      {(h.pidele || h.comandos.length > 0) && (
        <div className="hab-como">
          {h.pidele && (
            <p>
              Pídeselo: <b>«{h.pidele}»</b>
            </p>
          )}
          {h.comandos.length > 0 && (
            <p className="hab-cmds" aria-label="Comandos">
              {h.comandos.map((c) => (
                <code key={c}>{c}</code>
              ))}
            </p>
          )}
        </div>
      )}

      {h.resumen && (
        <div className={`hab-resumen${verMas ? ' abierto' : ''}`}>
          <p>{h.resumen}</p>
          <button type="button" onClick={() => setVerMas((v) => !v)}>
            {verMas ? 'Ver menos' : 'Ver lo que contó al terminar'}
          </button>
        </div>
      )}

      {fallo && (
        <p className="hab-fallo">
          <b>Después intentó</b> {nombreCorto(fallo.que).toLowerCase()} y no pudo ({hora(fallo.fin)}): {(fallo.resumen ?? '').split(/\n|\. /)[0]}.
        </p>
      )}
    </article>
  )
}

/* ------------------------------------------------------------------ */
/* Aprendiendo ahora                                                    */
/* ------------------------------------------------------------------ */

const ETAPAS = [
  { id: 'revisa', label: 'Revisa su hardware', re: /^(Reviso|Encontré)/ },
  { id: 'escribe', label: 'Escribe su código', re: /^Escribo/ },
  { id: 'instala', label: 'Se lo instala', re: /^(Instalo|Versión .* corriendo|El Pi rechazó|La versión .* no se reportó)/ },
  { id: 'prueba', label: 'Lo prueba', re: /^(Pruebo|Miro)/ },
]

function Aprendiendo({ a, ahora }: { a: Aprendizaje; ahora: number }) {
  let etapa = -1
  for (const p of a.pasos) ETAPAS.forEach((e, i) => e.re.test(p.texto) && (etapa = Math.max(etapa, i)))
  const pasos = a.pasos.filter((p) => !/^Pienso/.test(p.texto)).slice(-5)
  const ultimo = a.pasos[a.pasos.length - 1]
  const seg = Math.max(0, Math.round((ahora - (a.inicio ?? a.ultimo)) / 1000))
  return (
    <article className="card glass hab-hero hab-vivo" aria-live="polite">
      <span className="glow glow-y hab-glow" aria-hidden />
      <div className="hab-hero-top">
        <p className="eyebrow">Aprendiendo ahora</p>
        <span className="live">
          <i className="live-dot" aria-hidden />
          {Math.floor(seg / 60)}:{String(seg % 60).padStart(2, '0')}
        </span>
      </div>
      <div className="hab-hero-nombre">
        <span className="hab-emoji hab-emoji-vivo" aria-hidden>
          🧠
        </span>
        <div>
          <h2>{nombreCorto(a.que)}</h2>
          <p className="hab-cuando">Nadie le está escribiendo el código: lo hace él</p>
        </div>
      </div>
      {a.pedido && (
        <blockquote className="hab-pedido">
          <p>«{a.pedido.length > 180 ? `${a.pedido.slice(0, 178)}…` : a.pedido}»</p>
          <footer>{a.canal ? CANAL[a.canal] : 'lo que le pidieron'}</footer>
        </blockquote>
      )}
      <ol className="hab-etapas">
        {ETAPAS.map((e, i) => (
          <li key={e.id} data-estado={i < etapa ? 'hecha' : i === etapa ? 'ahora' : 'falta'}>
            <i aria-hidden>{i < etapa ? '✓' : i + 1}</i>
            {e.label}
          </li>
        ))}
      </ol>
      <ol className="hab-pasos">
        {pasos.map((p, i) => (
          <li key={`${p.ts}-${i}`} className={p === ultimo ? 'ahora' : ''}>
            <span>{hora(p.ts)}</span>
            {p.texto.length > 140 ? `${p.texto.slice(0, 138)}…` : p.texto}
          </li>
        ))}
        {ultimo && /^Pienso/.test(ultimo.texto) && (
          <li className="ahora pensando">
            <span>{hora(ultimo.ts)}</span>
            {ultimo.texto}
          </li>
        )}
      </ol>
    </article>
  )
}

/* ------------------------------------------------------------------ */
/* Autonomía: cifras                                                    */
/* ------------------------------------------------------------------ */

function Autonomia({
  tiene,
  solas,
  releases,
  fw,
  quien,
  ahora,
}: {
  tiene: Habilidad[]
  solas: Habilidad[]
  releases: Release[]
  fw: string | null
  quien: Autoria | null
  ahora: number
}) {
  const equipo = releases[0]
  const corrioSolo = fw && equipo ? cmpSemver(fw, equipo.version) > 0 : false
  const desde = equipo?.date ? Date.parse(equipo.date) : undefined
  const tiempos = solas.filter((h) => h.inicio && h.cuando && !h.aprox).map((h) => h.cuando! - h.inicio!)
  const promedio = tiempos.length ? tiempos.reduce((s, t) => s + t, 0) / tiempos.length : undefined
  const totalCodigo = quien ? quien.equipo + quien.solo : 0
  const pct = quien && totalCodigo ? Math.round((quien.solo / totalCodigo) * 100) : null

  return (
    <article className="card glass hab-auto">
      <p className="eyebrow">Autonomía</p>
      <p className="hab-cifra">
        {solas.length}
        <span> de {tiene.length}</span>
      </p>
      <p className="hab-cifra-s">habilidades las aprendió solo, escribiendo su propio código</p>

      <ul className="hab-datos">
        <li>
          <span className="hab-dato-t">Su código</span>
          {pct !== null ? (
            <>
              <span className="hab-dato-v">{pct} % lo escribió él</span>
              <span
                className="hab-barra"
                role="img"
                aria-label={`${quien!.solo} líneas de Python las escribió él y ${quien!.equipo} el equipo`}
                style={{ '--p': `${(quien!.solo / totalCodigo) * 100}%` } as React.CSSProperties}
              >
                <i />
                <i />
              </span>
              <span className="hab-dato-s">
                <i className="k k-solo" aria-hidden /> {quien!.solo.toLocaleString('es-CL')} líneas suyas
                <i className="k k-equipo" aria-hidden /> {quien!.equipo.toLocaleString('es-CL')} del equipo
              </span>
            </>
          ) : (
            <span className="hab-dato-s">Se cuenta cuando llega su código (conéctate al relé con la clave del equipo).</span>
          )}
        </li>
        {corrioSolo && desde && (
          <li>
            <span className="hab-dato-t">El equipo no toca su código desde</span>
            <span className="hab-dato-v">
              las {hora(desde)} <small>({hace(desde, ahora)})</small>
            </span>
            <span className="hab-dato-s">
              Desde la v{equipo!.version} hasta la v{fw}, cada versión la escribió él.
            </span>
          </li>
        )}
        {promedio !== undefined && (
          <li>
            <span className="hab-dato-t">Aprende algo nuevo en</span>
            <span className="hab-dato-v">{duracion(promedio)}</span>
            <span className="hab-dato-s">en promedio, desde que se lo piden hasta que funciona</span>
          </li>
        )}
      </ul>
    </article>
  )
}

/* ------------------------------------------------------------------ */
/* Gráfico: lo que sabe hacer, hora a hora                              */
/* ------------------------------------------------------------------ */

const C_EQUIPO = '#3a6fd8'
const C_SOLO = '#f0a000'

/** Ancho real del contenedor, para dibujar el gráfico en píxeles (el texto no se deforma). */
function useAncho() {
  const [w, setW] = useState(0)
  const ro = useRef<ResizeObserver | null>(null)
  const ref = useCallback((el: HTMLElement | null) => {
    ro.current?.disconnect()
    if (!el) return
    ro.current = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)))
    ro.current.observe(el)
  }, [])
  return [ref, w] as const
}

function Crecimiento({ habilidades, ahora, aprendiendo }: { habilidades: Habilidad[]; ahora: number; aprendiendo: Aprendizaje | null }) {
  const [ref, W] = useAncho()
  const [hover, setHover] = useState<{ x: number; t: number; h?: Habilidad } | null>(null)
  const [tabla, setTabla] = useState(false)
  const puntos = habilidades.filter((h) => h.cuando).sort((a, b) => a.cuando! - b.cuando!)
  const sinHora = habilidades.length - puntos.length

  const H = W < 560 ? 220 : 260
  const M = { t: 30, r: W < 560 ? 64 : 132, b: 28, l: 34 }
  const iw = Math.max(10, W - M.l - M.r)
  const ih = H - M.t - M.b

  if (!puntos.length)
    return (
      <article className="card glass hab-graf">
        <header className="card-head">
          <div>
            <h2>Lo que sabe hacer, hora a hora</h2>
            <p>Todavía no hay horas registradas.</p>
          </div>
        </header>
        <div className="hab-graf-lienzo" ref={ref} />
      </article>
    )

  const t0 = puntos[0].cuando! - 30 * 60_000
  const t1 = Math.max(ahora, puntos[puntos.length - 1].cuando!) + 10 * 60_000
  const x = (t: number) => M.l + ((t - t0) / (t1 - t0)) * iw
  const total = puntos.length
  const yMax = Math.max(4, Math.ceil((total + 1) / 2) * 2)
  const y = (n: number) => M.t + ih - (n / yMax) * ih
  const cuenta = (t: number) => {
    let e = 0
    let s = 0
    for (const p of puntos) if (p.cuando! <= t) p.origen === 'solo' ? s++ : e++
    return { e, s }
  }

  // Escalones: cada habilidad suma uno en su hora.
  const pasosE: [number, number][] = [[t0, 0]]
  const pasosT: [number, number][] = [[t0, 0]]
  let e = 0
  let s = 0
  for (const p of puntos) {
    const t = p.cuando!
    if (p.origen === 'solo') s++
    else e++
    pasosE.push([t, e])
    pasosT.push([t, e + s])
  }
  const linea = (pts: [number, number][]) => {
    let d = ''
    pts.forEach(([t, n], i) => {
      d += i === 0 ? `M${x(t)},${y(n)}` : `H${x(t)}V${y(n)}`
    })
    return `${d}H${x(ahora)}`
  }
  const dE = linea(pasosE)
  const dT = linea(pasosT)
  const areaE = `${dE}V${y(0)}H${x(t0)}Z`
  // La banda de lo que aprendió solo: entre el total (arriba) y lo del equipo (abajo), de vuelta por los escalones.
  let vuelta = `V${y(e)}`
  for (let i = pasosE.length - 1; i >= 1; i--) vuelta += `H${x(pasosE[i][0])}V${y(pasosE[i - 1][1])}`
  const bandaS = `${dT}${vuelta}H${x(t0)}Z`

  // Marcas del eje x: cada 1, 2, 3 o 6 h según el ancho.
  const horas = (t1 - t0) / 3_600_000
  const cada = [1, 2, 3, 6, 12].find((c) => horas / c <= Math.max(3, Math.floor(iw / 90))) ?? 12
  const ticks: number[] = []
  const primero = new Date(t0)
  primero.setMinutes(0, 0, 0)
  for (let t = primero.getTime() + 3_600_000; t < t1; t += 3_600_000) if (new Date(t).getHours() % cada === 0) ticks.push(t)
  const yTicks = Array.from({ length: yMax / 2 + 1 }, (_, i) => i * 2)

  // Desde cuándo puede aprender solo (la habilidad "aprender" del equipo).
  const hito = puntos.find((p) => p.id === 'aprender')
  const ultimaSola = [...puntos].reverse().find((p) => p.origen === 'solo')
  const fin = cuenta(ahora)

  const mover = (ev: React.PointerEvent<SVGSVGElement>) => {
    const r = ev.currentTarget.getBoundingClientRect()
    const px = ev.clientX - r.left
    if (px < M.l || px > M.l + iw + 8) return setHover(null)
    const t = t0 + ((px - M.l) / iw) * (t1 - t0)
    // La habilidad más cercana, si está a menos de 14 px.
    let cerca: Habilidad | undefined
    let dmin = 14
    for (const p of puntos) {
      const d = Math.abs(x(p.cuando!) - px)
      if (d < dmin) {
        dmin = d
        cerca = p
      }
    }
    setHover({ x: cerca ? x(cerca.cuando!) : px, t: cerca ? cerca.cuando! : Math.min(t, ahora), h: cerca })
  }

  const hc = hover ? cuenta(hover.t) : null
  const resumen = `De ${hora(t0 + 30 * 60_000)} a ${hora(ahora)} pasó de 1 a ${fin.e + fin.s} habilidades: ${fin.e} se las programó el equipo y ${fin.s} las aprendió solo.`

  return (
    <article className="card glass hab-graf">
      <header className="card-head">
        <div>
          <h2>Lo que sabe hacer, hora a hora</h2>
          <p>Cada escalón es una habilidad nueva. Las amarillas las aprendió solo: nadie le escribió ese código.</p>
        </div>
        <div className="hab-leyenda" aria-label="Leyenda">
          <span>
            <i className="k k-solo" aria-hidden /> Aprendió solo
          </span>
          <span>
            <i className="k k-equipo" aria-hidden /> Se las programó el equipo
          </span>
        </div>
      </header>

      <div className="hab-graf-lienzo" ref={ref}>
        {W > 0 && (
          <svg width={W} height={H} role="img" aria-label={resumen} onPointerMove={mover} onPointerLeave={() => setHover(null)}>
            {yTicks.map((n) => (
              <g key={n}>
                <line x1={M.l} x2={M.l + iw} y1={y(n)} y2={y(n)} className="g-grid" />
                <text x={M.l - 8} y={y(n)} dy="0.32em" textAnchor="end" className="g-tick">
                  {n}
                </text>
              </g>
            ))}
            {ticks.map((t) => (
              <text key={t} x={x(t)} y={H - 8} textAnchor="middle" className="g-tick">
                {hora(t)}
              </text>
            ))}

            {hito && (
              <g className="g-hito">
                <line x1={x(hito.cuando!)} x2={x(hito.cuando!)} y1={M.t - 14} y2={y(0)} />
                {/* Si la línea queda a la derecha, el rótulo va a su izquierda para no salirse. */}
                <text x={x(hito.cuando!) + (x(hito.cuando!) > M.l + iw * 0.55 ? -6 : 6)} y={M.t - 6} textAnchor={x(hito.cuando!) > M.l + iw * 0.55 ? 'end' : 'start'}>
                  {W < 560 ? 'Aprende solo desde aquí' : 'Desde aquí puede aprender solo'}
                </text>
              </g>
            )}

            <path d={areaE} fill={C_EQUIPO} fillOpacity={0.1} />
            <path d={bandaS} fill={C_SOLO} fillOpacity={0.28} />
            <path d={dE} fill="none" stroke={C_EQUIPO} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            <path d={dT} fill="none" stroke={C_SOLO} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

            {/* ahora */}
            <line x1={x(ahora)} x2={x(ahora)} y1={M.t} y2={y(0)} className="g-ahora" />
            {aprendiendo && (
              <g className="g-vivo">
                <circle cx={x(ahora)} cy={y(fin.e + fin.s + 1)} r={5} fill={C_SOLO} />
                {W >= 560 && (
                  <text x={x(ahora) - 8} y={y(fin.e + fin.s + 1)} dy="0.32em" textAnchor="end">
                    aprendiendo…
                  </text>
                )}
              </g>
            )}

            {puntos.map((p) => {
              const c = cuenta(p.cuando!)
              const cy = p.origen === 'solo' ? y(c.e + c.s) : y(c.e)
              return (
                <circle
                  key={p.id}
                  cx={x(p.cuando!)}
                  cy={cy}
                  r={p.origen === 'solo' ? 5 : 4}
                  fill={p.aprox ? '#fbf7f4' : p.origen === 'solo' ? C_SOLO : C_EQUIPO}
                  stroke={p.aprox ? C_SOLO : '#fbf7f4'}
                  strokeWidth={2}
                  className={hover?.h === p ? 'g-punto activo' : 'g-punto'}
                />
              )
            })}

            {/* rótulos directos al final de cada banda */}
            <text x={x(ahora) + 8} y={y(fin.e + fin.s)} dy="0.32em" className="g-fin">
              <tspan className="g-fin-n">{fin.e + fin.s}</tspan> {W < 560 ? '' : 'en total'}
            </text>
            {fin.s > 0 && (
              <text x={x(ahora) + 8} y={(y(fin.e) + y(fin.e + fin.s)) / 2 + (W < 560 ? 0 : 8)} dy="0.32em" className="g-fin g-fin-s">
                {fin.s} {W < 560 ? 'solo' : fin.s === 1 ? 'aprendida sola' : 'aprendidas solo'}
              </text>
            )}
            {ultimaSola && !hover && !aprendiendo && W >= 560 && (
              <text x={x(ultimaSola.cuando!) - 8} y={y(cuenta(ultimaSola.cuando!).e + cuenta(ultimaSola.cuando!).s) - 12} textAnchor="end" className="g-rotulo">
                {ultimaSola.nombre} · {hora(ultimaSola.cuando)}
              </text>
            )}

            {hover && (
              <line x1={hover.x} x2={hover.x} y1={M.t} y2={y(0)} className="g-cruz" />
            )}
          </svg>
        )}
        {hover && hc && (
          <div className="hab-tip" style={{ left: Math.min(Math.max(hover.x, 120), W - 120) }} role="status">
            {hover.h ? (
              <>
                <p className="hab-tip-t">
                  {hover.h.icono} {hover.h.nombre}
                </p>
                <p>
                  {hover.h.origen === 'solo' ? 'La aprendió solo' : 'Se la programó el equipo'} · {hover.h.aprox ? 'antes de las ' : ''}
                  {hora(hover.h.cuando)}
                </p>
              </>
            ) : (
              <p className="hab-tip-t">{hora(hover.t)}</p>
            )}
            <p className="hab-tip-s">
              <i className="k k-solo" aria-hidden /> {hc.s} solo <i className="k k-equipo" aria-hidden /> {hc.e} del equipo
            </p>
          </div>
        )}
      </div>

      <div className="hab-graf-pie">
        {sinHora > 0 && <span>{sinHora} sin hora registrada no aparecen en el gráfico.</span>}
        {puntos.some((p) => p.aprox) && <span>Los puntos huecos son «a más tardar»: no quedó la hora exacta.</span>}
        <button type="button" className="btn-link" onClick={() => setTabla((v) => !v)} aria-expanded={tabla}>
          {tabla ? 'Ocultar tabla' : 'Ver como tabla'}
        </button>
      </div>
      {tabla && (
        <table className="hab-tabla">
          <thead>
            <tr>
              <th>Hora</th>
              <th>Habilidad</th>
              <th>Quién</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {puntos.map((p) => {
              const c = cuenta(p.cuando!)
              return (
                <tr key={p.id}>
                  <td>
                    {p.aprox ? '≤ ' : ''}
                    {hora(p.cuando)}
                  </td>
                  <td>{p.nombre}</td>
                  <td>{p.origen === 'solo' ? 'Él solo' : 'Equipo'}</td>
                  <td>
                    {c.e + c.s} ({c.s} solo)
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </article>
  )
}

/* ------------------------------------------------------------------ */
/* Qué sabe hacer                                                       */
/* ------------------------------------------------------------------ */

function Lista({ habilidades, ahora, fw }: { habilidades: Habilidad[]; ahora: number; fw: string | null }) {
  const orden = (a: Habilidad, b: Habilidad) => (b.cuando ?? 0) - (a.cuando ?? 0)
  const solas = habilidades.filter((h) => h.origen === 'solo').sort(orden)
  const delEquipo = habilidades.filter((h) => h.origen === 'equipo').sort(orden)
  const n = habilidades.filter((h) => h.presente).length
  return (
    <article className="card glass hab-lista">
      <header className="card-head">
        <div>
          <h2>Qué sabe hacer</h2>
          <p>
            {n} habilidades{fw ? ` en la v${fw}` : ''}. Pídeselas con palabras, empezando por «bicho».
          </p>
        </div>
      </header>
      <Grupo titulo="Lo aprendió solo" sub="Escribió el código, se lo instaló y lo probó" lista={solas} ahora={ahora} fw={fw} />
      <Grupo titulo="Se lo programó el equipo" sub="Lo que traía de fábrica" lista={delEquipo} ahora={ahora} fw={fw} />
    </article>
  )
}

function Grupo({ titulo, sub, lista, ahora, fw }: { titulo: string; sub: string; lista: Habilidad[]; ahora: number; fw: string | null }) {
  if (!lista.length) return null
  return (
    <div className="hab-grupo">
      <p className="hab-grupo-t">
        {titulo} <span>{lista.filter((h) => h.presente).length}</span>
        <small>{sub}</small>
      </p>
      <ul className="hab-cards">
        {lista.map((h) => {
          const nueva = h.presente && h.origen === 'solo' && h.cuando && !h.aprox && ahora - h.cuando < 30 * 60_000
          return (
            <li key={h.id} className={`hab-card hab-${h.origen}${h.presente ? '' : ' hab-borrada'}${nueva ? ' hab-nueva' : ''}`}>
              <span className="hab-card-emoji" aria-hidden>
                {h.icono}
              </span>
              <div className="hab-card-cuerpo">
                <p className="hab-card-nombre">
                  {h.nombre}
                  {nueva && <span className="tag tag-new">Nueva</span>}
                </p>
                {h.que_hace && <p className="hab-card-que">{h.que_hace}</p>}
                {h.pidele && <p className="hab-card-pide">«{h.pidele}»</p>}
                {h.comandos.length > 0 && (
                  <p className="hab-cmds">
                    {h.comandos.map((c) => (
                      <code key={c}>{c}</code>
                    ))}
                  </p>
                )}
                <p className="hab-card-pie">
                  {!h.presente
                    ? `Se le borró: el bicho volvió a la v${fw}`
                    : [h.cuando ? `${h.aprox ? 'antes de las' : 'a las'} ${hora(h.cuando)}` : '', h.version ? `v${h.version}` : '', h.origen === 'solo' && h.inicio && h.cuando && !h.aprox ? `tardó ${duracion(h.cuando - h.inicio)}` : '']
                        .filter(Boolean)
                        .join(' · ')}
                </p>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
