import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ESTADOS, EQUIPO, ErrorApi, autor, clave, inventario, mensajeParaClaude, plano, type Cambio, type Campos, type Item } from '../lib/inventario'
import type { Toast } from './Toasts'
import { Icon, fmtAgo } from './ui'

type ToastFn = (t: Omit<Toast, 'id'>, ms?: number) => void
type IA = { pregunta: string; respuesta: string; ids: number[]; ms: number }

const REFRESCO_MS = 12000
const VACIO: Campos = { nombre: '', cantidad: 1, categoria: 'Otros', origen: null, estado: 'Listo', uso_bicho: null, ubicacion: null, notas: null }

const tonoEstado = (e: string) => {
  const p = plano(e)
  if (p === 'listo') return 'ok'
  if (p === 'en uso') return 'uso'
  if (p.includes('dan') || p.includes('falta')) return 'mal'
  return 'duda'
}

const etiquetaCampo: Record<string, string> = {
  nombre: 'nombre',
  cantidad: 'cantidad',
  categoria: 'categoría',
  origen: 'origen',
  estado: 'estado',
  uso_bicho: 'uso en el bicho',
  ubicacion: 'ubicación',
  notas: 'notas',
}

function textoCambio(c: Cambio) {
  const nombre = c.despues?.nombre ?? c.antes?.nombre ?? `ítem ${c.item_id}`
  if (c.accion === 'crear') return { que: 'agregó', nombre, detalle: '' }
  if (c.accion === 'borrar') return { que: 'borró', nombre, detalle: '' }
  const keys = Object.keys(c.despues ?? {}).filter((k) => k !== 'nombre' || c.antes?.nombre !== c.despues?.nombre)
  const detalle = keys
    .map((k) => {
      const a = (c.antes as Record<string, unknown> | null)?.[k]
      const d = (c.despues as Record<string, unknown> | null)?.[k]
      return k === 'cantidad' || k === 'estado' ? `${etiquetaCampo[k]} ${a ?? '—'} → ${d ?? '—'}` : etiquetaCampo[k] ?? k
    })
    .join(', ')
  return { que: 'editó', nombre, detalle }
}

