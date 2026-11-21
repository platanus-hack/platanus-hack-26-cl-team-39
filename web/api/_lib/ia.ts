// Búsqueda en lenguaje natural sobre el inventario, con Claude.
// Credenciales: ANTHROPIC_API_KEY (directo a Anthropic). Sin ella, usa Vercel AI Gateway
// (AI_GATEWAY_API_KEY, o VERCEL_OIDC_TOKEN que Vercel pone solo en sus funciones).
import Anthropic from '@anthropic-ai/sdk'
import { betaZodOutputFormat } from '@anthropic-ai/sdk/helpers/beta/zod'
import { z } from 'zod'
import { ErrorHttp, listar, type Item } from './inventario.js'

const MODELO = 'claude-opus-5-5'

const Respuesta = z.object({
  respuesta: z.string().describe('Respuesta corta en español de Chile, en texto plano. Nombra los ítems y cuántos hay.'),
  ids: z.array(z.number().int()).describe('IDs de los ítems que responden la pregunta, del más al menos relevante. Vacío si no hay ninguno.'),
})
export type RespuestaIA = z.infer<typeof Respuesta> & { modelo: string }

const INSTRUCCIONES = `Eres el buscador del inventario de hardware del equipo CRBRC en Platanus Hack 26 (una hackathon de 36 horas, track hardware).
El equipo construye "el bicho": un robot sobre un chasis 4WD con una Raspberry Pi 3, que maneja un agente Claude. Antes la idea era una lámpara robótica; la columna "uso en la lámpara" viene de esa idea y ya no manda.

Responde la pregunta usando solo el inventario de abajo. Reglas:
- Sé breve y concreto: qué hay, cuántos, de quién es (origen) y en qué estado. Si sirve, di dónde está o qué notas tiene.
- Entiende sinónimos, nombres en inglés, modelos y abreviaturas (por ejemplo "motor" incluye servos, motores TT y N20; "batería" incluye packs y portapilas; "cámara" incluye la ESP32-CAM).
- Si lo que piden no está, dilo claro y sugiere lo más parecido que sí hay.
- Si hay ítems que parecen el mismo listado dos veces (por ejemplo en dos pestañas del Sheet original), avísalo en vez de sumarlos.
- No inventes ítems, cantidades ni especificaciones que no estén en el inventario.
- En "ids" pon solo IDs que existan en el inventario.`

function cliente() {
  // baseURL fijo: en local puede haber un ANTHROPIC_BASE_URL de otra herramienta en el entorno.
  if (process.env.ANTHROPIC_API_KEY)
    return { client: new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY, baseURL: 'https://api.anthropic.com' }), modelo: MODELO, gateway: false }
  const token = process.env.AI_GATEWAY_API_KEY || process.env.VERCEL_OIDC_TOKEN
  if (token)
    return {
      client: new Anthropic({ apiKey: null, authToken: token, baseURL: 'https://ai-gateway.vercel.sh' }),
      // En AI Gateway los modelos van como "anthropic/claude-opus-5.5".
      modelo: `anthropic/${MODELO.replace(/-(\d+)-(\d+)$/, '-$1.$2')}`,
      gateway: true,
    }
  throw new ErrorHttp(503, 'El servidor no tiene credenciales de Claude (ANTHROPIC_API_KEY o AI Gateway).')
}

function tabla(items: Item[]) {
  const c = (v: unknown) => String(v ?? '').replace(/\s+/g, ' ').replace(/\|/g, '/').trim()
  const filas = items.map((i) =>
    [i.id, c(i.nombre), i.cantidad ?? '?', c(i.categoria), c(i.origen), c(i.estado), c(i.uso_bicho), c(i.ubicacion), c(i.notas), c(i.uso_lampara)].join(' | '),
  )
  return ['id | ítem | cant. | categoría | origen | estado | uso en el bicho | ubicación | notas | uso en la lámpara (idea anterior)', ...filas].join('\n')
}

export async function preguntar(pregunta: string): Promise<RespuestaIA> {
  const { client, modelo, gateway } = cliente()
  const items = await listar()
  const existentes = new Set(items.map((i) => i.id))

  try {
    const msg = await client.beta.messages.parse({
      model: modelo,
      max_tokens: 4000,
      // Respuesta rápida: es una búsqueda, no un problema difícil.
      output_config: { effort: 'low', format: betaZodOutputFormat(Respuesta) },
      // Si el modelo declina por seguridad, la API reintenta sola con otro modelo (solo en la API directa de Anthropic).
      ...(gateway ? {} : { betas: ['server-side-fallback-2026-07-01'], fallbacks: 'default' as const }),
      system: [
        { type: 'text', text: INSTRUCCIONES },
        { type: 'text', text: `Inventario (${items.length} ítems):\n${tabla(items)}`, cache_control: { type: 'ephemeral' } },
      ],
      messages: [{ role: 'user', content: pregunta }],
    })
    if (msg.stop_reason === 'refusal') throw new ErrorHttp(422, 'Claude no quiso responder esa pregunta.')
    const out = msg.parsed_output
    if (!out) throw new ErrorHttp(502, 'Claude no devolvió una respuesta válida. Intenta de nuevo.')
    return { respuesta: out.respuesta, ids: out.ids.filter((id) => existentes.has(id)), modelo: msg.model }
  } catch (e) {
    if (e instanceof ErrorHttp) throw e
    if (e instanceof Anthropic.AuthenticationError || e instanceof Anthropic.PermissionDeniedError)
      throw new ErrorHttp(503, `Las credenciales de Claude del servidor no sirven (${gateway ? 'AI Gateway' : 'ANTHROPIC_API_KEY'}): ${e.message}`)
    if (e instanceof Anthropic.RateLimitError) throw new ErrorHttp(429, 'Claude está saturado. Prueba en unos segundos.')
    if (e instanceof Anthropic.APIError) throw new ErrorHttp(502, `Error de Claude (${e.status}): ${e.message}`)
    throw e
  }
}
