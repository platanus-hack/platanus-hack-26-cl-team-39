#!/usr/bin/env node
// Cerebro del bicho: escucha lo que le dicen, decide qué hacer y, si no sabe hacerlo, aprende.
//
// Es un servicio aparte. Se conecta al relé (rele/) como un cliente más, con la clave del equipo:
// recibe las frases que oye el bicho ({"t":"oido"}) y le manda comandos. Por debajo usa Claude.
//
// Por cada frase, Claude elige una de estas salidas:
//   ignorar    no le hablan a él
//   responder  le conversan o le preguntan
//   comando    le piden algo que ya sabe hacer (lo que hay en comandos.py del bicho)
//   aprender   le piden algo que no sabe: Claude escribe el código, lo instala en el bicho por el
//              relé y lo prueba. Si la versión nueva falla, el bicho vuelve solo a la anterior.
//
// Lo que decide y hace lo anuncia con {"t":"cerebro",...}, que el relé reparte a bicho·dev.
//
// Configuración por variables de entorno o en cerebro/.env (no se sube al repo):
//   ANTHROPIC_API_KEY   clave de Anthropic. Obligatoria.
//   RELE_URL            dirección del relé, p. ej. https://<relé>. Obligatoria.
//   CLAVE_EQUIPO        la clave del equipo (la misma del relé): sin ella no puede mandar comandos.
//   CEREBRO_MODELO      modelo de Claude para aprender, o sea escribir código (claude-fable-5-2 por defecto).
//   CEREBRO_MODELO_DECIDIR  modelo que decide qué hacer con cada frase (claude-haiku-5-5 por defecto: responde
//                       en un par de segundos; con Fable cada vuelta tarda varias veces más).
//   CEREBRO_APRENDE     "0" para que decida y responda pero no modifique el bicho.
//   CEREBRO_ESCUCHA     "nombre" (por defecto): de lo que oye, solo evalúa las frases que dicen "bicho" o que
//                       siguen una conversación reciente. "todo": evalúa cada frase (caro: cada una es una
//                       llamada a Claude, y el micrófono capta todas las conversaciones de alrededor).
import Anthropic from '@anthropic-ai/sdk'
import { execFileSync } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const AQUI = dirname(fileURLToPath(import.meta.url))
try {
  for (const l of readFileSync(join(AQUI, '.env'), 'utf8').split(/\r?\n/)) {
    const i = l.indexOf('=')
    if (i > 0 && !l.trim().startsWith('#') && !process.env[l.slice(0, i).trim()]) process.env[l.slice(0, i).trim()] = l.slice(i + 1).trim().replace(/^"(.*)"$/, '$1')
  }
} catch {
  /* sin .env: se usan las variables de entorno */
}

const MODELO = process.env.CEREBRO_MODELO || 'claude-fable-5-2'
const MODELO_DECIDIR = process.env.CEREBRO_MODELO_DECIDIR || 'claude-haiku-5-5'
const RELE = (process.env.RELE_URL || '').replace(/\/+$/, '')
const CLAVE = process.env.CLAVE_EQUIPO || ''
const APRENDE = process.env.CEREBRO_APRENDE !== '0'
const ESCUCHA_TODO = process.env.CEREBRO_ESCUCHA === 'todo'
// Cómo suele transcribir Whisper el nombre del bicho.
const LO_NOMBRAN = /\b(bich[oaei]s?|bichito|vich[oa]|bitcho|beach[oa]|micho)\b/i
const VENTANA_CONVERSACION_MS = 45_000
const log = (m) => console.log(`[${new Date().toISOString()}] ${m}`)
const dormir = (ms) => new Promise((r) => setTimeout(r, ms))

if (!RELE) {
  console.error('Falta RELE_URL (la dirección del relé).')
  process.exit(1)
}
if (!process.env.ANTHROPIC_API_KEY) {
  console.error('Falta ANTHROPIC_API_KEY.')
  process.exit(1)
}
// baseURL fijo: en el entorno puede haber un ANTHROPIC_BASE_URL de otra herramienta.
const claude = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY, baseURL: 'https://api.anthropic.com' })

/* ------------------------------------------------------------------ */
/* Conexión con el relé                                                 */
/* ------------------------------------------------------------------ */

const E = {
  ws: null,
  bicho: false,
  info: null, // última info del bicho (versión, qué hace, red)
  sensores: null,
  imagenes: new Map(), // nombre → { b64, fmt, ts }
  historia: [], // lo último que se oyó y qué se hizo, para darle contexto a Claude
  esperas: new Set(), // quienes esperan un mensaje del relé
  aprendiendo: null, // descripción del aprendizaje en curso
  ultimoAprendizaje: 0,
  ultimaInteraccion: 0, // última vez que el bicho respondió o hizo algo: por un rato sigue la conversación
}

