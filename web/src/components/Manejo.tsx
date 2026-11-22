import { useCallback, useEffect, useRef, useState } from 'react'
import './manejo.css'

/**
 * Manejo: flechas para mover el bicho mientras se mantienen apretadas, velocidad y freno, más acciones rápidas
 * (giro completo, sonidos, luces, foto). Los comandos van al bicho igual que los de la consola (por el relé,
 * con la clave del equipo). Teclado: flechas para moverse, barra espaciadora para frenar.
 */
type Dir = 'adelante' | 'atras' | 'izquierda' | 'derecha'

const PARAR = JSON.stringify({ cmd: 'motores', on: false })
const mover = (d: Dir, pot: number) =>
  JSON.stringify(
    d === 'adelante'
      ? { cmd: 'motores', on: true, pot, seg: 0 }
      : d === 'atras'
        ? { cmd: 'motores', on: true, sentido: -1, pot, seg: 0 }
        : { cmd: 'motores', giro: d, pot, seg: 0 },
  )
const sonido = (estado: string) => JSON.stringify({ cmd: 'expresar', estado, seg: 2 })

const ACCIONES: { nombre: string; lineas: (pot: number) => string[] }[] = [
  { nombre: '↻ Giro completo', lineas: () => [PARAR, JSON.stringify({ cmd: 'motores', giro: 'derecha', pot: 70, seg: 2.5 }), sonido('contento')] },
  { nombre: '👋 Hola', lineas: () => [sonido('hola')] },
  { nombre: '😄 Contento', lineas: () => [sonido('contento')] },
  { nombre: '🤩 Emocionado', lineas: () => [sonido('emocionado')] },
  { nombre: '🌈 Arcoíris', lineas: () => [JSON.stringify({ cmd: 'anillo', efecto: 'arcoiris', brillo: 200, seg: 6 })] },
  { nombre: '📷 Foto', lineas: () => [JSON.stringify({ cmd: 'foto' })] },
]

const TECLAS: Record<string, Dir> = { ArrowUp: 'adelante', ArrowDown: 'atras', ArrowLeft: 'izquierda', ArrowRight: 'derecha' }

export function Manejo({ conectado, motivo, enviar }: { conectado: boolean; motivo: string | null; enviar: (linea: string) => void }) {
  const decir = (texto: string) => enviar(JSON.stringify({ t: 'cerebro', id: crypto.randomUUID(), tipo: 'decir', texto, ts: Date.now() }))
  const [pot, setPot] = useState(50)
  const [activo, setActivo] = useState<Dir | null>(null)
  const activoRef = useRef<Dir | null>(null)
  const puede = conectado && !motivo

  const parar = useCallback(() => {
    activoRef.current = null
    setActivo(null)
    enviar(PARAR)
  }, [enviar])

  const empezar = useCallback(
    (d: Dir) => {
      if (!puede || activoRef.current === d) return
      activoRef.current = d
      setActivo(d)
      enviar(PARAR) // el bicho no acepta un movimiento encima de otro
      enviar(mover(d, pot))
    },
    [enviar, pot, puede],
  )

  // Teclado: mantener una flecha mueve; soltarla frena. Espacio frena siempre.
  useEffect(() => {
    if (!puede) return
    const enCampo = (e: KeyboardEvent) => e.target instanceof HTMLElement && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)
    const abajo = (e: KeyboardEvent) => {
      if (enCampo(e)) return
      if (e.code === 'Space') {
        e.preventDefault()
        parar()
      } else if (TECLAS[e.key] && !e.repeat) {
        e.preventDefault()
        empezar(TECLAS[e.key])
      }
    }
    const arriba = (e: KeyboardEvent) => {
      if (TECLAS[e.key] && activoRef.current === TECLAS[e.key]) parar()
    }
    window.addEventListener('keydown', abajo)
    window.addEventListener('keyup', arriba)
    window.addEventListener('blur', parar)
    return () => {
      window.removeEventListener('keydown', abajo)
      window.removeEventListener('keyup', arriba)
      window.removeEventListener('blur', parar)
    }
  }, [empezar, parar, puede])

  const flecha = (d: Dir, etiqueta: string, simbolo: string) => (
    <button
      type="button"
      className={`manejo-flecha manejo-${d}${activo === d ? ' activo' : ''}`}
      aria-label={etiqueta}
      aria-pressed={activo === d}
      disabled={!puede}
      onPointerDown={(e) => {
        e.currentTarget.setPointerCapture(e.pointerId)
        empezar(d)
      }}
      onPointerUp={parar}
      onPointerCancel={parar}
      onContextMenu={(e) => e.preventDefault()}
    >
      {simbolo}
    </button>
  )

  return (
    <section className="sec" id="manejo" aria-label="Manejo">
      <article className="card glass manejo">
        <header className="card-head">
          <div>
            <h2>Manejo</h2>
            <p>Mantén apretada una flecha para moverlo; al soltarla frena. También con las flechas del teclado y la barra espaciadora.</p>
          </div>
        </header>
        {!puede && <p className="manejo-aviso">{motivo ?? 'Conecta el bicho para manejarlo'}.</p>}
        <div className="manejo-cuerpo">
          <div className="manejo-cruz">
            {flecha('adelante', 'Adelante', '▲')}
            {flecha('izquierda', 'Girar a la izquierda', '◀')}
            <button type="button" className="manejo-freno" onClick={parar} disabled={!conectado} aria-label="Frenar">
              FRENO
            </button>
            {flecha('derecha', 'Girar a la derecha', '▶')}
            {flecha('atras', 'Atrás', '▼')}
          </div>
          <div className="manejo-lado">
            <label className="manejo-vel" htmlFor="manejo-pot">
              <span>
                Velocidad <b>{pot} %</b>
              </span>
              <input id="manejo-pot" type="range" min={20} max={100} step={5} value={pot} onChange={(e) => setPot(Number(e.target.value))} />
            </label>
            <div className="manejo-acciones">
              <button type="button" className="btn-secondary" disabled={!puede} onClick={() => decir('preséntate')} title="Dice «Hola, soy el Bicho» con su voz de ElevenLabs">
                🗣️ Hola, soy el Bicho
              </button>
              {ACCIONES.map((a) => (
                <button key={a.nombre} type="button" className="btn-secondary" disabled={!puede} onClick={() => a.lineas(pot).forEach(enviar)}>
                  {a.nombre}
                </button>
              ))}
            </div>
          </div>
        </div>
      </article>
    </section>
  )
}
