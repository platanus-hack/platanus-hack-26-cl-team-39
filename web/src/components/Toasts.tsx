import { Icon } from './ui'

export type Toast = {
  id: number
  tone: 'ok' | 'info' | 'warn' | 'err'
  title: string
  body?: string
  action?: { label: string; onClick: () => void }
}

/** Notificaciones arriba a la derecha, al estilo de macOS. */
export function Toasts({ items, onClose }: { items: Toast[]; onClose: (id: number) => void }) {
  return (
    <div className="toasts" aria-live="polite">
      {items.map((t) => (
        <div key={t.id} className={`toast glass ${t.tone}`} role="status">
          <span className="toast-ic" aria-hidden>
            {t.tone === 'ok' ? <Icon.Check /> : t.tone === 'info' ? <Icon.Info /> : <Icon.Alert />}
          </span>
          <div className="toast-text">
            <p className="toast-t">{t.title}</p>
            {t.body && <p className="toast-b">{t.body}</p>}
          </div>
          {t.action && (
            <button
              type="button"
              className="btn-secondary toast-act"
              onClick={() => {
                t.action!.onClick()
                onClose(t.id)
              }}
            >
              {t.action.label}
            </button>
          )}
          <button type="button" className="toast-x" onClick={() => onClose(t.id)} aria-label="Cerrar aviso">
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