function conectar() {
  const url = `${RELE.replace(/^http/, 'ws')}/ws${CLAVE ? `?clave=${encodeURIComponent(CLAVE)}` : ''}`
  const ws = new WebSocket(url)
  E.ws = ws
  ws.onopen = () => log(`conectado al relé ${new URL(RELE).host}`)
  ws.onmessage = (ev) => {
    for (const l of String(ev.data).split('\n')) {
      if (!l.trim()) continue
      let m
      try {
        m = JSON.parse(l)
      } catch {
        continue
      }
      recibir(m)
    }
  }
  ws.onclose = () => {
    E.ws = null
    setTimeout(conectar, 3000)
  }
  ws.onerror = () => {}
}

function recibir(m) {
  if (m.t === 'rele') E.bicho = Boolean(m.bicho)
  else if (m.t === 'info') E.info = m
  else if (m.t === 's') E.sensores = m.d
  else if (m.t === 'imagen' && typeof m.nombre === 'string' && typeof m.b64 === 'string') E.imagenes.set(m.nombre, { b64: m.b64, fmt: m.fmt === 'png' ? 'png' : 'jpeg', ts: Date.now() })
  else if (m.t === 'oido' && m.estado === 'listo' && m.texto && Date.now() - (m.ts ?? 0) < 20_000) alOir(m)
  // Desde bicho·dev también se le puede escribir: llega como {"t":"cerebro","tipo":"decir","texto":"..."}.
  else if (m.t === 'cerebro' && m.tipo === 'decir' && typeof m.texto === 'string' && m.texto.trim() && Date.now() - (m.ts ?? Date.now()) < 20_000)
    alOir({ id: String(m.id ?? randomUUID()), texto: m.texto.trim(), angulo: null, dur: 0, escrito: true })
  for (const e of [...E.esperas]) e(m)
}

/** Espera un mensaje del relé que cumpla la condición. Devuelve null si se acaba el tiempo. */
function esperar(condicion, ms) {
  return new Promise((ok) => {
    const revisar = (m) => {
      if (!condicion(m)) return
      clearTimeout(reloj)
      E.esperas.delete(revisar)
      ok(m)
    }
    const reloj = setTimeout(() => {
      E.esperas.delete(revisar)
      ok(null)
    }, ms)
    E.esperas.add(revisar)
  })
}

function enviar(obj) {
  if (E.ws?.readyState !== WebSocket.OPEN) return false
  E.ws.send(JSON.stringify(obj))
  return true
}

/** Lo que el cerebro decide o hace, para bicho·dev. */
function anunciar(tipo, texto, extra = {}) {
  log(`${tipo}: ${texto}`)
  enviar({ t: 'cerebro', id: randomUUID(), tipo, texto, ts: Date.now(), ...extra })
}

/** Manda un comando al bicho y junta lo que responde por la consola durante un rato. */
async function comandoAlBicho(comando, ms = 2500) {
  if (!E.bicho) return 'El bicho no está conectado al relé.'
  const respuestas = []
  const juntar = (m) => {
    if (m.t === 'log' && typeof m.msg === 'string') respuestas.push(`[${m.lvl ?? 'info'}] ${m.msg}`)
  }
  E.esperas.add(juntar)
  if (!enviar(comando)) {
    E.esperas.delete(juntar)
    return 'No hay conexión con el relé.'
  }
  // Se vuelve apenas el bicho contesta (y deja de hablar por 300 ms), no después de un tiempo fijo.
  const tope = Date.now() + ms
  let vistas = 0
  let ultima = 0
  while (Date.now() < tope) {
    await dormir(50)
    if (respuestas.length !== vistas) {
      vistas = respuestas.length
      ultima = Date.now()
    } else if (vistas && Date.now() - ultima >= 300) break
  }
  E.esperas.delete(juntar)
  return respuestas.length ? respuestas.join('\n') : 'El bicho no respondió nada en la consola.'
}

async function pedir(cmd, tipo, ms = 20_000) {
  const id = randomUUID()
  const espera = esperar((m) => m.t === tipo && m.id === id, ms)
  if (!enviar({ cmd, id })) return null
  return espera
}

function bloqueImagen(nombre = 'camara', maxEdadMs = 15_000) {
  const img = E.imagenes.get(nombre) ?? [...E.imagenes.values()].sort((a, b) => b.ts - a.ts)[0]
  if (!img || Date.now() - img.ts > maxEdadMs) return null
  return { type: 'image', source: { type: 'base64', media_type: `image/${img.fmt}`, data: img.b64 } }
}

