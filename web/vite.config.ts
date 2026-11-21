import { defineConfig, loadEnv, type Plugin, type ViteDevServer } from 'vite'
import react from '@vitejs/plugin-react'
import { execSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import type { IncomingMessage } from 'node:http'
import pkg from './package.json' with { type: 'json' }

/** API del inventario ya publicada. Si no tienes web/.env con DATABASE_URL, el dev server le pasa /api a ella. */
const API_PUBLICA = 'https://bicho-dev.vercel.app'

function gitSha(): string | null {
  try {
    return execSync('git rev-parse --short HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
  } catch {
    return null
  }
}

async function cuerpo(req: IncomingMessage) {
  const chunks: Buffer[] = []
  for await (const c of req) chunks.push(c as Buffer)
  return Buffer.concat(chunks)
}

/** Corre las funciones de web/api/*.ts dentro del dev server, igual que en Vercel (Request → Response). */
function apiLocal(): Plugin {
  return {
    name: 'api-local',
    configureServer(server: ViteDevServer) {
      server.middlewares.use(async (req, res, next) => {
        const url = new URL(req.url ?? '/', 'http://localhost')
        const m = url.pathname.match(/^\/api\/([a-z-]+)\/?$/)
        if (!m) return next()
        const file = resolve(server.config.root, 'api', `${m[1]}.ts`)
        if (!existsSync(file)) return next()
        try {
          const mod = await server.ssrLoadModule(file)
          const handler = mod[req.method ?? 'GET'] as ((r: Request) => Promise<Response> | Response) | undefined
          if (!handler) {
            res.statusCode = 405
            return res.end()
          }
          const body = req.method === 'GET' || req.method === 'HEAD' ? undefined : await cuerpo(req)
          const headers = new Headers()
          for (const [k, v] of Object.entries(req.headers)) if (typeof v === 'string') headers.set(k, v)
          const out = await handler(new Request(url, { method: req.method, headers, body }))
          res.statusCode = out.status
          out.headers.forEach((v, k) => res.setHeader(k, v))
          res.end(Buffer.from(await out.arrayBuffer()))
        } catch (e) {
          server.ssrFixStacktrace(e as Error)
          console.error(e)
          res.statusCode = 500
          res.setHeader('content-type', 'application/json')
          res.end(JSON.stringify({ error: (e as Error).message }))
        }
      })
    },
  }
}

export default defineConfig(({ mode }) => {
  // Las variables de web/.env (DATABASE_URL, INVENTARIO_TOKEN, ANTHROPIC_API_KEY) quedan para las funciones de api/.
  const env = loadEnv(mode, process.cwd(), '')
  for (const k of ['DATABASE_URL', 'INVENTARIO_TOKEN', 'ANTHROPIC_API_KEY', 'AI_GATEWAY_API_KEY', 'VERCEL_OIDC_TOKEN']) if (env[k] && !process.env[k]) process.env[k] = env[k]
  const local = Boolean(process.env.DATABASE_URL)

  return {
    plugins: [react(), ...(local ? [apiLocal()] : [])],
    define: {
      __APP_VERSION__: JSON.stringify(pkg.version),
      __GIT_SHA__: JSON.stringify(gitSha()),
      __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
    },
    server: {
      port: 5173,
      host: 'localhost',
      proxy: local ? undefined : { '/api': { target: env.INVENTARIO_API || API_PUBLICA, changeOrigin: true } },
    },
  }
})
