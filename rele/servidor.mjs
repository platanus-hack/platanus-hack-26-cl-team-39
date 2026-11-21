#!/usr/bin/env node
// Relé del bicho: un servicio aparte que une al bicho con la web, estén en la red que estén.
//
// El bicho no tiene dirección pública, así que es él quien sale a conectarse acá y deja la conexión
// abierta. La web (cualquier navegador) se conecta a este mismo servicio, que pasa los mensajes de un
// lado al otro. Hacia la web se ve igual que un bicho (mismas rutas que bichod, ver PROTOCOLO.md):
//
//   WebSocket /bicho    el bicho. Header `Authorization: Bearer <BICHO_RELE_TOKEN>`.
//   WebSocket /ws       la web. Mirar es libre; para mandar comandos, `?clave=<clave del equipo>`.
//   GET  /info          la última info del bicho (503 si no está conectado).
//   POST /update        instala un paquete .tar.gz en el bicho. `Authorization: Bearer <clave del equipo>`.
//   GET  /              estado del relé: ¿está el bicho?, desde cuándo, cuánta gente mira.
//
// El relé agrega un mensaje propio: {"t":"rele","bicho":true|false}.
// Solo usa la librería estándar de Node (20 o más): `node rele/servidor.mjs`.
//
// Configuración por variables de entorno o en rele/.env (no se sube al repo):
//   BICHO_RELE_TOKEN   secreto que comparte con el bicho. Obligatorio.
//   CLAVE_EQUIPO       clave para mandar comandos y actualizar (la del inventario). Sin ella, cualquiera puede.
//   RELE_PUERTO        puerto (8787 por defecto).     RELE_HOST   interfaz (127.0.0.1 por defecto).
import { createHash, randomUUID, timingSafeEqual } from 'node:crypto'
import { readFileSync } from 'node:fs'
import http from 'node:http'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

try {
  for (const l of readFileSync(join(dirname(fileURLToPath(import.meta.url)), '.env'), 'utf8').split(/\r?\n/)) {
    const i = l.indexOf('=')
    if (i > 0 && !l.trim().startsWith('#') && !process.env[l.slice(0, i).trim()]) process.env[l.slice(0, i).trim()] = l.slice(i + 1).trim().replace(/^"(.*)"$/, '$1')
  }
} catch {
  /* sin .env: se usan las variables de entorno */
}

const PUERTO = Number(process.env.RELE_PUERTO || 8787)
const HOST = process.env.RELE_HOST || '127.0.0.1'
const log = (m) => console.log(`[${new Date().toISOString()}] ${m}`)

const WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
const MAX_MENSAJE = 1024 * 1024 // lo que puede mandar un cliente en un mensaje
const MAX_PAQUETE = 20 * 1024 * 1024
const LATIDO_MS = 20_000

/* ------------------------------------------------------------------ */
/* WebSocket mínimo del lado servidor (RFC 6455), sin dependencias      */
/* ------------------------------------------------------------------ */

class Conexion {
  vivo = true
  visto = Date.now()
  puedeMandar = false
  alMensaje = () => {}
  alCerrar = () => {}
  buf = Buffer.alloc(0)
  partes = []

  constructor(socket) {
    this.socket = socket
    socket.on('data', (d) => this.recibir(d))
    socket.on('end', () => this.cerrar()) // el otro lado cerró: en un servidor HTTP el socket queda a medio abrir
    socket.on('close', () => this.cerrar())
    socket.on('error', () => this.cerrar())
  }

  trama(opcode, datos) {
    const n = datos.length
    let cabeza
    if (n < 126) cabeza = Buffer.from([0x80 | opcode, n])
    else if (n < 65536) {
      cabeza = Buffer.alloc(4)
      cabeza[0] = 0x80 | opcode
      cabeza[1] = 126
      cabeza.writeUInt16BE(n, 2)
    } else {
      cabeza = Buffer.alloc(10)
      cabeza[0] = 0x80 | opcode
      cabeza[1] = 127
      cabeza.writeBigUInt64BE(BigInt(n), 2)
    }
    return Buffer.concat([cabeza, datos])
  }