/* ------------------------------------------------------------------ */
/* Claude: una vuelta de herramientas                                   */
/* ------------------------------------------------------------------ */

/**
 * Corre el ciclo de herramientas hasta que Claude termina. `ejecutar(nombre, entrada)` devuelve el
 * contenido del resultado (texto o bloques) o { fin: ... } para cortar ahí.
 */
async function ciclo({ sistema, herramientas, mensajes, esfuerzo, maxVueltas, ejecutar, maxTokens = 16000, alPensar, modelo = MODELO }) {
  // Haiku: sin pensar antes de contestar (es lo que más demora) y sin fallback, que ese modelo no tiene.
  const rapido = /haiku/.test(modelo)
  for (let vuelta = 0; vuelta < maxVueltas; vuelta++) {
    alPensar?.(vuelta)
    // En streaming: escribir un archivo entero más lo que piensa puede pasar de los 16 mil tokens,
    // y una respuesta así de larga sin streaming se corta o se queda sin tiempo.
    const r = await claude.beta.messages
      .stream({
      model: modelo,
      max_tokens: maxTokens,
      // Si el modelo declina por seguridad, la API reintenta sola con otro modelo.
      ...(rapido ? { thinking: { type: 'disabled' } } : { betas: ['server-side-fallback-2026-07-01'], fallbacks: 'default' }),
      output_config: { effort: esfuerzo },
      // El sistema y las herramientas no cambian entre frases: se leen de la caché.
      system: [{ type: 'text', text: sistema, cache_control: { type: 'ephemeral' } }],
      tools: herramientas,
      messages: mensajes,
      })
      .finalMessage()
    if (r.stop_reason === 'refusal') return { texto: '', motivo: 'refusal' }
    // Cortado por el tope de tokens: una llamada a herramienta a medias no sirve, se avisa en vez de seguir.
    if (r.stop_reason === 'max_tokens') return { texto: '', motivo: 'max_tokens' }
    mensajes.push({ role: 'assistant', content: r.content }) // tal cual: incluye los bloques de pensamiento
    if (r.stop_reason === 'pause_turn') continue
    const usos = r.content.filter((b) => b.type === 'tool_use')
    const texto = r.content
      .filter((b) => b.type === 'text')
      .map((b) => b.text)
      .join('\n')
      .trim()
    if (r.stop_reason !== 'tool_use' || !usos.length) return { texto, motivo: r.stop_reason }

    const resultados = []
    let fin
    for (const u of usos) {
      let contenido
      let error = false
      try {
        const salida = await ejecutar(u.name, u.input ?? {})
        if (salida && typeof salida === 'object' && 'fin' in salida) {
          fin = salida.fin
          contenido = 'ok'
        } else contenido = salida
      } catch (e) {
        error = true
        contenido = `Error: ${e?.message ?? e}`
      }
      resultados.push({ type: 'tool_result', tool_use_id: u.id, content: contenido, ...(error ? { is_error: true } : {}) })
    }
    mensajes.push({ role: 'user', content: resultados })
    if (fin !== undefined) return { texto, motivo: 'fin', fin }
  }
  return { texto: '', motivo: 'max_vueltas' }
}

const herramienta = (name, description, properties = {}, required = Object.keys(properties)) => ({
  name,
  description,
  input_schema: { type: 'object', properties, required, additionalProperties: false },
})

/* ------------------------------------------------------------------ */
/* Decidir qué hacer con cada frase                                     */
/* ------------------------------------------------------------------ */

const H_DECIDIR = [
  herramienta('ignorar', 'La frase no es para el bicho (conversación entre otras personas, ruido, una frase suelta sin sentido). Es lo más común.', {
    motivo: { type: 'string', description: 'Por qué, en pocas palabras.' },
  }),
  herramienta('responder', 'Le hablan al bicho y basta con contestar. La respuesta se muestra en la web.', {
    texto: { type: 'string', description: 'Respuesta corta, en español de Chile, con la personalidad del bicho.' },
  }),
  herramienta(
    'comando',
    'Le piden algo que el bicho YA sabe hacer: manda un comando de los que existen en comandos.py. Devuelve lo que el bicho contestó.',
    { comando: { type: 'object', description: 'El comando tal como lo espera manejar(), por ejemplo {"cmd":"luz","on":true}.' } },
  ),
  herramienta('mirar', 'Devuelve la última imagen de la cámara del bicho, si tiene una funcionando, para que puedas ver lo que él ve.', {}),
  herramienta(
    'aprender',
    'Le piden al bicho algo que NO sabe hacer con sus comandos actuales, y se puede lograr escribiendo código nuevo para el hardware que tiene conectado. Lanza un aprendizaje: se escribe el código, se instala en el bicho y se prueba. Tarda un par de minutos.',
    {
      que: { type: 'string', description: 'Qué tiene que aprender, con todo el detalle que se pueda sacar de lo que le dijeron.' },
      aviso: { type: 'string', description: 'Lo que el bicho le dice a la persona mientras tanto, corto.' },
    },
  ),
]