export function Inventario({ toast }: { toast: ToastFn }) {
  const [items, setItems] = useState<Item[] | null>(null)
  const [error, setError] = useState<string>()
  const [cambios, setCambios] = useState<Cambio[]>([])
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('')
  const [origen, setOrigen] = useState('')
  const [estado, setEstado] = useState('')
  const [ia, setIa] = useState<IA | null>(null)
  const [soloIa, setSoloIa] = useState(false)
  const [pensando, setPensando] = useState(false)
  const [abierto, setAbierto] = useState<Item | 'nuevo' | null>(null)
  const [ajustes, setAjustes] = useState<string | false>(false)
  const [copiado, setCopiado] = useState(false)
  const ultimoCambio = useRef<string | number | null>(null)
  const buscador = useRef<HTMLInputElement>(null)

  const cargar = useCallback(async () => {
    try {
      const [its, cs] = await Promise.all([inventario.listar(), inventario.historial(30)])
      setItems(its)
      setError(undefined)
      setCambios(cs)
      // Avisa de cambios que hizo otra persona (o su Claude) desde la última vez.
      const yo = autor.get()
      if (ultimoCambio.current !== null) {
        const nuevos = cs.filter((c) => Number(c.id) > Number(ultimoCambio.current) && c.autor !== yo)
        if (nuevos.length) {
          const t = textoCambio(nuevos[0])
          toast({ tone: 'info', title: `${nuevos[0].autor ?? 'Alguien'} ${t.que} ${t.nombre}`, body: nuevos.length > 1 ? `y ${nuevos.length - 1} cambio(s) más en el inventario` : t.detalle || undefined }, 7000)
        }
      }
      ultimoCambio.current = cs[0]?.id ?? 0
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [toast])

  useEffect(() => {
    cargar()
    const iv = setInterval(() => document.visibilityState === 'visible' && cargar(), REFRESCO_MS)
    return () => clearInterval(iv)
  }, [cargar])

  // "/" enfoca el buscador, como en muchas apps.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName)) {
        e.preventDefault()
        buscador.current?.focus()
      }
    }
    addEventListener('keydown', onKey)
    return () => removeEventListener('keydown', onKey)
  }, [])

  const categorias = useMemo(() => {
    const m = new Map<string, number>()
    for (const i of items ?? []) m.set(i.categoria, (m.get(i.categoria) ?? 0) + 1)
    return [...m.entries()].sort((a, b) => b[1] - a[1])
  }, [items])
  const origenes = useMemo(() => [...new Set((items ?? []).map((i) => i.origen).filter(Boolean) as string[])].sort(), [items])
  const estados = useMemo(() => [...new Set([...ESTADOS, ...(items ?? []).map((i) => i.estado)])], [items])

  const visibles = useMemo(() => {
    const palabras = plano(q).split(/\s+/).filter(Boolean)
    const iaIds = soloIa && ia ? new Set(ia.ids) : null
    const lista = (items ?? []).filter((i) => {
      if (iaIds) return iaIds.has(i.id)
      if (cat && i.categoria !== cat) return false
      if (origen && i.origen !== origen) return false
      if (estado && i.estado !== estado) return false
      if (!palabras.length) return true
      const txt = plano([i.nombre, i.categoria, i.origen, i.estado, i.uso_bicho, i.ubicacion, i.notas, i.uso_lampara].filter(Boolean).join(' '))
      return palabras.every((p) => txt.includes(p))
    })
    if (iaIds && ia) return lista.sort((a, b) => ia.ids.indexOf(a.id) - ia.ids.indexOf(b.id))
    return lista
  }, [items, q, cat, origen, estado, ia, soloIa])

  const unidades = (items ?? []).reduce((s, i) => s + (i.cantidad ?? 0), 0)
  const porVerificar = (items ?? []).filter((i) => tonoEstado(i.estado) === 'duda').length
  const iaSet = useMemo(() => new Set(ia?.ids ?? []), [ia])

  const pedirClave = (msg: string) => setAjustes(msg)
  const hayActividad = cambios.some((c) => c.autor !== 'carga inicial')

  const copiarParaClaude = async () => {
    const texto = mensajeParaClaude(location.origin)
    try {
      await navigator.clipboard.writeText(texto)
    } catch {
      // Sin permiso de portapapeles: copia con un textarea temporal.
      const ta = Object.assign(document.createElement('textarea'), { value: texto })
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      ta.remove()
    }
    setCopiado(true)
    setTimeout(() => setCopiado(false), 2500)
    if (!clave.get()) toast({ tone: 'info', title: 'Copiado sin la clave', body: 'Tu Claude te la va a pedir. Guárdala en “Quién eres” para que vaya incluida.' }, 6000)
  }

  const preguntar = async () => {
    const pregunta = q.trim()
    if (!pregunta || pensando) return
    setPensando(true)
    const t0 = performance.now()
    try {
      const r = await inventario.preguntar(pregunta)
      setIa({ pregunta, respuesta: r.respuesta, ids: r.ids, ms: performance.now() - t0 })
      setSoloIa(r.ids.length > 0)
    } catch (e) {
      if (e instanceof ErrorApi && e.status === 401) pedirClave('Para preguntarle a Claude necesitas la clave del equipo.')
      else toast({ tone: 'err', title: 'Claude no pudo responder', body: e instanceof Error ? e.message : String(e) }, 9000)
    } finally {
      setPensando(false)
    }
  }

  const guardar = async (base: Item | null, datos: Campos) => {
    if (!autor.get()) {
      pedirClave('Antes de guardar, dinos quién eres (queda en el historial).')
      return false
    }
    try {
      if (base) {
        const cambios: Partial<Campos> = {}
        for (const k of Object.keys(datos) as (keyof Campos)[]) if ((base[k] ?? null) !== (datos[k] ?? null)) (cambios as Record<string, unknown>)[k] = datos[k]
        if (Object.keys(cambios).length) {
          const it = await inventario.editar(base.id, cambios)
          setItems((all) => all?.map((x) => (x.id === it.id ? it : x)) ?? null)
          toast({ tone: 'ok', title: 'Guardado', body: it.nombre }, 3000)
        }
      } else {
        const it = await inventario.crear(datos)
        setItems((all) => [...(all ?? []), it])
        toast({ tone: 'ok', title: 'Agregado al inventario', body: it.nombre }, 3000)
      }
      cargar()
      return true
    } catch (e) {
      if (e instanceof ErrorApi && e.status === 401) pedirClave('Para modificar el inventario necesitas la clave del equipo.')
      else toast({ tone: 'err', title: 'No se pudo guardar', body: e instanceof Error ? e.message : String(e) }, 9000)
      return false
    }
  }

  const eliminar = async (it: Item) => {
    if (!autor.get()) {
      pedirClave('Antes de borrar, dinos quién eres (queda en el historial).')
      return false
    }
    try {
      await inventario.borrar(it.id)
      setItems((all) => all?.filter((x) => x.id !== it.id) ?? null)
      toast({ tone: 'ok', title: 'Borrado', body: `${it.nombre}. Queda en el historial.` }, 4000)
      cargar()
      return true
    } catch (e) {
      if (e instanceof ErrorApi && e.status === 401) pedirClave('Para borrar necesitas la clave del equipo.')
      else toast({ tone: 'err', title: 'No se pudo borrar', body: e instanceof Error ? e.message : String(e) }, 9000)
      return false
    }
  }

  const limpiarFiltros = () => {
    setQ('')
    setCat('')
    setOrigen('')
    setEstado('')
    setIa(null)
    setSoloIa(false)
  }
  const hayFiltros = Boolean(q || cat || origen || estado || ia)

  return (
    <>
      <header className="toolbar">
        <div className="tb-title">
          <h1>Inventario</h1>
          <p>
            {items ? `${items.length} ítems · ${unidades} unidades${porVerificar ? ` · ${porVerificar} por verificar` : ''}` : error ? 'Sin conexión con la API' : 'Cargando…'}
            {cambios[0] && ` · último cambio ${fmtAgo(cambios[0].fecha)}`}
          </p>
        </div>
        <div className="tb-actions">
          <button type="button" className="capsule" onClick={() => setAjustes('')} title="Tu nombre y la clave del equipo">
            <Icon.Key /> {autor.get() || 'Quién eres'}
          </button>
          <button type="button" className="capsule inv-add" onClick={() => setAbierto('nuevo')}>
            <Icon.Plus /> Agregar
          </button>
        </div>
      </header>

      {error && !items && (
        <p className="notice">
          <Icon.Warning /> {error} Si corres la web en tu computador, revisa que el servidor tenga web/.env o que haya internet para usar la API publicada.
        </p>
      )}

      <section className="inv-grid" aria-label="Inventario de hardware">
        <div className="inv-col">
          {/* buscador + pregunta a Claude */}
          <article className="card glass inv-search">
            <form
              className="inv-ask"
              onSubmit={(e) => {
                e.preventDefault()
                preguntar()
              }}
            >
              <span className="inv-ask-icon" aria-hidden>
                <Icon.Search />
              </span>
              <input
                ref={buscador}
                className="inv-ask-field"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value)
                  if (soloIa) setSoloIa(false)
                }}
                onKeyDown={(e) => e.key === 'Escape' && limpiarFiltros()}
                placeholder="Busca o pregunta: “¿qué tenemos para medir distancia?”"
                aria-label="Buscar en el inventario o preguntarle a Claude"
              />
              <button type="submit" className="inv-ask-btn" disabled={!q.trim() || pensando} title="Enter: pregúntale a Claude">
                <Icon.Sparkle /> {pensando ? 'Pensando…' : 'Preguntar'}
              </button>
            </form>
            <p className="inv-ask-hint">
              Al escribir se filtra la tabla al tiro. Con <kbd>Enter</kbd> le preguntas a Claude, que entiende sinónimos y te dice qué sirve.
            </p>

            {(pensando || ia) && (
              <div className={`inv-ia ${pensando ? 'is-loading' : ''}`} aria-live="polite">
                <div className="inv-ia-head">
                  <span className="inv-ia-badge">
                    <Icon.Sparkle /> Claude
                  </span>
                  {ia && !pensando && <span className="inv-ia-q">“{ia.pregunta}” · {(ia.ms / 1000).toFixed(1)} s</span>}
                  {ia && !pensando && (
                    <button type="button" className="inv-x" onClick={() => (setIa(null), setSoloIa(false))} aria-label="Cerrar respuesta">
                      <Icon.Close />
                    </button>
                  )}
                </div>
                {pensando ? (
                  <div className="inv-ia-skel" aria-label="Claude está buscando">
                    <i />
                    <i />
                    <i />
                  </div>
                ) : (
                  ia && (
                    <>
                      <p className="inv-ia-text">{ia.respuesta}</p>
                      {ia.ids.length > 0 && (
                        <div className="inv-ia-foot">
                          <div className="inv-ia-chips">
                            {ia.ids.slice(0, 12).map((id) => {
                              const it = items?.find((x) => x.id === id)
                              return (
                                it && (
                                  <button key={id} type="button" className="inv-chip" onClick={() => setAbierto(it)}>
                                    {it.nombre}
                                    <b>{it.cantidad ?? '?'}</b>
                                  </button>
                                )
                              )
                            })}
                          </div>
                          <button type="button" className="btn-link" onClick={() => setSoloIa((v) => !v)}>
                            {soloIa ? 'Ver todo el inventario' : `Ver solo estos ${ia.ids.length} en la tabla`}
                          </button>
                        </div>
                      )}
                    </>
                  )
                )}
              </div>
            )}
          </article>

          {/* filtros + tabla */}
          <article className="card glass inv-table-card">
            <div className="inv-filters">
              <div className="inv-cats" role="group" aria-label="Categoría">
                <button type="button" aria-pressed={!cat} onClick={() => setCat('')}>
                  Todo <span>{items?.length ?? 0}</span>
                </button>
                {categorias.map(([c, n]) => (
                  <button key={c} type="button" aria-pressed={cat === c} onClick={() => setCat(cat === c ? '' : c)}>
                    {c} <span>{n}</span>
                  </button>
                ))}
              </div>
              <div className="inv-selects">
                <select className="btn-secondary" value={origen} onChange={(e) => setOrigen(e.target.value)} aria-label="Origen">
                  <option value="">Todos los orígenes</option>
                  {origenes.map((o) => (
                    <option key={o}>{o}</option>
                  ))}
                </select>
                <select className="btn-secondary" value={estado} onChange={(e) => setEstado(e.target.value)} aria-label="Estado">
                  <option value="">Todos los estados</option>
                  {estados.map((o) => (
                    <option key={o}>{o}</option>
                  ))}
                </select>
                {hayFiltros && (
                  <button type="button" className="btn-link" onClick={limpiarFiltros}>
                    Limpiar
                  </button>
                )}
              </div>
            </div>

            <div className="inv-count">
              {soloIa && ia ? `${visibles.length} ítems que encontró Claude` : `${visibles.length} de ${items?.length ?? 0} ítems`}
            </div>

            <div className="inv-table-wrap">
              <table className="inv-table">
                <thead>
                  <tr>
                    <th>Ítem</th>
                    <th className="num">Cant.</th>
                    <th>Categoría</th>
                    <th>Origen</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {visibles.map((i) => (
                    <tr
                      key={i.id}
                      className={iaSet.has(i.id) ? 'is-ia' : undefined}
                      onClick={() => setAbierto(i)}
                      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), setAbierto(i))}
                      tabIndex={0}
                    >
                      <td className="inv-name">
                        <b>{i.nombre}</b>
                        {i.notas && <span>{i.notas}</span>}
                        {(i.uso_bicho || i.ubicacion) && (
                          <span className="inv-tags">
                            {i.uso_bicho && <em className="t-uso">🤖 {i.uso_bicho}</em>}
                            {i.ubicacion && <em className="t-ubi">📍 {i.ubicacion}</em>}
                          </span>
                        )}
                      </td>
                      <td className="num">{i.cantidad ?? <span className="muted">?</span>}</td>
                      <td>{i.categoria}</td>
                      <td className="inv-origen">{i.origen ?? <span className="muted">—</span>}</td>
                      <td>
                        <span className={`inv-estado e-${tonoEstado(i.estado)}`}>{i.estado}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {items && !visibles.length && (
                <div className="inv-empty">
                  <p>No hay ítems con esos filtros.</p>
                  {q.trim() && (
                    <button type="button" className="btn-secondary" onClick={preguntar} disabled={pensando}>
                      <Icon.Sparkle /> Pregúntale a Claude por “{q.trim()}”
                    </button>
                  )}
                </div>
              )}
              {!items && !error && <div className="inv-empty">Cargando el inventario…</div>}
            </div>
          </article>
        </div>

        {/* actividad */}
        <aside className="card glass inv-activity" aria-label="Últimos cambios">
          <header className="card-head">
            <div>
              <h2>Actividad</h2>
              <p>Lo que cambian ustedes y sus Claude, en vivo.</p>
            </div>
          </header>
          {hayActividad && (
          <ol className="inv-log">
            {cambios
              .filter((c) => c.autor !== 'carga inicial')
              .slice(0, 25)
              .map((c) => {
                const t = textoCambio(c)
                const it = items?.find((x) => x.id === c.item_id)
                return (
                  <li key={c.id} className={`a-${c.accion}`}>
                    <i aria-hidden />
                    <div>
                      <p>
                        <b>{c.autor ?? 'Alguien'}</b> {t.que}{' '}
                        {it ? (
                          <button type="button" className="inv-log-link" onClick={() => setAbierto(it)}>
                            {t.nombre}
                          </button>
                        ) : (
                          <span>{t.nombre}</span>
                        )}
                      </p>
                      {t.detalle && <small>{t.detalle}</small>}
                      <time dateTime={c.fecha}>{fmtAgo(c.fecha)}</time>
                    </div>
                  </li>
                )
              })}
          </ol>
          )}
          {!hayActividad && (
            <p className="inv-log-empty">
              Todavía nadie cambia nada. El inventario se cargó desde el Sheet{cambios.length ? ` ${fmtAgo(cambios[cambios.length - 1].fecha)}` : ''}.
            </p>
          )}
          <div className="inv-agents">
            <p>
              <b>¿Usas Claude?</b> Cópiale esto y podrá buscar y editar el inventario por ti.
            </p>
            <button type="button" className="btn-secondary" onClick={copiarParaClaude} title="Copia un mensaje con la URL, cómo usar la API y tu clave guardada">
              {copiado ? <Icon.Check /> : <Icon.Copy />} {copiado ? 'Copiado: pégaselo' : 'Copiar para tu Claude'}
            </button>
          </div>
        </aside>
      </section>

      {abierto &&
        createPortal(
        <Ficha
          key={abierto === 'nuevo' ? 'nuevo' : abierto.id}
          item={abierto === 'nuevo' ? null : abierto}
          categorias={categorias.map(([c]) => c)}
          origenes={origenes}
          estados={estados}
          onClose={() => setAbierto(null)}
          onSave={guardar}
          onDelete={eliminar}
        />,
          document.body,
        )}
      {ajustes !== false && createPortal(<Ajustes motivo={ajustes} onClose={() => setAjustes(false)} />, document.body)}
    </>
  )
}

