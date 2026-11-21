import { useEffect, useRef, useState } from 'react'

type Pieza = { id: string; nombre: string; rev?: string; historial?: { rev: string; fecha?: string; commit?: string; cambio?: string }[] }

const url = (id: string, rev: string) => `/bim/planos/${id}_rev${rev}.svg`

/** ¿Existe el SVG? El servidor de desarrollo (y Vercel) devuelve index.html con 200 si no existe: se mira el tipo. */
async function existe(u: string) {
  try {
    const r = await fetch(u, { cache: 'no-cache' })
    return r.ok && (r.headers.get('content-type') ?? '').includes('svg')
  } catch {
    return false
  }
}

/** Plano de una pieza sobre el visor: zoom con la rueda, arrastre y selector de revisiones. */
export function Plano({ pieza, rev, onRev, onCerrar }: { pieza: Pieza; rev: string; onRev: (rev: string) => void; onCerrar: () => void }) {
  const [revs, setRevs] = useState<string[] | null>(null)
  const [vista, setVista] = useState({ k: 1, x: 0, y: 0 })
  const [falta, setFalta] = useState(false)
  const caja = useRef<HTMLDivElement>(null)
  const arrastre = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null)

  useEffect(() => {
    let vivo = true
    const todas = [...new Set([...(pieza.historial ?? []).map((h) => h.rev), pieza.rev ?? rev])].filter((r) => r && r !== '-')
    Promise.all(todas.map(async (r) => ((await existe(url(pieza.id, r))) ? r : null))).then((ok) => {
      if (vivo) setRevs(ok.filter((r): r is string => r !== null))
    })
    return () => {
      vivo = false
    }
  }, [pieza, rev])

  useEffect(() => {
    setVista({ k: 1, x: 0, y: 0 })
    setFalta(false)
  }, [rev])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onCerrar()
    addEventListener('keydown', onKey)
    return () => removeEventListener('keydown', onKey)
  }, [onCerrar])

  // zoom alrededor del cursor (listener no pasivo para poder evitar el scroll)
  useEffect(() => {
    const el = caja.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const r = el.getBoundingClientRect()
      const cx = e.clientX - r.left - r.width / 2
      const cy = e.clientY - r.top - r.height / 2
      setVista((v) => {
        const k = Math.min(12, Math.max(0.5, v.k * Math.exp(-e.deltaY * 0.0015)))
        const f = k / v.k
        return { k, x: cx - (cx - v.x) * f, y: cy - (cy - v.y) * f }
      })
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  const zoom = (f: number) => setVista((v) => ({ k: Math.min(12, Math.max(0.5, v.k * f)), x: v.x * f, y: v.y * f }))
  const historia = pieza.historial?.find((h) => h.rev === rev)

  return (
    <div className="bz-plano" role="dialog" aria-label={`Plano de ${pieza.id}`}>
      <header className="bz-plano-head">
        <div>
          <p className="bz-ficha-id">Plano · {pieza.id}</p>
          <h2>{pieza.nombre}</h2>
          {historia && (
            <p className="bz-plano-sub">
              rev {historia.rev}
              {historia.fecha ? ` · ${historia.fecha}` : ''}
              {historia.commit ? ` · ${historia.commit}` : ''}
              {historia.cambio ? ` · ${historia.cambio}` : ''}
            </p>
          )}
        </div>
        <div className="bz-plano-acc">
          <div className="seg" role="group" aria-label="Revisión" style={{ gridTemplateColumns: `repeat(${Math.max(1, revs?.length ?? 1)},minmax(0,1fr))` }}>
            {(revs ?? [rev]).map((r) => (
              <button key={r} type="button" aria-pressed={r === rev} onClick={() => onRev(r)}>
                rev {r}
              </button>
            ))}
          </div>
          <button type="button" className="capsule" onClick={() => zoom(1 / 1.4)} aria-label="Alejar">
            −
          </button>
          <button type="button" className="capsule" onClick={() => setVista({ k: 1, x: 0, y: 0 })}>
            Ajustar
          </button>
          <button type="button" className="capsule" onClick={() => zoom(1.4)} aria-label="Acercar">
            +
          </button>
          <a className="capsule bz-dl-svg" href={url(pieza.id, rev)} download={`${pieza.id}_rev${rev}.svg`}>
            Descargar SVG
          </a>
          <button type="button" className="bz-x" onClick={onCerrar} aria-label="Cerrar plano">
            ×
          </button>
        </div>
      </header>
      <div
        ref={caja}
        className="bz-plano-caja"
        onPointerDown={(e) => {
          ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
          arrastre.current = { x: e.clientX, y: e.clientY, vx: vista.x, vy: vista.y }
        }}
        onPointerMove={(e) => {
          const a = arrastre.current
          if (a) setVista((v) => ({ ...v, x: a.vx + e.clientX - a.x, y: a.vy + e.clientY - a.y }))
        }}
        onPointerUp={() => (arrastre.current = null)}
        onPointerCancel={() => (arrastre.current = null)}
        onDoubleClick={() => setVista({ k: 1, x: 0, y: 0 })}
      >
        {falta ? (
          <p className="bz-plano-falta">No hay plano para la rev {rev}. Corre diseno/bim/planos.py.</p>
        ) : (
          <img
            src={url(pieza.id, rev)}
            alt={`Plano de ${pieza.id} rev ${rev}`}
            draggable={false}
            onError={() => setFalta(true)}
            style={{ transform: `translate(${vista.x}px, ${vista.y}px) scale(${vista.k})` }}
          />
        )}
      </div>
      {revs && revs.length < (pieza.historial?.filter((h) => h.rev !== '-').length ?? 0) && (
        <p className="bz-plano-nota">Algunas revisiones del historial no tienen plano guardado.</p>
      )}
    </div>
  )
}