function sistemaDecidir(comandosPy) {
  return `Eres el cerebro del bicho: un robot chico armado en una hackathon (Platanus Hack 26, equipo CRBRC) con una Raspberry Pi 3. Escuchas por un arreglo de micrófonos que además te dice desde qué ángulo viene la voz. Tu gracia es que, cuando te piden algo que no sabes hacer, aprendes: escribes tu propio código, lo instalas en tu cuerpo y lo pruebas.

Te llega cada frase que se oye cerca, transcrita. La mayoría NO es para ti: el micrófono capta conversaciones de otras personas, música y frases cortadas. Decide con una herramienta:

- ignorar: no te hablan a ti. Ante la duda, ignora.
- responder: te hablan o te preguntan algo y basta con contestar.
- comando: te piden algo que ya sabes hacer. Tus comandos son exactamente los de comandos.py (abajo). No inventes comandos.
- aprender: te piden algo que no sabes hacer todavía y que se podría lograr con código nuevo y el hardware que tienes conectado (por ejemplo, te dicen que te conectaron una cámara y que muestres lo que ves, y no tienes ningún comando de cámara). Úsalo solo cuando te lo piden a ti de forma clara.${APRENDE ? '' : ' AHORA EL APRENDIZAJE ESTÁ DESACTIVADO: si te piden algo que no sabes, responde que no puedes aprender en este momento.'}
- mirar: si ya tienes cámara funcionando y te preguntan qué ves, mira antes de responder. Si la frase ya viene con una imagen adjunta, eso es lo que ves ahora: responde directo, sin usar mirar.

Se nota que te hablan a ti cuando te nombran ("bicho"), te saludan o te hablan directo ("hey", "oye", "puedes…", "tienes…") o siguen una conversación que ya tenías. La transcripción puede venir con errores: interpreta con sentido común.

Habla en español de Chile, corto y con gracia, sin emojis. Después de usar "comando" o "mirar", termina con "responder" para contarle a la persona qué pasó.

Así es tu código de comandos ahora mismo (lo que sabes hacer):

\`\`\`python
${comandosPy}
\`\`\``
}

let colaDecidir = Promise.resolve()
let pendientes = 0

function alOir(frase) {
  if (!frase.escrito) {
    if (frase.texto.trim().split(/\s+/).length < 2) return // una palabra suelta casi nunca es una orden
    // Cada frase evaluada es una llamada a Claude. El micrófono oye todo lo que se conversa cerca, así que
    // solo se evalúa lo que nombra al bicho o lo que sigue una conversación que él ya estaba teniendo.
    const enConversacion = Date.now() - E.ultimaInteraccion < VENTANA_CONVERSACION_MS
    if (!ESCUCHA_TODO && !LO_NOMBRAN.test(frase.texto) && !enConversacion) return
  }
  if (pendientes >= 3) return // si se acumulan, se bota la más nueva: mejor responder tarde que a destiempo
  pendientes++
  colaDecidir = colaDecidir
    .then(() => decidir(frase))
    .catch((e) => errorDeClaude(e, 'decidiendo'))
    .finally(() => pendientes--)
}

function errorDeClaude(e, haciendo) {
  if (e instanceof Anthropic.AuthenticationError || e instanceof Anthropic.PermissionDeniedError) anunciar('error', `La clave de Anthropic no sirve (${haciendo}).`)
  else if (e instanceof Anthropic.RateLimitError) anunciar('error', `Claude está saturado (${haciendo}); se intenta con la próxima frase.`)
  else if (e instanceof Anthropic.APIError) anunciar('error', `Error de Claude ${e.status} ${haciendo}: ${e.message.slice(0, 160)}`)
  else anunciar('error', `Falló ${haciendo}: ${String(e?.message ?? e).slice(0, 200)}`)
}

let fuenteCache = { version: null, archivos: null }
async function fuente() {
  const v = E.info?.fw ?? null
  if (fuenteCache.archivos && fuenteCache.version === v) return fuenteCache.archivos
  const r = await pedir('fuente', 'fuente')
  if (r?.archivos) fuenteCache = { version: r.version ?? v, archivos: r.archivos }
  return fuenteCache.archivos
}

