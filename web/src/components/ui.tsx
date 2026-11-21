import type { SVGProps } from 'react'
import { HISTORY } from '../lib/sensors'

/* ------------------------------------------------------------------ */
/* Íconos (trazo, estilo SF Symbols)                                    */
/* ------------------------------------------------------------------ */

type P = SVGProps<SVGSVGElement>
const base = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeLinecap: 'round', strokeLinejoin: 'round' } as const

export const Icon = {
  Chip: (p: P) => (
    <svg {...base} strokeWidth={1.7} {...p}>
      <rect x="6.5" y="6.5" width="11" height="11" rx="2.2" />
      <path d="M10 3v3.5M14 3v3.5M10 17.5V21M14 17.5V21M3 10h3.5M3 14h3.5M17.5 10H21M17.5 14H21" />
    </svg>
  ),
  Pulse: (p: P) => (
    <svg {...base} strokeWidth={1.7} {...p}>
      <path d="M3 12h3l2.2-6 3.8 12 3-9 2 3H21" />
    </svg>
  ),
  Terminal: (p: P) => (
    <svg {...base} strokeWidth={1.7} {...p}>
      <rect x="3" y="4.5" width="18" height="15" rx="3.2" />
      <path d="m7.5 9.5 3 2.5-3 2.5M12.5 15h4" />
    </svg>
  ),
  History: (p: P) => (
    <svg {...base} strokeWidth={1.7} {...p}>
      <path d="M3.6 12a8.4 8.4 0 1 0 2.5-6" />
      <path d="M3.2 3.8v4.3h4.3" />
      <path d="M12 7.8v4.4l3 1.8" />
    </svg>
  ),
  Power: (p: P) => (
    <svg {...base} strokeWidth={2} {...p}>
      <path d="M12 3.5v7.5" />
      <path d="M6.6 7a7.6 7.6 0 1 0 10.8 0" />
    </svg>
  ),
  Info: (p: P) => (
    <svg {...base} strokeWidth={2} {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5.5" />
      <circle cx="12" cy="7.7" r=".6" fill="currentColor" />
    </svg>
  ),
  Download: (p: P) => (
    <svg {...base} strokeWidth={2.2} {...p}>
      <path d="M12 4v11M7 10.5l5 5 5-5M5.5 20h13" />
    </svg>
  ),
  Arrow: (p: P) => (
    <svg {...base} strokeWidth={2} {...p}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  ),
  Send: (p: P) => (
    <svg {...base} strokeWidth={2} {...p}>
      <path d="M4 12h12M12 6l6 6-6 6" />
    </svg>
  ),
  Check: (p: P) => (
    <svg {...base} strokeWidth={2.6} {...p}>
      <path d="m5.5 12.5 4.2 4.2 8.8-9.2" />
    </svg>
  ),
  Alert: (p: P) => (
    <svg {...base} strokeWidth={2.2} {...p}>
      <path d="M12 8v5" />
      <circle cx="12" cy="16.6" r=".7" fill="currentColor" />
    </svg>
  ),
  Warning: (p: P) => (
    <svg {...base} strokeWidth={1.9} {...p}>
      <path d="M10.3 4.2 2.9 17.3A2 2 0 0 0 4.6 20h14.8a2 2 0 0 0 1.7-2.7L13.7 4.2a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9.5v4" />
      <circle cx="12" cy="16.6" r=".6" fill="currentColor" />
    </svg>
  ),
  Folder: (p: P) => (
    <svg {...base} strokeWidth={1.9} {...p}>
      <path d="M3.5 7.5a2 2 0 0 1 2-2h3.6l2 2.2h7.4a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2Z" />
    </svg>
  ),
  Refresh: (p: P) => (
    <svg {...base} strokeWidth={2} {...p}>
      <path d="M20 11a8 8 0 0 0-14.3-4.9L4 8" />
      <path d="M4 3.5V8h4.5" />
      <path d="M4 13a8 8 0 0 0 14.3 4.9L20 16" />
      <path d="M20 20.5V16h-4.5" />
    </svg>
  ),
  Pause: (p: P) => (
    <svg {...base} strokeWidth={2.2} {...p}>
      <path d="M9 6v12M15 6v12" />
    </svg>
  ),
  Play: (p: P) => (
    <svg {...base} strokeWidth={2} {...p}>
      <path d="M8 5.5v13l10-6.5Z" fill="currentColor" />
    </svg>
  ),
  Box: (p: P) => (
    <svg {...base} strokeWidth={1.7} {...p}>
      <path d="M3.5 7.5 12 3l8.5 4.5v9L12 21l-8.5-4.5z" />
      <path d="M3.5 7.5 12 12l8.5-4.5M12 12v9" />
    </svg>
  ),
  Sparkle: (p: P) => (
    <svg {...base} strokeWidth={1.7} {...p}>
      <path d="M12 3.5c.5 3.9 2.6 6 6.5 6.5-3.9.5-6 2.6-6.5 6.5-.5-3.9-2.6-6-6.5-6.5 3.9-.5 6-2.6 6.5-6.5Z" fill="currentColor" fillOpacity={0.18} />
      <path d="M18.5 15.5c.2 1.5 1 2.3 2.5 2.5-1.5.2-2.3 1-2.5 2.5-.2-1.5-1-2.3-2.5-2.5 1.5-.2 2.3-1 2.5-2.5Z" />
    </svg>
  ),
  Search: (p: P) => (
    <svg {...base} strokeWidth={1.9} {...p}>
      <circle cx="10.8" cy="10.8" r="6.3" />
      <path d="m15.5 15.5 4.5 4.5" />
    </svg>
  ),
  Plus: (p: P) => (
    <svg {...base} strokeWidth={2} {...p}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  ),
  Close: (p: P) => (
    <svg {...base} strokeWidth={2} {...p}>
      <path d="m6.5 6.5 11 11M17.5 6.5l-11 11" />
    </svg>
  ),
  Copy: (p: P) => (
    <svg {...base} strokeWidth={1.8} {...p}>
      <rect x="8.5" y="8.5" width="11" height="11" rx="2.5" />
      <path d="M15.5 5.8A2.5 2.5 0 0 0 13.2 4.5H7A2.5 2.5 0 0 0 4.5 7v6.2a2.5 2.5 0 0 0 1.3 2.2" />
    </svg>
  ),
  Key: (p: P) => (
    <svg {...base} strokeWidth={1.8} {...p}>
      <circle cx="8" cy="15" r="4" />
      <path d="m10.8 12.2 7.7-7.7M15.5 7.5l2.5 2.5M17.8 5.2l1.8 1.8" />
    </svg>
  ),
  /** El ojo de Bicho con su curita: el ícono de la app, sobre el cuadrado amarillo (marca/MARCA.md). */
  Ojo: (p: P) => (
    <svg viewBox="0 0 240 240" fill="none" {...p}>
      <g transform="translate(-6 6)">
        <circle cx="120" cy="120" r="86" stroke="#1D1D1F" strokeWidth={20} />
        <circle cx="120" cy="120" r="34" fill="#1D1D1F" />
        <circle cx="120" cy="120" r="15" fill="#8FDCC4" />
        <circle cx="126.5" cy="113.5" r="5" fill="#FFFFFF" />
        <g transform="translate(180.81 59.19) rotate(45)">
          <rect x="-60" y="-21" width="120" height="42" rx="21" fill="#F4996F" stroke="#FFFFFF" strokeWidth={7} paintOrder="stroke" />
          <rect x="-20" y="-14" width="40" height="28" rx="6" fill="#FFD4BF" />
        </g>
      </g>
    </svg>
  ),
  /** Brazo con lámpara: el ícono de la sección Cerebro. */
  Bicho: (p: P) => (
    <svg viewBox="0 0 32 32" fill="none" stroke="#3b2a00" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" {...p}>
      <path d="M8.5 26h12" />
      <path d="M13 25.5 10.6 17l7.4-5.2" />
      <circle cx="10.6" cy="17" r="1.5" fill="#3b2a00" stroke="none" />
      <path d="M16.2 9.4 23.8 7l1.6 6.8z" fill="#3b2a00" />
      <path d="M22.6 16.4l1.6 2.4M19.6 17.6l.4 2.8" strokeWidth={1.6} opacity={0.7} />
    </svg>
  ),
}

/** Degradé compartido por todas las sparklines (se monta una vez). */
export function SparkDefs() {
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden focusable="false">
      <defs>
        <linearGradient id="g-spark" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#007aff" stopOpacity=".22" />
          <stop offset="1" stopColor="#007aff" stopOpacity="0" />
        </linearGradient>
      </defs>
    </svg>
  )
}

