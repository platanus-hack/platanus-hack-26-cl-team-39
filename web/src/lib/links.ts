import { CMD, parseLine, type DeviceInfo, type DeviceMsg } from './protocol'

export type LinkKind = 'serial' | 'wifi' | 'sim'
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

function dispatchLine(line: string, h: LinkHandlers) {
  if (!line) return
  const msg = parseLine(line)
  h.onLine(line, 'in')
  if (msg) h.onMessage(msg)
}

/* ------------------------------------------------------------------ */
/* USB (Web Serial)                                                     */
/* ------------------------------------------------------------------ */

export class SerialLink implements DeviceLink {
  readonly kind = 'serial' as const
  private reader?: ReadableStreamDefaultReader<Uint8Array>
  private closing = false
  private loop?: Promise<void>
  private onDisconnect = (e: Event) => {
    if ((e as Event & { target: SerialPort }).target === this.port && !this.closing) {
      this.h.onStatus('disconnected', 'Se desconectó el cable USB')
    }
  }

  constructor(
    readonly port: SerialPort,
    private h: LinkHandlers,
    private baud = 115200,
  ) {}

  get label() {
    const i = this.port.getInfo()
    const id = i.usbVendorId ? `${i.usbVendorId.toString(16)}:${i.usbProductId?.toString(16)}` : ''
    return `USB ${id}`.trim()
  }

  async open() {
    this.h.onStatus('connecting', this.label)
    await this.port.open({ baudRate: this.baud, bufferSize: 16384 })
    navigator.serial.addEventListener('disconnect', this.onDisconnect)
    this.h.onStatus('connected', this.label)
    this.loop = this.readLoop()
    // Al abrir el puerto muchos ESP32 se reinician; pedimos info igual por si no.
    setTimeout(() => this.sendLine(CMD.info).catch(() => {}), 800)
  }

  private async readLoop() {
    const dec = new TextDecoder()
    let buf = ''
    while (this.port.readable && !this.closing) {
      this.reader = this.port.readable.getReader()
      try {
        for (;;) {
          const { value, done } = await this.reader.read()
          if (done) break
          buf += dec.decode(value, { stream: true })
          let i: number
          while ((i = buf.indexOf('\n')) >= 0) {
            dispatchLine(buf.slice(0, i).replace(/\r$/, ''), this.h)
            buf = buf.slice(i + 1)
          }
          if (buf.length > 16384) buf = buf.slice(-4096)
        }
      } catch (e) {
        if (!this.closing) this.h.onLine(`[serial] ${String(e)}`, 'sys')
      } finally {
        this.reader.releaseLock()
        this.reader = undefined
      }
    }
    if (!this.closing) this.h.onStatus('disconnected', 'Puerto cerrado')
  }

  async sendLine(line: string) {
    if (!this.port.writable) throw new Error('Puerto USB no disponible')
    const w = this.port.writable.getWriter()
    try {
      await w.write(new TextEncoder().encode(line + '\n'))
      this.h.onLine(line, 'out')
    } finally {
      w.releaseLock()
    }
  }

  /** Cierra el monitor y deja el puerto libre (p. ej. para flashear por USB). */
  async close() {
    this.closing = true
    navigator.serial.removeEventListener('disconnect', this.onDisconnect)
    try {
      await this.reader?.cancel()
    } catch {
      /* ya estaba cerrado */
    }
    await this.loop?.catch(() => {})
    try {
      await this.port.close()
    } catch {
      /* ya estaba cerrado */
    }
    this.h.onStatus('disconnected')
  }
}

/* ------------------------------------------------------------------ */
/* WiFi (WebSocket :81 + HTTP :80)                                      */
/* ------------------------------------------------------------------ */

export class WifiLink implements DeviceLink {
  readonly kind = 'wifi' as const
  private ws?: WebSocket
  private closed = false
  private retry = 0
  private timer?: ReturnType<typeof setTimeout>

  constructor(
    readonly host: string,
    private h: LinkHandlers,
  ) {}

  get label() {
    return this.host
  }

  get httpBase() {
    return `http://${this.host}`
  }

  async open() {
    this.connect()
  }

  private connect() {
    this.h.onStatus(this.retry ? 'reconnecting' : 'connecting', this.host)
    const ws = new WebSocket(`ws://${this.host}:81/`)
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
      this.h.onStatus('reconnecting', `${this.host} (intento ${this.retry})`)
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
/* Simulador: para desarrollar la web sin el bicho enchufado            */
/* ------------------------------------------------------------------ */

export class SimLink implements DeviceLink {
  readonly kind = 'sim' as const
  readonly label = 'Simulador'
  private iv?: ReturnType<typeof setInterval>
  private t0 = performance.now()
  private hz = 20
  info: DeviceInfo = {
    name: 'bicho-sim',
    fw: '0.1.0',
    desc: 'Firmware base simulado: micrófono, IMU, distancia y 3 servos.',
    chip: 'ESP32-S3 (sim)',
    build: new Date().toISOString().slice(0, 16),
    ip: '127.0.0.1',
    mac: 'SI:MU:LA:DO:00:01',
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
      // igual que el firmware: manda info cada ~10 s (uptime fresco)
      if (++n % (this.hz * 10) === 0) this.sendInfo()
    }, 1000 / this.hz)
  }

  private sendInfo() {
    const msg = { t: 'info', ...this.info, uptime: Math.round((performance.now() - this.t0) / 1000), heap: 180000 + Math.round(Math.random() * 4000) }
    const line = JSON.stringify(msg)
    this.h.onLine(line, 'in')
    this.h.onMessage(msg as DeviceMsg)
  }

  private tick() {
    const ms = Math.round(performance.now() - this.t0)
    const s = ms / 1000
    const noise = () => (Math.random() - 0.5) * 0.08
    const d = {
      mic: Math.max(0, Math.abs(Math.sin(s * 3.1)) * 0.6 + Math.random() * 0.3),
      imu: { pitch: +(Math.sin(s * 0.7) * 25 + noise() * 10).toFixed(2), roll: +(Math.cos(s * 0.5) * 12 + noise() * 10).toFixed(2) },
      dist_cm: +(60 + Math.sin(s * 0.3) * 40 + noise() * 20).toFixed(1),
      servo: [Math.round(90 + Math.sin(s) * 60), Math.round(90 + Math.cos(s * 1.3) * 45), Math.round(90 + Math.sin(s * 0.4) * 30)],
      temp_c: +(31 + Math.sin(s * 0.05) * 1.5 + noise()).toFixed(2),
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
    this.info = { ...this.info, fw: version, desc: desc ?? this.info.desc, build: new Date().toISOString().slice(0, 16) }
    await this.reboot()
  }

  private async reboot() {
    clearInterval(this.iv)
    this.h.onStatus('reconnecting', 'reiniciando…')
    this.h.onLine('[sim] rst:0x1 (POWERON_RESET)', 'in')
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
