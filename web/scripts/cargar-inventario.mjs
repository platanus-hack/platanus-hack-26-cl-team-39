#!/usr/bin/env node
// Carga en Neon un inventario exportado del Claude Sheet.
//
//   node --env-file=.env scripts/cargar-inventario.mjs <archivo.json> [--forzar]
//
// El archivo tiene la forma {"pestañas":[{"nombre":"…","filas":[{"Ítem":"…","Cant.":"…",…}]}]}.
// Si la tabla ya tiene filas no hace nada, salvo con --forzar (que agrega encima, no borra).
import { readFileSync } from 'node:fs'
import { neon } from '@neondatabase/serverless'

const [file, flag] = process.argv.slice(2)
if (!file) {
  console.error('Uso: node --env-file=.env scripts/cargar-inventario.mjs <archivo.json> [--forzar]')
  process.exit(1)
}
if (!process.env.DATABASE_URL) {
  console.error('Falta DATABASE_URL (ponla en web/.env).')
  process.exit(1)
}

const sql = neon(process.env.DATABASE_URL)
const [{ n }] = await sql`select count(*)::int as n from items`
if (n > 0 && flag !== '--forzar') {
  console.log(`La tabla ya tiene ${n} ítems; no cargo nada. Usa --forzar para agregar igual.`)
  process.exit(0)
}

const data = JSON.parse(readFileSync(file, 'utf8'))
const txt = (v) => {
  const s = String(v ?? '').trim()
  return s === '' ? null : s
}
const num = (v) => {
  const s = String(v ?? '').trim()
  return /^\d+$/.test(s) ? Number(s) : null
}

let total = 0
for (const tab of data.pestañas) {
  const rows = tab.filas.filter((f) => !f._tipo && txt(f['Ítem']))
  for (const f of rows) {
    const item = {
      nombre: txt(f['Ítem']),
      cantidad: num(f['Cant.']),
      categoria: txt(f['Categoría']) ?? 'Otros',
      origen: txt(f['Origen']),
      estado: txt(f['Estado']) ?? 'Por verificar',
      uso_lampara: txt(f['Uso en la lámpara']),
      notas: txt(f['Notas']),
      fuente: `Sheet · ${tab.nombre}`,
    }
    const [row] = await sql`
      insert into items (nombre, cantidad, categoria, origen, estado, uso_lampara, notas, fuente, actualizado_por)
      values (${item.nombre}, ${item.cantidad}, ${item.categoria}, ${item.origen}, ${item.estado}, ${item.uso_lampara}, ${item.notas}, ${item.fuente}, 'carga inicial')
      returning *`
    await sql`insert into cambios (item_id, accion, despues, autor) values (${row.id}, 'crear', ${JSON.stringify(row)}::jsonb, 'carga inicial')`
    total++
  }
  console.log(`${tab.nombre}: ${rows.length} ítems`)
}
console.log(`Listo: ${total} ítems cargados.`)