export function Sparkline({ data, stepped = false }: { data: number[]; stepped?: boolean }) {
  const W = 120
  const H = 36
  if (data.length < 2) return <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden />
  const lo = Math.min(...data)
  const hi = Math.max(...data)
  const span = hi - lo || 1
  const step = W / (HISTORY - 1)
  const x0 = W - (data.length - 1) * step
  let d = ''
  let py = '0'
  data.forEach((v, i) => {
    const x = (x0 + i * step).toFixed(2)
    const y = (H - 2 - ((v - lo) / span) * (H - 4)).toFixed(2)
    if (i === 0) d += `M${x},${y}`
    else {
      if (stepped) d += `L${x},${py}`
      d += `L${x},${y}`
    }
    py = y
  })
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden>
      <path className="spark-area" d={`${d}L${W},${H}L${x0.toFixed(2)},${H}Z`} />
      <path className="spark-line" d={d} fill="none" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

/* ------------------------------------------------------------------ */
/* Formato                                                              */
/* ------------------------------------------------------------------ */

export function fmtAgo(iso?: string) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const s = (Date.now() - d.getTime()) / 1000
  if (s < 60) return 'recién'
  if (s < 3600) return `hace ${Math.round(s / 60)} min`
  if (s < 86400) return `hace ${Math.round(s / 3600)} h`
  return d.toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' })
}

export function fmtBytes(n: number) {
  if (!Number.isFinite(n)) return '—'
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(1)} GB`
  if (n >= 1024 ** 2) return `${Math.round(n / 1024 ** 2)} MB`
  if (n >= 1024) return `${Math.round(n / 1024)} KB`
  return `${n} B`
}

export function fmtUptime(sec?: number) {
  if (sec == null || !Number.isFinite(sec)) return '—'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  return h ? `${h} h ${m} min` : m ? `${m} min ${s} s` : `${s} s`
}
