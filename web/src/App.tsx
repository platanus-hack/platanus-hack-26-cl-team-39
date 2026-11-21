import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Console, type ConsoleLine } from './components/Console'
import { Sensors } from './components/Sensors'
import { Toasts, type Toast } from './components/Toasts'
import { Icon, SparkDefs, fmtAgo, fmtUptime } from './components/ui'
import {
  cmpSemver,
  fetchBin,
  flashOta,
  flashUsb,
  loadManifest,
  looksLikeApp,
  looksLikeMerged,
  usbParts,
  type Manifest,
  type Release,
} from './lib/firmware'
import { SerialLink, SimLink, WifiLink, type DeviceLink, type LineDir, type LinkHandlers, type LinkStatus } from './lib/links'
import { CMD, type DeviceInfo } from './lib/protocol'
import { SensorStore } from './lib/sensors'

const hasSerial = typeof navigator !== 'undefined' && 'serial' in navigator
const MAX_LINES = 600

type FlashPhase = 'idle' | 'preparing' | 'flashing' | 'rebooting' | 'done' | 'warn' | 'error'
type FlashState = { phase: FlashPhase; pct: number; target?: string; via?: string; msg?: string; log: string[] }
type FlashSource = { kind: 'release'; rel: Release } | { kind: 'file'; file: File }
type FwState = 'outdated' | 'flashing' | 'uptodate' | 'newer' | 'unknown'

const SIM_RELEASE: Release = {
  version: '0.2.0',
  date: new Date().toISOString(),
  author: 'simulador',
  notes: '(simulada) Agrega detección de voz y baile de servos.',
  app: 'sim',
}

const NAV = [
  { id: 'firmware', label: 'Firmware', icon: Icon.Chip },
  { id: 'sensores', label: 'Sensores', icon: Icon.Pulse },
  { id: 'consola', label: 'Consola', icon: Icon.Terminal },
  { id: 'versiones', label: 'Versiones', icon: Icon.History },
] as const

