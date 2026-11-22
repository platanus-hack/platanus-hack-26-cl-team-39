// Atajos: las órdenes de movimiento más comunes se reconocen por palabras y se mandan al bicho al tiro,
// sin pasar por Claude. Una decisión con el modelo tarda 1 a 3 segundos; esto, lo que demora la red.
//
// Solo calza si la frase ENTERA es la orden (más un "bicho", un "por favor", una potencia o un tiempo).
// Cualquier otra cosa ("avanza hasta la puerta y vuelve", "¿por qué no avanzas?") sigue yendo al modelo.

const sinTildes = (s) => String(s ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()

const PARAR = /^(para|parate|paren|detente|detenete|alto|stop|frena|quieto|basta|para ahi|apaga(?: los)? motores|para(?: los)? motores|deten(?: los)? motores|corta(?: los)? motores)$/
const AVANZAR = /^(avanza|avanzar|adelante|hacia adelante|para adelante|pa delante|avanza (?:hacia |para )?adelante|anda (?:hacia |para )?adelante|ve (?:hacia |para )?adelante|camina|corre|acelera|acelerar|(?:prende|prender|enciende|encender|arranca|arrancar|activa|activar|echa a andar|parte|partir)(?: los| tus)? motores|motores)$/
const ATRAS = /^(atras|hacia atras|para atras|pa tras|retrocede|retroceder|reversa|marcha atras|retrocede (?:hacia |para )?atras|anda (?:hacia |para )?atras|ve (?:hacia |para )?atras|echate (?:para |pa )?atras)$/
// "Gira" a secas o "date una vuelta": un giro completo, por defecto hacia la derecha.
const VUELTA = /^(?:gira|girar|rota|rotar|vuelta|da una vuelta|date una vuelta|dale una vuelta|vuelta completa|gira completo|da la vuelta|date vuelta|gira en tu eje|gira sobre tu eje|rota sobre tu eje|gira sobre tu propio eje|rota sobre tu propio eje)(?: completa)?$/
const GIRO = /^(?:(?:gira|girar|rota|rotar|dobla|doblar|vira|virar|voltea|date vuelta|da vuelta|vuelta) )?(?:(?:a|hacia|para) )?(?:la )?(izquierda|derecha)$/

/** ¿La versión `v` es igual o mayor que `min`? ("0.35.0" ≥ "0.35.0") */
export function desde(v, min) {
  const a = String(v ?? '').split('.').map((x) => parseInt(x, 10) || 0)
  const b = min.split('.').map((x) => parseInt(x, 10) || 0)
  for (let i = 0; i < 3; i++) if ((a[i] ?? 0) !== (b[i] ?? 0)) return (a[i] ?? 0) > (b[i] ?? 0)
  return true
}

/**
 * Devuelve { tipo, cmd } si el texto es una orden directa de movimiento; si no, null.
 * tipo: "parar" | "avanzar" | "atras" | "giro". `fw` es la versión del bicho: girar existe desde la 0.35.0.
 */
export function atajo(texto, { potencia = 50, fw = null, giroSeg = 2.5, giroPot = 70, acelera = 80 } = {}) {
  let t = sinTildes(texto)
    .replace(/[^a-z0-9ñ%., ]+/g, ' ')
    .replace(/\b(bich[oaei]s?|bichito|vich[oa]|oye|hey|ey|ya|ahora|altiro|al tiro|porfa|por favor|rapido|no mas|po|pues|puedes|podrias|quiero que|necesito que|me puedes|te pido que)\b/g, ' ')
  // Potencia ("al 80", "80 %", "a toda potencia") y tiempo ("por 3 segundos", "2 s"). Se sacan de la frase.
  let pot = null
  let seg = null
  t = t.replace(/\b(?:por |durante )?(\d{1,2}(?:[.,]\d)?) ?(?:segundos?|segs?|s)\b/, (_, n) => ((seg = Number(n.replace(',', '.'))), ' '))
  t = t.replace(/\b(?:al?|con) (\d{1,3}) ?(?:%|por ciento)?(?= |$)|\b(\d{1,3}) ?(?:%|por ciento)/, (_, a, b) => ((pot = Number(a ?? b)), ' '))
  t = t.replace(/\b(?:a|con) (?:toda|full|maxima) (?:potencia|velocidad|maquina)\b|\ba fondo\b|\bal maximo\b/, () => ((pot = 100), ' '))
  t = t.replace(/\b(?:sin parar|sin limite|hasta que te diga)\b/, () => ((seg = 0), ' '))
  t = t.replace(/[.,]+/g, ' ').replace(/\s+/g, ' ').trim()
  if (!t || t.split(' ').length > 5) return null
  const p = Math.max(1, Math.min(100, pot ?? potencia))

  if (PARAR.test(t)) return { tipo: 'parar', cmd: { cmd: 'motores', on: false } }
  // Sin tiempo dicho, avanzar y retroceder siguen hasta que le digan "para": es un robot que tiene que poder correr.
  if (AVANZAR.test(t)) {
    const pa = pot === null && /^acelera/.test(t) ? acelera : p
    return { tipo: 'avanzar', cmd: { cmd: 'motores', on: true, pot: pa, seg: seg ?? 0 } }
  }
  if (ATRAS.test(t)) return { tipo: 'atras', cmd: { cmd: 'motores', on: true, sentido: -1, pot: p, seg: seg ?? 0 } }
  // Girar es un giro completo: giroSeg segundos a giroPot (se calibran con CEREBRO_GIRO_S y CEREBRO_GIRO_POT).
  const g = GIRO.exec(t)
  const vuelta = !g && VUELTA.test(t)
  if (g || vuelta) {
    if (!desde(fw, '0.35.0')) return null // esa versión del bicho todavía no sabe girar: que lo vea el modelo
    return { tipo: 'giro', cmd: { cmd: 'motores', giro: g ? g[1] : 'derecha', pot: pot ?? giroPot, seg: seg ?? giroSeg } }
  }
  return null
}
