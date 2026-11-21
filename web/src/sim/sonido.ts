/** Sintetiza los sonidos del bicho a partir de sus notas (el mismo formato que leerá la Pi). */
import type { Nota } from './lenguaje'

let ctx: AudioContext | null = null
let salida: GainNode | null = null
let ruido: AudioBuffer | null = null

/** Crea el audio. Hay que llamarlo desde un clic: el navegador no deja sonar antes. */
export function audio() {
  if (!ctx) {
    ctx = new AudioContext()
    salida = ctx.createGain()
    salida.gain.value = 0.7
    const comp = ctx.createDynamicsCompressor()
    salida.connect(comp).connect(ctx.destination)
    ruido = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate)
    const d = ruido.getChannelData(0)
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1
  }
  if (ctx.state === 'suspended') void ctx.resume()
  return ctx
}

export function tocar(notas: Nota[]) {
  if (!notas.length) return
  const c = audio()
  const t0 = c.currentTime + 0.03
  for (const n of notas) {
    const ini = t0 + n.t
    const fin = ini + n.d
    const vol = (n.vol ?? 0.4) * 0.8
    const ataque = Math.min(0.012, n.d / 4)
    const caida = Math.min(0.05, n.d / 3)

    const env = c.createGain()
    env.gain.setValueAtTime(0, ini)
    env.gain.linearRampToValueAtTime(vol, ini + ataque)
    env.gain.setValueAtTime(vol, Math.max(ini + ataque, fin - caida))
    env.gain.linearRampToValueAtTime(0, fin)
    env.connect(salida!)

    let fuente: AudioScheduledSourceNode
    if (n.onda === 'ruido') {
      const b = c.createBufferSource()
      b.buffer = ruido
      b.loop = true
      fuente = b
    } else {
      const o = c.createOscillator()
      o.type = n.onda
      o.frequency.setValueAtTime(n.f, ini)
      if (n.f2) o.frequency.exponentialRampToValueAtTime(n.f2, fin)
      fuente = o
    }

    let nodo: AudioNode = fuente
    if (n.filtro) {
      const f = c.createBiquadFilter()
      f.type = 'lowpass'
      f.frequency.setValueAtTime(n.filtro, ini)
      if (n.filtro2) f.frequency.exponentialRampToValueAtTime(n.filtro2, fin)
      nodo.connect(f)
      nodo = f
    }
    if (n.trem) {
      const am = c.createGain()
      am.gain.value = 0.5
      const lfo = c.createOscillator()
      lfo.frequency.value = n.trem
      const prof = c.createGain()
      prof.gain.value = 0.5
      lfo.connect(prof).connect(am.gain)
      lfo.start(ini)
      lfo.stop(fin + 0.05)
      nodo.connect(am)
      nodo = am
    }
    nodo.connect(env)
    fuente.start(ini)
    fuente.stop(fin + 0.05)
  }
}

/** Voz del navegador: en el robot será el parlante del ReSpeaker. */
export function decir(texto: string) {
  if (!('speechSynthesis' in window)) return
  speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(texto)
  const voces = speechSynthesis.getVoices()
  u.voice = voces.find((v) => v.lang === 'es-CL') ?? voces.find((v) => v.lang.startsWith('es')) ?? null
  u.lang = u.voice?.lang ?? 'es-CL'
  u.rate = 1.02
  u.pitch = 0.9
  speechSynthesis.speak(u)
}

export function callar() {
  if ('speechSynthesis' in window) speechSynthesis.cancel()
}
