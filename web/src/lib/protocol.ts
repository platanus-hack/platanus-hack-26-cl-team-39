// Protocolo bicho <-> web. Ver PROTOCOLO.md en la raíz del repo.
// Cada mensaje es una línea JSON (Serial a 115200 o WebSocket en ws://<host>:81).

export type DeviceInfo = {
  name?: string
  fw: string
  desc?: string
  chip?: string
  build?: string
  ip?: string
  red?: string | null
  mac?: string
  uptime?: number
  heap?: number
  [k: string]: unknown
}

export type SensorFrame = { ms?: number; d: Record<string, unknown> }

export type DeviceMsg =
  | ({ t: 'info' } & DeviceInfo)
  | ({ t: 's' } & SensorFrame)
  | { t: 'log'; lvl?: string; msg: string }
  | { t: string; [k: string]: unknown }

export function parseLine(line: string): DeviceMsg | null {
  const s = line.trim()
  if (!s.startsWith('{')) return null
  try {
    const obj = JSON.parse(s)
    if (obj && typeof obj === 'object' && typeof obj.t === 'string') return obj as DeviceMsg
  } catch {
    /* línea no JSON: va a la consola tal cual */
  }
  return null
}

export type Scalar = number | string | boolean | null

/** Aplana {imu:{ax:1}} -> {"imu.ax":1}. Los arrays se indexan: mic[0], mic[1]... */
export function flatten(obj: unknown, prefix = '', out: Record<string, Scalar> = {}): Record<string, Scalar> {
  if (obj === null || typeof obj !== 'object') {
    out[prefix || 'valor'] = obj as Scalar
    return out
  }
  if (Array.isArray(obj)) {
    obj.forEach((v, i) => flatten(v, `${prefix}[${i}]`, out))
    return out
  }
  for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
    flatten(v, prefix ? `${prefix}.${k}` : k, out)
  }
  return out
}

export const CMD = {
  info: '{"cmd":"info"}',
  rate: (hz: number) => JSON.stringify({ cmd: 'rate', hz }),
  reboot: '{"cmd":"reboot"}',
}
