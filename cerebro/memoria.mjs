// Memoria del cerebro del bicho. Tres capas, de la más durable a la más fugaz:
//
//   hechos        lo que el bicho decidió recordar (nombres, gustos, decisiones, cómo le conectaron algo).
//                 Va siempre en el contexto y solo cambia cuando él usa "recordar" u "olvidar".
//   resumen       lo conversado hace rato, comprimido en un párrafo cuando la conversación se alarga.
//   conversación  los últimos turnos en que le hablaron A ÉL (escrito o por voz), tal cual.
//
// Aparte queda el ruido: frases que oyó y decidió ignorar. Se guardan muy pocas y nunca desplazan la
// conversación: en una sala con mucha gente, el micrófono llenaba la memoria en menos de un minuto.
//
// Todo se guarda en un archivo JSON al lado del cerebro, así sobrevive a un reinicio. No se sube al repo.

import { existsSync, readFileSync, renameSync, writeFileSync } from 'node:fs'

const recortar = (s, n) => {
  const t = String(s ?? '').replace(/\s+/g, ' ').trim()
  return t.length > n ? `${t.slice(0, n - 1)}…` : t
}
const hora = (ts) => new Date(ts).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', hour12: false })

export function crearMemoria(archivo, { maxHechos = 40, maxTurnos = 24, alResumir = 12, maxRuido = 4, maxSucesos = 6 } = {}) {
  const datos = { hechos: [], resumen: '', conversacion: [], sucesos: [] }
  let ruido = [] // no se guarda en disco: es de este rato
  if (archivo && existsSync(archivo)) {
    try {
      const d = JSON.parse(readFileSync(archivo, 'utf8'))
      if (Array.isArray(d.hechos)) datos.hechos = d.hechos.filter((h) => h && typeof h.texto === 'string').slice(-maxHechos)
      if (typeof d.resumen === 'string') datos.resumen = d.resumen
      if (Array.isArray(d.conversacion)) datos.conversacion = d.conversacion.filter((t) => t && typeof t.texto === 'string')
      if (Array.isArray(d.sucesos)) datos.sucesos = d.sucesos.filter((s) => typeof s === 'string').slice(-maxSucesos)
    } catch {
      /* archivo dañado: se parte de cero y se reescribe con el próximo cambio */
    }
  }

  function guardar() {
    if (!archivo) return
    try {
      writeFileSync(`${archivo}.tmp`, JSON.stringify(datos, null, 1))
      renameSync(`${archivo}.tmp`, archivo)
    } catch {
      /* sin disco no hay memoria durable, pero el cerebro sigue */
    }
  }

  return {
    datos,

    /** Guarda un hecho. Devuelve lo que se le contesta a Claude. */
    recordar(texto) {
      const t = recortar(texto, 240)
      if (!t) return 'No había nada que recordar.'
      if (datos.hechos.some((h) => h.texto.toLowerCase() === t.toLowerCase())) return 'Eso ya lo recordabas.'
      datos.hechos.push({ texto: t, ts: Date.now() })
      let botado = null
      if (datos.hechos.length > maxHechos) botado = datos.hechos.shift()
      guardar()
      return `Guardado. Recuerdas ${datos.hechos.length} cosas.${botado ? ` Se cayó la más antigua: «${botado.texto}».` : ''}`
    },

    /** Borra los hechos cuyo número (como aparecen en el contexto) o texto calza. */
    olvidar(que) {
      const q = String(que ?? '').trim().toLowerCase()
      if (!q) return 'Falta decir qué olvidar.'
      const n = /^\d+$/.test(q) ? Number(q) : null
      const antes = datos.hechos.length
      datos.hechos = datos.hechos.filter((h, i) => (n !== null ? i + 1 !== n : !h.texto.toLowerCase().includes(q)))
      const borrados = antes - datos.hechos.length
      if (borrados) guardar()
      return borrados ? `Olvidado (${borrados}). Recuerdas ${datos.hechos.length} cosas.` : 'No encontré nada así en tu memoria.'
    },

    /** Un turno de conversación: algo que le dijeron a él y lo que hizo o contestó. */
    turno({ escrito, angulo, texto, tipo, respuesta, ts = Date.now() }) {
      datos.conversacion.push({ ts, escrito: Boolean(escrito), angulo: angulo ?? null, texto: recortar(texto, 500), tipo, respuesta: recortar(respuesta, 700) })
      guardar()
    },

    /** Algo que pasó sin que nadie le hablara (un aprendizaje terminó, por ejemplo). */
    suceso(texto) {
      datos.sucesos.push(`${hora(Date.now())} ${recortar(texto, 300)}`)
      if (datos.sucesos.length > maxSucesos) datos.sucesos.shift()
      guardar()
    },

    /** Una frase oída que no era para él. */
    ruido(texto) {
      ruido.push(recortar(texto, 120))
      if (ruido.length > maxRuido) ruido.shift()
    },

    /** La conversación reciente como mensajes para Claude (usuario y asistente alternados). */
    mensajes() {
      const m = []
      for (const t of datos.conversacion) {
        m.push({ role: 'user', content: `[${hora(t.ts)}, ${t.escrito ? 'te lo escribieron' : `lo oíste desde ${t.angulo ?? '?'}°`}] ${t.texto}` })
        m.push({ role: 'assistant', content: `${t.tipo === 'aprende' ? '(lanzaste un aprendizaje) ' : ''}${t.respuesta || '(no dijiste nada)'}` })
      }
      return m
    },

    /** Lo que va en el contexto de cada decisión, además de la conversación. */
    bloque() {
      return [
        datos.hechos.length ? `Tu memoria (lo que decidiste recordar; no se borra sola):\n${datos.hechos.map((h, i) => `${i + 1}. ${h.texto}`).join('\n')}` : 'Tu memoria está vacía: todavía no has guardado nada con "recordar".',
        datos.resumen ? `Resumen de lo que conversaron antes:\n${datos.resumen}` : '',
        datos.sucesos.length ? `Lo último que hiciste por tu cuenta:\n${datos.sucesos.map((s) => `- ${s}`).join('\n')}` : '',
        ruido.length ? `Frases sueltas que oíste hace poco y no eran para ti (ruido de la sala, no las contestes):\n${ruido.map((r) => `- ${r}`).join('\n')}` : '',
      ]
        .filter(Boolean)
        .join('\n\n')
    },

    /** Si la conversación ya es larga, devuelve los turnos más viejos para resumirlos; si no, null. */
    porResumir() {
      return datos.conversacion.length > maxTurnos ? datos.conversacion.slice(0, alResumir) : null
    },

    /** Reemplaza el resumen y bota los turnos que ya quedaron dentro de él. */
    aplicarResumen(resumen, turnos) {
      const t = recortar(resumen, 900)
      if (!t) return
      datos.resumen = t
      const viejos = new Set(turnos)
      datos.conversacion = datos.conversacion.filter((x) => !viejos.has(x))
      guardar()
    },

    /** Para pedirle a Claude el resumen: lo anterior más los turnos que salen. */
    textoParaResumir(turnos) {
      return [
        datos.resumen ? `Resumen anterior:\n${datos.resumen}` : '',
        `Turnos nuevos:\n${turnos.map((t) => `- [${hora(t.ts)}] Le dijeron: «${t.texto}» → ${t.tipo}: ${t.respuesta}`).join('\n')}`,
      ]
        .filter(Boolean)
        .join('\n\n')
    },
  }
}
