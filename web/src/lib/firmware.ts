import { ESPLoader, Transport, type IEspLoaderTerminal } from 'esptool-js'

export type Release = {
  version: string
  date?: string
  author?: string
  notes?: string
  chip?: string
  /** Binario de la app (sketch.ino.bin). Sirve para OTA por WiFi y para USB a 0x10000. */
  app?: string
  /** Imagen completa (sketch.ino.merged.bin): bootloader + particiones + app, se graba en 0x0 por USB. */
  merged?: string
}

export type Manifest = { device: string; releases: Release[] }

const base = import.meta.env.BASE_URL

export async function loadManifest(): Promise<Manifest> {
  const r = await fetch(`${base}firmware/manifest.json?ts=${Date.now()}`, { cache: 'no-store' })
  if (!r.ok) throw new Error(`No pude leer manifest.json (HTTP ${r.status})`)
  const m = (await r.json()) as Manifest
  m.releases = [...(m.releases ?? [])].sort((a, b) => cmpSemver(b.version, a.version))
  return m
}

/** Compara versiones tipo 1.2.3 (ignora sufijos -beta, etc. salvo como desempate). */
export function cmpSemver(a: string, b: string): number {
  const pa = a.replace(/^v/, '').split(/[.-]/)
  const pb = b.replace(/^v/, '').split(/[.-]/)
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const x = pa[i] ?? ''
    const y = pb[i] ?? ''
    const nx = Number(x)
    const ny = Number(y)
    if (!Number.isNaN(nx) && !Number.isNaN(ny) && x !== '' && y !== '') {
      if (nx !== ny) return nx - ny
    } else if (x !== y) {
      if (x === '') return 1 // 1.0.0 > 1.0.0-beta
      if (y === '') return -1
      return x < y ? -1 : 1
    }
  }
  return 0
}

export async function fetchBin(path: string): Promise<Uint8Array> {
  const r = await fetch(`${base}firmware/${path}`, { cache: 'no-store' })
  if (!r.ok) throw new Error(`No encontré ${path} (HTTP ${r.status})`)
  return new Uint8Array(await r.arrayBuffer())
}

export type FlashPart = { data: Uint8Array; address: number; label: string }

/** Offsets del esquema de particiones "default" de Arduino-ESP32. */
const OTADATA_ADDR = 0xe000
const APP_ADDR = 0x10000

/**
 * Arma las partes a grabar por USB.
 * - Con merged: una sola imagen en 0x0 (lo más seguro, deja todo como recién cargado desde el IDE).
 * - Solo app: borra otadata (igual que boot_app0.bin del IDE) para que arranque app0, y graba la app en 0x10000.
 */
export function usbParts(bins: { merged?: Uint8Array; app?: Uint8Array }): FlashPart[] {
  if (bins.merged) return [{ data: bins.merged, address: 0x0, label: 'merged @0x0' }]
  if (bins.app)
    return [
      { data: new Uint8Array(0x2000).fill(0xff), address: OTADATA_ADDR, label: 'otadata @0xe000' },
      { data: bins.app, address: APP_ADDR, label: 'app @0x10000' },
    ]
  throw new Error('La versión no tiene binario para grabar')
}

/**
 * ¿Es una imagen merged (bootloader + particiones + app) o una app suelta?
 * Las merged traen la tabla de particiones en 0x8000, que empieza con los bytes mágicos 0xAA 0x50.
 */
export function looksLikeMerged(bin: Uint8Array): boolean {
  return bin.length > 0x8002 && bin[0x8000] === 0xaa && bin[0x8001] === 0x50
}

/** Una app ESP32 válida empieza con el byte mágico 0xE9. */
export function looksLikeApp(bin: Uint8Array): boolean {
  return bin.length > 0x100 && bin[0] === 0xe9
}

export async function flashUsb(
  port: SerialPort,
  parts: FlashPart[],
  log: (s: string) => void,
  onProgress: (p: number) => void,
): Promise<string> {
  const transport = new Transport(port, false)
  let pending = ''
  const terminal: IEspLoaderTerminal = {
    clean: () => {},
    writeLine: (d) => {
      log(pending + d)
      pending = ''
    },
    write: (d) => {
      pending += d
    },
  }
  const loader = new ESPLoader({ transport, baudrate: 921600, romBaudrate: 115200, terminal })
  try {
    const chip = await loader.main()
    log(`Chip detectado: ${chip}`)
    const sizes = parts.map((p) => p.data.length)
    const total = sizes.reduce((a, b) => a + b, 0)
    const done = parts.map(() => 0)
    parts.forEach((p) => log(`→ ${p.label} (${(p.data.length / 1024).toFixed(0)} KB)`))
    await loader.writeFlash({
      fileArray: parts.map(({ data, address }) => ({ data, address })),
      flashMode: 'keep',
      flashFreq: 'keep',
      flashSize: 'keep',
      eraseAll: false,
      compress: true,
      reportProgress: (i, written, t) => {
        done[i] = t ? (written / t) * sizes[i] : 0
        onProgress(done.reduce((a, b) => a + b, 0) / total)
      },
    })
    onProgress(1)
    log('Reiniciando el bicho…')
    await loader.after('hard_reset')
    return chip
  } finally {
    await transport.disconnect().catch(() => {})
  }
}

/** OTA por WiFi: POST multipart a http://<host>/update (ver firmware/bicho). */
export function flashOta(httpBase: string, bin: Uint8Array, onProgress: (p: number) => void): Promise<string> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${httpBase}/update`)
    xhr.timeout = 120_000
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total)
    xhr.onload = () => (xhr.status < 300 ? resolve(xhr.responseText) : reject(new Error(`HTTP ${xhr.status}: ${xhr.responseText}`)))
    xhr.onerror = () => reject(new Error('Error de red: revisa que el bicho esté en la misma red y que la web corra en localhost'))
    xhr.ontimeout = () => reject(new Error('Se acabó el tiempo esperando al bicho'))
    const fd = new FormData()
    fd.append('firmware', new Blob([bin as BlobPart], { type: 'application/octet-stream' }), 'firmware.bin')
    xhr.send(fd)
  })
}
