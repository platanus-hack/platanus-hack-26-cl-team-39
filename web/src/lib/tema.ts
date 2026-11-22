/**
 * Tema de bicho·dev: claro («Cristal claro») u oscuro (el del pitch, para que no se sobresature en el streaming).
 *
 * Sigue al sistema (prefers-color-scheme) salvo que alguien lo fuerce con el botón de la barra lateral o con Mayús + D.
 * Lo forzado se recuerda en localStorage; si el tema elegido coincide con el del sistema, vuelve a seguir al sistema.
 * index.html aplica lo mismo antes de pintar, para que no parpadee en claro al cargar.
 */
export type Tema = 'claro' | 'oscuro'

const CLAVE = 'bicho.tema'
const mq = typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: dark)') : null
const oyentes = new Set<() => void>()

const delSistema = (): Tema => (mq?.matches ? 'oscuro' : 'claro')

function leer(): Tema | null {
  try {
    const v = localStorage.getItem(CLAVE)
    return v === 'claro' || v === 'oscuro' ? v : null
  } catch {
    return null
  }
}

function guardar(t: Tema | null) {
  try {
    if (t) localStorage.setItem(CLAVE, t)
    else localStorage.removeItem(CLAVE)
  } catch {
    /* sin localStorage (ventana privada, bloqueado): dura solo esta visita */
  }
}

let forzado = leer()

export const temaActual = (): Tema => forzado ?? delSistema()

function aplicar() {
  document.documentElement.dataset.tema = temaActual()
  oyentes.forEach((f) => f())
}

export function cambiarTema() {
  const nuevo: Tema = temaActual() === 'oscuro' ? 'claro' : 'oscuro'
  forzado = nuevo === delSistema() ? null : nuevo
  guardar(forzado)
  aplicar()
}

export function suscribirTema(f: () => void) {
  oyentes.add(f)
  return () => {
    oyentes.delete(f)
  }
}

mq?.addEventListener?.('change', aplicar)
// otra pestaña de bicho·dev cambió el tema
addEventListener('storage', (e) => {
  if (e.key !== CLAVE) return
  forzado = leer()
  aplicar()
})
// Mayús + D, salvo que se esté escribiendo
addEventListener('keydown', (e) => {
  if (e.code !== 'KeyD' || !e.shiftKey || e.metaKey || e.ctrlKey || e.altKey || e.repeat) return
  const el = e.target as HTMLElement | null
  if (el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName))) return
  e.preventDefault()
  cambiarTema()
})

aplicar()
