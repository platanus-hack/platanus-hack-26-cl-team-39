import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Console, type ConsoleLine } from './components/Console'
import { Countdown } from './components/Countdown'
import { Inventario } from './components/Inventario'
import { Sensors } from './components/Sensors'
import { Toasts, type Toast } from './components/Toasts'
import { BotonTema } from './components/Tema'
import { Icon, SparkDefs, fmtAgo, fmtBytes, fmtUptime } from './components/ui'
import { cmpSemver, fetchPackage, loadManifest, looksLikePackage, uploadPackage, type Manifest, type Release } from './lib/firmware'
import { Cerebro, type Evento, type Imagen } from './components/Cerebro'
import { Manejo } from './components/Manejo'
import { Habilidades } from './components/Habilidades'
import { Oido, type Frase } from './components/Oido'
import { clave as claveEquipo } from './lib/inventario'
import releCfg from './lib/rele.json'
import { SimLink, WifiLink, esRele, normalizeHost, type DeviceLink, type LineDir, type LinkHandlers, type LinkStatus } from './lib/links'
import { CMD, type DeviceInfo } from './lib/protocol'
import { SensorStore } from './lib/sensors'
// el simulador trae three.js (~600 kB): se carga solo al abrirlo
const Simulador = lazy(() => import('./sim/Simulador').then((m) => ({ default: m.Simulador })))
// la vista Brazo también trae three.js: misma idea
const Brazo = lazy(() => import('./brazo/Brazo').then((m) => ({ default: m.Brazo })))
// gemelo digital (chasis + brazo v4 + sensores en vivo) y la demo de las manos
const Gemelo = lazy(() => import('./gemelo/Gemelo').then((m) => ({ default: m.Gemelo })))
const Manos = lazy(() => import('./gemelo/Manos').then((m) => ({ default: m.Manos })))
import { puente } from './lib/puente'

type Vista = 'bicho' | 'inventario' | 'simulador' | 'brazo' | 'gemelo' | 'manos'
const VISTAS_HASH: Vista[] = ['inventario', 'simulador', 'brazo', 'gemelo', 'manos']
const vistaDelHash = (): Vista => VISTAS_HASH.find((v) => location.hash === `#${v}`) ?? 'bicho'

const MAX_LINES = 600
// Bicho por defecto de este computador: VITE_BICHO_HOST en web/.env.local (no va al repo).
const ENV_HOST = (import.meta.env.VITE_BICHO_HOST as string | undefined)?.trim() || ''

// Relé público del bicho (rele/ en el repo): con él da lo mismo en qué red estén el bicho y quien mira.
// La dirección no es secreta. Vacía = no hay relé publicado y se busca al bicho en la red local.
const RELE_PUBLICO = (import.meta.env.VITE_BICHO_RELE as string | undefined)?.trim() || releCfg.url

function savedHost(): string {
  try {
    return localStorage.getItem('bicho.host') || ''
  } catch {
    return ''
  }
}

type FlashPhase = 'idle' | 'preparing' | 'flashing' | 'rebooting' | 'done' | 'warn' | 'error'
type FlashState = { phase: FlashPhase; pct: number; target?: string; via?: string; msg?: string; log: string[] }
type FlashSource = { kind: 'release'; rel: Release } | { kind: 'file'; file: File }
type FwState = 'outdated' | 'flashing' | 'uptodate' | 'newer' | 'unknown'

const SIM_RELEASE: Release = {
  version: '0.2.0',
  date: new Date().toISOString(),
  author: 'simulador',
  notes: '(simulada) Agrega detección de voz y baile de servos.',
  package: 'sim',
}

const NAV = [
  { id: 'habilidades', label: 'Habilidades', icon: Icon.Sparkle },
  { id: 'firmware', label: 'Firmware', icon: Icon.Chip },
  { id: 'sensores', label: 'Sensores', icon: Icon.Pulse },
  { id: 'oido', label: 'Oído', icon: Icon.Sparkle },
  { id: 'cerebro', label: 'Cerebro', icon: Icon.Bicho },
  { id: 'consola', label: 'Consola', icon: Icon.Terminal },
  { id: 'versiones', label: 'Versiones', icon: Icon.History },
] as const

/** Ícono de la pestaña: el ojo de Bicho en el cuadrado amarillo, con un punto del color del estado. */
function setFavicon(dot: string) {
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><defs><linearGradient id='g' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#ffe46b'/><stop offset='1' stop-color='#ffad00'/></linearGradient></defs><rect x='2' y='2' width='60' height='60' rx='15' fill='url(#g)'/><circle cx='27' cy='29' r='16' fill='none' stroke='#1d1d1f' stroke-width='5'/><circle cx='27' cy='29' r='7' fill='#1d1d1f'/><circle cx='27' cy='29' r='3' fill='#8fdcc4'/><rect x='-12' y='-4.5' width='24' height='9' rx='4.5' transform='translate(38.3 17.7) rotate(45)' fill='#f4996f' stroke='#fff' stroke-width='2' paint-order='stroke'/><circle cx='50' cy='50' r='11' fill='${dot}' stroke='#fff' stroke-width='4'/></svg>`
  let el = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
  if (!el) {
    el = document.createElement('link')
    el.rel = 'icon'
    document.head.appendChild(el)
  }
  const href = `data:image/svg+xml,${encodeURIComponent(svg)}`
  if (el.getAttribute('href') !== href) el.setAttribute('href', href)
}

function frontendVersion() {
  const v = `v${__APP_VERSION__}`
  return import.meta.env.DEV ? `${v}-dev` : __GIT_SHA__ ? `${v}+${__GIT_SHA__}` : v
}

