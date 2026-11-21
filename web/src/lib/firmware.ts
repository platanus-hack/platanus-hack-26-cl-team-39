// Versiones del bicho: paquetes .tar.gz de la carpeta bicho/ publicados con `npm run release`.

export type Release = {
  version: string
  date?: string
  author?: string
  notes?: string
  /** Ruta del paquete dentro de public/firmware/, p. ej. "0.2.0/bicho-0.2.0.tar.gz". */
  package?: string
  size?: number
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

/** Compara versiones tipo 1.2.3 (los sufijos -beta, etc. solo desempatan). */
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

export async function fetchPackage(path: string): Promise<Uint8Array> {
  const r = await fetch(`${base}firmware/${path}`, { cache: 'no-store' })
  if (!r.ok) throw new Error(`No encontré ${path} (HTTP ${r.status})`)
  return new Uint8Array(await r.arrayBuffer())
}

/** Un .tar.gz empieza con los bytes mágicos de gzip (1F 8B); un .tar plano trae "ustar" en el byte 257. */
export function looksLikePackage(bin: Uint8Array): boolean {
  if (bin.length > 18 && bin[0] === 0x1f && bin[1] === 0x8b) return true
  return bin.length > 262 && String.fromCharCode(...bin.slice(257, 262)) === 'ustar'
}

/** Manda el paquete al agente: POST http://<bicho>/update con el .tar.gz como cuerpo. */
export function uploadPackage(httpBase: string, data: Uint8Array, onProgress: (p: number) => void): Promise<string> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${httpBase}/update`)
    xhr.setRequestHeader('Content-Type', 'application/octet-stream')
    xhr.timeout = 600_000 // pip puede tardar si la versión trae dependencias nuevas
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total)
    xhr.onload = () => (xhr.status < 300 ? resolve(xhr.responseText) : reject(new Error(xhr.responseText || `HTTP ${xhr.status}`)))
    xhr.onerror = () => reject(new Error('Error de red: revisa que el bicho esté en la misma red y que la web corra en localhost.'))
    xhr.ontimeout = () => reject(new Error('Se acabó el tiempo esperando al bicho.'))
    xhr.send(new Blob([data as BlobPart], { type: 'application/octet-stream' }))
  })
}
