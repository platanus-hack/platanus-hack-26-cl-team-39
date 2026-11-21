// Le dice a Claude qué está pasando en el evento y qué viene, según web/src/lib/cronograma.json.
// Lo llama al-iniciar.sh. Si algo falla, no imprime nada.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

try {
  const raiz = process.env.CLAUDE_PROJECT_DIR || process.cwd()
  const { eventos } = JSON.parse(readFileSync(join(raiz, 'web/src/lib/cronograma.json'), 'utf8'))
  const ev = eventos.map((e) => ({ ...e, i: new Date(e.inicio).getTime(), f: new Date(e.fin).getTime() })).sort((a, b) => a.i - b.i)
  const now = Date.now()

  const fmt = (ms) =>
    new Intl.DateTimeFormat('es-CL', { weekday: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: 'America/Santiago' }).format(ms)
  const falta = (ms) => {
    const min = Math.max(0, Math.round((ms - now) / 60000))
    if (min < 60) return `en ${min} min`
    return min % 60 ? `en ${Math.floor(min / 60)} h ${min % 60} min` : `en ${min / 60} h`
  }

  const ahora = ev.filter((e) => e.i <= now && now < e.f)
  const proximos = ev.filter((e) => e.i > now).slice(0, 3)
  const comida = ev.find((e) => e.tipo === 'comida' && e.i > now)
  const fin = ev.find((e) => e.titulo === 'Fin del hacking')

  const out = [`Cronograma del evento (hora de Santiago: ${fmt(now)}):`]
  for (const e of ahora) out.push(`- Ahora: ${e.icono} ${e.titulo}, hasta ${fmt(e.f)}.`)
  for (const e of proximos) out.push(`- Próximo: ${e.icono} ${e.titulo}, ${fmt(e.i)} (${falta(e.i)}).`)
  if (comida && !proximos.includes(comida)) out.push(`- Próxima comida: ${comida.icono} ${comida.titulo}, ${fmt(comida.i)} (${falta(comida.i)}).`)
  if (fin && fin.i > now) out.push(`- Fin del hacking: ${fmt(fin.i)} (${falta(fin.i)}); la entrega en la plataforma cierra el dom 22 a las 09:00.`)
  if (!ahora.length && !proximos.length) out.push('- El evento ya terminó.')
  out.push('Si tu humano pregunta qué viene o a qué hora se come, responde con esto; el cronograma completo está en web/src/lib/cronograma.json.')
  console.log(out.join('\n'))
} catch {
  // sin cronograma: no decimos nada
}
