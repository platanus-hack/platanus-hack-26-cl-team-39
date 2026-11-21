#!/usr/bin/env node
// Publica una versión del bicho para que bicho·dev la muestre como disponible.
//
// Uso (desde web/):
//   npm run release -- --notes "Qué cambia en esta versión" [--author Carlos] [--force]
//
// Toma la carpeta ../bicho, lee la versión de bicho/version.json (súbela antes de publicar),
// la empaqueta como public/firmware/<versión>/bicho-<versión>.tar.gz y la agrega a manifest.json.

import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const src = resolve(root, '..', 'bicho')
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

const o = args()
if (!existsSync(join(src, 'bichod.py'))) fail(`No encuentro ${src}/bichod.py`)
const meta = JSON.parse(readFileSync(join(src, 'version.json'), 'utf8'))
const version = String(meta.version || '')
if (!/^\d+\.\d+\.\d+([-.][\w.]+)?$/.test(version)) fail(`Versión inválida en bicho/version.json: "${version}"`)
if (o.version && o.version.replace(/^v/, '') !== version) fail(`--version ${o.version} no coincide con bicho/version.json (${version}). Sube la versión ahí.`)
const notes = o.notes || meta.desc
if (!notes) fail('Falta --notes "qué hace esta versión"')

const manifest = existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, 'utf8')) : { device: 'bicho', releases: [] }
if (manifest.releases.some((r) => r.version === version) && o.force !== 'true') {
  fail(`La versión ${version} ya está publicada. Sube "version" en bicho/version.json (o usa --force para reemplazarla).`)
}

let author = o.author
if (!author) {
  try {
    author = execFileSync('git', ['config', 'user.name'], { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
  } catch {
    author = process.env.USER
  }
}

// Copia limpia en un directorio temporal, con la fecha de publicación en version.json
const stage = mkdtempSync(join(tmpdir(), 'bicho-release-'))
cpSync(src, stage, {
  recursive: true,
  filter: (p) => !/(__pycache__|\.pyc$|\.venv|\.DS_Store|\/\.git(\/|$))/.test(p),
})
const built = new Date().toISOString().slice(0, 16).replace('T', ' ')
writeFileSync(join(stage, 'version.json'), JSON.stringify({ ...meta, built }, null, 2) + '\n')

const outDir = join(fwDir, version)
mkdirSync(outDir, { recursive: true })
const file = `bicho-${version}.tar.gz`
const out = join(outDir, file)
// COPYFILE_DISABLE evita que el tar de macOS meta archivos ._ con atributos extendidos
execFileSync('tar', ['-czf', out, '-C', stage, '.'], { env: { ...process.env, COPYFILE_DISABLE: '1' } })
rmSync(stage, { recursive: true, force: true })

const entry = { version, date: new Date().toISOString(), author, notes, package: `${version}/${file}`, size: statSync(out).size }
manifest.releases = [entry, ...manifest.releases.filter((r) => r.version !== version)]
writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n')

console.log(`✔ Publicada v${version} (${(entry.size / 1024).toFixed(1)} KB)`)
console.log(`  public/firmware/${entry.package}`)
console.log(`  "${notes}"`)
console.log('  bicho·dev la muestra como disponible en ~10 s.')
console.log(`  Recuerda hacer commit de public/firmware/ para que el resto del equipo la vea.`)