/** Ícono de la pestaña: la app con un punto del color del estado. */
function setFavicon(dot: string) {
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><defs><linearGradient id='g' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#ffe46b'/><stop offset='1' stop-color='#ffad00'/></linearGradient></defs><rect x='2' y='2' width='60' height='60' rx='15' fill='url(#g)'/><g transform='translate(5 4) scale(1.6)' fill='none' stroke='#3b2a00' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'><path d='M8.5 26h12'/><path d='M13 25.5 10.6 17l7.4-5.2'/><path d='M16.2 9.4 23.8 7l1.6 6.8z' fill='#3b2a00'/></g><circle cx='50' cy='50' r='11' fill='${dot}' stroke='#fff' stroke-width='4'/></svg>`
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
      const sameRow = Math.abs(tops[2] - tops[3]) < 4
      if (atEnd) cur = sameRow ? Math.max(cur, pinned.current === 3 ? 3 : 2) : secs.length - 1
      if (sameRow && cur >= 2) cur = pinned.current === 3 ? 3 : 2
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
  const [info, setInfo] = useState<DeviceInfo | null>(null)
  const [manifest, setManifest] = useState<Manifest | null>(null)
  const [manifestErr, setManifestErr] = useState<string>()
  const [host, setHost] = useState(() => {
    try {
      return localStorage.getItem('bicho.host') || 'bicho.local'
    } catch {
      return 'bicho.local'
    }
  })
  const [flash, setFlash] = useState<FlashState>({ phase: 'idle', pct: 0, log: [] })
  const [lines, setLines] = useState<ConsoleLine[]>([])
  const [toasts, setToasts] = useState<Toast[]>([])
  const [knownPorts, setKnownPorts] = useState<SerialPort[]>([])
  const [dragging, setDragging] = useState(false)

  const store = useRef(new SensorStore()).current
  const linkRef = useRef<DeviceLink | null>(null)
  const lineBuf = useRef<ConsoleLine[]>([])
  const lineId = useRef(0)
  const dirty = useRef(false)
  const expect = useRef<{ version?: string; timer?: ReturnType<typeof setTimeout> } | null>(null)
  const suppressDisconnect = useRef(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const mainRef = useRef<HTMLElement>(null)
  const { active, scrolled, pick } = useScrollSpy(mainRef)
  const toastId = useRef(0)
  const prevStatus = useRef<LinkStatus>('disconnected')
  const userClosing = useRef(false)
  const handlersRef = useRef<LinkHandlers | null>(null)
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

  /* ---------- puertos USB ya autorizados ---------- */
  const refreshPorts = useCallback(() => {
    if (hasSerial) navigator.serial.getPorts().then(setKnownPorts).catch(() => {})
  }, [])

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
        if (s === 'disconnected' && suppressDisconnect.current) return
        const prev = prevStatus.current
        prevStatus.current = s
        setStatus(s)
        setStatusDetail(detail)
        if (s === 'connected' && (prev === 'connecting' || prev === 'disconnected')) {
          const k = linkRef.current?.kind
          toast(
            k === 'sim'
              ? { tone: 'ok', title: 'Simulador abierto', body: 'Datos simulados, sin hardware.' }
              : { tone: 'ok', title: `Conectado por ${k === 'wifi' ? 'WiFi' : 'USB'}`, body: detail },
            3000,
          )
        }
        if (s === 'disconnected') {
          if (!userClosing.current && prev !== 'disconnected') toast({ tone: 'warn', title: 'Se perdió la conexión', body: detail ?? 'El bicho dejó de responder.' })
          userClosing.current = false
          linkRef.current = null
          setLink(null)
        }
      },
      onMessage: (m) => {
        if (m.t === 's' && m.d && typeof m.d === 'object') store.push(m.d as Record<string, unknown>)
        else if (m.t === 'info') {
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
                msg: `Se grabó, pero el bicho dice v${i.fw} y esperábamos v${ex.version}. ¿Subieron FW_VERSION antes de compilar?`,
              }))
            }
          }
        }
      },
    }),
    [pushLine, store, toast],
  )
  handlersRef.current = handlers

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

  const connectUsb = async () => {
    try {
      const port = await navigator.serial.requestPort()
      refreshPorts()
      await attach(new SerialLink(port, handlers))
    } catch (e) {
      if ((e as Error).name !== 'NotFoundError') pushLine(`USB: ${(e as Error).message}`, 'sys')
    }
  }
  /** Vuelve a abrir un puerto que ya se autorizó antes, sin el diálogo del navegador. */
  const reconnectUsb = () => {
    if (knownPorts[0]) attach(new SerialLink(knownPorts[0], handlers))
  }
  const connectWifi = () => {
    try {
      localStorage.setItem('bicho.host', host)
    } catch {
      /* sin localStorage */
    }
    attach(new WifiLink(host.trim(), handlers))
  }
  const connectSim = () => attach(new SimLink(handlers))
  const disconnect = () => {
    userClosing.current = true
    linkRef.current?.close()
  }

  const send = (l: string) => linkRef.current?.sendLine(l).catch((e) => pushLine(`No se pudo enviar: ${e.message}`, 'sys'))

  /* ---------- actualizar firmware ---------- */
  const flashVia = link?.kind === 'wifi' ? 'WiFi' : link?.kind === 'sim' ? 'el simulador' : 'USB'
  const busy = flash.phase === 'preparing' || flash.phase === 'flashing' || flash.phase === 'rebooting'

  const startFlash = async (src: FlashSource) => {
    const target = src.kind === 'release' ? src.rel.version : undefined
    const label = src.kind === 'release' ? `v${src.rel.version}` : src.file.name
    setFlash({ phase: 'preparing', pct: 0, target: label, via: flashVia, log: [] })
    const current = linkRef.current
    try {
      /* Simulador */
      if (current?.kind === 'sim') {
        setFlash((f) => ({ ...f, phase: 'flashing' }))
        expect.current = { version: target }
        await (current as SimLink).simulateFlash(target ?? '0.0.0-local', src.kind === 'release' ? src.rel.notes : undefined, (p) =>
          setFlash((f) => ({ ...f, pct: p })),
        )
        return
      }

      /* Binarios */
      let app: Uint8Array | undefined
      let merged: Uint8Array | undefined
      if (src.kind === 'file') {
        const bin = new Uint8Array(await src.file.arrayBuffer())
        if (looksLikeMerged(bin)) merged = bin
        else if (looksLikeApp(bin)) app = bin
        else throw new Error('El archivo no parece un firmware ESP32 (.bin de la app o .merged.bin).')
        flashLog(`${src.file.name}: ${merged ? 'imagen merged' : 'app'} de ${(bin.length / 1024).toFixed(0)} KB`)
      } else {
        const wantMerged = current?.kind !== 'wifi' && src.rel.merged
        if (wantMerged) merged = await fetchBin(src.rel.merged!)
        else if (src.rel.app) app = await fetchBin(src.rel.app)
        else throw new Error('Esta versión solo trae imagen merged; por WiFi se necesita el .bin de la app.')
        flashLog(`Descargado ${wantMerged ? src.rel.merged : src.rel.app}`)
      }

      /* WiFi OTA */
      if (current?.kind === 'wifi') {
        if (!app) throw new Error('Por WiFi solo se puede subir el .bin de la app, no la imagen merged. Usa USB para esa.')
        const wl = current as WifiLink
        setFlash((f) => ({ ...f, phase: 'flashing' }))
        flashLog(`Subiendo a ${wl.httpBase}/update…`)
        const res = await flashOta(wl.httpBase, app, (p) => setFlash((f) => ({ ...f, pct: p })))
        flashLog(`Respuesta del bicho: ${res || 'OK'}`)
        setFlash((f) => ({ ...f, phase: 'rebooting', pct: 1, msg: 'Reiniciando… esperando que vuelva a reportar su versión.' }))
        expect.current = {
          version: target,
          timer: setTimeout(() => {
            if (expect.current) {
              expect.current = null
              setFlash((f) => ({ ...f, phase: 'warn', msg: 'Subió, pero el bicho no volvió a conectarse en 30 s. Revisa la consola o el monitor serial.' }))
            }
          }, 30_000),
        }
        return
      }

      /* USB */
      if (!hasSerial) throw new Error('Este navegador no tiene Web Serial. Usa Chrome o Edge.')
      let port: SerialPort
      if (current?.kind === 'serial') {
        port = (current as SerialLink).port
        suppressDisconnect.current = true
        await current.close()
      } else {
        port = await navigator.serial.requestPort()
      }
      setFlash((f) => ({ ...f, phase: 'flashing' }))
      const parts = usbParts({ app, merged })
      await flashUsb(port, parts, flashLog, (p) => setFlash((f) => ({ ...f, pct: p })))
      suppressDisconnect.current = false
      setFlash((f) => ({ ...f, phase: 'rebooting', msg: 'Grabado. Reabriendo el monitor serial…' }))
      expect.current = {
        version: target,
        timer: setTimeout(() => {
          if (expect.current) {
            expect.current = null
            setFlash((f) => ({ ...f, phase: 'warn', msg: 'Grabado, pero el bicho no reportó su versión en 15 s. ¿El firmware manda {"t":"info"} al arrancar?' }))
          }
        }, 15_000),
      }
      await new Promise((r) => setTimeout(r, 300))
      await attach(new SerialLink(port, handlers))
    } catch (e) {
      suppressDisconnect.current = false
      const msg = (e as Error).name === 'NotFoundError' ? 'Cancelado: no se eligió puerto.' : String((e as Error).message ?? e)
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
  const kindLabel = link?.kind === 'serial' ? 'USB' : link?.kind === 'wifi' ? 'WiFi' : 'Simulador'
  const canFlash = !busy && (!!link || hasSerial)

  const statusText = busy
    ? `Actualizando · ${Math.round(flash.pct * 100)} %`
    : conn === 'wait'
      ? 'Conectando'
      : !connected
        ? 'Sin conexión'
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

  /* ---------- avisos del grabado ---------- */
  const prevPhase = useRef<FlashPhase>('idle')
  useEffect(() => {
    const p = prevPhase.current
    prevPhase.current = flash.phase
    if (p === flash.phase) return
    if (flash.phase === 'done') toast({ tone: 'ok', title: 'Firmware actualizado', body: flash.msg })
    if (flash.phase === 'warn') toast({ tone: 'warn', title: 'Revisa el grabado', body: flash.msg }, 9000)
    if (flash.phase === 'error') toast({ tone: 'err', title: 'No se pudo grabar', body: flash.msg }, 9000)
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

  /* ---------- detectar el bicho al enchufarlo ---------- */
  useEffect(() => {
    if (!hasSerial) return
    refreshPorts()
    const onConnect = (e: Event) => {
      refreshPorts()
      const port = e.target as SerialPort
      if (linkRef.current || !handlersRef.current) return
      toast(
        {
          tone: 'info',
          title: 'Bicho enchufado',
          body: 'Se detectó por USB un puerto que ya usaste.',
          action: { label: 'Conectar', onClick: () => attach(new SerialLink(port, handlersRef.current!)) },
        },
        12000,
      )
    }
    navigator.serial.addEventListener('connect', onConnect)
    navigator.serial.addEventListener('disconnect', refreshPorts)
    return () => {
      navigator.serial.removeEventListener('connect', onConnect)
      navigator.serial.removeEventListener('disconnect', refreshPorts)
    }
  }, [refreshPorts, toast, attach])

  /* ---------- soltar un .bin en cualquier parte ---------- */
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
      if (!/\.bin$/i.test(f.name)) return toast({ tone: 'warn', title: 'Ese archivo no es un firmware', body: 'Suelta un .bin exportado desde Arduino.' })
      if (busyRef.current) return toast({ tone: 'warn', title: 'Ya se está grabando', body: 'Espera a que termine.' })
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

  const pickFile = () => fileInput.current?.click()
  const resetFlash = () => setFlash({ phase: 'idle', pct: 0, log: [] })

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
            <p className="drop-t">Suelta el .bin para grabarlo</p>
            <p className="drop-s">{busy ? 'Espera: ya se está grabando.' : link ? `Se graba por ${flashVia}.` : 'Se graba por USB: te va a pedir el puerto.'}</p>
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
        accept=".bin"
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
              <Icon.Bicho />
            </span>
            <div>
              <p className="brand-name">bicho·dev</p>
              <p className="brand-sub">CRBRC · Platanus Hack 26</p>
            </div>
          </div>

          <nav className="nav" aria-label="Secciones">
            <p className="nav-label">Bicho</p>
            {NAV.map((n, i) => (
              <a key={n.id} href={`#${n.id}`} aria-current={active === i ? 'true' : undefined} onClick={() => pick(i)}>
                <n.icon />
                <span>{n.label}</span>
                {n.id === 'firmware' && fwState === 'outdated' && <i className="nav-badge" title="Hay una versión nueva" />}
                {n.id === 'sensores' && <small className="nav-aside">{connected ? store.hz.toFixed(1) : '0.0'} Hz</small>}
              </a>
            ))}
          </nav>

          <div className="conn">
            <p className="conn-label">Conexión</p>
            <div className="conn-head">
              <span className="conn-dot" aria-hidden />
              <div className="conn-text">
                <p className="conn-title">{connected ? `Conectado por ${kindLabel}` : conn === 'wait' ? 'Conectando…' : 'Sin conexión'}</p>
                <p className="conn-host">{!link ? 'Elige cómo conectar' : link.kind === 'sim' ? 'Datos simulados' : (statusDetail ?? link.label)}</p>
              </div>
            </div>
            {!link && (
              <div className="host-row">
                <input
                  className="field"
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && connectWifi()}
                  placeholder="bicho.local o IP"
                  aria-label="Dirección del bicho por WiFi"
                />
              </div>
            )}
            <div className="seg" role="group" aria-label="Conectar por">
              <button type="button" aria-pressed={link?.kind === 'serial'} disabled={!hasSerial || busy} onClick={connectUsb} title={hasSerial ? 'Conectar por cable USB' : 'Necesitas Chrome o Edge'}>
                USB
              </button>
              <button type="button" aria-pressed={link?.kind === 'wifi'} disabled={busy} onClick={connectWifi} title={`Conectar a ${host}`}>
                WiFi
              </button>
              <button type="button" aria-pressed={link?.kind === 'sim'} disabled={busy} onClick={connectSim} title="Datos simulados, sin hardware">
                Simulador
              </button>
            </div>
            {!link && knownPorts.length > 0 && (
              <button type="button" className="btn-link conn-again" onClick={reconnectUsb} disabled={busy}>
                Reconectar al último USB
              </button>
            )}
            {link && (
              <button type="button" className="btn-quiet" onClick={disconnect} disabled={busy}>
                <Icon.Power /> Desconectar
              </button>
            )}
          </div>
        </aside>

        {/* ── contenido ── */}
        <main className={`main ${scrolled ? 'scrolled' : ''}`} ref={mainRef}>
          <div className="main-inner">
          <header className="toolbar">
            <div className="tb-title">
              <h1>{NAV[active].label}</h1>
              <p>
                {info?.name ?? 'bicho'} · {info?.chip ?? (connected ? 'esperando info' : 'sin conectar')}
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

          {!hasSerial && (
            <p className="notice">
              <Icon.Warning /> Este navegador no tiene Web Serial, así que el USB no va a funcionar. Abre la web en Chrome o Edge.
            </p>
          )}
          {location.protocol === 'https:' && (
            <p className="notice">
              <Icon.Warning /> Estás en HTTPS: el navegador bloquea el WiFi hacia el bicho. Para usar WiFi corre la web en localhost; el USB funciona igual.
            </p>
          )}

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
                      {info.desc || runningRelease?.notes || <span className="muted">El firmware no mandó descripción (campo “desc”).</span>}
                    </p>
                    <dl className="meta">
                      {[
                        ['Chip', info.chip],
                        ['Dirección IP', info.ip],
                        ['Encendido hace', fmtUptime(info.uptime)],
                        ['Compilado', info.build],
                        ['Memoria libre', info.heap ? `${Math.round(info.heap / 1024)} KB` : undefined],
                        ['MAC', info.mac],
                      ].map(([k, v]) => (
                        <div key={k}>
                          <dt>{k}</dt>
                          <dd>{v ?? '—'}</dd>
                        </div>
                      ))}
                    </dl>
                  </>
                ) : (
                  <>
                    <p className="version empty">{connected ? 'Esperando…' : conn === 'wait' ? 'Conectando…' : 'Sin bicho'}</p>
                    <p className="desc">
                      {connected
                        ? 'Ya hay conexión, pero el bicho todavía no manda su versión.'
                        : 'Enchúfalo por USB para ver qué firmware tiene, o abre el simulador para probar la web sin hardware.'}
                    </p>
                    <div className="hero-actions">
                      {connected ? (
                        <button type="button" className="btn-secondary" onClick={() => send(CMD.info)}>
                          <Icon.Refresh /> Pedir versión
                        </button>
                      ) : (
                        <>
                          {knownPorts.length > 0 ? (
                            <button type="button" className="btn-primary" onClick={reconnectUsb} disabled={busy}>
                              Reconectar USB
                            </button>
                          ) : (
                            <button type="button" className="btn-primary" onClick={connectUsb} disabled={!hasSerial || busy}>
                              Conectar por USB
                            </button>
                          )}
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
                    <p className="up-by">{latest ? `Lista para grabar por ${flashVia}` : 'Nada publicado todavía'}</p>
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
                          Publica una versión con <code>npm run release</code> o graba un .bin desde tu computador.
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
                                : `Grabando ${flash.target} por ${flash.via}…`}
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
                            <p className="ok-t">{flash.phase === 'error' ? 'No se pudo grabar' : 'Revisa esto'}</p>
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
                          <button type="button" className="btn-primary" disabled={!canFlash} onClick={() => startFlash({ kind: 'release', rel: latest })}>
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
                              <p className="ok-t">Corre algo más nuevo</p>
                              <p className="ok-s">v{info!.fw} no está publicada. ¿Alguien grabó desde el IDE?</p>
                            </div>
                          </div>
                          <button type="button" className="btn-primary" disabled={!canFlash} onClick={() => startFlash({ kind: 'release', rel: latest })}>
                            <Icon.Download /> Grabar v{latest.version} publicada
                          </button>
                        </>
                      )}

                      {latest && fwState === 'unknown' && (
                        <>
                          <button type="button" className="btn-primary" disabled={!canFlash} onClick={() => startFlash({ kind: 'release', rel: latest })}>
                            <Icon.Download /> Grabar v{latest.version}
                          </button>
                          <p className="off-hint">
                            {link ? 'El bicho todavía no reporta su versión.' : hasSerial ? 'Sin conexión: se graba por USB y te pide el puerto.' : 'Conecta el bicho para poder actualizar.'}
                          </p>
                        </>
                      )}

                      <div className="links-row">
                        {latest && fwState === 'uptodate' && (
                          <button type="button" className="btn-link" disabled={!canFlash} onClick={() => startFlash({ kind: 'release', rel: latest })}>
                            Volver a grabar v{latest.version}
                          </button>
                        )}
                        <button type="button" className="btn-link" disabled={!canFlash} onClick={pickFile}>
                          Grabar un .bin local
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

          <Sensors store={store} connected={connected} onRate={(hz) => send(CMD.rate(hz))} />

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
                            <span className="rel-by">
                              {[r.author, fmtAgo(r.date), [r.app && 'app', r.merged && 'merged'].filter(Boolean).join(' + ')].filter(Boolean).join(' · ')}
                            </span>
                          </div>
                          <button type="button" className="btn-link" disabled={!canFlash} onClick={() => startFlash({ kind: 'release', rel: r })}>
                            Grabar
                          </button>
                        </li>
                      )
                    })}
                  </ol>
                )}
              </article>
            </section>
          </div>
          </div>
        </main>
      </div>
    </>
  )
}
