#!/usr/bin/env node
// Publica una versión de firmware para que aparezca en la web como "disponible".
//
// Uso:
//   npm run release -- --version 0.2.0 --notes "Qué hace esta versión" --dir ../firmware/bicho/build
//   npm run release -- --version 0.2.0 --notes "..." --app ruta/bicho.ino.bin [--merged ruta/bicho.ino.merged.bin] [--author Carlos]
//
// Con --dir busca *.ino.bin y *.ino.merged.bin (lo que deja Arduino IDE con "Sketch > Export Compiled Binary"
// o arduino-cli compile --export-binaries). Copia todo a public/firmware/<version>/ y actualiza manifest.json.

import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { basename, dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execSync } from 'node:child_process'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const fwDir = join(root, 'public', 'firmware')
const manifestPath = join(fwDir, 'manifest.json')

function args() {
  const out = {}
  const a = process.argv.slice(2)
  for (let i = 0; i < a.length; i++) {
    if (!a[i].startsWith('--')) continue
    const k = a[i].slice(2)
    const v = a[i + 1] && !a[i + 1].startsWith('--') ? a[++i] : 'true'
    out[k] = v
  }
  return out
}

function fail(msg) {
  console.error(`✖ ${msg}`)
  process.exit(1)
}

function findIn(dir, test) {
  const hits = []
  const walk = (d) => {
    for (const f of readdirSync(d)) {
      const p = join(d, f)
      if (statSync(p).isDirectory()) walk(p)
      else if (test(f)) hits.push(p)
    }
  }
  walk(dir)
  return hits.sort((x, y) => statSync(y).mtimeMs - statSync(x).mtimeMs)[0]
}

const o = args()
const version = (o.version || '').replace(/^v/, '')
if (!/^\d+\.\d+\.\d+([-.][\w.]+)?$/.test(version)) fail('Falta --version X.Y.Z (igual al FW_VERSION del firmware)')
if (!o.notes) fail('Falta --notes "qué hace esta versión"')

let app = o.app
let merged = o.merged
if (o.dir) {
  const d = resolve(o.dir)
  if (!existsSync(d)) fail(`No existe ${d}`)
  merged ??= findIn(d, (f) => f.endsWith('.merged.bin'))
  app ??= findIn(d, (f) => f.endsWith('.bin') && !/\.(merged|bootloader|partitions)\.bin$/.test(f) && f !== 'boot_app0.bin')
}
if (!app && !merged) fail('No encontré binarios. Usa --dir, --app o --merged')

const buf = readFileSync(app ?? merged)
if (app && buf[0] !== 0xe9) fail(`${app} no parece una app ESP32 (no empieza con 0xE9)`)

// Avisar si el binario no contiene la versión declarada (FW_VERSION queda como string en el .bin)
if (app && !buf.includes(Buffer.from(version))) {
  console.warn(`⚠ El binario no contiene el texto "${version}". ¿Subiste FW_VERSION antes de compilar?`)
}

const manifest = existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, 'utf8')) : { device: 'bicho', releases: [] }
if (manifest.releases.some((r) => r.version === version) && o.force !== 'true') fail(`La versión ${version} ya existe. Usa otra o agrega --force`)

let author = o.author
if (!author) {
  try {
    author = execSync('git config user.name', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
  } catch {
    author = process.env.USER
  }
}

const outDir = join(fwDir, version)
mkdirSync(outDir, { recursive: true })
const entry = { version, date: new Date().toISOString(), author, notes: o.notes }
if (o.chip) entry.chip = o.chip
if (app) {
  copyFileSync(app, join(outDir, 'app.bin'))
  entry.app = `${version}/app.bin`
}
if (merged) {
  copyFileSync(merged, join(outDir, 'merged.bin'))
  entry.merged = `${version}/merged.bin`
}

manifest.releases = [entry, ...manifest.releases.filter((r) => r.version !== version)]
writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n')

console.log(`✔ Publicada v${version}`)
if (app) console.log(`  app:    ${basename(app)} → public/firmware/${entry.app}`)
if (merged) console.log(`  merged: ${basename(merged)} → public/firmware/${entry.merged}`)
console.log('  La web la muestra como disponible en ~10 s.')