/** Resalta en la barra lateral la sección visible y muestra el fondo de la barra de herramientas al hacer scroll. */
function useScrollSpy(mainRef: React.RefObject<HTMLElement>) {
  const [active, setActive] = useState(0)
  const [scrolled, setScrolled] = useState(false)
  const pinned = useRef(0)
  const pinUntil = useRef(0)

  useEffect(() => {
    const main = mainRef.current
    if (!main) return
    let raf = 0
    const spy = () => {
      raf = 0
      setScrolled(main.scrollTop > 4)
      if (performance.now() < pinUntil.current) return
      const secs = NAV.map((n) => document.getElementById(n.id))
      if (secs.some((s) => !s)) return
      const inner = main.scrollHeight > main.clientHeight + 1 && getComputedStyle(main).overflowY !== 'visible'
      const atEnd = inner ? main.scrollTop + main.clientHeight >= main.scrollHeight - 4 : innerHeight + scrollY >= document.documentElement.scrollHeight - 4
      const tops = secs.map((s) => s!.getBoundingClientRect().top)
      let cur = 0
      tops.forEach((t, i) => {
        if (t <= 140) cur = i
      })
      // Consola y Versiones van lado a lado: al llegar abajo se marca la que se eligió.
      const a = NAV.findIndex((n) => n.id === 'consola')
      const b = NAV.findIndex((n) => n.id === 'versiones')
      const sameRow = Math.abs(tops[a] - tops[b]) < 4
      if (atEnd) cur = sameRow ? Math.max(cur, pinned.current === b ? b : a) : secs.length - 1
      if (sameRow && cur >= a) cur = pinned.current === b ? b : a
      setActive(cur)
    }
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(spy)
    }
    main.addEventListener('scroll', onScroll, { passive: true })
    addEventListener('scroll', onScroll, { passive: true })
    addEventListener('resize', onScroll)
    return () => {
      main.removeEventListener('scroll', onScroll)
      removeEventListener('scroll', onScroll)
      removeEventListener('resize', onScroll)
      cancelAnimationFrame(raf)
    }
  }, [mainRef])

  const pick = (i: number) => {
    pinned.current = i
    pinUntil.current = performance.now() + 900
    setActive(i)
  }
  return { active, scrolled, pick }
}