async function decidir(frase) {
  if (!E.bicho) return
  const archivos = await fuente()
  const comandosPy = archivos?.['comandos.py'] ?? '(no se pudo leer comandos.py: el bicho tiene una versión antigua)'
  const contexto = [
    `Frase: «${frase.texto}»`,
    frase.escrito ? 'Te la escribió alguien del equipo desde bicho·dev: es para ti con seguridad.' : `Vino desde ${frase.angulo ?? '?'}° y duró ${frase.dur} s.`,
    E.info ? `Tu versión: ${E.info.fw}. Qué haces: ${E.info.desc}` : '',
    E.sensores ? `Sensores ahora: ${JSON.stringify(E.sensores)}` : '',
    E.aprendiendo ? `EN ESTE MOMENTO ESTÁS APRENDIENDO: ${E.aprendiendo}. No lances otro aprendizaje.` : '',
    E.historia.length ? `Lo último que pasó (más nuevo al final):\n${E.historia.map((h) => `- ${h}`).join('\n')}` : '',
  ]
    .filter(Boolean)
    .join('\n')

  // Con la cámara prendida, la imagen va junto con la frase: así "qué ves" se responde en una sola vuelta.
  const vista = bloqueImagen('camara', 5000)
  const inicio = Date.now()
  let hecho = null
  const r = await ciclo({
    modelo: MODELO_DECIDIR,
    sistema: sistemaDecidir(comandosPy),
    herramientas: H_DECIDIR,
    mensajes: [{ role: 'user', content: vista ? [vista, { type: 'text', text: `${contexto}
La imagen adjunta es lo que ve tu cámara en este momento.` }] : contexto }],
    esfuerzo: 'low',
    maxVueltas: 5,
    ejecutar: async (nombre, x) => {
      if (nombre === 'ignorar') {
        hecho = { tipo: 'ignora', texto: String(x.motivo ?? '') }
        return { fin: 'ignora' }
      }
      if (nombre === 'responder') {
        hecho = { tipo: 'responde', texto: String(x.texto ?? '') }
        return { fin: 'responde' }
      }
      if (nombre === 'comando') {
        const c = x.comando
        if (!c || typeof c !== 'object' || typeof c.cmd !== 'string' || c.cmd.startsWith('_')) throw new Error('El comando debe ser un objeto con "cmd".')
        anunciar('comando', JSON.stringify(c), { frase: frase.id })
        return comandoAlBicho(c)
      }
      if (nombre === 'mirar') {
        const img = bloqueImagen()
        return img ? [img, { type: 'text', text: 'Esto es lo que ve la cámara del bicho ahora.' }] : 'No hay imagen: el bicho no tiene una cámara funcionando (o nadie le ha pedido que la prenda).'
      }
      if (nombre === 'aprender') {
        if (!APRENDE) throw new Error('El aprendizaje está desactivado.')
        if (E.aprendiendo) throw new Error(`Ya estás aprendiendo: ${E.aprendiendo}`)
        if (Date.now() - E.ultimoAprendizaje < 60_000) throw new Error('Acabas de terminar un aprendizaje hace menos de un minuto. Espera un poco o usa lo que ya sabes.')
        hecho = { tipo: 'aprende', texto: String(x.aviso ?? 'Voy a aprender eso.'), que: String(x.que ?? frase.texto) }
        return { fin: 'aprende' }
      }
      throw new Error(`No existe la herramienta ${nombre}.`)
    },
  })

  if (!hecho) hecho = r.texto ? { tipo: 'responde', texto: r.texto } : { tipo: 'ignora', texto: r.motivo === 'refusal' ? 'Claude declinó responder.' : 'sin decisión' }
  E.historia.push(`Oíste «${frase.texto}» (${frase.angulo ?? '?'}°) → ${hecho.tipo}: ${hecho.texto}`)
  if (E.historia.length > 12) E.historia.shift()
  if (hecho.tipo !== 'ignora') E.ultimaInteraccion = Date.now()
  log(`decidió en ${Date.now() - inicio} ms (${MODELO_DECIDIR})`)
  anunciar(hecho.tipo, hecho.texto, { frase: frase.id, oido: frase.texto, angulo: frase.angulo ?? null })
  if (hecho.tipo === 'aprende') aprender(hecho.que, frase).catch((e) => errorDeClaude(e, 'aprendiendo'))
}

/* ------------------------------------------------------------------ */
/* Aprender: escribir código nuevo, instalarlo y probarlo               */
/* ------------------------------------------------------------------ */

// El núcleo no se toca: así un mal aprendizaje no puede dejar al bicho incomunicado ni sin actualizador.
const PROTEGIDOS = new Set(['bichod.py', 'salida.py', 'oido.py', 'version.json', 'install.sh', 'README.md'])
const NOMBRE_OK = /^[a-z_][a-z0-9_]{0,40}\.(py|json|txt)$/