  enviar(texto) {
    if (this.vivo) this.socket.write(this.trama(0x1, Buffer.from(texto, 'utf8')))
  }

  latido() {
    if (this.vivo) this.socket.write(this.trama(0x9, Buffer.alloc(0)))
  }

  cerrar() {
    if (!this.vivo) return
    this.vivo = false
    try {
      this.socket.write(this.trama(0x8, Buffer.alloc(0)))
    } catch {
      /* ya estaba cerrado */
    }
    this.socket.destroy()
    this.alCerrar()
  }

  recibir(d) {
    this.buf = this.buf.length ? Buffer.concat([this.buf, d]) : d
    while (this.vivo) {
      if (this.buf.length < 2) return
      const fin = this.buf[0] & 0x80
      const opcode = this.buf[0] & 0x0f
      const enmascarado = this.buf[1] & 0x80
      let n = this.buf[1] & 0x7f
      let pos = 2
      if (n === 126) {
        if (this.buf.length < 4) return
        n = this.buf.readUInt16BE(2)
        pos = 4
      } else if (n === 127) {
        if (this.buf.length < 10) return
        const grande = this.buf.readBigUInt64BE(2)
        if (grande > BigInt(MAX_MENSAJE)) return this.cerrar()
        n = Number(grande)
        pos = 10
      }
      if (n > MAX_MENSAJE) return this.cerrar()
      const total = pos + (enmascarado ? 4 : 0) + n
      if (this.buf.length < total) return
      let datos = this.buf.subarray(total - n, total)
      if (enmascarado) {
        const m = this.buf.subarray(pos, pos + 4)
        datos = Buffer.from(datos)
        for (let i = 0; i < n; i++) datos[i] ^= m[i & 3]
      }
      this.buf = this.buf.subarray(total)
      this.visto = Date.now()
      if (opcode === 0x8) return this.cerrar()
      if (opcode === 0x9) {
        this.socket.write(this.trama(0xa, datos))
        continue
      }
      if (opcode === 0xa) continue
      if (opcode === 0x0 || opcode === 0x1) {
        this.partes.push(datos)
        if (this.partes.reduce((s, p) => s + p.length, 0) > MAX_MENSAJE) return this.cerrar()
        if (fin) {
          const texto = Buffer.concat(this.partes).toString('utf8')
          this.partes = []
          try {
            this.alMensaje(texto)
          } catch (e) {
            console.error('[rele]', e)
          }
        }
      }
    }
  }
}

/* ------------------------------------------------------------------ */
/* Estado                                                               */
/* ------------------------------------------------------------------ */

const E = {
  bicho: null,
  info: null,
  desde: null,
  webs: new Set(),
  pendientes: new Map(),
  latido: setInterval(() => {
    const limite = Date.now() - LATIDO_MS * 3
    for (const c of [E.bicho, ...E.webs]) {
      if (!c) continue
      if (c.visto < limite) c.cerrar()
      else c.latido()
    }
  }, LATIDO_MS),
}
E.latido.unref?.()

const linea = (obj) => JSON.stringify(obj)
const aviso = (msg, lvl = 'warn') => linea({ t: 'log', lvl, msg })
const aLasWebs = (texto) => {
  for (const w of E.webs) w.enviar(texto)
}
const avisarEspectadores = () => E.bicho?.enviar(linea({ cmd: '_espectadores', n: E.webs.size }))

function iguales(a, b) {
  const x = Buffer.from(a)
  const y = Buffer.from(b)
  return x.length === y.length && timingSafeEqual(x, y)
}

/** Clave del equipo (la misma del inventario). Si el servidor no tiene ninguna, en desarrollo local, no se pide. */
function claveOk(clave) {
  const esperada = process.env.CLAVE_EQUIPO || process.env.INVENTARIO_TOKEN
  if (!esperada) return true
  return Boolean(clave) && iguales(clave.trim(), esperada)
}

