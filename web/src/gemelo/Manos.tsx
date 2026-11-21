import { useEffect, useRef } from 'react'
import { puente } from '../lib/puente'
import './gemelo.css'

/* Vista «Manos»: la demo de enseñarle una seña (web/public/manos/). Le pasa lo que oye el bicho real y lo que
   anuncia el servicio de señas (handtracking/tracker/senas.py), para que la demo pueda moverse con el bicho de verdad. */
export function Manos() {
  const frame = useRef<HTMLIFrameElement>(null)
  useEffect(
    () =>
      puente.escuchar((m) => {
        if (m.t === 'oido' || m.t === 'cerebro') frame.current?.contentWindow?.postMessage({ fuente: 'bicho-dev', m }, location.origin)
      }),
    [],
  )
  return (
    <div className="mn">
      <header className="toolbar">
        <div className="tb-title">
          <h1>Manos</h1>
          <p>Lo llamas, viene, le enseñas una seña frente a su cámara y la próxima vez que la ve se detiene</p>
        </div>
        <div className="tb-actions">
          <a className="capsule" href="/manos/index.html#demo" target="_blank" rel="noopener">
            Abrir la demo en pantalla completa
          </a>
        </div>
      </header>
      <iframe ref={frame} className="mn-frame" src="/manos/index.html" title="Demo de las manos del Bicho" allow="microphone" />
    </div>
  )
}
