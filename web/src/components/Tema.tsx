import { useSyncExternalStore } from 'react'
import { cambiarTema, suscribirTema, temaActual } from '../lib/tema'

/** Botón claro/oscuro de la barra lateral (también con Mayús + D). */
export function BotonTema() {
  const oscuro = useSyncExternalStore(suscribirTema, temaActual) === 'oscuro'
  return (
    <button
      type="button"
      className="tema-btn"
      onClick={cambiarTema}
      aria-pressed={oscuro}
      aria-label="Modo oscuro"
      title={`${oscuro ? 'Pasar a modo claro' : 'Pasar a modo oscuro'} (Mayús + D)`}
    >
      {oscuro ? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" aria-hidden>
          <circle cx="12" cy="12" r="4.2" />
          <path d="M12 2.8v2M12 19.2v2M2.8 12h2M19.2 12h2M5.5 5.5l1.4 1.4M17.1 17.1l1.4 1.4M5.5 18.5l1.4-1.4M17.1 6.9l1.4-1.4" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinejoin="round" aria-hidden>
          <path d="M19.6 14.6A8 8 0 0 1 9.4 4.4a8 8 0 1 0 10.2 10.2Z" />
        </svg>
      )}
    </button>
  )
}