const bearer = (h) => (h ?? '').replace(/^Bearer\s+/i, '').trim()

/* ------------------------------------------------------------------ */
/* WebSocket                                                            */
/* ------------------------------------------------------------------ */

function rechazar(socket, estado, msg) {
  socket.end(`HTTP/1.1 ${estado} ${msg}\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: ${Buffer.byteLength(msg)}\r\nConnection: close\r\n\r\n${msg}`)
}

function upgrade(req, socket) {
  socket.on('error', () => {})
  const url = new URL(req.url ?? '/', 'http://rele')
  const ruta = url.pathname.replace(/\/$/, '')
  const llave = req.headers['sec-websocket-key']
  if (typeof llave !== 'string' || String(req.headers.upgrade).toLowerCase() !== 'websocket') return rechazar(socket, 400, 'Se esperaba un WebSocket')
  if (ruta !== '/bicho' && ruta !== '/ws') return rechazar(socket, 404, 'No existe')

  if (ruta === '/bicho') {
    const token = process.env.BICHO_RELE_TOKEN
    if (!token) return rechazar(socket, 503, 'Falta BICHO_RELE_TOKEN en el servidor')
    if (!iguales(bearer(req.headers.authorization), token)) return rechazar(socket, 401, 'Token del bicho incorrecto')
  }

  const acepta = createHash('sha1').update(llave + WS_GUID).digest('base64')
  socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${acepta}\r\n\r\n`)
  const c = new Conexion(socket)
  if (ruta === '/bicho') conectarBicho(c)
  else conectarWeb(c, claveOk(url.searchParams.get('clave')))
}

function conectarBicho(c) {
  E.bicho?.cerrar() // si quedó una conexión vieja colgada, manda la nueva
  E.bicho = c
  E.desde = new Date().toISOString()
  log('bicho conectado')
  c.alMensaje = (texto) => {
    for (const l of texto.split('\n')) {
      if (!l.trim()) continue
      let m = null
      try {
        m = JSON.parse(l)
      } catch {
        /* línea que no es JSON: pasa tal cual a la consola de la web */
      }
      if (m?.t === '_update') {
        E.pendientes.get(String(m.id))?.listo({ ok: Boolean(m.ok), msg: String(m.msg ?? '') })
        continue
      }
      if (m?.t === 'info') E.info = m
      aLasWebs(l)
    }
  }
  c.alCerrar = () => {
    if (E.bicho !== c) return
    E.bicho = null
    E.info = null
    E.desde = null
    log('bicho desconectado')
    aLasWebs(linea({ t: 'rele', bicho: false }))
    for (const p of E.pendientes.values()) p.listo({ ok: false, msg: 'El bicho se desconectó a mitad de la actualización.' })
  }
  aLasWebs(linea({ t: 'rele', bicho: true }))
  avisarEspectadores()
}

function conectarWeb(c, puedeMandar) {
  c.puedeMandar = puedeMandar
  E.webs.add(c)
  c.enviar(linea({ t: 'rele', bicho: Boolean(E.bicho) }))
  if (E.info) c.enviar(linea(E.info))
  c.alMensaje = (texto) => {
    for (const l of texto.split('\n')) {
      if (!l.trim()) continue
      let cmd
      try {
        cmd = JSON.parse(l).cmd
      } catch {
        cmd = undefined
      }
      if (cmd === 'info') {
        if (E.info) c.enviar(linea(E.info))
        continue
      }
      if (!c.puedeMandar) {
        c.enviar(aviso('Para mandar comandos al bicho falta la clave del equipo. Ponla en Equipo → Inventario y vuelve a conectar.'))
        continue
      }
      if (typeof cmd === 'string' && cmd.startsWith('_')) continue // reservados para el relé
      if (!E.bicho) {
        c.enviar(aviso('El bicho no está conectado al relé.'))
        continue
      }
      E.bicho.enviar(l)
    }
  }
  c.alCerrar = () => {
    E.webs.delete(c)
    avisarEspectadores()
  }
  avisarEspectadores()
}

/* ------------------------------------------------------------------ */
/* HTTP                                                                 */
/* ------------------------------------------------------------------ */

// La web vive en otro sitio (bicho·dev publicado o localhost): se permite desde cualquier origen.
const CORS = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET, POST, OPTIONS',
  'access-control-allow-headers': 'content-type, authorization',
  'access-control-max-age': '86400',
}

function responder(res, estado, cuerpo, tipo = 'text/plain; charset=utf-8') {
  const datos = typeof cuerpo === 'string' ? cuerpo : JSON.stringify(cuerpo)
  res.writeHead(estado, { 'content-type': typeof cuerpo === 'string' ? tipo : 'application/json; charset=utf-8', 'cache-control': 'no-store', ...CORS })
  res.end(datos)
}

function leerCuerpo(req, max) {
  return new Promise((ok, mal) => {
    const partes = []
    let n = 0
    req.on('data', (d) => {
      n += d.length
      if (n > max) {
        mal(new Error('demasiado grande'))
        req.destroy()
      } else partes.push(d)
    })
    req.on('end', () => ok(Buffer.concat(partes)))
    req.on('error', mal)
  })
}

async function actualizar(req, res) {
  if (!claveOk(bearer(req.headers.authorization))) return responder(res, 401, 'Falta la clave del equipo o no es correcta. Ponla en Equipo → Inventario.')
  const bicho = E.bicho
  if (!bicho) return responder(res, 503, 'El bicho no está conectado al relé.')
  let paquete
  try {
    paquete = await leerCuerpo(req, MAX_PAQUETE)
  } catch {
    return responder(res, 413, 'Paquete demasiado grande para mandarlo por el relé.')
  }
  if (!paquete.length) return responder(res, 400, 'Falta el paquete (.tar.gz) en el cuerpo.')

  const id = randomUUID()
  const r = await new Promise((listo) => {
    const reloj = setTimeout(() => listo({ ok: false, msg: 'El bicho no respondió a tiempo.' }), 300_000)
    E.pendientes.set(id, { listo, reloj })
    bicho.enviar(linea({ cmd: '_update', id, b64: paquete.toString('base64') }))
  })
  clearTimeout(E.pendientes.get(id)?.reloj)
  E.pendientes.delete(id)
  log(`actualización: ${r.msg}`)
  responder(res, r.ok ? 200 : 400, r.msg || (r.ok ? 'OK' : 'FALLO'))
}

const servidor = http.createServer((req, res) => {
  const ruta = (req.url ?? '/').split('?')[0].replace(/\/$/, '') || '/'
  if (req.method === 'OPTIONS') {
    res.writeHead(204, CORS)
    return res.end()
  }
  if (req.method === 'GET' && ruta === '/') return responder(res, 200, { rele: true, bicho: Boolean(E.bicho), desde: E.desde, espectadores: E.webs.size, fw: E.info?.fw ?? null })
  if (req.method === 'GET' && ruta === '/info') return E.info ? responder(res, 200, E.info) : responder(res, 503, { error: 'El bicho no está conectado al relé.' })
  if (req.method === 'POST' && ruta === '/update') return void actualizar(req, res).catch((e) => responder(res, 500, String(e?.message ?? e)))
  responder(res, 404, 'relé del bicho: no existe')
})
servidor.on('upgrade', (req, socket) => {
  try {
    upgrade(req, socket)
  } catch (e) {
    console.error(e)
    socket.destroy()
  }
})
servidor.listen(PUERTO, HOST, () => {
  log(`relé en http://${HOST}:${PUERTO}`)
  if (!process.env.BICHO_RELE_TOKEN) log('OJO: falta BICHO_RELE_TOKEN; el bicho no va a poder conectarse')
  if (!process.env.CLAVE_EQUIPO && !process.env.INVENTARIO_TOKEN) log('OJO: sin CLAVE_EQUIPO cualquiera puede mandarle comandos al bicho')
})