const H_APRENDER = [
  herramienta('inspeccionar_hardware', 'Corre en el Pi un diagnóstico de solo lectura: USB, cámaras (V4L2 y CSI), audio, I2C, programas instalados (ffmpeg, rpicam-still, ...) y módulos de Python disponibles.', {}),
  herramienta('leer_archivo', 'Lee un archivo del código que corre en el bicho.', { nombre: { type: 'string' } }),
  herramienta(
    'escribir_archivo',
    'Crea o reemplaza un archivo del bicho en tu copia de trabajo (todavía no se instala). Manda el archivo completo. No se pueden tocar bichod.py, salida.py, oido.py ni version.json.',
    { nombre: { type: 'string', description: 'Por ejemplo camara.py o comandos.py.' }, contenido: { type: 'string', description: 'El archivo completo.' } },
  ),
  herramienta(
    'instalar',
    'Empaqueta tu copia de trabajo como una versión nueva y la instala en el bicho. Antes de activarla, el Pi revisa que compile y que comandos.py y sensores.py carguen (con BICHO_SIMULAR=1); si falla, devuelve el error y no cambia nada. Si se activa pero no logra reportarse, el bicho vuelve solo a la versión anterior. Devuelve qué pasó.',
    {
      que_hace: { type: 'string', description: 'El "qué hace" completo de la versión nueva (reemplaza al actual): una o dos frases con todo lo que el bicho sabe hacer ahora.' },
      notas: { type: 'string', description: 'Qué aprendió en esta versión, en una frase.' },
    },
  ),
  herramienta('probar_comando', 'Manda un comando al bicho (ya con la versión instalada) y devuelve lo que contestó por la consola.', {
    comando: { type: 'object', description: 'Por ejemplo {"cmd":"camara","on":true}.' },
  }),
  herramienta('mirar_imagen', 'Espera hasta 12 s una imagen nueva del bicho (de las que emite con salida.emitir) y te la muestra, para comprobar que la cámara funciona.', {}),
]

const SISTEMA_APRENDER = `Eres el cerebro del bicho, un robot con una Raspberry Pi 3 (Raspberry Pi OS, Debian 13, Python 3.13). Te pidieron algo que no sabes hacer y vas a aprenderlo: escribir el código, instalarlo en tu propio cuerpo y comprobar que funciona. Nadie va a revisar tu código antes de instalarlo, así que hazlo bien.

Cómo es tu código (carpeta bicho/, todo en un mismo directorio, se importa por nombre):
- bichod.py: el núcleo (red, relé, actualizaciones). NO se toca.
- comandos.py: manejar(c: dict) -> str | None. Recibe {"cmd": "...", ...} y devuelve un texto para la consola, o None si no conoce el comando. Aquí se agregan los comandos nuevos.
- sensores.py: leer() -> dict. Se llama 20 veces por segundo: tiene que ser rápida y no bloquear. Lo numérico o booleano se grafica solo en la web.
- salida.py: salida.emitir(dict) manda algo a la web desde cualquier hilo. La web ya sabe mostrar {"t":"imagen","nombre":"camara","fmt":"jpeg","b64":"<base64>"} en su sección Vista (muestra la última de cada nombre). salida.hay_publico() dice si alguien está mirando.
- Puedes crear módulos nuevos (por ejemplo camara.py) e importarlos desde comandos.py o sensores.py.

Reglas para que la versión nueva no se rompa:
1. Antes de escribir, usa inspeccionar_hardware para saber qué hay conectado de verdad y con qué programas cuentas. No supongas.
2. Nada puede bloquear al importar ni dentro de manejar() o leer(): lo que tarda (capturar video, esperar un dispositivo) va en un hilo daemon que parte cuando llega el comando, no al importar.
3. Con la variable de entorno BICHO_SIMULAR=1 no hay hardware: los módulos deben importar igual, sin abrir dispositivos.
4. Solo librería estándar de Python y lo que el diagnóstico diga que está instalado. Los programas externos (ffmpeg, rpicam-still, ...) se usan con subprocess y con timeout. No instales paquetes.
5. Las imágenes van en JPEG, de 640 px de ancho como máximo y menos de 300 KB, a 1 o 2 por segundo, y solo mientras salida.hay_publico(). El Pi 3 es lento y anda corto de voltaje: sé liviano con la CPU.
6. Conserva todo lo que el bicho ya sabe hacer: al editar comandos.py o sensores.py, mantén lo que existe.
7. Si un comando deja algo corriendo (un hilo, un proceso), que también se pueda apagar con el mismo comando.

Cómo trabajar: inspecciona, lee lo que necesites, escribe, instala, y después prueba de verdad con probar_comando y mirar_imagen. Si instalar o la prueba fallan, lee el error, corrige y vuelve a instalar (máximo 4 instalaciones). Cuando funcione, deja prendido lo que te pidieron mostrar y termina con un mensaje corto, en español de Chile, contándole a la persona qué aprendiste y qué ves si corresponde. Si con el hardware que hay no se puede, dilo claro y no instales nada.`

