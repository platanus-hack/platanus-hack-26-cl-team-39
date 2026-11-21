// Visor 3D del brazo: carga /bim/brazo.glb (metros, +Y arriba, el brazo mira a +X) y mueve sus articulaciones.
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { CSS2DObject, CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js'

export type Vista = '3d' | 'lado' | 'frente' | 'arriba'

export type Articulacion = {
  nodo: string
  servo: string
  canal: number
  eje_gltf: string
  min: number
  max: number
  inicio: number
  angulo_nodo: string
  espejo?: string
  que_hace?: string
}

type Avisos = {
  hover: (id: string | null, x: number, y: number) => void
  clic: (id: string | null) => void
}

const G = 9.81
const CENTRO = new THREE.Vector3(0.05, 0.1, 0)
const VISTAS: Record<Vista, THREE.Vector3> = {
  '3d': new THREE.Vector3(0.5, 0.32, 0.55),
  lado: new THREE.Vector3(0.03, 0.12, 0.72),
  frente: new THREE.Vector3(0.74, 0.12, 0),
  arriba: new THREE.Vector3(0.03, 0.78, 0.0005),
}

/**
 * Convierte la fórmula de `angulo_nodo` del registro ("deg - 90", "-deg", "180 - deg") en a·deg + b.
 * Acepta la forma general  [n ±] [-]deg [± n].  Si no la entiende, devuelve null (y el nodo no se mueve).
 */
export function formula(txt: string): ((deg: number) => number) | null {
  const s = txt.replace(/\s+/g, '').replace(/°/g, '')
  const m = s.match(/^(?:(-?\d+(?:\.\d+)?)([+-]))?(-)?deg(?:([+-])(\d+(?:\.\d+)?))?$/)
  if (!m) return null
  const pre = m[1] ? Number(m[1]) : 0
  let a = m[3] ? -1 : 1
  if (m[2] === '-') a = -a
  const post = m[4] ? (m[4] === '-' ? -1 : 1) * Number(m[5]) : 0
  return (deg) => pre + a * deg + post
}

/** "Y", "-Z", "+X" → vector unitario del eje local. */
function eje(txt: string) {
  const t = txt.trim().toUpperCase()
  const sign = t.startsWith('-') ? -1 : 1
  const c = t.replace(/[+-]/g, '')
  return new THREE.Vector3(c === 'X' ? sign : 0, c === 'Y' ? sign : 0, c === 'Z' ? sign : 0)
}

type Junta = { obj: THREE.Object3D; base: THREE.Quaternion; eje: THREE.Vector3; f: (d: number) => number; espejo?: THREE.Object3D; baseEspejo?: THREE.Quaternion }
type Masa = { obj: THREE.Object3D; kg: number }

export class VisorBrazo {
  private renderer: THREE.WebGLRenderer
  private etiquetas: CSS2DRenderer
  private escena = new THREE.Scene()
  private camara = new THREE.PerspectiveCamera(32, 1, 0.005, 20)
  private controles: OrbitControls
  private raiz: THREE.Object3D | null = null
  private juntas = new Map<string, Junta>()
  private piezas = new Map<string, THREE.Object3D>()
  private mallas = new Map<THREE.Mesh, string>()
  private masas: Masa[] = []
  private puntaLocal = new THREE.Vector3(0.09, 0, 0)
  private rotulos: { obj: CSS2DObject; de: THREE.Object3D }[] = []
  private ro: ResizeObserver
  private raf = 0
  private vuelo: { desde: THREE.Vector3; hasta: THREE.Vector3; t0: number } | null = null
  private ray = new THREE.Raycaster()
  private hoverId: string | null = null
  private selId: string | null = null
  private avisos: Avisos
  private abajo: { x: number; y: number } | null = null
  private muerto = false

  constructor(
    private lienzo: HTMLCanvasElement,
    capa: HTMLElement,
    avisos: Avisos,
  ) {
    this.avisos = avisos
    this.renderer = new THREE.WebGLRenderer({ canvas: lienzo, antialias: true, alpha: true, preserveDrawingBuffer: true })
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
    this.renderer.outputColorSpace = THREE.SRGBColorSpace
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    this.renderer.toneMappingExposure = 1.05
    this.renderer.shadowMap.enabled = true
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap

    this.etiquetas = new CSS2DRenderer({ element: capa })

    this.camara.position.copy(VISTAS['3d'])
    this.controles = new OrbitControls(this.camara, lienzo)
    this.controles.target.copy(CENTRO)
    this.controles.enableDamping = true
    this.controles.dampingFactor = 0.12
    this.controles.minDistance = 0.15
    this.controles.maxDistance = 2.2
    this.controles.update()

    // luz de estudio: cielo cálido, piso frío, un sol con sombra suave
    this.escena.add(new THREE.HemisphereLight(0xfff6ec, 0xc9d4e6, 1.5))
    const sol = new THREE.DirectionalLight(0xffffff, 2.2)
    sol.position.set(0.5, 0.9, 0.35)
    sol.castShadow = true
    sol.shadow.mapSize.set(1024, 1024)
    const sc = sol.shadow.camera as THREE.OrthographicCamera
    sc.left = sc.bottom = -0.35
    sc.right = sc.top = 0.35
    sc.near = 0.1
    sc.far = 2.5
    sol.shadow.bias = -0.0004
    this.escena.add(sol)
    const relleno = new THREE.DirectionalLight(0xdbe7ff, 0.6)
    relleno.position.set(-0.6, 0.3, -0.4)
    this.escena.add(relleno)

    // cubierta del bicho (320 × 200 × 4 mm), semitransparente, para dar escala
    const cubierta = new THREE.Mesh(
      new THREE.BoxGeometry(0.32, 0.004, 0.2),
      new THREE.MeshStandardMaterial({ color: 0xeae4dc, roughness: 0.7, transparent: true, opacity: 0.55, depthWrite: false }),
    )
    cubierta.position.set(-0.07, -0.002, 0)
    cubierta.receiveShadow = true
    this.escena.add(cubierta)
    const borde = new THREE.LineSegments(new THREE.EdgesGeometry(cubierta.geometry), new THREE.LineBasicMaterial({ color: 0xb9ad9f, transparent: true, opacity: 0.8 }))
    borde.position.copy(cubierta.position)
    this.escena.add(borde)
    const grilla = new THREE.GridHelper(0.6, 30, 0xd6cfc6, 0xe6e0d8)
    grilla.position.y = -0.0045
    ;(grilla.material as THREE.Material).transparent = true
    ;(grilla.material as THREE.Material).opacity = 0.55
    this.escena.add(grilla)

    this.ro = new ResizeObserver(() => this.medir())
    this.ro.observe(lienzo.parentElement ?? lienzo)
    this.medir()

    lienzo.addEventListener('pointermove', this.onMove)
    lienzo.addEventListener('pointerleave', this.onLeave)
    lienzo.addEventListener('pointerdown', this.onDown)
    lienzo.addEventListener('pointerup', this.onUp)

    const loop = (t: number) => {
      this.raf = requestAnimationFrame(loop)
      this.tick(t)
    }
    this.raf = requestAnimationFrame(loop)
  }

  /** Carga el glb. Resuelve con los ids de las piezas que trae el modelo. */
  async cargar(url: string, articulaciones: Articulacion[]): Promise<string[]> {
    const gltf = await new GLTFLoader().loadAsync(url)
    if (this.muerto) return []
    const raiz = gltf.scene
    this.raiz = raiz
    this.escena.add(raiz)

    raiz.traverse((o) => {
      const m = o as THREE.Mesh
      if (m.isMesh) {
        m.castShadow = true
        m.receiveShadow = true
        // material propio por malla, para poder resaltar una sola pieza
        m.material = Array.isArray(m.material) ? m.material.map((x) => x.clone()) : m.material.clone()
      }
    })

    // piezas y componentes: nodos con nombre de pieza (P07…) o de servo (S1_giro…), o con extras.pieza
    raiz.traverse((o) => {
      const id = /^(P\d+|S\d+_\w+)$/.test(o.name) ? o.name : typeof o.userData.pieza === 'string' ? o.userData.pieza : null
      if (id && !this.piezas.has(id)) this.piezas.set(id, o)
      if (typeof o.userData.masa_g === 'number') this.masas.push({ obj: o, kg: o.userData.masa_g / 1000 })
    })
    for (const [id, o] of this.piezas) o.traverse((c) => (c as THREE.Mesh).isMesh && this.mallas.set(c as THREE.Mesh, id))

    for (const a of articulaciones) {
      const obj = raiz.getObjectByName(a.nodo)
      const f = formula(a.angulo_nodo)
      if (!obj || !f) continue
      const esp = a.espejo ? raiz.getObjectByName(a.espejo) : undefined
      this.juntas.set(a.nodo, { obj, base: obj.quaternion.clone(), eje: eje(a.eje_gltf), f, espejo: esp, baseEspejo: esp?.quaternion.clone() })
    }

    // punta del eslabón 2: el extremo más lejano de P10 en el marco del codo
    const codo = raiz.getObjectByName('J_codo')
    const p10 = raiz.getObjectByName('P10')
    if (codo && p10) {
      raiz.updateMatrixWorld(true)
      const inv = codo.matrixWorld.clone().invert()
      const caja = new THREE.Box3()
      p10.traverse((c) => {
        const m = c as THREE.Mesh
        if (!m.isMesh) return
        m.geometry.computeBoundingBox()
        caja.union(m.geometry.boundingBox!.clone().applyMatrix4(new THREE.Matrix4().multiplyMatrices(inv, m.matrixWorld)))
      })
      if (!caja.isEmpty()) this.puntaLocal.set(caja.max.x, (caja.min.y + caja.max.y) / 2, (caja.min.z + caja.max.z) / 2)
    }

    // rótulos con el número de cada servo
    for (const [id, o] of this.piezas) {
      const m = id.match(/^S(\d+)_(\w+)$/)
      if (!m) continue
      const el = document.createElement('div')
      el.className = 'bz-rotulo'
      el.innerHTML = `<b>${m[1]}</b><span>${m[2]}</span>`
      const obj = new CSS2DObject(el)
      this.escena.add(obj)
      this.rotulos.push({ obj, de: o })
    }
    return [...this.piezas.keys()]
  }

  /** Mueve una articulación a `deg` grados de servo. */
  setAngulo(nodo: string, deg: number) {
    const j = this.juntas.get(nodo)
    if (!j) return
    const rad = THREE.MathUtils.degToRad(j.f(deg))
    j.obj.quaternion.copy(j.base).multiply(new THREE.Quaternion().setFromAxisAngle(j.eje, rad))
    if (j.espejo && j.baseEspejo) j.espejo.quaternion.copy(j.baseEspejo).multiply(new THREE.Quaternion().setFromAxisAngle(j.eje, -rad))
  }

  tieneNodo(nodo: string) {
    return this.juntas.has(nodo)
  }

  resaltar(hover: string | null, sel: string | null) {
    this.hoverId = hover
    this.selId = sel
    for (const [malla, id] of this.mallas) {
      const mats = Array.isArray(malla.material) ? malla.material : [malla.material]
      for (const mat of mats) {
        const s = mat as THREE.MeshStandardMaterial
        if (!s.emissive) continue
        if (id === sel) s.emissive.setRGB(0.0, 0.25, 0.75)
        else if (id === hover) s.emissive.setRGB(0.55, 0.38, 0.0)
        else s.emissive.setRGB(0, 0, 0)
      }
    }
  }

  vista(v: Vista) {
    this.vuelo = { desde: this.camara.position.clone(), hasta: VISTAS[v].clone(), t0: performance.now() }
    this.controles.target.copy(CENTRO)
  }

  /**
   * Torque estático (N·m) que ven el hombro y el codo con la pose actual.
   * Suma m·g·brazo horizontal de cada masa que cuelga de la articulación, más la carga en la punta.
   */
  torques(cargaG: number): { hombro: number | null; codo: number | null } {
    if (!this.raiz) return { hombro: null, codo: null }
    this.raiz.updateMatrixWorld(true)
    const calc = (nodo: string) => {
      const j = this.juntas.get(nodo)
      const obj = j?.obj ?? this.raiz!.getObjectByName(nodo)
      if (!obj) return null
      const p = obj.getWorldPosition(new THREE.Vector3())
      const ax = (j?.eje ?? new THREE.Vector3(0, 0, -1)).clone().transformDirection(obj.matrixWorld)
      const fz = new THREE.Vector3(0, -G, 0)
      let tau = 0
      const sumar = (punto: THREE.Vector3, kg: number) => {
        tau += punto.clone().sub(p).cross(fz.clone().multiplyScalar(kg)).dot(ax)
      }
      for (const m of this.masas) {
        if (!esDescendiente(m.obj, obj)) continue
        sumar(new THREE.Box3().setFromObject(m.obj).getCenter(new THREE.Vector3()), m.kg)
      }
      if (cargaG > 0) sumar(this.punta(), cargaG / 1000)
      return Math.abs(tau)
    }
    return { hombro: calc('J_hombro'), codo: calc('J_codo') }
  }

  /** Dónde se cuelga la carga: la pinza si ya está en el modelo, si no la punta del eslabón 2. */
  private punta() {
    const pz = this.raiz?.getObjectByName('J_pinza_a')
    if (pz) return pz.getWorldPosition(new THREE.Vector3())
    const codo = this.raiz?.getObjectByName('J_codo')
    return codo ? codo.localToWorld(this.puntaLocal.clone()) : new THREE.Vector3()
  }

  private medir() {
    const el = this.lienzo.parentElement ?? this.lienzo
    const w = Math.max(1, el.clientWidth)
    const h = Math.max(1, el.clientHeight)
    this.renderer.setSize(w, h, false)
    this.lienzo.style.width = `${w}px`
    this.lienzo.style.height = `${h}px`
    this.etiquetas.setSize(w, h)
    this.camara.aspect = w / h
    this.camara.updateProjectionMatrix()
  }

  private tick(t: number) {
    if (this.vuelo) {
      const k = Math.min(1, (t - this.vuelo.t0) / 450)
      const e = 1 - Math.pow(1 - k, 3)
      this.camara.position.lerpVectors(this.vuelo.desde, this.vuelo.hasta, e)
      if (k >= 1) this.vuelo = null
    }
    this.controles.update()
    for (const r of this.rotulos) {
      const c = new THREE.Box3().setFromObject(r.de).getCenter(new THREE.Vector3())
      r.obj.position.copy(c).add(new THREE.Vector3(0, 0.028, 0))
    }
    this.renderer.render(this.escena, this.camara)
    this.etiquetas.render(this.escena, this.camara)
  }

  private pick(e: PointerEvent): string | null {
    const r = this.lienzo.getBoundingClientRect()
    const v = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
    this.ray.setFromCamera(v, this.camara)
    const hit = this.ray.intersectObjects([...this.mallas.keys()], false)[0]
    return hit ? (this.mallas.get(hit.object as THREE.Mesh) ?? null) : null
  }

  private onMove = (e: PointerEvent) => {
    if (e.buttons) return
    const id = this.pick(e)
    const r = this.lienzo.getBoundingClientRect()
    this.avisos.hover(id, e.clientX - r.left, e.clientY - r.top)
    this.lienzo.style.cursor = id ? 'pointer' : 'grab'
  }
  private onLeave = () => this.avisos.hover(null, 0, 0)
  private onDown = (e: PointerEvent) => {
    this.abajo = { x: e.clientX, y: e.clientY }
  }
  private onUp = (e: PointerEvent) => {
    const a = this.abajo
    this.abajo = null
    if (!a || Math.hypot(e.clientX - a.x, e.clientY - a.y) > 4) return
    this.avisos.clic(this.pick(e))
  }

  /** Para la verificación: qué está resaltado ahora. */
  estado() {
    return { hover: this.hoverId, sel: this.selId, piezas: [...this.piezas.keys()], juntas: [...this.juntas.keys()] }
  }

  dispose() {
    this.muerto = true
    cancelAnimationFrame(this.raf)
    this.ro.disconnect()
    this.lienzo.removeEventListener('pointermove', this.onMove)
    this.lienzo.removeEventListener('pointerleave', this.onLeave)
    this.lienzo.removeEventListener('pointerdown', this.onDown)
    this.lienzo.removeEventListener('pointerup', this.onUp)
    for (const r of this.rotulos) r.obj.element.remove()
    this.controles.dispose()
    this.escena.traverse((o) => {
      const m = o as THREE.Mesh
      if (!m.isMesh && !(o as THREE.LineSegments).isLineSegments) return
      m.geometry?.dispose()
      const mats = Array.isArray(m.material) ? m.material : [m.material]
      mats.forEach((x) => x?.dispose())
    })
    this.renderer.dispose()
  }
}

function esDescendiente(o: THREE.Object3D, padre: THREE.Object3D) {
  for (let p: THREE.Object3D | null = o.parent; p; p = p.parent) if (p === padre) return true
  return false
}