/* ── ficha de un ítem (ver, editar, agregar) ── */
function Ficha({
  item,
  categorias,
  origenes,
  estados,
  onClose,
  onSave,
  onDelete,
}: {
  item: Item | null
  categorias: string[]
  origenes: string[]
  estados: string[]
  onClose: () => void
  onSave: (base: Item | null, datos: Campos) => Promise<boolean>
  onDelete: (it: Item) => Promise<boolean>
}) {
  const [d, setD] = useState<Campos>(() => (item ? { nombre: item.nombre, cantidad: item.cantidad, categoria: item.categoria, origen: item.origen, estado: item.estado, uso_bicho: item.uso_bicho, ubicacion: item.ubicacion, notas: item.notas } : VACIO))
  const [guardando, setGuardando] = useState(false)
  const [confirmar, setConfirmar] = useState(false)
  const [hist, setHist] = useState<Cambio[] | null>(null)
  const primero = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!item) primero.current?.focus()
    else inventario.historial(20, item.id).then(setHist, () => setHist([]))
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    addEventListener('keydown', onKey)
    return () => removeEventListener('keydown', onKey)
  }, [item, onClose])

  const set = <K extends keyof Campos>(k: K, v: Campos[K]) => setD((x) => ({ ...x, [k]: v }))
  const txt = (v: string) => (v.trim() === '' ? null : v)
  const cambiado = !item || (Object.keys(d) as (keyof Campos)[]).some((k) => (item[k] ?? null) !== (d[k] ?? null))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!d.nombre.trim()) return primero.current?.focus()
    setGuardando(true)
    const ok = await onSave(item, { ...d, nombre: d.nombre.trim() })
    setGuardando(false)
    if (ok) onClose()
  }

  return (
    <div className="inv-sheet-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="inv-sheet glass" onSubmit={submit} aria-label={item ? `Ficha de ${item.nombre}` : 'Agregar ítem'}>
        <header className="inv-sheet-head">
          <div>
            <p className="eyebrow">{item ? `Ítem #${item.id}` : 'Nuevo ítem'}</p>
            <h2>{item ? item.nombre : 'Agregar al inventario'}</h2>
          </div>
          <button type="button" className="inv-x" onClick={onClose} aria-label="Cerrar">
            <Icon.Close />
          </button>
        </header>

        <div className="inv-form">
          <label className="span2">
            <span>Nombre</span>
            <input ref={primero} className="inv-in" value={d.nombre} onChange={(e) => set('nombre', e.target.value)} placeholder="Ej: Sensor ultrasónico HC-SR04" required />
          </label>
          <label>
            <span>Cantidad</span>
            <div className="inv-qty">
              <button type="button" onClick={() => set('cantidad', Math.max(0, (d.cantidad ?? 0) - 1))} aria-label="Uno menos">
                −
              </button>
              <input
                className="inv-in"
                inputMode="numeric"
                value={d.cantidad ?? ''}
                onChange={(e) => {
                  const v = e.target.value.replace(/\D/g, '')
                  set('cantidad', v === '' ? null : Number(v))
                }}
                placeholder="?"
                aria-label="Cantidad"
              />
              <button type="button" onClick={() => set('cantidad', (d.cantidad ?? 0) + 1)} aria-label="Uno más">
                +
              </button>
            </div>
          </label>
          <label>
            <span>Estado</span>
            <select className="inv-in" value={d.estado} onChange={(e) => set('estado', e.target.value)}>
              {estados.map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Categoría</span>
            <input className="inv-in" list="inv-cats" value={d.categoria} onChange={(e) => set('categoria', e.target.value)} />
            <datalist id="inv-cats">
              {categorias.map((x) => (
                <option key={x} value={x} />
              ))}
            </datalist>
          </label>
          <label>
            <span>Origen</span>
            <input className="inv-in" list="inv-origenes" value={d.origen ?? ''} onChange={(e) => set('origen', txt(e.target.value))} placeholder="De quién es" />
            <datalist id="inv-origenes">
              {origenes.map((x) => (
                <option key={x} value={x} />
              ))}
            </datalist>
          </label>
          <label className="span2">
            <span>Uso en el bicho</span>
            <input className="inv-in" value={d.uso_bicho ?? ''} onChange={(e) => set('uso_bicho', txt(e.target.value))} placeholder="Para qué lo usamos en el robot" />
          </label>
          <label className="span2">
            <span>Ubicación</span>
            <input className="inv-in" value={d.ubicacion ?? ''} onChange={(e) => set('ubicacion', txt(e.target.value))} placeholder="Dónde está: caja, mochila, mesa…" />
          </label>
          <label className="span2">
            <span>Notas</span>
            <textarea className="inv-in" rows={3} value={d.notas ?? ''} onChange={(e) => set('notas', txt(e.target.value))} placeholder="Modelo, voltaje, si falta algo…" />
          </label>
        </div>

        {item && (
          <dl className="inv-meta">
            {item.uso_lampara && (
              <div>
                <dt>Uso en la lámpara (idea anterior)</dt>
                <dd>{item.uso_lampara}</dd>
              </div>
            )}
            {item.fuente && (
              <div>
                <dt>Vino de</dt>
                <dd>{item.fuente}</dd>
              </div>
            )}
            <div>
              <dt>Último cambio</dt>
              <dd>
                {item.actualizado_por ?? '—'} · {fmtAgo(item.actualizado)}
              </dd>
            </div>
          </dl>
        )}

        {item && hist && hist.length > 0 && (
          <div className="inv-hist">
            <p className="eyebrow">Historial</p>
            <ol>
              {hist.map((c) => {
                const t = textoCambio(c)
                return (
                  <li key={c.id}>
                    <b>{c.autor ?? 'Alguien'}</b> {t.que}
                    {t.detalle && `: ${t.detalle}`} <time dateTime={c.fecha}>{fmtAgo(c.fecha)}</time>
                  </li>
                )
              })}
            </ol>
          </div>
        )}

        <footer className="inv-sheet-foot">
          {item &&
            (confirmar ? (
              <span className="inv-confirm">
                ¿Borrar “{item.nombre}”?
                <button type="button" className="btn-quiet" onClick={async () => (await onDelete(item)) && onClose()}>
                  Sí, borrar
                </button>
                <button type="button" className="btn-link" onClick={() => setConfirmar(false)}>
                  No
                </button>
              </span>
            ) : (
              <button type="button" className="btn-quiet" onClick={() => setConfirmar(true)}>
                Borrar
              </button>
            ))}
          <button type="submit" className="btn-primary inv-save" disabled={guardando || !cambiado || !d.nombre.trim()}>
            <Icon.Check /> {guardando ? 'Guardando…' : item ? 'Guardar cambios' : 'Agregar'}
          </button>
        </footer>
      </form>
    </div>
  )
}

