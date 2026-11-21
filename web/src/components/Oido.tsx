import { useEffect, useState } from 'react'
import type { SensorStore } from '../lib/sensors'
import './oido.css'

/** Una frase que escuchó el bicho. La manda el relé: primero sin texto y después transcrita (mismo id). */
export type Frase = {
  id: string
  angulo: number | null
  dur: number
  ts?: number
  texto?: string | null
  estado?: 'transcribiendo' | 'listo' | 'vacio' | 'error' | 'sin-transcriptor'
  ms?: number
}

const R = 92 // radio del dial
const C = 120 // centro

/** Punto sobre el dial. 0° arriba y los grados crecen en el sentido del reloj. */
function punto(grados: number, radio: number): [number, number] {
  const a = ((grados - 90) * Math.PI) / 180
  return [C + radio * Math.cos(a), C + radio * Math.sin(a)]
}

/** Cuña de ±ancho grados alrededor del ángulo. */
function cuna(grados: number, ancho: number) {
  const [x1, y1] = punto(grados - ancho, R)
  const [x2, y2] = punto(grados + ancho, R)
  return `M${C} ${C} L${x1.toFixed(1)} ${y1.toFixed(1)} A${R} ${R} 0 0 1 ${x2.toFixed(1)} ${y2.toFixed(1)} Z`
}

const hora = (ts?: number) => (ts ? new Date(ts).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '')

function textoDe(f: Frase) {
  if (f.texto) return f.texto
  switch (f.estado) {
    case 'vacio':
      return 'No se entendió nada (ruido o voz muy baja).'
    case 'error':
      return 'Falló la transcripción.'
    case 'sin-transcriptor':
      return 'Se oyó algo, pero el relé no tiene configurado con qué transcribir.'
    case 'transcribiendo':
      return 'Transcribiendo…'
    default:
      return 'Se oyó algo. La transcripción llega solo por el relé.'
  }
}

export function Oido({ store, connected, frases }: { store: SensorStore; connected: boolean; frases: Frase[] }) {
  const [, setTick] = useState(0)
  useEffect(() => {
    const iv = setInterval(() => setTick((t) => t + 1), 100)
    return () => clearInterval(iv)
  }, [])

  const sA = store.series.get('oido.angulo')
  const sV = store.series.get('oido.voz')
  const vivo = connected && !!sA && performance.now() - sA.updatedAt < 1500
  const angulo = vivo && typeof sA!.last === 'number' ? sA!.last : null
  const voz = vivo && sV?.last === true
  const lista = [...frases].reverse()

  return (
    <section className="sec" id="oido" aria-label="Oído">
      <article className="card glass oido">
        <header className="card-head">
          <div>
            <h2>Oído</h2>
            <p>Lo que le dicen al bicho y desde qué ángulo · ReSpeaker XVF3800</p>
          </div>
          <span className={`live ${voz ? '' : 'idle'}`}>
            <i className="live-dot" aria-hidden />
            {!vivo ? 'Sin micrófono' : voz ? 'Alguien habla' : 'Silencio'}
          </span>
        </header>

        <div className="oido-cuerpo">
          <figure className="oido-dial" aria-label={angulo === null ? 'Sin dirección' : `La voz viene de ${angulo} grados`}>
            <svg viewBox="0 0 240 240" role="img">
              <circle cx={C} cy={C} r={R} className="oido-aro" />
              {Array.from({ length: 12 }, (_, i) => {
                const [x1, y1] = punto(i * 30, R)
                const [x2, y2] = punto(i * 30, R - (i % 3 === 0 ? 10 : 5))
                return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} className="oido-marca" />
              })}
              {[0, 90, 180, 270].map((g) => {
                const [x, y] = punto(g, R + 15)
                return (
                  <text key={g} x={x} y={y} className="oido-grado" textAnchor="middle" dominantBaseline="central">
                    {g}°
                  </text>
                )
              })}
              {/* de dónde vinieron las últimas frases: las más viejas, más tenues */}
              {frases.slice(-8).map((f, i, a) => {
                if (f.angulo === null) return null
                const [x, y] = punto(f.angulo, R)
                return <circle key={f.id} cx={x} cy={y} r={4.5} className="oido-rastro" style={{ opacity: 0.2 + (0.6 * (i + 1)) / a.length }} />
              })}
              {angulo !== null && <path d={cuna(angulo, 14)} className={`oido-cuna ${voz ? 'habla' : ''}`} />}
              <circle cx={C} cy={C} r={34} className="oido-centro" />
              <text x={C} y={C - 3} className="oido-valor" textAnchor="middle" dominantBaseline="central">
                {angulo === null ? '—' : `${angulo}°`}
              </text>
              <text x={C} y={C + 17} className="oido-sub" textAnchor="middle">
                {angulo === null ? 'sin dato' : voz ? 'voz' : 'último'}
              </text>
            </svg>
            <figcaption>0° es la marca de referencia del ReSpeaker; los grados crecen en el sentido del reloj.</figcaption>
          </figure>

          <div className="oido-frases">
            {lista.length === 0 ? (
              <div className="empty">
                <p className="empty-t">{vivo ? 'Todavía no le dicen nada' : 'Sin micrófono'}</p>
                <p className="empty-s">
                  {vivo
                    ? 'Háblale al bicho: cada frase aparece acá con el ángulo desde donde vino.'
                    : 'Conecta el bicho con el ReSpeaker enchufado por USB. El ángulo y las frases aparecen solos.'}
                </p>
              </div>
            ) : (
              <ol>
                {lista.map((f) => (
                  <li key={f.id} className={f.texto ? '' : 'pendiente'}>
                    <span className="oido-de" title={f.angulo === null ? 'Sin dirección' : `Desde ${f.angulo}°`}>
                      <svg viewBox="0 0 24 24" style={{ transform: `rotate(${f.angulo ?? 0}deg)` }} aria-hidden>
                        <path d="M12 3.5 17 14h-3.4v6.5h-3.2V14H7z" />
                      </svg>
                      <b>{f.angulo === null ? '—' : `${f.angulo}°`}</b>
                    </span>
                    <p>{textoDe(f)}</p>
                    <span className="oido-cuando">
                      {hora(f.ts)}
                      {f.dur ? ` · ${f.dur.toFixed(1)} s` : ''}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      </article>
    </section>
  )
}
