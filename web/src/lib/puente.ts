// Reparte los mensajes del bicho (los mismos que recibe App) a las vistas que los quieren: Gemelo y Manos.
type Mensaje = Record<string, unknown>
const subs = new Set<(m: Mensaje) => void>()
export const puente = {
  emitir(m: Mensaje) {
    for (const f of subs) f(m)
  },
  escuchar(f: (m: Mensaje) => void) {
    subs.add(f)
    return () => {
      subs.delete(f)
    }
  },
}