export default function App() {
  const [link, setLink] = useState<DeviceLink | null>(null)
  const [status, setStatus] = useState<LinkStatus>('disconnected')
  const [statusDetail, setStatusDetail] = useState<string>()
  // Por el relé: hay conexión con el relé, pero el bicho no está conectado a él (apagado o sin internet).
  const [sinBicho, setSinBicho] = useState(false)
  // Frases que escuchó el bicho (ReSpeaker). El relé manda cada una dos veces: al oírla y ya transcrita.
  const [frases, setFrases] = useState<Frase[]>([])
  // Lo que decide y aprende el cerebro, y las imágenes que manda el bicho (su cámara, si aprendió a usarla).
  const [eventos, setEventos] = useState<Evento[]>([])
  const [imagenes, setImagenes] = useState<Imagen[]>([])
  // Lo que el bicho dijo en voz alta: audio (data URL) por id del evento del cerebro.
  const [voces, setVoces] = useState<Record<string, string>>({})
  // El código que corre el bicho ({"t":"fuente"}): de ahí sale cuánto escribió él y su propia lista de habilidades.
  const [codigo, setCodigo] = useState<{ version: string | null; archivos: Record<string, string> } | null>(null)
  // Si su voz también suena en este computador (plan B por si el parlante del bicho falla).
  const [vozAqui, setVozAqui] = useState(() => {
    try {
      return localStorage.getItem('bicho.vozAqui') === '1'
    } catch {
      return false
    }
  })
  const vozAquiRef = useRef(vozAqui)
  vozAquiRef.current = vozAqui
  const cambiarVozAqui = (v: boolean) => {
    setVozAqui(v)
    try {
      localStorage.setItem('bicho.vozAqui', v ? '1' : '0')
    } catch {
      /* sin localStorage */
    }
  }
  // El relé no dejó mandar desde esta conexión (clave del equipo ausente o incorrecta).
  const [claveRechazada, setClaveRechazada] = useState(false)
  // Lo que esta web le escribió al cerebro y el relé todavía no devuelve.
  const pendientes = useRef(new Set<string>())
  const [info, setInfo] = useState<DeviceInfo | null>(null)
  const [manifest, setManifest] = useState<Manifest | null>(null)
  const [manifestErr, setManifestErr] = useState<string>()
  const [host, setHost] = useState(() => ENV_HOST || savedHost() || RELE_PUBLICO || 'bicho.local')
  const [flash, setFlash] = useState<FlashState>({ phase: 'idle', pct: 0, log: [] })
  const [lines, setLines] = useState<ConsoleLine[]>([])
  const [toasts, setToasts] = useState<Toast[]>([])
  const [dragging, setDragging] = useState(false)

  const store = useRef(new SensorStore()).current
  const linkRef = useRef<DeviceLink | null>(null)
  const lineBuf = useRef<ConsoleLine[]>([])
  const lineId = useRef(0)
  const dirty = useRef(false)
  const expect = useRef<{ version?: string; timer?: ReturnType<typeof setTimeout> } | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const mainRef = useRef<HTMLElement>(null)
  const { active, scrolled, pick } = useScrollSpy(mainRef)
  // Vista principal: el panel del bicho, el simulador (#simulador) o el inventario del equipo (#inventario).
  const [view, setView] = useState<Vista>(vistaDelHash)
  useEffect(() => {
    const onHash = () => setView(vistaDelHash())
    addEventListener('hashchange', onHash)
    return () => removeEventListener('hashchange', onHash)
  }, [])
  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0 })
  }, [view])
  const goSection = (e: React.MouseEvent, i: number) => {
    if (view === 'bicho') return pick(i)
    e.preventDefault()
    history.pushState(null, '', `#${NAV[i].id}`)
    setView('bicho')
    requestAnimationFrame(() => requestAnimationFrame(() => document.getElementById(NAV[i].id)?.scrollIntoView()))
    pick(i)
  }
  const toastId = useRef(0)
  const prevStatus = useRef<LinkStatus>('disconnected')
  const userClosing = useRef(false)
  const startFlashRef = useRef<(s: FlashSource) => void>(() => {})
  const busyRef = useRef(false)

  /* ---------- avisos ---------- */
  const closeToast = useCallback((id: number) => setToasts((all) => all.filter((t) => t.id !== id)), [])
  const toast = useCallback(
    (t: Omit<Toast, 'id'>, ms = 5000) => {
      const id = ++toastId.current
      setToasts((all) => [...all.slice(-3), { ...t, id }])
      if (ms) setTimeout(() => closeToast(id), ms)
    },
    [closeToast],
  )

  /* ---------- consola con buffer (las lecturas llegan a 20+ Hz) ---------- */
  const pushLine = useCallback((text: string, dir: LineDir) => {
    lineBuf.current.push({ id: lineId.current++, dir, text, at: Date.now() })
    if (lineBuf.current.length > MAX_LINES) lineBuf.current.splice(0, lineBuf.current.length - MAX_LINES)
    dirty.current = true
  }, [])
  useEffect(() => {
    const iv = setInterval(() => {
      if (!dirty.current) return
      dirty.current = false
      setLines([...lineBuf.current])
    }, 150)
    return () => clearInterval(iv)
  }, [])

  const flashLog = useCallback(
    (s: string) => {
      pushLine(s, 'sys')
      setFlash((f) => ({ ...f, log: [...f.log.slice(-40), s] }))
    },
    [pushLine],
  )

  /* ---------- handlers de las conexiones ---------- */
  const handlers: LinkHandlers = useMemo(
    () => ({
      onLine: pushLine,
      onStatus: (s, detail) => {
        const prev = prevStatus.current
        prevStatus.current = s
        setStatus(s)
        setStatusDetail(detail)
        if (s === 'connected' && (prev === 'connecting' || prev === 'disconnected')) {
          const k = linkRef.current?.kind
          toast(k === 'sim' ? { tone: 'ok', title: 'Simulador abierto', body: 'Datos simulados, sin hardware.' } : { tone: 'ok', title: (linkRef.current as WifiLink | null)?.rele ? 'Conectado al relé' : 'Conectado por WiFi', body: detail }, 3000)
        }
        if (s === 'disconnected') {
          if (!userClosing.current && prev !== 'disconnected') toast({ tone: 'warn', title: 'Se perdió la conexión', body: detail ?? 'El bicho dejó de responder.' })
          userClosing.current = false
          linkRef.current = null
          setLink(null)
        }
      },
      onMessage: (m) => {
        puente.emitir(m as Record<string, unknown>)
        // El relé avisa cuando esta conexión no tiene la clave del equipo (o no es la correcta).
        if (m.t === 'log' && typeof m.msg === 'string' && m.msg.includes('falta la clave')) setClaveRechazada(true)
        if (m.t === 's' && m.d && typeof m.d === 'object') store.push(m.d as Record<string, unknown>)
        else if (m.t === 'cerebro') {
          const e = m as unknown as Evento
          // Si lo escribió esta web, ya estaba en la lista como pendiente: el relé confirma que lo recibió.
          if (e.id) pendientes.current.delete(e.id)
          if (e.id && e.tipo)
            setEventos((prev) => (prev.some((x) => x.id === e.id) ? prev.map((x) => (x.id === e.id ? { ...e, pendiente: false } : x)) : [...prev, e].slice(-80)))
        } else if (m.t === 'voz') {
          // El cerebro manda el audio de lo que el bicho dijo en voz alta (ElevenLabs, WAV en base64).
          const v = m as unknown as { evento?: string; fmt?: string; b64?: string }
          if (v.evento && v.b64) {
            const url = `data:audio/${v.fmt === 'mp3' ? 'mpeg' : 'wav'};base64,${v.b64}`
            setVoces((prev) => Object.fromEntries([...Object.entries(prev).slice(-9), [v.evento!, url]]))
            if (vozAquiRef.current) new Audio(url).play().catch(() => {})
          }
        } else if (m.t === 'fuente') {
          // Lo pide el cerebro (o esta web) y el relé lo reparte a todos.
          const f = m as unknown as { version?: string; archivos?: Record<string, unknown> }
          if (f.archivos && typeof f.archivos === 'object')
            setCodigo({
              version: f.version ?? null,
              archivos: Object.fromEntries(Object.entries(f.archivos).filter((e): e is [string, string] => typeof e[1] === 'string')),
            })
        } else if (m.t === 'imagen') {
          const i = m as unknown as { nombre?: string; fmt?: string; b64?: string }
          if (i.nombre && i.b64) {
            const img = { nombre: i.nombre, url: `data:image/${i.fmt === 'png' ? 'png' : 'jpeg'};base64,${i.b64}`, ts: Date.now() }
            setImagenes((prev) => [...prev.filter((x) => x.nombre !== img.nombre), img])
          }
        } else if (m.t === 'oido') {
          const f = m as unknown as Frase
          if (f.estado === 'vacio') setFrases((prev) => prev.filter((x) => x.id !== f.id)) // era ruido: no dijo nada
          else
            setFrases((prev) => (prev.some((x) => x.id === f.id) ? prev.map((x) => (x.id === f.id ? { ...x, ...f } : x)) : [...prev, { ...f, ts: f.ts ?? Date.now() }].slice(-40)))
        } else if (m.t === 'rele') {
          // El relé avisa si el bicho está conectado a él. Si no, la web espera sin mostrar datos viejos.
          const esta = Boolean((m as { bicho?: boolean }).bicho)
          setSinBicho(!esta)
          if ((m as { puedeMandar?: boolean }).puedeMandar === false) setClaveRechazada(true)
          if (!esta) {
            setInfo(null)
            store.clear()
            pushLine('El bicho se desconectó del relé: ¿está prendido y con internet? Vuelve solo cuando se conecte.', 'sys')
          }
        } else if (m.t === 'info') {
          const i = m as unknown as DeviceInfo
          setInfo(i)
          const ex = expect.current
          if (ex) {
            clearTimeout(ex.timer)
            expect.current = null
            if (!ex.version || ex.version === i.fw) {
              setFlash((f) => ({ ...f, phase: 'done', pct: 1, msg: `Listo: el bicho ahora corre v${i.fw}.` }))
            } else {
              setFlash((f) => ({
                ...f,
                phase: 'warn',
                pct: 1,
                msg: `Se instaló, pero el bicho dice v${i.fw} y esperábamos v${ex.version}.`,
              }))
            }
          }
        }
      },
    }),
    [pushLine, store, toast],
  )

  /* ---------- versiones publicadas ---------- */
  const refreshManifest = useCallback(async () => {
    try {
      setManifest(await loadManifest())
      setManifestErr(undefined)
    } catch (e) {
      setManifestErr(String((e as Error).message ?? e))
    }
  }, [])
  useEffect(() => {
    refreshManifest()
    const iv = setInterval(refreshManifest, 10_000)
    return () => clearInterval(iv)
  }, [refreshManifest])

  const releases = useMemo(() => {
    const r = manifest?.releases ?? []
    return link?.kind === 'sim' && r.length === 0 ? [SIM_RELEASE] : r
  }, [manifest, link])
  const latest = releases[0]

  /* ---------- conectar / desconectar ---------- */
  const attach = useCallback(
    async (l: DeviceLink) => {
      if (linkRef.current) {
        userClosing.current = true
        await linkRef.current.close()
      }
      store.clear()
      setInfo(null)
      setSinBicho(false)
      setClaveRechazada(false)
      setFrases([])
      setEventos([])
      setImagenes([])
      setVoces({})
      setCodigo(null)
      linkRef.current = l
      setLink(l)
      try {
        await l.open()
      } catch (e) {
        pushLine(`No pude conectar: ${(e as Error).message}`, 'sys')
        linkRef.current = null
        setLink(null)
        setStatus('disconnected')
      }
    },
    [pushLine, store],
  )

  const connectWifi = () => {
    try {
      localStorage.setItem('bicho.host', host)
    } catch {
      /* sin localStorage */
    }
    attach(new WifiLink(host, handlers))
  }
  const connectSim = () => attach(new SimLink(handlers))

  /* Al abrir la página se conecta sola al bicho configurado o al último usado. */
  const autoTried = useRef(false)
  useEffect(() => {
    if (autoTried.current) return
    autoTried.current = true
    const h = ENV_HOST || savedHost() || RELE_PUBLICO
    if (h) attach(new WifiLink(h, handlers))
  }, [attach, handlers])
  const disconnect = () => {
    userClosing.current = true
    linkRef.current?.close()
  }

  const send = (l: string) => linkRef.current?.sendLine(l).catch((e) => pushLine(`No se pudo enviar: ${e.message}`, 'sys'))

  /* ---------- escribirle al cerebro ---------- */
  // El cerebro escucha por el relé. El relé reparte lo escrito a todas las webs (también a esta): si en unos
  // segundos no vuelve, no llegó, y casi siempre es porque el relé no aceptó la clave de esta conexión.
  const relLink = link?.kind === 'wifi' && (link as WifiLink).rele ? (link as WifiLink) : null
  const motivoCerebro = !relLink
    ? 'El cerebro escucha por el relé: conéctate al relé para escribirle'
    : !claveEquipo.get()
      ? 'Para escribirle, pon la clave del equipo en Equipo → Inventario'
      : !relLink.claveAlDia
        ? 'Cambió la clave del equipo después de conectar: vuelve a conectar para usarla'
        : claveRechazada
          ? 'El relé no aceptó la clave del equipo. Revísala en Equipo → Inventario y vuelve a conectar'
          : null
  const reconectarRele = relLink && claveEquipo.get() && (!relLink.claveAlDia || claveRechazada) ? () => attach(new WifiLink(relLink.direccion, handlers)) : undefined
  const decirAlCerebro = (texto: string) => {
    const id = crypto.randomUUID()
    const ts = Date.now()
    pendientes.current.add(id)
    setEventos((prev) => [...prev, { id, tipo: 'decir' as const, texto, ts, pendiente: true }].slice(-80))
    send(JSON.stringify({ t: 'cerebro', id, tipo: 'decir', texto, ts }))
    setTimeout(() => {
      if (!pendientes.current.delete(id)) return // el relé ya lo devolvió
      setClaveRechazada(true)
      setEventos((prev) =>
        prev.map((x) => (x.id === id ? { ...x, tipo: 'error' as const, pendiente: false, texto: `No llegó al cerebro: «${texto}». El relé no lo recibió; lo más probable es que no aceptó la clave del equipo de esta conexión.` } : x)),
      )
    }, 6000)
  }

  /* ---------- su código, para contar cuánto escribió él ---------- */
  // Se pide una vez por versión (es solo lectura). Por el relé hace falta la clave del equipo.
  const puedePedirCodigo = status === 'connected' && !sinBicho && link?.kind === 'wifi' && (!relLink || !motivoCerebro)
  const fwActual = info?.fw
  const versionCodigo = codigo?.version
  useEffect(() => {
    if (!puedePedirCodigo || !fwActual || versionCodigo === fwActual) return
    const t = setTimeout(() => linkRef.current?.sendLine(JSON.stringify({ cmd: 'fuente', id: `web-${crypto.randomUUID()}` })).catch(() => {}), 4000)
    return () => clearTimeout(t)
  }, [puedePedirCodigo, fwActual, versionCodigo])

  /* ---------- actualizar ---------- */
  const flashVia = link?.kind === 'sim' ? 'el simulador' : 'WiFi'
  const busy = flash.phase === 'preparing' || flash.phase === 'flashing' || flash.phase === 'rebooting'

  const startFlash = async (src: FlashSource) => {
    const target = src.kind === 'release' ? src.rel.version : undefined
    const label = src.kind === 'release' ? `v${src.rel.version}` : src.file.name
    setFlash({ phase: 'preparing', pct: 0, target: label, via: flashVia, log: [] })
    const current = linkRef.current
    try {
      if (!current) throw new Error('Conecta el bicho por WiFi para poder actualizarlo.')

      /* Simulador */
      if (current.kind === 'sim') {
        setFlash((f) => ({ ...f, phase: 'flashing' }))
        expect.current = { version: target }
        await (current as SimLink).simulateFlash(target ?? '0.0.0-local', src.kind === 'release' ? src.rel.notes : undefined, (p) =>
          setFlash((f) => ({ ...f, pct: p })),
        )
        return
      }

      /* Paquete */
      let pkg: Uint8Array
      if (src.kind === 'file') {
        pkg = new Uint8Array(await src.file.arrayBuffer())
        if (!looksLikePackage(pkg)) throw new Error('El archivo no es un paquete .tar.gz del bicho.')
        flashLog(`${src.file.name}: ${fmtBytes(pkg.length)}`)
      } else {
        if (!src.rel.package) throw new Error('Esta versión no trae paquete.')
        pkg = await fetchPackage(src.rel.package)
        flashLog(`Descargado ${src.rel.package} (${fmtBytes(pkg.length)})`)
      }

      /* Subida al agente */
      const wl = current as WifiLink
      setFlash((f) => ({ ...f, phase: 'flashing' }))
      flashLog(`Subiendo a ${wl.updateUrl}…`)
      const res = await uploadPackage(wl.updateUrl, pkg, (p) => setFlash((f) => ({ ...f, pct: p })), wl.rele ? claveEquipo.get() : undefined)
      flashLog(`Respuesta del bicho: ${res || 'OK'}`)
      setFlash((f) => ({ ...f, phase: 'rebooting', pct: 1, msg: 'Reiniciando… esperando que vuelva a reportar su versión.' }))
      expect.current = {
        version: target,
        timer: setTimeout(() => {
          if (expect.current) {
            expect.current = null
            setFlash((f) => ({ ...f, phase: 'warn', msg: 'Se instaló, pero el bicho no volvió en 30 s. Revisa `journalctl -u bichod` en el Pi.' }))
          }
        }, 30_000),
      }
    } catch (e) {
      const msg = String((e as Error).message ?? e)
      flashLog(`✖ ${msg}`)
      setFlash((f) => ({ ...f, phase: 'error', msg }))
    }
  }
  startFlashRef.current = startFlash
  busyRef.current = busy

  /* ---------- estado ---------- */
  const connected = status === 'connected'
  const conn = connected ? 'on' : status === 'connecting' || status === 'reconnecting' ? 'wait' : 'off'
  const cmp = info && latest ? cmpSemver(latest.version, info.fw) : null
  const fwState: FwState = busy ? 'flashing' : cmp === null ? 'unknown' : cmp > 0 ? 'outdated' : cmp === 0 ? 'uptodate' : 'newer'
  const runningRelease = info ? releases.find((r) => r.version === info.fw) : undefined
  const kindLabel = link?.kind === 'sim' ? 'Simulador' : 'WiFi'
  const canFlash = !busy && connected

  const statusText = busy
    ? `Actualizando · ${Math.round(flash.pct * 100)} %`
    : conn === 'wait'
      ? 'Conectando'
      : !connected
        ? 'Sin conexión'
        : sinBicho
          ? 'Bicho desconectado'
          : !info
            ? 'Esperando versión'
          : !latest
            ? 'Sin versiones publicadas'
            : cmp! > 0
              ? 'Desactualizado'
              : cmp === 0
                ? 'Al día'
                : 'Más nuevo que lo publicado'

  useEffect(() => {
    const root = document.documentElement
    root.dataset.state = fwState
    root.dataset.conn = busy ? 'on' : conn
  }, [fwState, conn, busy])

  /* ---------- pestaña: título e ícono con el estado ---------- */
  useEffect(() => {
    document.title = busy
      ? `${Math.round(flash.pct * 100)} % · Actualizando · bicho·dev`
      : info && connected
        ? `v${info.fw} · ${statusText} · bicho·dev`
        : 'bicho·dev'
    setFavicon(busy || fwState === 'newer' ? '#007aff' : !connected ? '#aeaeb2' : fwState === 'outdated' ? '#ff9f0a' : fwState === 'uptodate' ? '#34c759' : '#aeaeb2')
  }, [busy, flash.pct, info, connected, statusText, fwState])

  /* ---------- avisos de la actualización ---------- */
  const prevPhase = useRef<FlashPhase>('idle')
  useEffect(() => {
    const p = prevPhase.current
    prevPhase.current = flash.phase
    if (p === flash.phase) return
    if (flash.phase === 'done') toast({ tone: 'ok', title: 'Bicho actualizado', body: flash.msg })
    if (flash.phase === 'warn') toast({ tone: 'warn', title: 'Revisa la actualización', body: flash.msg }, 9000)
    if (flash.phase === 'error') toast({ tone: 'err', title: 'No se pudo actualizar', body: flash.msg }, 9000)
  }, [flash.phase, flash.msg, toast])

  /* ---------- aviso cuando alguien publica una versión nueva ---------- */
  const published = manifest?.releases[0]
  const prevPublished = useRef<string | undefined>(undefined)
  useEffect(() => {
    const v = published?.version
    const prev = prevPublished.current
    prevPublished.current = v
    if (prev && v && cmpSemver(v, prev) > 0)
      toast({ tone: 'info', title: `Nueva versión publicada: v${v}`, body: [published?.author, published?.notes].filter(Boolean).join(' · ') }, 9000)
  }, [published?.version, published?.author, published?.notes, toast])

  /* ---------- soltar un paquete en cualquier parte ---------- */
  useEffect(() => {
    let depth = 0
    const hasFiles = (e: DragEvent) => !!e.dataTransfer && [...e.dataTransfer.types].includes('Files')
    const enter = (e: DragEvent) => {
      if (!hasFiles(e)) return
      e.preventDefault()
      depth++
      setDragging(true)
    }
    const over = (e: DragEvent) => {
      if (hasFiles(e)) e.preventDefault()
    }
    const leave = (e: DragEvent) => {
      if (!hasFiles(e)) return
      depth = Math.max(0, depth - 1)
      if (!depth) setDragging(false)
    }
    const drop = (e: DragEvent) => {
      if (!hasFiles(e)) return
      e.preventDefault()
      depth = 0
      setDragging(false)
      const f = e.dataTransfer!.files[0]
      if (!f) return
      if (!/\.(tar\.gz|tgz)$/i.test(f.name)) return toast({ tone: 'warn', title: 'Ese archivo no es un paquete del bicho', body: 'Suelta un .tar.gz hecho con npm run release.' })
      if (busyRef.current) return toast({ tone: 'warn', title: 'Ya se está actualizando', body: 'Espera a que termine.' })
      startFlashRef.current({ kind: 'file', file: f })
    }
    addEventListener('dragenter', enter)
    addEventListener('dragover', over)
    addEventListener('dragleave', leave)
    addEventListener('drop', drop)
    return () => {
      removeEventListener('dragenter', enter)
      removeEventListener('dragover', over)
      removeEventListener('dragleave', leave)
      removeEventListener('drop', drop)
    }
  }, [toast])

  const onDeadlineAlert = useCallback(
    (a: { title: string; body: string; urgent: boolean }) => toast({ tone: a.urgent ? 'err' : 'warn', title: a.title, body: a.body }, a.urgent ? 20000 : 12000),
    [toast],
  )

  const pickFile = () => fileInput.current?.click()
  const resetFlash = () => setFlash({ phase: 'idle', pct: 0, log: [] })
  const startRelease = (r: Release) => startFlash({ kind: 'release', rel: r })

  return (
    <>
      <SparkDefs />
      <Toasts items={toasts} onClose={closeToast} />
      {dragging && (
        <div className="drop" aria-hidden>
          <div className="drop-card glass">
            <span className="up-icon">
              <Icon.Download />
            </span>
            <p className="drop-t">Suelta el paquete para instalarlo</p>
            <p className="drop-s">{busy ? 'Espera: ya se está actualizando.' : connected ? `Se instala por ${flashVia}.` : 'Primero conecta el bicho por WiFi.'}</p>
          </div>
        </div>
      )}
      <div className="wallpaper" aria-hidden>
        <i className="b1" />
        <i className="b2" />
        <i className="b3" />
        <i className="b4" />
        <i className="b5" />
        <i className="b6" />
      </div>
      <input
        ref={fileInput}
        type="file"
        accept=".gz,.tgz"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0]
          e.target.value = ''
          if (f) startFlash({ kind: 'file', file: f })
        }}
      />

      <div className="window">
        {/* ── barra lateral ── */}
        <aside className="sidebar glass" aria-label="Navegación y conexión">
          <div className="brand">
            <span className="appicon" aria-hidden>
              <Icon.Ojo />
            </span>
            <div>
              <p className="brand-name">bicho·dev</p>
              <p className="brand-sub">CRBRC · Platanus Hack 26</p>
            </div>
            <BotonTema />
          </div>

          <Countdown onAlert={onDeadlineAlert} />

          <nav className="nav" aria-label="Secciones">
            <p className="nav-label">Bicho</p>
            {NAV.map((n, i) => (
              <a key={n.id} href={`#${n.id}`} aria-current={view === 'bicho' && active === i ? 'true' : undefined} onClick={(e) => goSection(e, i)}>
                <n.icon />
                <span>{n.label}</span>
                {n.id === 'firmware' && fwState === 'outdated' && <i className="nav-badge" title="Hay una versión nueva" />}
                {n.id === 'sensores' && <small className="nav-aside">{connected ? store.hz.toFixed(1) : '0.0'} Hz</small>}
              </a>
            ))}
            <a href="#simulador" aria-current={view === 'simulador' ? 'true' : undefined}>
              <Icon.Play />
              <span>Simulador</span>
            </a>
            <a href="#brazo" aria-current={view === 'brazo' ? 'true' : undefined}>
              <Icon.Brazo />
              <span>Brazo</span>
            </a>
            <a href="#gemelo" aria-current={view === 'gemelo' ? 'true' : undefined}>
              <Icon.Bicho />
              <span>Gemelo 3D</span>
            </a>
            <a href="#manos" aria-current={view === 'manos' ? 'true' : undefined}>
              <Icon.Sparkle />
              <span>Manos</span>
            </a>
          </nav>

          <nav className="nav nav-inv" aria-label="Equipo">
            <p className="nav-label">Equipo</p>
            <a href="#inventario" aria-current={view === 'inventario' ? 'true' : undefined}>
              <Icon.Box />
              <span>Inventario</span>
            </a>
          </nav>

          <div className="conn">
            <p className="conn-label">Conexión</p>
            <div className="conn-head">
              <span className="conn-dot" aria-hidden />
              <div className="conn-text">
                <p className="conn-title">{connected ? ((link as WifiLink | null)?.rele ? (sinBicho ? 'Relé arriba, bicho desconectado' : 'Conectado por el relé') : `Conectado por ${kindLabel}`) : conn === 'wait' ? 'Conectando…' : 'Sin conexión'}</p>
                <p className="conn-host">{!link ? 'Raspberry Pi por WiFi' : link.kind === 'sim' ? 'Datos simulados' : (statusDetail ?? link.label)}</p>
              </div>
            </div>
            {!link && (
              <div className="host-row">
                <input
                  className="field"
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && connectWifi()}
                  placeholder="bicho.local, IP o https://relé"
                  aria-label="Dirección del bicho"
                  title={`Se conecta a ${normalizeHost(host || 'bicho.local')}`}
                />
              </div>
            )}
            <div className="seg two" role="group" aria-label="Conectar por">
              <button type="button" aria-pressed={link?.kind === 'wifi'} disabled={busy} onClick={connectWifi} title={`Conectar a ${normalizeHost(host || 'bicho.local')}`}>
                WiFi
              </button>
              <button type="button" aria-pressed={link?.kind === 'sim'} disabled={busy} onClick={connectSim} title="Datos simulados, sin hardware">
                Simulador
              </button>
            </div>
            {link && (
              <button type="button" className="btn-quiet" onClick={disconnect} disabled={busy}>
                <Icon.Power /> Desconectar
              </button>
            )}
          </div>
        </aside>

        {/* ── contenido ── */}
        <main className={`main ${scrolled ? 'scrolled' : ''} ${view === 'brazo' || view === 'gemelo' || view === 'manos' ? 'fija' : ''}`} ref={mainRef}>
          <div className="main-inner">
            {view === 'inventario' ? (
              <Inventario toast={toast} />
            ) : view === 'simulador' ? (
              <Suspense fallback={<p className="notice">Cargando el simulador…</p>}>
                <Simulador />
              </Suspense>
            ) : view === 'gemelo' ? (
              <Suspense fallback={<p className="notice">Armando el gemelo…</p>}>
                <Gemelo store={store} conectado={connected && !sinBicho} imagenes={imagenes} enviar={(l) => void send(l)} />
              </Suspense>
            ) : view === 'manos' ? (
              <Suspense fallback={<p className="notice">Cargando la demo…</p>}>
                <Manos />
              </Suspense>
            ) : view === 'brazo' ? (
              <Suspense fallback={<p className="notice">Cargando el brazo…</p>}>
                <Brazo conectado={connected && !sinBicho} motivo={relLink ? motivoCerebro : null} enviar={(l) => void send(l)} />
              </Suspense>
            ) : (
            <>
            <header className="toolbar">
              <div className="tb-title">
                <h1>{NAV[active].label}</h1>
                <p>
                  {info?.name ?? 'bicho'} · {info?.chip ?? (connected ? (sinBicho ? 'desconectado del relé' : 'esperando info') : 'sin conectar')}
                </p>
              </div>
              <div className="tb-actions">
                <span className="capsule" title={`Versión de esta web · build ${__BUILD_TIME__}`}>
                  Web <b>{frontendVersion()}</b>
                </span>
                <button type="button" className="capsule" disabled={!connected} onClick={() => send(CMD.info)} title="Pedir info al bicho">
                  <Icon.Info /> Pedir info
                </button>
              </div>
            </header>

            {location.protocol === 'https:' && !esRele(host) && (
              <p className="notice">
                <Icon.Warning /> Estás en HTTPS: el navegador bloquea la conexión directa con el bicho en la red local. Conéctate por el relé
                {RELE_PUBLICO ? ` (${RELE_PUBLICO})` : ''} o corre la web en localhost.
              </p>
            )}

            <Habilidades eventos={eventos} fw={info?.fw ?? null} releases={manifest?.releases ?? []} codigo={codigo?.archivos ?? null} />

            {/* firmware + disponible */}
            <section className="sec" id="firmware" aria-label="Firmware">
              <div className="fw-grid">
                <article className="card glass hero">
                  <span className="glow glow-y" aria-hidden />
                  <span className="glow glow-b" aria-hidden />
                  <span className="glow glow-g" aria-hidden />
                  <div className="hero-top">
                    <p className="eyebrow">Firmware en el bicho</p>
                    <span className="status">
                      <i aria-hidden />
                      {statusText}
                    </span>
                  </div>

                  {info ? (
                    <>
                      <p className="version" key={info.fw}>
                        <span className="v">v</span>
                        {info.fw}
                      </p>
                      <p className="desc">
                        {info.desc || runningRelease?.notes || <span className="muted">El agente no mandó descripción (campo “desc” de version.json).</span>}
                      </p>
                      <dl className="meta">
                        {[
                          ['Placa', info.chip],
                          ['Red', typeof info.red === 'string' ? info.red : undefined],
                          ['Dirección IP', info.ip],
                          ['Encendido hace', fmtUptime(info.uptime)],
                          ['Publicado', info.build],
                          ['Memoria libre', typeof info.heap === 'number' ? fmtBytes(info.heap) : undefined],
                          ['MAC', info.mac],
                        ].map(([k, v]) => (
                          <div key={k}>
                            <dt>{k}</dt>
                            <dd title={v ?? undefined}>{v ?? '—'}</dd>
                          </div>
                        ))}
                      </dl>
                    </>
                  ) : (
                    <>
                      <p className="version empty">{connected && !sinBicho ? 'Esperando…' : conn === 'wait' ? 'Conectando…' : 'Sin bicho'}</p>
                      <p className="desc">
                        {connected && sinBicho
                          ? 'El relé está arriba, pero el bicho no está conectado a él. ¿Está prendido y con internet? Cuando vuelva, aparece solo.'
                          : connected
                          ? 'Ya hay conexión, pero el bicho todavía no manda su versión.'
                          : conn === 'wait'
                            ? esRele(host)
                              ? `Esperando al bicho en el relé ${normalizeHost(host)}. ¿Está prendido y con internet?`
                              : `Buscando el Raspberry en ${normalizeHost(host || 'bicho.local')}. ¿Está prendido y en la misma red?`
                            : 'Prende el Raspberry y conéctate por WiFi, o abre el simulador para probar la web sin hardware.'}
                      </p>
                      <div className="hero-actions">
                        {connected ? (
                          <button type="button" className="btn-secondary" onClick={() => send(CMD.info)}>
                            <Icon.Refresh /> Pedir versión
                          </button>
                        ) : (
                          <>
                            <button type="button" className="btn-primary" onClick={connectWifi} disabled={busy || conn === 'wait'}>
                              Conectar a {host || 'bicho.local'}
                            </button>
                            <button type="button" className="btn-secondary" onClick={connectSim} disabled={busy}>
                              Abrir simulador
                            </button>
                          </>
                        )}
                      </div>
                    </>
                  )}
                </article>

                <article className="card glass update">
                  <div className="up-head">
                    <span className="up-icon" aria-hidden>
                      <Icon.Download />
                    </span>
                    <div className="up-head-text">
                      <p className="eyebrow">Versión disponible</p>
                      <p className="up-by">{latest ? `Lista para instalar por ${flashVia}` : 'Nada publicado todavía'}</p>
                    </div>
                    {fwState === 'outdated' && <span className="chip-new">Nueva</span>}
                  </div>

                  {latest ? (
                    <>
                      <p className="up-version">
                        <span className="v">v</span>
                        {latest.version}
                      </p>
                      {latest.notes && <p className="up-notes">{latest.notes}</p>}
                      <dl className="meta up-meta">
                        <div>
                          <dt>Autor</dt>
                          <dd>{latest.author || '—'}</dd>
                        </div>
                        <div>
                          <dt>Publicada</dt>
                          <dd>{fmtAgo(latest.date) || '—'}</dd>
                        </div>
                      </dl>
                    </>
                  ) : (
                    <>
                      <p className="up-empty">Nada publicado todavía.</p>
                      <p className="up-empty-hint">
                        {manifestErr ?? (
                          <>
                            Publica una versión con <code>npm run release</code> o suelta aquí un paquete <code>.tar.gz</code>.
                          </>
                        )}
                      </p>
                    </>
                  )}

                  <div className="up-action">
                    {busy ? (
                      <>
                        <button type="button" className="btn-primary" disabled>
                          <Icon.Download /> Actualizando…
                        </button>
                        <div className="progress">
                          <div className="bar" style={{ '--p': flash.pct } as React.CSSProperties}>
                            <span />
                          </div>
                          <div className="progress-meta">
                            <span>
                              {flash.phase === 'preparing'
                                ? `Preparando ${flash.target}…`
                                : flash.phase === 'rebooting'
                                  ? (flash.msg ?? 'Reiniciando…')
                                  : `Enviando ${flash.target} por ${flash.via}…`}
                            </span>
                            <b>{Math.round(flash.pct * 100)} %</b>
                          </div>
                          {flash.log.length > 0 && <pre className="flash-log">{flash.log.slice(-4).join('\n')}</pre>}
                        </div>
                      </>
                    ) : (
                      <>
                        {(flash.phase === 'warn' || flash.phase === 'error') && (
                          <div className={`ok ${flash.phase === 'error' ? 'err' : 'warn'}`}>
                            <span className="ok-ic" aria-hidden>
                              <Icon.Alert />
                            </span>
                            <div>
                              <p className="ok-t">{flash.phase === 'error' ? 'No se pudo actualizar' : 'Revisa esto'}</p>
                              <p className="ok-s">{flash.msg}</p>
                            </div>
                          </div>
                        )}

                        {latest && fwState === 'outdated' && (
                          <>
                            <p className="up-diff">
                              <span>v{info!.fw}</span>
                              <Icon.Arrow />
                              <b>v{latest.version}</b>
                            </p>
                            <button type="button" className="btn-primary" disabled={!canFlash} onClick={() => startRelease(latest)}>
                              <Icon.Download /> Actualizar a v{latest.version}
                            </button>
                          </>
                        )}

                        {latest && fwState === 'uptodate' && (
                          <div className="ok">
                            <span className="ok-ic" aria-hidden>
                              <Icon.Check />
                            </span>
                            <div>
                              <p className="ok-t">El bicho está al día</p>
                              <p className="ok-s">{flash.phase === 'done' && flash.msg ? flash.msg : 'Corre la última versión publicada.'}</p>
                            </div>
                          </div>
                        )}

                        {latest && fwState === 'newer' && (
                          <>
                            <div className="ok info">
                              <span className="ok-ic" aria-hidden>
                                <Icon.Info />
                              </span>
                              <div>
                                <p className="ok-t">Corre una versión que aprendió solo</p>
                                <p className="ok-s">
                                  v{info!.fw} la instaló su cerebro y no está publicada en el repo. Volver a v{latest.version} le borra lo que aprendió.
                                </p>
                              </div>
                            </div>
                            <button type="button" className="btn-link" disabled={!canFlash} onClick={() => startRelease(latest)}>
                              Volver a v{latest.version} publicada
                            </button>
                          </>
                        )}

                        {latest && fwState === 'unknown' && (
                          <>
                            <button type="button" className="btn-primary" disabled={!canFlash} onClick={() => startRelease(latest)}>
                              <Icon.Download /> Instalar v{latest.version}
                            </button>
                            <p className="off-hint">{connected ? (sinBicho ? 'El bicho no está conectado al relé: préndelo para poder actualizarlo.' : 'El bicho todavía no reporta su versión.') : 'Conecta el bicho por WiFi para poder actualizarlo.'}</p>
                          </>
                        )}

                        <div className="links-row">
                          {latest && fwState === 'uptodate' && (
                            <button type="button" className="btn-link" disabled={!canFlash} onClick={() => startRelease(latest)}>
                              Reinstalar v{latest.version}
                            </button>
                          )}
                          <button type="button" className="btn-link" disabled={!canFlash} onClick={pickFile} title="También puedes soltarlo en cualquier parte de la página">
                            Instalar un paquete local
                          </button>
                          {(flash.phase === 'warn' || flash.phase === 'error' || flash.phase === 'done') && (
                            <button type="button" className="btn-link" onClick={resetFlash}>
                              Ocultar aviso
                            </button>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                </article>
              </div>
            </section>

            <Manejo conectado={connected && !sinBicho} motivo={relLink ? motivoCerebro : null} enviar={(l) => void send(l)} />

            <Sensors store={store} connected={connected} onRate={(hz) => send(CMD.rate(hz))} />

            <Oido store={store} connected={connected} frases={frases} />

            <Cerebro
              eventos={eventos}
              imagenes={imagenes}
              voces={voces}
              vozAqui={vozAqui}
              onVozAqui={cambiarVozAqui}
              connected={connected}
              sinBicho={sinBicho}
              motivo={motivoCerebro}
              onReconectar={reconectarRele}
              onDecir={decirAlCerebro}
            />

            <div className="split">
              <Console
                lines={lines}
                connected={connected}
                linkLabel={kindLabel}
                onSend={send}
                onClear={() => {
                  lineBuf.current = []
                  setLines([])
                }}
              />

              <section className="sec" id="versiones" aria-label="Versiones">
                <article className="card glass versions">
                  <header className="card-head">
                    <div>
                      <h2>Versiones</h2>
                      <p>Historial publicado por el equipo</p>
                    </div>
                    <div className="head-actions">
                      <button type="button" className="btn-secondary" onClick={refreshManifest} title="Recargar versiones" aria-label="Recargar versiones">
                        <Icon.Refresh />
                      </button>
                    </div>
                  </header>
                  {releases.length === 0 ? (
                    <div className="empty">
                      <p className="empty-t">Sin versiones</p>
                      <p className="empty-s">
                        Publícalas con <code>npm run release</code>.
                      </p>
                    </div>
                  ) : (
                    <ol className="releases">
                      {/* Lo que el bicho aprendió solo no está en el manifiesto: se muestra igual, sin botón de instalar. */}
                      {info?.fw && !releases.some((r) => r.version === info.fw) && (
                        <li className="rel" data-current="">
                          <span className="rel-dot" aria-hidden />
                          <div>
                            <div className="rel-head">
                              <b>v{info.fw}</b>
                              <span className="tag tag-cur">En el bicho</span>
                            </div>
                            {info.desc && <p>{info.desc}</p>}
                            <span className="rel-by">Aprendida por el bicho · no publicada</span>
                          </div>
                        </li>
                      )}
                      {releases.map((r) => {
                        const current = info?.fw === r.version
                        const isLatest = r === latest
                        return (
                          <li key={r.version} className="rel" data-current={current ? '' : undefined} data-latest={isLatest ? '' : undefined}>
                            <span className="rel-dot" aria-hidden />
                            <div>
                              <div className="rel-head">
                                <b>v{r.version}</b>
                                {current && <span className="tag tag-cur">En el bicho</span>}
                                {isLatest && <span className="tag tag-new">Última</span>}
                              </div>
                              {r.notes && <p>{r.notes}</p>}
                              <span className="rel-by">{[r.author, fmtAgo(r.date), r.size ? fmtBytes(r.size) : ''].filter(Boolean).join(' · ')}</span>
                            </div>
                            <button type="button" className="btn-link" disabled={!canFlash} onClick={() => startRelease(r)}>
                              Instalar
                            </button>
                          </li>
                        )
                      })}
                    </ol>
                  )}
                </article>
              </section>
            </div>
            </>
            )}
          </div>
        </main>
      </div>
    </>
  )
}