/* ── quién eres + clave del equipo ── */
function Ajustes({ motivo, onClose }: { motivo: string; onClose: () => void }) {
  const [nombre, setNombre] = useState(autor.get())
  const [k, setK] = useState(clave.get())
  return (
    <div className="inv-sheet-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form
        className="inv-sheet inv-keys glass"
        onSubmit={(e) => {
          e.preventDefault()
          autor.set(nombre)
          clave.set(k)
          onClose()
        }}
      >
        <header className="inv-sheet-head">
          <div>
            <p className="eyebrow">Inventario</p>
            <h2>Quién eres</h2>
          </div>
          <button type="button" className="inv-x" onClick={onClose} aria-label="Cerrar">
            <Icon.Close />
          </button>
        </header>
        {motivo && <p className="notice">{motivo}</p>}
        <div className="inv-form">
          <label className="span2">
            <span>Tu nombre</span>
            <input className="inv-in" list="inv-equipo" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Ej: Renate" autoFocus={!nombre} />
            <datalist id="inv-equipo">
              {EQUIPO.map((x) => (
                <option key={x} value={x} />
              ))}
            </datalist>
          </label>
          <label className="span2">
            <span>Clave del equipo</span>
            <input className="inv-in mono" type="password" value={k} onChange={(e) => setK(e.target.value)} placeholder="crbrc-…" autoFocus={Boolean(nombre)} />
          </label>
        </div>
        <p className="inv-keys-note">Se guardan solo en este navegador. Sin clave puedes ver y buscar; para editar y preguntarle a Claude hace falta.</p>
        <footer className="inv-sheet-foot">
          <button type="submit" className="btn-primary inv-save" disabled={!nombre.trim()}>
            <Icon.Check /> Listo
          </button>
        </footer>
      </form>
    </div>
  )
}
