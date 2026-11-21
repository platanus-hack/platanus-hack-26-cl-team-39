import { clave } from './inventario'
import { CMD, parseLine, type DeviceInfo, type DeviceMsg } from './protocol'

export type LinkKind = 'wifi' | 'sim'
export type LinkStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected'
export type LineDir = 'in' | 'out' | 'sys'

export interface LinkHandlers {
  onMessage: (m: DeviceMsg) => void
  onLine: (line: string, dir: LineDir) => void
  onStatus: (s: LinkStatus, detail?: string) => void
}

export interface DeviceLink {
  readonly kind: LinkKind
  readonly label: string
  open(): Promise<void>
  sendLine(line: string): Promise<void>
  close(): Promise<void>
}

export const DEFAULT_PORT = 8080

/** ¿Es la dirección del relé (https://…) y no la del bicho en la red local? */
export const esRele = (host: string) => /^https?:\/\//i.test(host.trim())

/** "bicho.local" → "bicho.local:8080"; si ya trae puerto lo respeta. Un sitio con relé queda como su dominio. */
export function normalizeHost(host: string) {
  if (esRele(host)) {
    try {
      return new URL(host.trim()).host
    } catch {
      /* dirección a medio escribir: sigue abajo */
    }
  }
  const h = host.trim().replace(/^(https?|wss?):\/\//, '').replace(/\/.*$/, '')
  return /:\d+$/.test(h) ? h : `${h}:${DEFAULT_PORT}`
}

function dispatchLine(line: string, h: LinkHandlers) {
  if (!line) return
  const msg = parseLine(line)
  // Las imágenes y el código fuente son líneas enormes: en la consola va solo un resumen.
  const pesado = msg && (msg.t === 'imagen' || msg.t === 'fuente') && line.length > 400
  h.onLine(pesado ? `{"t":"${msg.t}", … ${Math.round(line.length / 1024)} KB}` : line, 'in')
  if (msg) h.onMessage(msg)
}

/* ------------------------------------------------------------------ */
/* WiFi: WebSocket ws://<bicho>:8080/ws + HTTP en el mismo puerto       */
/* Relé: si la dirección es https://…, es el relé (rele/ en el repo),    */
/* que tiene las mismas rutas y le pasa todo al bicho, esté donde esté. */
/* ------------------------------------------------------------------ */

export class WifiLink implements DeviceLink {
  readonly kind = 'wifi' as const
  readonly host: string
  /** true si se llega al bicho por el relé y no directo por la red local. */
  readonly rele: boolean
  private readonly origen: string
  private ws?: WebSocket
  private closed = false
  private retry = 0
  private timer?: ReturnType<typeof setTimeout>

  constructor(
    host: string,
    private h: LinkHandlers,
  ) {
    this.host = normalizeHost(host)
    this.rele = esRele(host)
    this.origen = this.rele ? new URL(host.trim()).origin : `http://${this.host}`
  }

  get label() {
    return this.host
  }

  /** A dónde se manda el paquete de una versión nueva. */
  get updateUrl() {
    return `${this.origen}/update`
  }

  private get wsUrl() {
    const url = `${this.origen.replace(/^http/, 'ws')}/ws`
    const k = this.rele ? clave.get() : '' // el relé deja mirar a cualquiera; para mandar comandos pide la clave del equipo
    return k ? `${url}?clave=${encodeURIComponent(k)}` : url
  }

  async open() {
    this.connect()
  }

  private connect() {
    this.h.onStatus(this.retry ? 'reconnecting' : 'connecting', this.host)
    const ws = new WebSocket(this.wsUrl)
    this.ws = ws
    ws.onopen = () => {
      this.retry = 0
      this.h.onStatus('connected', this.host)
      ws.send(CMD.info)
    }
    ws.onmessage = (ev) => {
      if (typeof ev.data === 'string') ev.data.split('\n').forEach((l) => dispatchLine(l, this.h))
    }
    ws.onclose = () => {
      if (this.closed) return
      this.retry++
      this.h.onStatus('reconnecting', `${this.host} · intento ${this.retry}`)
      this.timer = setTimeout(() => this.connect(), Math.min(5000, 400 * this.retry))
    }
  }

  async sendLine(line: string) {
    if (this.ws?.readyState !== WebSocket.OPEN) throw new Error('WebSocket no conectado')
    this.ws.send(line)
    this.h.onLine(line, 'out')
  }

  async close() {
    this.closed = true
    clearTimeout(this.timer)
    this.ws?.close()
    this.h.onStatus('disconnected')
  }
}

/* ------------------------------------------------------------------ */
/* Simulador: para desarrollar la web sin el Raspberry                  */
/* ------------------------------------------------------------------ */

export class SimLink implements DeviceLink {
  readonly kind = 'sim' as const
  readonly label = 'Simulador'
  private iv?: ReturnType<typeof setInterval>
  private t0 = performance.now()
  private hz = 20
  info: DeviceInfo = {
    name: 'bicho',
    fw: '0.1.0',
    desc: 'Agente base simulado: micrófono, IMU, distancia y 2 servos.',
    chip: 'Raspberry Pi 3 Model B (sim)',
    build: new Date().toISOString().slice(0, 16).replace('T', ' '),
    ip: '127.0.0.1',
    mac: 'B8:27:EB:00:00:01',
  }

  constructor(private h: LinkHandlers) {}

  async open() {
    this.h.onStatus('connected', this.label)
    this.sendInfo()
    this.start()
  }

  private start() {
    clearInterval(this.iv)
    let n = 0
    this.iv = setInterval(() => {
      this.tick()
      // igual que el agente: manda info cada ~10 s (uptime fresco)
      if (++n % (this.hz * 10) === 0) this.sendInfo()
    }, 1000 / this.hz)
  }

  private sendInfo() {
    const msg = {
      t: 'info',
      ...this.info,
      uptime: Math.round((performance.now() - this.t0) / 1000),
      heap: 512_000_000 + Math.round(Math.random() * 8_000_000),
      python: '3.11.2',
    }
    const line = JSON.stringify(msg)
    this.h.onLine(line, 'in')
    this.h.onMessage(msg as DeviceMsg)
  }

  private tick() {
    const ms = Math.round(performance.now() - this.t0)
    const s = ms / 1000
    const noise = () => (Math.random() - 0.5) * 0.08
    const d = {
      temp_cpu: +(48 + Math.sin(s * 0.05) * 3 + noise()).toFixed(1),
      carga: +(0.4 + Math.abs(Math.sin(s * 0.2)) * 0.5).toFixed(2),
      mic: Math.max(0, Math.abs(Math.sin(s * 3.1)) * 0.6 + Math.random() * 0.3),
      imu: { pitch: +(Math.sin(s * 0.7) * 25 + noise() * 10).toFixed(2), roll: +(Math.cos(s * 0.5) * 12 + noise() * 10).toFixed(2) },
      dist_cm: +(60 + Math.sin(s * 0.3) * 40 + noise() * 20).toFixed(1),
      servo: [Math.round(90 + Math.sin(s) * 60), Math.round(90 + Math.cos(s * 1.3) * 45)],
      boton: Math.sin(s * 0.9) > 0.92,
    }
    const msg = { t: 's', ms, d }
    this.h.onLine(JSON.stringify(msg), 'in')
    this.h.onMessage(msg as DeviceMsg)
  }

  async sendLine(line: string) {
    this.h.onLine(line, 'out')
    try {
      const c = JSON.parse(line)
      if (c.cmd === 'info') this.sendInfo()
      if (c.cmd === 'rate' && Number(c.hz) > 0) {
        this.hz = Math.min(100, Number(c.hz))
        this.start()
      }
      if (c.cmd === 'reboot') this.reboot()
    } catch {
      this.h.onLine(`[sim] eco: ${line}`, 'sys')
    }
  }

  /** Simula una actualización: progreso, reinicio y nueva versión. */
  async simulateFlash(version: string, desc: string | undefined, onProgress: (p: number) => void) {
    for (let p = 0; p <= 1.0001; p += 0.04) {
      onProgress(Math.min(1, p))
      await new Promise((r) => setTimeout(r, 70))
    }
    this.info = { ...this.info, fw: version, desc: desc ?? this.info.desc, build: new Date().toISOString().slice(0, 16).replace('T', ' ') }
    await this.reboot()
  }

  private async reboot() {
    clearInterval(this.iv)
    this.h.onStatus('reconnecting', 'reiniciando…')
    this.h.onLine('[sim] bichod reiniciando', 'in')
    await new Promise((r) => setTimeout(r, 1200))
    this.t0 = performance.now()
    this.h.onStatus('connected', this.label)
    this.sendInfo()
    this.start()
  }

  async close() {
    clearInterval(this.iv)
    this.h.onStatus('disconnected')
  }
}