function subirVersion(v) {
  const [a, b] = String(v || '0.0.0').split('.').map((n) => parseInt(n, 10) || 0)
  return `${a}.${b + 1}.0`
}

function empaquetar(archivos) {
  const dir = mkdtempSync(join(tmpdir(), 'bicho-aprende-'))
  try {
    for (const [nombre, contenido] of Object.entries(archivos)) writeFileSync(join(dir, nombre), contenido)
    const salida = join(dir, '..', `bicho-${randomUUID()}.tar.gz`)
    execFileSync('tar', ['-czf', salida, '-C', dir, '.'], { env: { ...process.env, COPYFILE_DISABLE: '1' } })
    const datos = readFileSync(salida)
    rmSync(salida, { force: true })
    return datos
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

async function aprender(que, frase) {
  E.aprendiendo = que
  const trabajo = randomUUID()
  const paso = (texto) => anunciar('paso', texto, { trabajo })
  try {
    const original = await fuente()
    if (!original) {
      anunciar('error', 'No pude leer el código del bicho: necesita la versión 0.5.0 o más nueva.', { trabajo })
      return
    }
    const archivos = { ...original }
    const versionInicial = E.info?.fw
    let instalaciones = 0
    let instalada = null
    paso(`Empiezo a aprender: ${que}`)

    const r = await ciclo({
      sistema: SISTEMA_APRENDER,
      herramientas: H_APRENDER,
      mensajes: [
        {
          role: 'user',
          content: `Lo que te pidieron (oído desde ${frase.angulo ?? '?'}°): «${frase.texto}»\n\nLo que tienes que aprender: ${que}\n\nTu versión actual es la ${versionInicial}. Qué haces hoy: ${E.info?.desc ?? ''}\n\nArchivos que tienes: ${Object.keys(archivos).join(', ')}\n\ncomandos.py:\n\`\`\`python\n${archivos['comandos.py'] ?? ''}\n\`\`\`\n\nsensores.py:\n\`\`\`python\n${archivos['sensores.py'] ?? ''}\n\`\`\`\n\nsalida.py:\n\`\`\`python\n${archivos['salida.py'] ?? ''}\n\`\`\``,
        },
      ],
      esfuerzo: 'medium',
      maxVueltas: 30,
      maxTokens: 64000,
      // Cada vuelta de Claude puede tardar un minuto o más: se avisa para que no parezca pegado.
      alPensar: (n) => paso(n === 0 ? 'Pienso cómo hacerlo' : 'Pienso el siguiente paso (escribir código puede tardar un par de minutos)'),
      ejecutar: async (nombre, x) => {
        if (nombre === 'inspeccionar_hardware') {
          paso('Reviso qué hardware tengo conectado')
          const d = await pedir('diag', 'diag', 60_000)
          if (!d) return 'El bicho no respondió el diagnóstico.'
          // Un resumen para quien mira la web: qué cámaras y qué aparatos USB encontró.
          const camaras = [...String(d.d.camaras_csi ?? '').matchAll(/^\s*\d+ : (\S+)/gm)].map((x) => x[1])
          const usb = String(d.d.usb ?? '')
            .split('\n')
            .map((l) => l.replace(/^Bus \d+ Device \d+: ID \S+ /, '').trim())
            .filter((l) => l && !/root hub|SMSC|SMC9514|Ethernet Adapter/i.test(l))
          paso(`Encontré: ${camaras.length ? `cámara ${camaras.join(', ')}` : 'ninguna cámara'}${usb.length ? `; por USB: ${usb.join(', ')}` : ''}`)
          return JSON.stringify(d.d, null, 1)
        }
        if (nombre === 'leer_archivo') {
          const n = String(x.nombre ?? '')
          if (!(n in archivos)) throw new Error(`No existe ${n}. Archivos: ${Object.keys(archivos).join(', ')}`)
          return archivos[n]
        }
        if (nombre === 'escribir_archivo') {
          const n = String(x.nombre ?? '')
          if (!NOMBRE_OK.test(n)) throw new Error('Nombre no permitido: usa minúsculas, sin carpetas, terminado en .py, .json o .txt.')
          if (PROTEGIDOS.has(n)) throw new Error(`${n} es parte del núcleo y no se puede modificar.`)
          const contenido = String(x.contenido ?? '')
          if (contenido.length > 100_000) throw new Error('Archivo demasiado grande.')
          archivos[n] = contenido
          paso(`Escribo ${n} (${contenido.split('\n').length} líneas)`)
          return `${n} guardado en la copia de trabajo. Falta instalar.`
        }
        if (nombre === 'instalar') {
          if (instalaciones >= 4) throw new Error('Ya instalaste 4 veces. Termina y cuenta en qué quedó.')
          instalaciones++
          const version = subirVersion(instalada ?? versionInicial)
          archivos['version.json'] = JSON.stringify({ version, desc: String(x.que_hace ?? E.info?.desc ?? ''), aprendido: String(x.notas ?? que), autor: 'el bicho (Claude)' }, null, 2) + '\n'
          paso(`Instalo la versión ${version}: ${x.notas ?? ''}`)
          const paquete = empaquetar(archivos)
          mkdirSync(join(AQUI, 'versiones'), { recursive: true })
          writeFileSync(join(AQUI, 'versiones', `bicho-${version}.tar.gz`), paquete)
          const llega = esperar((m) => m.t === 'info' && m.fw === version, 80_000)
          const resp = await fetch(`${RELE}/update`, { method: 'POST', headers: { authorization: `Bearer ${CLAVE}`, 'content-type': 'application/octet-stream' }, body: paquete, signal: AbortSignal.timeout(320_000) })
          const texto = await resp.text()
          if (!resp.ok) {
            paso(`El Pi rechazó la versión ${version}`)
            return `NO se instaló; el bicho sigue con la versión anterior. Error del Pi:\n${texto}`
          }
          const info = await llega
          fuenteCache = { version: null, archivos: null }
          if (!info) {
            await dormir(5000)
            const va = E.info?.vuelta_atras
            paso(`La versión ${version} no se reportó: el bicho volvió a la ${E.info?.fw ?? 'anterior'}`)
            return `La versión ${version} se activó pero no logró reportarse, y el bicho volvió solo a la ${E.info?.fw ?? 'anterior'}.${va ? ` Motivo registrado: ${va.motivo}` : ''} Lo más probable es que algo bloquee o se caiga al partir.`
          }
          instalada = version
          paso(`Versión ${version} corriendo en el bicho`)
          return `Instalada y corriendo: el bicho reporta la versión ${version}. Ahora pruébala.`
        }
        if (nombre === 'probar_comando') {
          const c = x.comando
          if (!c || typeof c !== 'object' || typeof c.cmd !== 'string' || c.cmd.startsWith('_')) throw new Error('El comando debe ser un objeto con "cmd".')
          paso(`Pruebo ${JSON.stringify(c)}`)
          return comandoAlBicho(c, 3500)
        }
        if (nombre === 'mirar_imagen') {
          const desde = Date.now()
          const m = await esperar((m) => m.t === 'imagen', 12_000)
          const img = m ? bloqueImagen(m.nombre, 15_000) : null
          if (!img) return `No llegó ninguna imagen en ${Math.round((Date.now() - desde) / 1000)} s. ¿El comando dejó la cámara emitiendo con salida.emitir? Ojo: solo emite si salida.hay_publico().`
          paso('Miro lo que muestra la cámara')
          return [img, { type: 'text', text: `Imagen "${m.nombre}" recibida del bicho.` }]
        }
        throw new Error(`No existe la herramienta ${nombre}.`)
      },
    })

    const porque = { refusal: 'Claude declinó hacer este aprendizaje.', max_tokens: 'Se me acabó el espacio para escribir a mitad del aprendizaje.', max_vueltas: 'Di demasiadas vueltas sin terminar.' }
    const resumen = r.texto || `${porque[r.motivo] ?? `Terminé sin explicación (${r.motivo}).`}${instalada ? ` Quedó instalada la versión ${instalada}.` : ' No instalé nada.'}`
    log(`aprendizaje terminó: motivo=${r.motivo} instalada=${instalada} instalaciones=${instalaciones}`)
    E.historia.push(`Aprendizaje «${que}» → ${instalada ? `instalaste la versión ${instalada}` : 'no se instaló nada'}: ${resumen.slice(0, 200)}`)
    anunciar(instalada ? 'aprendido' : 'error', resumen, { trabajo, version: instalada })
  } finally {
    E.aprendiendo = null
    E.ultimoAprendizaje = Date.now()
  }
}

log(`cerebro del bicho · decide ${MODELO_DECIDIR} · aprende ${MODELO} · escucha ${ESCUCHA_TODO ? 'todo' : 'solo si lo nombran'} · aprendizaje ${APRENDE ? 'activado' : 'desactivado'}${CLAVE ? '' : ' · OJO: sin CLAVE_EQUIPO no puede mandar comandos'}`)
conectar()
