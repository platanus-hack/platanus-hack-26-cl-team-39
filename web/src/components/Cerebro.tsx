import { useRef, useState } from 'react'
import './cerebro.css'

/** Lo que el cerebro (cerebro/ en el repo) decide o hace. Lo reparte el relé. */
export type Evento = {
  id: string
  tipo: 'ignora' | 'responde' | 'comando' | 'aprende' | 'paso' | 'aprendido' | 'error' | 'decir'
  texto: string
  ts?: number
  frase?: string
  oido?: string
  angulo?: number | null
  trabajo?: string
  version?: string | null
  /** Lo escribió esta web y el relé todavía no confirma que lo recibió. */
  pendiente?: boolean
  /** Lo dijo en voz alta, con esa voz (ElevenLabs). */
  voz?: 'dueno' | 'extrano'
  /** De dónde vino lo que se le dijo ("app": la app de voz del teléfono). */
  canal?: string
  /** En "aprendido": la habilidad nueva, con nombre corto, cómo pedírsela y sus comandos. */
  habilidad?: { nombre?: string; pidele?: string; comandos?: string[] }
}

export type Imagen = { nombre: string; url: string; ts: number }

const ETIQUETA: Record<Evento['tipo'], string> = {
  ignora: 'No era para mí',
  responde: 'Responde',
  comando: 'Hace',
  aprende: 'Va a aprender',
  paso: 'Aprendiendo',
  aprendido: 'Aprendió',
  error: 'Problema',
  decir: 'Le escribieron',
}

const VOZ: Record<NonNullable<Evento['voz']>, string> = { dueno: 'voz del dueño', extrano: 'voz para extraños' }

// Dictado del navegador (Chrome, Edge, Safari): le hablas al bicho desde el micrófono del computador o del
// teléfono, cerca de la boca, en vez del ReSpeaker que oye toda la sala. Lo dictado llega como si lo escribieras.
type Reconocedor = {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null
  onend: (() => void) | null
  onerror: ((e: { error: string }) => void) | null
  start: () => void
  stop: () => void
}
const ClaseReconocedor = (() => {
  const w = typeof window !== 'undefined' ? (window as unknown as Record<string, unknown>) : {}
  return (w.SpeechRecognition ?? w.webkitSpeechRecognition) as (new () => Reconocedor) | undefined
})()

const hora = (ts?: number) => (ts ? new Date(ts).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '')

