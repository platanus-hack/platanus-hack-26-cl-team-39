/**
 * Idioma del bicho. Los datos viven en bicho/lenguaje.json, para que el simulador y la Pi lean lo mismo.
 * Aquí solo están los tipos y unos ayudantes.
 */
import datos from '../../../bicho/lenguaje.json'

export type Onda = 'sine' | 'triangle' | 'square' | 'sawtooth' | 'ruido'
export type Nota = { onda: Onda; f: number; f2?: number; t: number; d: number; vol?: number; trem?: number; filtro?: number; filtro2?: number }

export type Patron = 'fijo' | 'respira' | 'gira' | 'parpadea' | 'destello' | 'llena' | 'corre' | 'arcoiris' | 'faro' | 'lado' | 'apagando' | 'sectores'
export type Luz = { patron: Patron; color: string; periodo?: number; brillo?: number }

export type Mirar = 'dueno' | 'objetivo' | 'frente' | 'abajo' | 'alrededor'
export type Gesto = 'asentir' | 'negar' | 'ladear_izq' | 'ladear_der' | 'sacudir' | 'escanear' | 'atras'
export type Cabeza = { mirar: Mirar; gesto?: Gesto }

export type Cuerpo =
  | 'quieto' | 'mirar_dueno' | 'acercarse' | 'retroceder' | 'giro' | 'baile' | 'vaiven' | 'curiosear' | 'orientar'
  | 'plantarse' | 'patrullar' | 'base' | 'lento' | 'intentar' | 'prueba' | 'vuelta' | 'levantado'

export type Estado = {
  id: string
  nombre: string
  grupo: string
  sonido: Nota[]
  repetir?: number
  voz?: string
  luz: Luz
  cabeza: Cabeza
  cuerpo: Cuerpo
  matriz: string
  app: string | null
  foto?: boolean
  foco?: boolean
  agua?: boolean
  solo_animales?: boolean
  si_persona?: string
  visita_se_va?: boolean
}

export type Pieza = { id: string; nombre: string; cantidad: number | null; uso: string }
export type Escena = { id: string; nombre: string; visita: Visita; pasos: [string, number][] }
export type Visita = 'ninguna' | 'perro' | 'persona'

type Lenguaje = { piezas: Pieza[]; reposo: Estado; estados: Estado[]; escenas: Escena[]; iconos: Record<string, string[]> }

export const LENGUAJE = datos as unknown as Lenguaje
export const ESTADOS = LENGUAJE.estados
export const REPOSO = LENGUAJE.reposo
export const PIEZAS = LENGUAJE.piezas
export const ESCENAS = LENGUAJE.escenas
export const ICONOS = LENGUAJE.iconos

const porId = new Map([REPOSO, ...ESTADOS].map((e) => [e.id, e]))
export const estado = (id: string) => porId.get(id) ?? REPOSO

/** Grupos en el orden en que aparecen. */
export const GRUPOS = [...new Set(ESTADOS.map((e) => e.grupo))]

export function textoApp(e: Estado, v: Visita): string | null {
  if (!e.app) return null
  const min = v === 'perro' ? 'el perro' : v === 'persona' ? 'una persona' : 'algo'
  const may = v === 'perro' ? 'El perro' : v === 'persona' ? 'La persona' : 'Eso'
  return e.app.replace('{visita}', min).replace('{Visita}', may)
}

/** Duración de un sonido, en segundos. */
export const duracion = (notas: Nota[]) => notas.reduce((m, n) => Math.max(m, n.t + n.d), 0)

const MIRAR: Record<Mirar, string> = { dueno: 'te mira', objetivo: 'mira lo que vio', frente: 'mira al frente', abajo: 'mira abajo', alrededor: 'mira alrededor' }
const GESTO: Record<Gesto, string> = {
  asentir: 'asiente', negar: 'niega', ladear_izq: 'se ladea', ladear_der: 'se ladea al otro lado', sacudir: 'se sacude', escanear: 'barre de lado a lado', atras: 'se echa atrás',
}
const CUERPO: Record<Cuerpo, string> = {
  quieto: 'quieto', mirar_dueno: 'se gira hacia ti', acercarse: 'se acerca a ti', retroceder: 'retrocede', giro: 'da un giro', baile: 'baila', vaiven: 'va y viene',
  curiosear: 'se acerca despacio', orientar: 'se gira hacia lo que vio', plantarse: 'avanza y se planta', patrullar: 'patrulla', base: 'vuelve a su base',
  lento: 'avanza lento', intentar: 'intenta y retrocede', prueba: 'prueba las ruedas', vuelta: 'da una vuelta lenta', levantado: 'frena las ruedas',
}
const PATRON: Record<Patron, string> = {
  fijo: 'fija', respira: 'que respira', gira: 'que gira', parpadea: 'que parpadea', destello: 'destello', llena: 'que se llena', corre: 'colores que corren',
  arcoiris: 'arcoíris', faro: 'faro que gira', lado: 'hacia donde mira', apagando: 'que se apaga', sectores: 'por partes',
}

export function describir(e: Estado) {
  return {
    luz: PATRON[e.luz.patron],
    cabeza: [MIRAR[e.cabeza.mirar], e.cabeza.gesto && GESTO[e.cabeza.gesto]].filter(Boolean).join(' y '),
    cuerpo: CUERPO[e.cuerpo],
  }
}
