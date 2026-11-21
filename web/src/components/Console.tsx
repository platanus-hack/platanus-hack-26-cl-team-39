import { useEffect, useRef, useState } from 'react'
import type { LineDir } from '../lib/links'
import { CMD } from '../lib/protocol'
import { Icon } from './ui'

export type ConsoleLine = { id: number; dir: LineDir; text: string; at: number }

export function Console({
  lines,
  onSend,
  onClear,
  connected,
  linkLabel,
}: {
  lines: ConsoleLine[]
  onSend: (l: string) => void
  onClear: () => void
  connected: boolean
  linkLabel: string
}) {
  const [hideFrames, setHideFrames] = useState(true)
  const [input, setInput] = useState('')
  const [history, setHistory] = useState<string[]>([])
  const [hIdx, setHIdx] = useState(-1)
  const [copied, setCopied] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const stick = useRef(true)

  const shown = hideFrames ? lines.filter((l) => !(l.dir === 'in' && l.text.startsWith('{"t":"s"'))) : lines

  useEffect(() => {
    const el = box.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  }, [shown.length, lines])

  const send = (l: string) => {
    if (!l.trim()) return
    onSend(l)
    setHistory((h) => [l, ...h.filter((x) => x !== l)].slice(0, 30))
    setHIdx(-1)
    setInput('')
  }

  return (
    <section className="sec" id="consola" aria-label="Consola">
      <article className="card glass console-card">
        <header className="card-head">
          <div>
            <h2>Consola</h2>
            <p>{connected ? `Mensajes por ${linkLabel}` : 'Sin conexión'}</p>
          </div>
          <div className="head-actions">
            <button type="button" className="btn-secondary" disabled={!connected} onClick={() => send(CMD.info)}>
              <Icon.Send /> Pedir info
            </button>
          </div>
        </header>

        <div
          ref={box}
          className="console"
          role="log"
          aria-label="Consola del bicho"
          onScroll={(e) => {
            const el = e.currentTarget
            stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24
          }}
        >
          {shown.length === 0 && <div className="none">Sin mensajes todavía.</div>}
          {shown.map((l) => (
            <div key={l.id} className={`line line-${l.dir}`}>
              <span className="t">{new Date(l.at).toLocaleTimeString('es-CL', { hour12: false })}</span>
              <span className="d">{l.dir === 'out' ? '→' : l.dir === 'sys' ? '•' : '←'}</span>
              <span className="m">{l.text}</span>
            </div>
          ))}
        </div>

        <div className="cmd-row">
          <input
            className="field"
            value={input}
            disabled={!connected}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') send(input)
              if (e.key === 'ArrowUp' && history.length) {
                const i = Math.min(history.length - 1, hIdx + 1)
                setHIdx(i)
                setInput(history[i])
                e.preventDefault()
              }
              if (e.key === 'ArrowDown') {
                const i = hIdx - 1
                setHIdx(Math.max(-1, i))
                setInput(i >= 0 ? history[i] : '')
                e.preventDefault()
              }
            }}
            placeholder={connected ? 'Comando para el bicho, JSON o texto' : 'Conecta el bicho para mandar comandos'}
            aria-label="Comando para el bicho"
          />
          <button type="button" className="btn-secondary" disabled={!connected} onClick={() => send(CMD.reboot)} title="Reiniciar el bicho">
            <Icon.Power /> Reiniciar
          </button>
        </div>

        <footer className="console-foot">
          <div className="legend">
            <span>
              <b className="k-in">←</b> del bicho
            </span>
            <span>
              <b className="k-out">→</b> al bicho
            </span>
            <span>
              <b className="k-sys">•</b> sistema
            </span>
          </div>
          <div className="head-actions">
            <button type="button" className="switch" role="switch" aria-checked={hideFrames} onClick={() => setHideFrames((v) => !v)}>
              <span /> Ocultar lecturas
            </button>
            <button
              type="button"
              className="btn-link"
              disabled={!shown.length}
              onClick={() => {
                const text = shown.map((l) => `${new Date(l.at).toLocaleTimeString('es-CL', { hour12: false })} ${l.dir === 'out' ? '→' : l.dir === 'sys' ? '•' : '←'} ${l.text}`).join('\n')
                navigator.clipboard?.writeText(text).then(() => {
                  setCopied(true)
                  setTimeout(() => setCopied(false), 1500)
                })
              }}
            >
              {copied ? 'Copiado' : 'Copiar'}
            </button>
            <button type="button" className="btn-link" onClick={onClear}>
              Limpiar
            </button>
          </div>
        </footer>
      </article>
    </section>
  )
}