export function Cerebro({
  eventos,
  imagenes,
  voces,
  vozAqui,
  onVozAqui,
  connected,
  sinBicho,
  motivo,
  onReconectar,
  onDecir,
}: {
  eventos: Evento[]
  imagenes: Imagen[]
  /** Audio de lo que dijo en voz alta, por id del evento. */
  voces: Record<string, string>
  /** Si su voz también suena en este computador. */
  vozAqui: boolean
  onVozAqui: (v: boolean) => void
  connected: boolean
  /** El relé está, pero el bicho (la Raspberry) no está conectado a él. */
  sinBicho?: boolean
  /** Por qué no se le puede escribir ahora (null si se puede). */
  motivo: string | null
  /** Si volver a conectar lo arregla (por ejemplo, la clave cambió). */
  onReconectar?: () => void
  onDecir: (texto: string) => void
}) {
  const puedeMandar = !motivo
  const [texto, setTexto] = useState('')
  const [verIgnoradas, setVerIgnoradas] = useState(false)
  const lista = [...eventos].reverse().filter((e) => verIgnoradas || e.tipo !== 'ignora')
  const ignoradas = eventos.filter((e) => e.tipo === 'ignora').length
  const aprendiendo = (() => {
    const ultimo = [...eventos].reverse().find((e) => e.tipo === 'paso' || e.tipo === 'aprendido' || e.tipo === 'error')
    return ultimo?.tipo === 'paso'
  })()
  const vista = [...imagenes].sort((a, b) => b.ts - a.ts)

  const [dictando, setDictando] = useState(false)
  const [errorVoz, setErrorVoz] = useState<string | null>(null)
  const reconocedor = useRef<Reconocedor | null>(null)
  const dictar = () => {
    if (!ClaseReconocedor) return
    if (dictando) {
      reconocedor.current?.stop()
      return
    }
    const r = new ClaseReconocedor()
    r.lang = 'es-CL'
    r.interimResults = true
    r.continuous = false
    let final = ''
    r.onresult = (e) => {
      let parcial = ''
      for (let i = 0; i < e.results.length; i++) {
        const res = e.results[i]
        if (res.isFinal) final += res[0].transcript
        else parcial += res[0].transcript
      }
      setTexto((final + parcial).trim())
    }
    r.onerror = (e) => setErrorVoz(e.error === 'not-allowed' ? 'El navegador no dio permiso para usar el micrófono' : e.error === 'no-speech' ? 'No te escuché: intenta de nuevo, más cerca' : `Falló el dictado (${e.error})`)
    r.onend = () => {
      setDictando(false)
      reconocedor.current = null
      const t = final.trim()
      if (t) {
        onDecir(t)
        setTexto('')
      }
    }
    setErrorVoz(null)
    setTexto('')
    reconocedor.current = r
    setDictando(true)
    r.start()
  }

  const mandar = () => {
    const t = texto.trim()
    if (!t) return
    onDecir(t)
    setTexto('')
  }

  return (
    <section className="sec" id="cerebro" aria-label="Cerebro">
      <article className="card glass cerebro">
        <header className="card-head">
          <div>
            <h2>Cerebro</h2>
            <p>Qué decide con lo que oye, qué hace y qué aprende · Claude Fable 5.2</p>
          </div>
          <div className="cerebro-estado">
            <button
              type="button"
              className="capsule"
              aria-pressed={vozAqui}
              onClick={() => onVozAqui(!vozAqui)}
              title="Cuando el bicho hable, que su voz suene también en este computador (por si su parlante falla)"
            >
              Voz aquí <b>{vozAqui ? 'sí' : 'no'}</b>
            </button>
            <span className={`live ${aprendiendo ? '' : 'idle'}`}>
              <i className="live-dot" aria-hidden />
              {aprendiendo ? 'Aprendiendo…' : 'Atento'}
            </span>
          </div>
        </header>

        <div className="cerebro-cuerpo">
          <div className="cerebro-col">
            <form
              className="cerebro-decir"
              onSubmit={(e) => {
                e.preventDefault()
                mandar()
              }}
            >
              <input
                className="field"
                value={texto}
                onChange={(e) => setTexto(e.target.value)}
                disabled={!connected || !puedeMandar}
                placeholder={!connected ? 'Conecta el bicho para escribirle' : (motivo ?? 'Escríbele al bicho, como si le hablaras')}
                aria-label="Escríbele al bicho"
              />
              <button type="submit" className="btn-secondary" disabled={!connected || !puedeMandar || !texto.trim()}>
                Decir
              </button>
              {ClaseReconocedor && (
                <button
                  type="button"
                  className={`btn-secondary cerebro-voz${dictando ? ' activo' : ''}`}
                  onClick={dictar}
                  disabled={!connected || !puedeMandar}
                  aria-pressed={dictando}
                  title="Háblale con el micrófono de este equipo, cerca de la boca: no depende del micrófono del bicho"
                >
                  {dictando ? 'Escuchando… (toca para terminar)' : '🎤 Hablarle'}
                </button>
              )}
            </form>
            {errorVoz && (
              <p className="cerebro-aviso" role="status">
                {errorVoz}.
              </p>
            )}
            {connected && motivo && (
              <p className="cerebro-aviso" role="status">
                {motivo}.
                {onReconectar && (
                  <button type="button" onClick={onReconectar}>
                    Volver a conectar
                  </button>
                )}
              </p>
            )}

            {connected && sinBicho && (
              <p className="cerebro-aviso" role="status">
                El bicho no está conectado: está apagado o sin internet. Puedes escribirle y conversa igual, pero no va a moverse, ver ni oír hasta que vuelva.
              </p>
            )}

            {lista.length === 0 ? (
              <div className="empty">
                <p className="empty-t">Todavía no decide nada</p>
                <p className="empty-s">Háblale o escríbele al bicho. Acá aparece qué entendió, qué hizo y, si no sabía hacerlo, cómo lo aprende.</p>
              </div>
            ) : (
              <ol className="cerebro-eventos">
                {lista.map((e) => (
                  <li key={e.id} className={`ev ev-${e.tipo}${e.pendiente ? ' ev-pendiente' : ''}`}>
                    <span className="ev-tipo">{e.pendiente ? 'Enviando…' : e.voz ? 'Dice' : (ETIQUETA[e.tipo] ?? e.tipo)}</span>
                    <div className="ev-cuerpo">
                      {e.oido && <p className="ev-oido">«{e.oido}»{typeof e.angulo === 'number' ? ` · ${e.angulo}°` : ''}</p>}
                      <p className="ev-texto">{e.texto}</p>
                      {e.voz && (
                        <div className={`ev-voz ev-voz-${e.voz}`}>
                          <span>En voz alta · {VOZ[e.voz]}</span>
                          {voces[e.id] ? <audio controls preload="none" src={voces[e.id]} /> : <small>preparando el audio…</small>}
                        </div>
                      )}
                    </div>
                    <span className="ev-hora">{hora(e.ts)}</span>
                  </li>
                ))}
              </ol>
            )}
            {ignoradas > 0 && (
              <button type="button" className="cerebro-ign" onClick={() => setVerIgnoradas((v) => !v)}>
                {verIgnoradas ? 'Ocultar' : 'Ver'} las {ignoradas} frases que no eran para él
              </button>
            )}
          </div>

          <figure className="cerebro-vista">
            {vista.length === 0 ? (
              <div className="vista-vacia">
                <p className="empty-t">Sin vista</p>
                <p className="empty-s">Cuando el bicho aprenda a usar una cámara, lo que ve aparece acá.</p>
              </div>
            ) : (
              vista.map((v) => (
                <div key={v.nombre} className="vista-img">
                  <img src={v.url} alt={`Lo que ve el bicho (${v.nombre})`} />
                  <figcaption>
                    {v.nombre} · {hora(v.ts)}
                  </figcaption>
                </div>
              ))
            )}
          </figure>
        </div>
      </article>
    </section>
  )
}
