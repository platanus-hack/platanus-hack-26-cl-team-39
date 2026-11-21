import { useEffect, useRef, useState, type CSSProperties } from 'react'

/** Horarios de la Platanus Hack 26 (hora de Santiago). */
export const HACKATHON = {
  start: new Date('2026-11-20T18:00:00-03:00'),
  deadline: new Date('2026-11-22T09:00:00-03:00'),
}

/** Avisos al cruzar estos umbrales (minutos restantes). */
const ALERTS = [
  { min: 180, title: 'Quedan 3 horas para entregar', body: 'Buen momento para llenar platanus-hack-project.jsonc y project-description.md.' },
  { min: 60, title: 'Queda 1 hora para entregar', body: 'Congelen funcionalidades: demo, logo y README.' },
  { min: 15, title: 'Quedan 15 minutos', body: 'Hagan push de todo al repo del equipo.' },
]

function parts(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return { h, m, sec }
}

const pad = (n: number) => String(n).padStart(2, '0')

/** "domingo 22 a las 9:00", en hora de Santiago. */
function fmtWhen(d: Date) {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat('es-CL', { weekday: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit', hourCycle: 'h23', timeZone: 'America/Santiago' })
      .formatToParts(d)
      .map((x) => [x.type, x.value]),
  )
  return `${p.weekday} ${p.day} a las ${Number(p.hour)}:${p.minute}`
}

export function Countdown({ onAlert }: { onAlert?: (a: { title: string; body: string; urgent: boolean }) => void }) {
  const [now, setNow] = useState(() => Date.now())
  const prevLeft = useRef<number | null>(null)

  useEffect(() => {
    const iv = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(iv)
  }, [])

  const left = HACKATHON.deadline.getTime() - now
  const total = HACKATHON.deadline.getTime() - HACKATHON.start.getTime()
  const elapsed = Math.min(1, Math.max(0, (now - HACKATHON.start.getTime()) / total))

  // Avisar solo cuando se cruza un umbral con la web abierta (no al cargar)
  useEffect(() => {
    const prev = prevLeft.current
    prevLeft.current = left
    if (prev === null || !onAlert) return
    for (const a of ALERTS) {
      const t = a.min * 60_000
      if (prev > t && left <= t) onAlert({ title: a.title, body: a.body, urgent: a.min <= 60 })
    }
    if (prev > 0 && left <= 0) onAlert({ title: 'Se acabó el tiempo', body: 'La entrega cerró a las 9:00.', urgent: true })
  }, [left, onAlert])

  const level = left <= 0 ? 'over' : left <= 3_600_000 ? 'urgent' : left <= 6 * 3_600_000 ? 'soon' : 'ok'
  const notStarted = now < HACKATHON.start.getTime()
  const { h, m, sec } = parts(left)
  const when = fmtWhen(HACKATHON.deadline)

  return (
    <div className="clock" data-level={level} role="timer" aria-label="Tiempo para entregar el proyecto">
      <div className="clock-head">
        <span className="clock-label">Entrega del proyecto</span>
        {level === 'urgent' && <span className="clock-chip">¡Ya!</span>}
      </div>
      {level === 'over' ? (
        <p className="clock-time over">Tiempo cumplido</p>
      ) : (
        <p className="clock-time" aria-live="off">
          {h}
          <i>:</i>
          {pad(m)}
          <i>:</i>
          <small>{pad(sec)}</small>
        </p>
      )}
      <p className="clock-sub">{notStarted ? `Empieza el ${fmtWhen(HACKATHON.start)} · cierra el ${when}` : `Cierra el ${when}`}</p>
      <div className="clock-bar" title={`${Math.round(elapsed * 100)} % de la hackathon`}>
        <span style={{ '--p': elapsed } as CSSProperties} />
      </div>
    </div>
  )
}
