/**
 * El bicho en 3D: chasis 4WD, brazo de 3 ejes con la cabeza (anillo + cámara), pantalla 8×8, LiDAR, sensores,
 * bomba de agua, y un patio con huerto, un perro y una persona. Medidas en metros, parecidas a las reales.
 * El robot mira hacia +z en su propio sistema; +x es su izquierda.
 */
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { ICONOS, REPOSO, type Estado, type Visita } from './lenguaje'
import { N_LEDS, anillo, brillo, hex } from './luces'

const { PI, sin, cos, atan2, hypot, min, max, abs } = Math
const clamp = (x: number, a: number, b: number) => min(b, max(a, x))
const envolver = (a: number) => atan2(sin(a), cos(a))
const suave = (actual: number, meta: number, k: number, dt: number) => actual + (meta - actual) * (1 - Math.exp(-k * dt))

const CERCA = 2.6
const LIMITE = 2.35
const HUERTO = { x0: 0.8, x1: 2.0, z0: -1.85, z1: -1.15, alto: 0.25 }
const RUTA: [number, number][] = [[0.55, 0.6], [0.45, -0.7], [-0.9, -1.3], [-1.4, 0.2]]
const RUEDA = 0.033
const MEDIA_VIA = 0.098
const ALTO_CABEZA = 0.3
const LIDAR_RAYOS = 180
const GOTAS = 160

export type Eventos = {
  hover?: (pieza: string | null, x: number, y: number) => void
  visitaSeFue?: () => void
}

function mat(color: number, o: THREE.MeshStandardMaterialParameters = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.55, metalness: 0, ...o })
}
const acrilico = () => new THREE.MeshPhysicalMaterial({ color: 0x121212, roughness: 0.22, clearcoat: 1, clearcoatRoughness: 0.08 })
const pla = () => mat(0xffc93c, { roughness: 0.62 })
const pcbVerde = () => mat(0x1f7a3d, { roughness: 0.45 })
const metal = (c = 0xc8c8c8) => mat(c, { metalness: 0.85, roughness: 0.3 })

/** Placa de acrílico con esquinas redondeadas y agujeros. */
function placa(ancho: number, largo: number, radio: number, grosor: number) {
  const w = ancho / 2
  const l = largo / 2
  const s = new THREE.Shape()
  s.moveTo(-w + radio, -l)
  s.lineTo(w - radio, -l)
  s.quadraticCurveTo(w, -l, w, -l + radio)
  s.lineTo(w, l - radio)
  s.quadraticCurveTo(w, l, w - radio, l)
  s.lineTo(-w + radio, l)
  s.quadraticCurveTo(-w, l, -w, l - radio)
  s.lineTo(-w, -l + radio)
  s.quadraticCurveTo(-w, -l, -w + radio, -l)
  for (let i = -3; i <= 3; i++) {
    for (const sx of [-1, 1]) {
      const h = new THREE.Path()
      h.absarc(sx * (w - 0.009), i * (largo / 8.5), 0.0028, 0, PI * 2, true)
      s.holes.push(h)
    }
  }
  const ranura = new THREE.Path()
  ranura.absellipse(0, 0, 0.022, 0.009, 0, PI * 2, true, 0)
  s.holes.push(ranura)
  const g = new THREE.ExtrudeGeometry(s, { depth: grosor, bevelEnabled: false, curveSegments: 10 })
  g.rotateX(-PI / 2)
  return g
}

function texturaBrillo() {
  const c = document.createElement('canvas')
  c.width = c.height = 64
  const g = c.getContext('2d')!
  const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32)
  gr.addColorStop(0, 'rgba(255,255,255,1)')
  gr.addColorStop(0.22, 'rgba(255,255,255,.6)')
  gr.addColorStop(1, 'rgba(255,255,255,0)')
  g.fillStyle = gr
  g.fillRect(0, 0, 64, 64)
  const t = new THREE.CanvasTexture(c)
  t.colorSpace = THREE.SRGBColorSpace
  return t
}

/** Distancia por la que un rayo 2D (o + d·t) entra a una caja alineada a los ejes, o Infinity. */
function rayoCaja(ox: number, oz: number, dx: number, dz: number, x0: number, x1: number, z0: number, z1: number) {
  let t0 = -Infinity
  let t1 = Infinity
  for (const [o, d, a, b] of [[ox, dx, x0, x1], [oz, dz, z0, z1]]) {
    if (abs(d) < 1e-9) {
      if (o < a || o > b) return Infinity
    } else {
      let ta = (a - o) / d
      let tb = (b - o) / d
      if (ta > tb) [ta, tb] = [tb, ta]
      t0 = max(t0, ta)
      t1 = min(t1, tb)
    }
  }
  return t1 >= max(t0, 0) && t0 > 0 ? t0 : Infinity
}

function rayoCirculo(ox: number, oz: number, dx: number, dz: number, cx: number, cz: number, r: number) {
  const fx = ox - cx
  const fz = oz - cz
  const b = fx * dx + fz * dz
  const c = fx * fx + fz * fz - r * r
  const h = b * b - c
  if (h < 0) return Infinity
  const t = -b - Math.sqrt(h)
  return t > 0 ? t : Infinity
}

type Pata = { grupo: THREE.Group; fase: number }

export class Simulacion {
  private renderer: THREE.WebGLRenderer
  private scene = new THREE.Scene()
  private camara: THREE.PerspectiveCamera
  private controles: OrbitControls
  private sol: THREE.DirectionalLight
  private robot = new THREE.Group()
  private cuerpoRobot = new THREE.Group()
  private ruedas: THREE.Group[] = []
  private brazo = { base: new THREE.Group(), hombro: new THREE.Group(), muneca: new THREE.Group(), cabeza: new THREE.Group() }
  private leds: { mat: THREE.MeshStandardMaterial; halo: THREE.Sprite }[] = []
  private matriz: THREE.MeshStandardMaterial[] = []
  private luzOjo = new THREE.PointLight(0xffffff, 0, 1.4, 2)
  private foco = { led: mat(0xfff8e0), luz: new THREE.SpotLight(0xfff3d6, 0, 3.5, 0.42, 0.55, 1.6), haz: new THREE.Mesh() }
  private lidarTope = new THREE.Group()
  private lidarPuntos: THREE.Points
  private ultrasonido: THREE.Mesh
  private agua: THREE.Points
  private gotas = Array.from({ length: GOTAS }, () => ({ p: new THREE.Vector3(), v: new THREE.Vector3(), viva: false }))
  private boquilla = new THREE.Object3D()
  private parlante = new THREE.Object3D()
  private ondas: THREE.Mesh[] = []
  private camCabeza = new THREE.PerspectiveCamera(64, 4 / 3, 0.02, 30)
  private rt = new THREE.WebGLRenderTarget(320, 240)
  private perro = new THREE.Group()
  private persona = new THREE.Group()
  private patasPerro: Pata[] = []
  private colaPerro = new THREE.Group()
  private piezas = new Map<string, THREE.Mesh[]>()
  private resaltada: string | null = null
  private raycaster = new THREE.Raycaster()
  private suelo = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)

  private e: Estado = REPOSO
  private tEstado = 0
  private t = 0
  private pose = { x: 0, z: 0, th: 0, v: 0, w: 0, y: 0 }
  private art = { yaw: 0, hombro: 0.12, muneca: 0.05 }
  private ruta = 0
  private visita: Visita = 'ninguna'
  private visitaPos = new THREE.Vector3(0.9, 0, -0.6)
  private huyendo = false
  private hablando = 0
  private sensores = true
  private pip = true
  private reloj = new THREE.Clock()
  private raf = 0
  private obs: ResizeObserver
  private apretado: { x: number; y: number; t: number } | null = null
  private hoverPendiente: { x: number; y: number } | null = null
  private ancho = 1
  private ultimoToque = -10
  private alto = 1

  constructor(private lienzo: HTMLCanvasElement, private ev: Eventos = {}) {
    const r = new THREE.WebGLRenderer({ canvas: lienzo, antialias: true })
    r.setPixelRatio(min(devicePixelRatio, 2))
    r.toneMapping = THREE.ACESFilmicToneMapping
    r.toneMappingExposure = 1.02
    r.outputColorSpace = THREE.SRGBColorSpace
    r.shadowMap.enabled = true
    r.shadowMap.type = THREE.PCFSoftShadowMap
    this.renderer = r
    this.rt.texture.colorSpace = THREE.SRGBColorSpace

    this.scene.background = new THREE.Color(0xf3eee7)
    this.scene.fog = new THREE.Fog(0xf3eee7, 5, 13)

    this.camara = new THREE.PerspectiveCamera(38, 1, 0.02, 60)
    this.camara.position.set(0.78, 0.52, 1.0)
    this.controles = new OrbitControls(this.camara, lienzo)
    this.controles.target.set(0, 0.14, 0)
    this.controles.enableDamping = true
    this.controles.minDistance = 0.32
    this.controles.maxDistance = 7
    this.controles.maxPolarAngle = 1.48
    this.controles.addEventListener('start', () => (this.ultimoToque = this.t))
    this.camara.layers.enable(1)

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0xd8cdbf, 1.25))
    this.sol = new THREE.DirectionalLight(0xfff1df, 2.1)
    this.sol.castShadow = true
    this.sol.shadow.mapSize.set(2048, 2048)
    const sc = this.sol.shadow.camera
    sc.left = sc.bottom = -1.6
    sc.right = sc.top = 1.6
    sc.near = 0.5
    sc.far = 9
    this.sol.shadow.bias = -0.0004
    this.sol.shadow.normalBias = 0.01
    this.scene.add(this.sol, this.sol.target)

    this.construirPatio()
    this.construirRobot()
    this.construirVisitas()

    // LiDAR: puntos rojos en el suelo
    const lp = new THREE.BufferGeometry()
    lp.setAttribute('position', new THREE.BufferAttribute(new Float32Array(LIDAR_RAYOS * 3), 3))
    this.lidarPuntos = new THREE.Points(lp, new THREE.PointsMaterial({ color: 0xff3b30, size: 0.03, sizeAttenuation: true, transparent: true, opacity: 0.9, depthWrite: false }))
    this.lidarPuntos.frustumCulled = false
    this.scene.add(this.lidarPuntos)

    // gotas de agua
    const ag = new THREE.BufferGeometry()
    ag.setAttribute('position', new THREE.BufferAttribute(new Float32Array(GOTAS * 3), 3))
    this.agua = new THREE.Points(ag, new THREE.PointsMaterial({ color: 0x59b8ff, size: 0.014, transparent: true, opacity: 0.85, depthWrite: false }))
    this.agua.frustumCulled = false
    this.scene.add(this.agua)

    // cono del ultrasonido
    const cono = new THREE.ConeGeometry(0.27, 1, 28, 1, true)
    cono.translate(0, -0.5, 0)
    cono.rotateX(-PI / 2)
    this.ultrasonido = new THREE.Mesh(cono, new THREE.MeshBasicMaterial({ color: 0x5ac8fa, transparent: true, opacity: 0.13, depthWrite: false, side: THREE.DoubleSide }))
    this.ultrasonido.position.set(0, 0.075, 0.132)
    this.cuerpoRobot.add(this.ultrasonido)

    this.obs = new ResizeObserver(() => this.ajustar())
    this.obs.observe(lienzo.parentElement ?? lienzo)
    this.ajustar()

    lienzo.addEventListener('pointerdown', this.alApretar)
    lienzo.addEventListener('pointerup', this.alSoltar)
    lienzo.addEventListener('pointermove', this.alMover)
    lienzo.addEventListener('pointerleave', this.alSalir)

    this.reloj.start()
    this.raf = requestAnimationFrame(this.cuadro)
  }

  /* ───────────────────────── API ───────────────────────── */

  setEstado(e: Estado) {
    this.e = e
    this.tEstado = 0
    if (e.cuerpo === 'patrullar') {
      let mejor = 0
      let dmin = Infinity
      RUTA.forEach(([x, z], i) => {
        const d = hypot(x - this.pose.x, z - this.pose.z)
        if (d < dmin) [dmin, mejor] = [d, i]
      })
      this.ruta = mejor
    }
    if (e.visita_se_va && this.visita !== 'ninguna') this.huyendo = true
  }

  setVisita(v: Visita) {
    if (v === this.visita && !this.huyendo) return
    this.huyendo = false
    this.visita = v
    if (v === 'perro') this.visitaPos.set(0.85, 0, -0.55)
    if (v === 'persona') this.visitaPos.set(-0.75, 0, -1.05)
    this.perro.visible = v === 'perro'
    this.persona.visible = v === 'persona'
  }

  setSensores(on: boolean) {
    this.sensores = on
  }

  setPip(on: boolean) {
    this.pip = on
  }

  /** Muestra las ondas del parlante durante unos segundos. */
  hablar(segundos: number) {
    this.hablando = max(this.hablando, segundos)
  }

  resaltar(id: string | null) {
    if (this.resaltada === id) return
    const pintar = (pid: string | null, on: boolean) => {
      if (!pid) return
      for (const m of this.piezas.get(pid) ?? []) {
        if (m.userData.led) continue
        const mt = m.material as THREE.MeshStandardMaterial
        if (on) {
          m.userData.em ??= mt.emissive.getHex()
          m.userData.emI ??= mt.emissiveIntensity
          mt.emissive.setHex(0xffa800)
          mt.emissiveIntensity = 0.6
        } else {
          mt.emissive.setHex(m.userData.em ?? 0)
          mt.emissiveIntensity = m.userData.emI ?? 1
        }
      }
    }
    pintar(this.resaltada, false)
    this.resaltada = id
    pintar(id, true)
  }

  /** Foto de lo que ve la cámara de la cabeza, como data URL. */
  foto(): string | null {
    const w = 320
    const h = 240
    this.camCabeza.updateMatrixWorld()
    this.renderer.setRenderTarget(this.rt)
    this.renderer.render(this.scene, this.camCabeza)
    const buf = new Uint8Array(w * h * 4)
    this.renderer.readRenderTargetPixels(this.rt, 0, 0, w, h, buf)
    this.renderer.setRenderTarget(null)
    const c = document.createElement('canvas')
    c.width = w
    c.height = h
    const g = c.getContext('2d')
    if (!g) return null
    const img = g.createImageData(w, h)
    for (let y = 0; y < h; y++) img.data.set(buf.subarray((h - 1 - y) * w * 4, (h - y) * w * 4), y * w * 4)
    g.putImageData(img, 0, 0)
    return c.toDataURL('image/jpeg', 0.85)
  }

  /** Vuelve la cámara a la vista inicial, detrás del bicho. */
  encuadrar() {
    const p = new THREE.Vector3(this.pose.x, 0.14, this.pose.z)
    this.controles.target.copy(p)
    this.camara.position.copy(p).add(new THREE.Vector3(0.78, 0.38, 1.0))
  }

  dispose() {
    cancelAnimationFrame(this.raf)
    this.obs.disconnect()
    this.lienzo.removeEventListener('pointerdown', this.alApretar)
    this.lienzo.removeEventListener('pointerup', this.alSoltar)
    this.lienzo.removeEventListener('pointermove', this.alMover)
    this.lienzo.removeEventListener('pointerleave', this.alSalir)
    this.controles.dispose()
    this.scene.traverse((o) => {
      const m = o as THREE.Mesh
      if (m.geometry) m.geometry.dispose()
      const mats = Array.isArray(m.material) ? m.material : m.material ? [m.material] : []
      for (const x of mats) x.dispose()
    })
    this.rt.dispose()
    this.renderer.dispose()
  }

  /* ─────────────────────── construcción ─────────────────────── */

  private registrar<T extends THREE.Object3D>(id: string, o: T, led = false): T {
    o.traverse((x) => {
      const m = x as THREE.Mesh
      if (!m.isMesh) return
      m.userData.pieza = id
      if (led) m.userData.led = true
      m.castShadow = !led
      m.receiveShadow = true
      const lista = this.piezas.get(id) ?? []
      lista.push(m)
      this.piezas.set(id, lista)
    })
    return o
  }

  private caja(id: string, [w, h, d]: [number, number, number], m: THREE.Material | number, [x, y, z]: [number, number, number], padre: THREE.Object3D) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), typeof m === 'number' ? mat(m) : m)
    mesh.position.set(x, y, z)
    padre.add(mesh)
    return this.registrar(id, mesh)
  }

  private cil(id: string, r: number, h: number, m: THREE.Material | number, [x, y, z]: [number, number, number], padre: THREE.Object3D, eje: 'x' | 'y' | 'z' = 'y', seg = 24) {
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, seg), typeof m === 'number' ? mat(m) : m)
    if (eje === 'x') mesh.rotation.z = PI / 2
    if (eje === 'z') mesh.rotation.x = PI / 2
    mesh.position.set(x, y, z)
    padre.add(mesh)
    return this.registrar(id, mesh)
  }

  private construirPatio() {
    const piso = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), mat(0xe8e1d5, { roughness: 1 }))
    piso.rotation.x = -PI / 2
    piso.receiveShadow = true
    this.scene.add(piso)

    const pasto = new THREE.Mesh(new THREE.PlaneGeometry(CERCA * 2, CERCA * 2), mat(0xd3e0bf, { roughness: 1 }))
    pasto.rotation.x = -PI / 2
    pasto.position.y = 0.001
    pasto.receiveShadow = true
    this.scene.add(pasto)

    const grilla = new THREE.GridHelper(CERCA * 2, 26, 0xb9c9a4, 0xb9c9a4)
    grilla.position.y = 0.002
    const gm = grilla.material as THREE.Material
    gm.transparent = true
    gm.opacity = 0.45
    this.scene.add(grilla)

    // base de carga del bicho
    const base = new THREE.Mesh(new THREE.RingGeometry(0.17, 0.19, 48), new THREE.MeshBasicMaterial({ color: 0xffc700, transparent: true, opacity: 0.8 }))
    base.rotation.x = -PI / 2
    base.position.y = 0.003
    this.scene.add(base)
    const baseFondo = new THREE.Mesh(new THREE.CircleGeometry(0.17, 48), new THREE.MeshBasicMaterial({ color: 0xffc700, transparent: true, opacity: 0.14 }))
    baseFondo.rotation.x = -PI / 2
    baseFondo.position.y = 0.0025
    this.scene.add(baseFondo)

    // cerca de madera: atrás y a los lados
    const madera = mat(0xcfae84, { roughness: 0.8 })
    const postes: [number, number][] = []
    for (let i = -CERCA; i <= CERCA + 1e-6; i += 0.5) {
      postes.push([i, -CERCA])
      if (i > -CERCA) {
        postes.push([-CERCA, i])
        postes.push([CERCA, i])
      }
    }
    const inst = new THREE.InstancedMesh(new THREE.BoxGeometry(0.07, 0.95, 0.07), madera, postes.length)
    const m4 = new THREE.Matrix4()
    postes.forEach(([x, z], i) => inst.setMatrixAt(i, m4.makeTranslation(x, 0.475, z)))
    inst.castShadow = true
    inst.receiveShadow = true
    this.scene.add(inst)
    for (const y of [0.35, 0.78]) {
      const atras = new THREE.Mesh(new THREE.BoxGeometry(CERCA * 2, 0.07, 0.025), madera)
      atras.position.set(0, y, -CERCA)
      const izq = new THREE.Mesh(new THREE.BoxGeometry(0.025, 0.07, CERCA * 2), madera)
      izq.position.set(-CERCA, y, 0)
      const der = izq.clone()
      der.position.x = CERCA
      for (const m of [atras, izq, der]) {
        m.castShadow = true
        this.scene.add(m)
      }
    }

    // huerto
    const h = HUERTO
    const cx = (h.x0 + h.x1) / 2
    const cz = (h.z0 + h.z1) / 2
    const anchoH = h.x1 - h.x0
    const largoH = h.z1 - h.z0
    const tabla = mat(0xa8784e, { roughness: 0.85 })
    for (const [w, d, x, z] of [
      [anchoH, 0.04, cx, h.z0 + 0.02],
      [anchoH, 0.04, cx, h.z1 - 0.02],
      [0.04, largoH, h.x0 + 0.02, cz],
      [0.04, largoH, h.x1 - 0.02, cz],
    ]) {
      const b = new THREE.Mesh(new THREE.BoxGeometry(w, h.alto, d), tabla)
      b.position.set(x, h.alto / 2, z)
      b.castShadow = b.receiveShadow = true
      this.scene.add(b)
    }
    const tierra = new THREE.Mesh(new THREE.BoxGeometry(anchoH - 0.08, 0.02, largoH - 0.08), mat(0x6e4b33, { roughness: 1 }))
    tierra.position.set(cx, h.alto - 0.03, cz)
    tierra.receiveShadow = true
    this.scene.add(tierra)
    const hoja = mat(0x5f9e46, { roughness: 0.7 })
    for (let i = 0; i < 8; i++) {
      const p = new THREE.Mesh(new THREE.SphereGeometry(0.06 + (i % 3) * 0.015, 14, 10), hoja)
      p.position.set(h.x0 + 0.15 + (i % 4) * 0.28, h.alto + 0.02, cz + (i < 4 ? -0.15 : 0.15))
      p.scale.y = 0.8
      p.castShadow = true
      this.scene.add(p)
    }
  }

  private construirRobot() {
    const r = this.cuerpoRobot
    this.robot.add(r)
    this.scene.add(this.robot)

    // ruedas y motores TT
    for (const [sx, sz] of [[1, 1], [-1, 1], [1, -1], [-1, -1]]) {
      const g = new THREE.Group()
      g.position.set(sx * MEDIA_VIA, RUEDA, sz * 0.075)
      g.userData.lado = sx
      this.cil('motores', RUEDA, 0.026, mat(0x1b1b1b, { roughness: 0.92 }), [0, 0, 0], g, 'x', 36)
      this.cil('motores', RUEDA * 0.62, 0.0275, mat(0xffc400, { roughness: 0.5 }), [0, 0, 0], g, 'x')
      this.caja('motores', [0.029, RUEDA * 1.15, 0.005], mat(0xe0a400), [0, 0, 0], g)
      r.add(g)
      this.ruedas.push(g)
      this.caja('motores', [0.062, 0.019, 0.022], mat(0xffd21f, { roughness: 0.6 }), [sx * 0.05, 0.037, sz * 0.075], r)
    }

    // pisos de acrílico y separadores de bronce
    const abajo = new THREE.Mesh(placa(0.15, 0.25, 0.035, 0.004), acrilico())
    abajo.position.y = 0.048
    r.add(this.registrar('chasis', abajo))
    const arriba = new THREE.Mesh(placa(0.14, 0.21, 0.03, 0.004), acrilico())
    arriba.position.y = 0.098
    r.add(this.registrar('chasis', arriba))
    for (const sx of [-1, 1]) for (const z of [-0.085, 0, 0.085]) this.cil('chasis', 0.0028, 0.046, metal(0xc9a227), [sx * 0.058, 0.075, z], r, 'y', 8)

    // piso de abajo: drivers, PCA9685, batería, IMU, bomba y estanque
    for (const sx of [-1, 1]) this.caja('drivers', [0.02, 0.002, 0.02], 0x6c2bd9, [sx * 0.03, 0.054, 0.063], r)
    this.caja('pca9685', [0.062, 0.002, 0.025], 0x1565c0, [0, 0.054, 0.028], r)
    this.caja('bateria', [0.042, 0.016, 0.074], 0x202020, [-0.018, 0.06, -0.04], r)
    for (const sx of [-1, 1]) this.cil('bateria', 0.009, 0.065, mat(0x2e7d32, { roughness: 0.35 }), [-0.018 + sx * 0.0095, 0.069, -0.04], r, 'z')
    this.caja('imu', [0.016, 0.002, 0.02], 0x0d47a1, [0.042, 0.054, -0.005], r)
    const estanque = new THREE.Mesh(new THREE.BoxGeometry(0.036, 0.036, 0.036), new THREE.MeshPhysicalMaterial({ color: 0xdff3ff, transparent: true, opacity: 0.35, roughness: 0.05 }))
    estanque.position.set(0.03, 0.07, -0.098)
    r.add(this.registrar('bomba', estanque))
    this.caja('bomba', [0.03, 0.022, 0.03], mat(0x2f8cff, { transparent: true, opacity: 0.7 }), [0.03, 0.064, -0.098], r)
    this.cil('bomba', 0.008, 0.026, 0x111111, [-0.012, 0.062, -0.1], r, 'z')
    this.caja('piso', [0.045, 0.002, 0.012], 0x1a1a1a, [0, 0.045, 0.108], r)

    // frente: ultrasonido y ToF
    this.caja('ultrasonido', [0.045, 0.02, 0.0016], 0x1565c0, [0, 0.075, 0.124], r)
    for (const sx of [-1, 1]) {
      this.cil('ultrasonido', 0.008, 0.012, metal(), [sx * 0.013, 0.075, 0.131], r, 'z')
      this.cil('ultrasonido', 0.0062, 0.0125, mat(0x222222, { roughness: 0.9 }), [sx * 0.013, 0.075, 0.1312], r, 'z')
      const tof = this.caja('tof', [0.013, 0.013, 0.0016], 0x7b1fa2, [sx * 0.063, 0.07, 0.108], r)
      tof.rotation.y = sx * 0.7
    }

    // piso de arriba: Pi 3, UPS, ReSpeaker y parlante
    const pi = new THREE.Group()
    pi.position.set(-0.041, 0.108, -0.045)
    r.add(pi)
    this.caja('pi', [0.056, 0.0016, 0.085], pcbVerde(), [0, 0, 0], pi)
    this.caja('pi', [0.014, 0.0015, 0.014], 0x111111, [0, 0.0015, 0.005], pi)
    this.caja('pi', [0.05, 0.008, 0.005], 0x1a1a1a, [0, 0.004, 0.039], pi)
    for (const x of [-0.016, 0.004]) this.caja('pi', [0.014, 0.015, 0.017], metal(), [x, 0.0085, -0.034], pi)
    this.caja('pi', [0.016, 0.013, 0.021], metal(0xb0b0b0), [0.02, 0.0075, -0.032], pi)
    this.caja('ups', [0.045, 0.0016, 0.07], 0x1565c0, [0.044, 0.108, -0.048], r)
    for (const sx of [-1, 1]) this.cil('ups', 0.009, 0.065, mat(0xe86a7a, { roughness: 0.35 }), [0.044 + sx * 0.011, 0.118, -0.048], r, 'z')
    this.caja('respeaker', [0.034, 0.0016, 0.034], 0x111111, [-0.045, 0.106, 0.052], r)
    for (const x of [-0.055, -0.035]) this.cil('respeaker', 0.002, 0.002, metal(), [x, 0.108, 0.052], r)
    this.cil('respeaker', 0.017, 0.012, 0x161616, [0.046, 0.108, 0.05], r)
    this.cil('respeaker', 0.014, 0.0125, mat(0x3a3a3a, { roughness: 0.95 }), [0.046, 0.1085, 0.05], r)
    this.parlante.position.set(0.046, 0.116, 0.05)
    r.add(this.parlante)
    for (let i = 0; i < 3; i++) {
      const o = new THREE.Mesh(new THREE.RingGeometry(0.019, 0.022, 36), new THREE.MeshBasicMaterial({ color: 0x5ac8fa, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide }))
      o.rotation.x = -PI / 2
      this.parlante.add(o)
      this.ondas.push(o)
    }

    // LiDAR en una torre impresa, atrás
    this.cil('impresas', 0.012, 0.064, pla(), [0, 0.134, -0.082], r)
    this.cil('lidar', 0.035, 0.016, 0x1c1c1c, [0, 0.174, -0.082], r, 'y', 36)
    this.lidarTope.position.set(0, 0.192, -0.082)
    r.add(this.lidarTope)
    this.cil('lidar', 0.029, 0.02, mat(0x262626, { roughness: 0.3 }), [0, 0, 0], this.lidarTope, 'y', 36)
    this.caja('lidar', [0.018, 0.009, 0.004], mat(0xff5a1f, { emissive: 0x551100, roughness: 0.2 }), [0, 0, 0.028], this.lidarTope)

    // pantalla 8×8 en el pecho
    const pantalla = new THREE.Group()
    pantalla.position.set(0, 0.139, 0.101)
    r.add(pantalla)
    this.caja('impresas', [0.074, 0.074, 0.008], pla(), [0, 0, -0.004], pantalla)
    this.caja('matriz', [0.066, 0.066, 0.002], 0x111111, [0, 0, 0.001], pantalla)
    for (let fila = 0; fila < 8; fila++) {
      for (let col = 0; col < 8; col++) {
        const m = mat(0x1d1d1d, { emissive: 0x000000, emissiveIntensity: 2.4, roughness: 0.35 })
        const px = new THREE.Mesh(new THREE.BoxGeometry(0.0058, 0.0058, 0.0018), m)
        px.position.set((3.5 - col) * 0.0079, (3.5 - fila) * 0.0079, 0.0025)
        pantalla.add(this.registrar('matriz', px, true))
        this.matriz.push(m)
      }
    }

    // brazo de 3 ejes: base (MG995), hombro (MG995), muñeca (MG90S)
    const { base, hombro, muneca, cabeza } = this.brazo
    this.caja('brazo', [0.021, 0.04, 0.041], 0x1e1e1e, [0, 0.12, 0.012], r)
    base.position.set(0, 0.14, 0.012)
    r.add(base)
    this.cil('brazo', 0.027, 0.007, pla(), [0, 0.003, 0], base, 'y', 36)
    for (const sx of [-1, 1]) this.caja('brazo', [0.004, 0.05, 0.03], pla(), [sx * 0.024, 0.03, 0], base)
    this.caja('brazo', [0.041, 0.021, 0.038], 0x1e1e1e, [0, 0.04, 0], base)
    hombro.position.set(0, 0.042, 0)
    base.add(hombro)
    this.caja('brazo', [0.022, 0.104, 0.013], pla(), [0, 0.052, 0], hombro)
    this.cil('brazo', 0.012, 0.03, pla(), [0, 0, 0], hombro, 'x')
    muneca.position.set(0, 0.104, 0)
    hombro.add(muneca)
    this.caja('brazo', [0.023, 0.013, 0.023], 0x1f5fbf, [0, 0, 0], muneca)
    this.caja('brazo', [0.018, 0.042, 0.011], pla(), [0, 0.022, 0], muneca)
    cabeza.position.set(0, 0.047, 0)
    muneca.add(cabeza)

    // cabeza: carcasa impresa, anillo de 24 LEDs, cámara al centro, foco, boquilla y pinza
    this.cil('impresas', 0.042, 0.022, mat(0xfafafa, { roughness: 0.5 }), [0, 0, 0], cabeza, 'z', 48)
    const aro = new THREE.Mesh(new THREE.RingGeometry(0.024, 0.0365, 48), mat(0x111111, { roughness: 0.4 }))
    aro.position.z = 0.0112
    cabeza.add(this.registrar('anillo', aro))
    const halo = texturaBrillo()
    for (let i = 0; i < N_LEDS; i++) {
      const a = (i / N_LEDS) * PI * 2
      const m = mat(0x2a2a2a, { emissive: 0x000000, emissiveIntensity: 2.6, roughness: 0.3 })
      const led = new THREE.Mesh(new THREE.BoxGeometry(0.0056, 0.0056, 0.0022), m)
      led.position.set(-sin(a) * 0.0305, cos(a) * 0.0305, 0.0125)
      led.rotation.z = -a
      cabeza.add(this.registrar('anillo', led, true))
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: halo, color: 0x000000, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }))
      s.position.set(led.position.x, led.position.y, 0.016)
      s.scale.setScalar(0.022)
      cabeza.add(s)
      this.leds.push({ mat: m, halo: s })
    }
    this.caja('camara', [0.025, 0.024, 0.002], pcbVerde(), [0, 0, 0.0115], cabeza)
    this.cil('camara', 0.0048, 0.007, 0x0c0c0c, [0, 0, 0.0155], cabeza, 'z')
    this.cil('camara', 0.0026, 0.0072, mat(0x203a66, { metalness: 0.6, roughness: 0.1 }), [0, 0, 0.0158], cabeza, 'z')
    this.luzOjo.position.set(0, 0, 0.06)
    cabeza.add(this.luzOjo)
    this.camCabeza.position.set(0, 0, 0.022)
    this.camCabeza.rotation.y = PI
    cabeza.add(this.camCabeza)

    this.caja('impresas', [0.018, 0.012, 0.014], pla(), [0, 0.046, 0.002], cabeza)
    this.foco.led.emissive.setHex(0x000000)
    this.foco.led.emissiveIntensity = 3
    this.cil('foco', 0.0085, 0.003, this.foco.led, [0, 0.048, 0.0105], cabeza, 'z', 6)
    this.foco.luz.position.set(0, 0.048, 0.015)
    this.foco.luz.target.position.set(0, -0.25, 1)
    cabeza.add(this.foco.luz, this.foco.luz.target)
    const haz = new THREE.ConeGeometry(0.42, 1.4, 32, 1, true)
    haz.translate(0, -0.7, 0)
    haz.rotateX(-PI / 2)
    this.foco.haz = new THREE.Mesh(haz, new THREE.MeshBasicMaterial({ color: 0xfff4d8, transparent: true, opacity: 0.09, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide }))
    this.foco.haz.position.set(0, 0.048, 0.015)
    this.foco.haz.rotation.x = 0.18
    this.foco.haz.visible = false
    this.foco.haz.layers.set(1)
    cabeza.add(this.foco.haz)

    this.cil('bomba', 0.0032, 0.03, mat(0x2f8cff), [0, -0.047, 0.012], cabeza, 'z', 10)
    this.boquilla.position.set(0, -0.047, 0.03)
    cabeza.add(this.boquilla)

    this.caja('pinza', [0.023, 0.012, 0.022], 0x1f5fbf, [0, -0.05, -0.012], cabeza)
    for (const sx of [-1, 1]) {
      const dedo = this.caja('pinza', [0.005, 0.032, 0.008], pla(), [sx * 0.011, -0.069, -0.004], cabeza)
      dedo.rotation.z = sx * 0.18
    }
  }

  private construirVisitas() {
    // perro café
    const cafe = mat(0x9a6a3a, { roughness: 0.8 })
    const oscuro = mat(0x6b4526, { roughness: 0.8 })
    const negro = mat(0x111111, { roughness: 0.3 })
    const cuerpo = new THREE.Mesh(new THREE.CapsuleGeometry(0.1, 0.28, 6, 14), cafe)
    cuerpo.rotation.x = PI / 2
    cuerpo.position.y = 0.36
    const cabeza = new THREE.Mesh(new THREE.SphereGeometry(0.095, 18, 14), cafe)
    cabeza.position.set(0, 0.5, 0.25)
    const hocico = new THREE.Mesh(new THREE.BoxGeometry(0.075, 0.065, 0.1), cafe)
    hocico.position.set(0, 0.47, 0.34)
    const nariz = new THREE.Mesh(new THREE.SphereGeometry(0.018, 10, 8), negro)
    nariz.position.set(0, 0.49, 0.39)
    this.perro.add(cuerpo, cabeza, hocico, nariz)
    for (const sx of [-1, 1]) {
      const oreja = new THREE.Mesh(new THREE.BoxGeometry(0.035, 0.08, 0.05), oscuro)
      oreja.position.set(sx * 0.07, 0.55, 0.22)
      oreja.rotation.z = sx * 0.35
      const ojo = new THREE.Mesh(new THREE.SphereGeometry(0.012, 8, 6), negro)
      ojo.position.set(sx * 0.04, 0.53, 0.33)
      this.perro.add(oreja, ojo)
    }
    for (const [sx, sz, fase] of [[1, 1, 0], [-1, 1, PI], [1, -1, PI], [-1, -1, 0]]) {
      const g = new THREE.Group()
      g.position.set(sx * 0.06, 0.32, sz * 0.15)
      const pata = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.024, 0.32, 10), cafe)
      pata.position.y = -0.16
      g.add(pata)
      this.perro.add(g)
      this.patasPerro.push({ grupo: g, fase })
    }
    this.colaPerro.position.set(0, 0.42, -0.23)
    const cola = new THREE.Mesh(new THREE.CylinderGeometry(0.014, 0.01, 0.16, 8), oscuro)
    cola.position.y = 0.07
    this.colaPerro.add(cola)
    this.colaPerro.rotation.x = -0.6
    this.perro.add(this.colaPerro)

    // persona con chaqueta roja
    const jeans = mat(0x3b5b8a, { roughness: 0.85 })
    const chaqueta = mat(0xc0392b, { roughness: 0.7 })
    const piel = mat(0xd9a77e, { roughness: 0.6 })
    for (const sx of [-1, 1]) {
      const pierna = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.055, 0.85, 12), jeans)
      pierna.position.set(sx * 0.08, 0.425, 0)
      const brazo = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.04, 0.6, 12), chaqueta)
      brazo.position.set(sx * 0.23, 1.12, 0)
      brazo.rotation.z = sx * 0.08
      this.persona.add(pierna, brazo)
    }
    const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.16, 0.38, 6, 16), chaqueta)
    torso.position.y = 1.15
    torso.scale.z = 0.7
    const cabezaP = new THREE.Mesh(new THREE.SphereGeometry(0.11, 18, 14), piel)
    cabezaP.position.y = 1.6
    const pelo = new THREE.Mesh(new THREE.SphereGeometry(0.115, 18, 10, 0, PI * 2, 0, PI / 2), mat(0x2b1d14))
    pelo.position.y = 1.62
    this.persona.add(torso, cabezaP, pelo)

    for (const g of [this.perro, this.persona]) {
      g.traverse((o) => {
        const m = o as THREE.Mesh
        if (m.isMesh) m.castShadow = m.receiveShadow = true
      })
      g.visible = false
      this.scene.add(g)
    }
  }

  /* ─────────────────────── simulación ─────────────────────── */

  private cuadro = () => {
    this.raf = requestAnimationFrame(this.cuadro)
    const dt = min(this.reloj.getDelta(), 0.05)
    this.t += dt
    this.tEstado += dt

    this.conducir(dt)
    this.moverBrazo(dt)
    this.pintarLuces(dt)
    this.moverVisita(dt)
    this.mojar(dt)
    this.sentir(dt)
    this.seguirConCamara(dt)
    if (this.hoverPendiente) this.revisarHover()

    this.controles.update()
    this.renderer.setViewport(0, 0, this.ancho, this.alto)
    this.renderer.render(this.scene, this.camara)
    if (this.pip) {
      const w = Math.round(min(this.ancho * 0.26, 260))
      const h = Math.round((w * 3) / 4)
      const x = this.ancho - w - 12
      this.renderer.setScissorTest(true)
      this.renderer.setScissor(x, 12, w, h)
      this.renderer.setViewport(x, 12, w, h)
      this.renderer.render(this.scene, this.camCabeza)
      this.renderer.setScissorTest(false)
    }
  }

  private get objetivo(): THREE.Vector3 | null {
    return this.visita !== 'ninguna' && !this.huyendo ? this.visitaPos : null
  }

  private conducir(dt: number) {
    const p = this.pose
    const t = this.tEstado
    const cam = this.camara.position
    const obj = this.objetivo
    let v = 0
    let w = 0
    const mirarA = (x: number, z: number) => {
      w = clamp(envolver(atan2(x - p.x, z - p.z) - p.th) * 3.5, -2.6, 2.6)
    }
    const irA = (x: number, z: number, parar: number, vmax: number) => {
      const dist = hypot(x - p.x, z - p.z)
      const dif = envolver(atan2(x - p.x, z - p.z) - p.th)
      if (dist > parar) {
        w = clamp(dif * 3, -2.6, 2.6)
        v = vmax * max(0, cos(dif)) * clamp((dist - parar) * 4, 0.25, 1)
      }
      return dist
    }

    switch (this.e.cuerpo) {
      case 'mirar_dueno':
        mirarA(cam.x, cam.z)
        break
      case 'acercarse':
        if (irA(cam.x, cam.z, 0.72, 0.24) <= 0.72) mirarA(cam.x, cam.z)
        break
      case 'retroceder':
        v = t < 0.45 ? -0.28 : 0
        break
      case 'giro':
        w = t < 1.1 ? (2 * PI) / 1.1 : 0
        break
      case 'baile':
        if (t < 2.6) {
          w = 3.4 * sin(2 * PI * 1.4 * t)
          v = 0.09 * sin(2 * PI * 2.8 * t)
        }
        break
      case 'vaiven':
        if (t < 1.8) v = 0.32 * sin(2 * PI * 2.2 * t)
        break
      case 'curiosear':
        if (obj && irA(obj.x, obj.z, 0.55, 0.1) <= 0.55) mirarA(obj.x, obj.z)
        break
      case 'orientar':
        if (obj) mirarA(obj.x, obj.z)
        break
      case 'plantarse': {
        if (!obj) break
        const parar = this.visita === 'persona' ? 0.95 : 0.62
        if (irA(obj.x, obj.z, parar, 0.32) <= parar) mirarA(obj.x, obj.z)
        break
      }
      case 'patrullar': {
        const [x, z] = RUTA[this.ruta]
        if (irA(x, z, 0.1, 0.28) < 0.16) this.ruta = (this.ruta + 1) % RUTA.length
        break
      }
      case 'base':
        if (irA(0, 0, 0.04, 0.26) <= 0.06) mirarA(cam.x, cam.z)
        break
      case 'lento':
        v = t < 2.5 ? 0.05 : 0
        break
      case 'intentar':
        if (t < 2.7) v = t % 0.9 < 0.45 ? 0.2 : -0.13
        break
      case 'prueba':
        if (t < 2.2) {
          v = 0.1 * sin(2 * PI * 1.2 * t)
          w = 0.9 * sin(2 * PI * 0.6 * t)
        }
        break
      case 'vuelta':
        w = t < 4 ? 0.7 : 0
        break
    }

    const levantado = this.e.cuerpo === 'levantado'
    if (levantado) v = w = 0
    p.v = suave(p.v, v, 9, dt)
    p.w = suave(p.w, w, 11, dt)
    p.th += p.w * dt
    p.x += p.v * sin(p.th) * dt
    p.z += p.v * cos(p.th) * dt
    p.x = clamp(p.x, -LIMITE, LIMITE)
    p.z = clamp(p.z, -LIMITE, LIMITE)
    // no se mete al huerto
    const m = 0.17
    const h = HUERTO
    if (p.x > h.x0 - m && p.x < h.x1 + m && p.z > h.z0 - m && p.z < h.z1 + m) {
      const salidas = [p.x - (h.x0 - m), h.x1 + m - p.x, p.z - (h.z0 - m), h.z1 + m - p.z]
      const i = salidas.indexOf(min(...salidas))
      if (i === 0) p.x = h.x0 - m
      if (i === 1) p.x = h.x1 + m
      if (i === 2) p.z = h.z0 - m
      if (i === 3) p.z = h.z1 + m
    }
    p.y = suave(p.y, levantado ? 0.34 : 0, levantado ? 3 : 5, dt)

    this.robot.position.set(p.x, p.y, p.z)
    this.robot.rotation.set(levantado ? 0.12 * sin(this.t * 1.7) : 0, p.th, levantado ? 0.08 * sin(this.t * 1.3) : 0)
    for (const g of this.ruedas) {
      const lado = g.userData.lado as number
      const vel = levantado ? 0 : p.v - lado * p.w * MEDIA_VIA
      g.rotation.x += (vel / RUEDA) * dt
    }

    this.sol.position.set(p.x + 1.6, 3.2, p.z + 1.2)
    this.sol.target.position.set(p.x, 0, p.z)
  }

  private moverBrazo(dt: number) {
    const c = this.e.cabeza
    const t = this.tEstado
    let yaw = 0
    let mira = 0.12
    let hombro = 0.12
    let punto: THREE.Vector3 | null = null
    if (c.mirar === 'dueno') punto = this.camara.position.clone()
    if (c.mirar === 'objetivo' && this.objetivo) punto = this.objetivo.clone().setY(this.visita === 'persona' ? 1.45 : 0.45)
    if (punto) {
      const local = this.robot.worldToLocal(punto).sub(new THREE.Vector3(0, ALTO_CABEZA, 0.012))
      yaw = atan2(local.x, local.z)
      mira = -atan2(local.y, hypot(local.x, local.z))
      if (abs(yaw) > 1.6) yaw = Math.sign(yaw) * 1.6
    } else if (c.mirar === 'abajo') {
      mira = 0.95
      hombro = 0.42
    } else if (c.mirar === 'alrededor') {
      yaw = 0.7 * sin(0.45 * this.t) + 0.25 * sin(1.3 * this.t)
      mira = 0.08 + 0.1 * sin(0.7 * this.t)
    }

    const fin = max(0, 1 - t / 1.6)
    switch (c.gesto) {
      case 'asentir':
        mira += 0.3 * sin(2 * PI * 2.4 * t) * fin
        break
      case 'negar':
        yaw += 0.42 * sin(2 * PI * 2.2 * t) * fin
        break
      case 'ladear_izq':
        yaw += 0.28
        mira -= 0.22
        break
      case 'ladear_der':
        yaw -= 0.28
        mira -= 0.22
        break
      case 'sacudir':
        yaw += 0.3 * sin(2 * PI * 6 * t) * max(0, 1 - t / 0.9)
        break
      case 'escanear':
        yaw += 0.9 * sin((2 * PI * t) / 3.5)
        break
      case 'atras': {
        const k = max(0, 1 - t / 1.2)
        hombro -= 0.4 * k
        mira -= 0.35 * k
        break
      }
    }

    const a = this.art
    a.yaw = suave(a.yaw, clamp(yaw, -1.65, 1.65), 9, dt)
    a.hombro = suave(a.hombro, clamp(hombro, -0.5, 0.7), 8, dt)
    a.muneca = suave(a.muneca, clamp(mira - hombro, -1.2, 1.3), 14, dt)
    this.brazo.base.rotation.y = a.yaw
    this.brazo.hombro.rotation.x = a.hombro
    this.brazo.muneca.rotation.x = a.muneca
  }

  private pintarLuces(dt: number) {
    const luz = this.e.luz
    const leds = anillo(luz, this.tEstado, clamp(this.art.yaw * 1.6, -1.5, 1.5))
    const c = new THREE.Color()
    leds.forEach(([r, g, b], i) => {
      const { mat: m, halo } = this.leds[i]
      c.setRGB(r, g, b, THREE.SRGBColorSpace)
      m.emissive.copy(c)
      halo.material.color.copy(c)
      halo.material.opacity = min(1, max(r, g, b) * 1.3)
    })
    const k = brillo(leds)
    const [r0, g0, b0] = hex(luz.color)
    this.luzOjo.color.setRGB(r0, g0, b0, THREE.SRGBColorSpace)
    this.luzOjo.intensity = k * 0.5

    const icono = ICONOS[this.e.matriz] ?? ICONOS.sonrisa
    const km = clamp(k * 1.7, 0.35, 1)
    for (let fila = 0; fila < 8; fila++) {
      for (let col = 0; col < 8; col++) {
        const m = this.matriz[fila * 8 + col]
        const on = icono[fila]?.[col] === '1'
        if (!on) {
          m.emissive.setRGB(0, 0, 0)
          continue
        }
        if (luz.patron === 'arcoiris' || luz.patron === 'corre') m.emissive.setHSL((fila / 8 + this.t * 0.4) % 1, 1, 0.5)
        else m.emissive.setRGB(r0 * km, g0 * km, b0 * km, THREE.SRGBColorSpace)
      }
    }

    const foco = !!this.e.foco
    this.foco.led.emissive.setHex(foco ? 0xfff6e0 : 0x000000)
    this.foco.luz.intensity = foco ? 9 : 0
    this.foco.haz.visible = foco

    this.hablando = max(0, this.hablando - dt)
    this.ondas.forEach((o, i) => {
      const fase = (this.t * 1.6 + i / 3) % 1
      o.scale.setScalar(1 + fase * 3.2)
      ;(o.material as THREE.MeshBasicMaterial).opacity = this.hablando > 0 ? (1 - fase) * 0.55 : 0
    })
  }

  private moverVisita(dt: number) {
    if (this.visita === 'ninguna') return
    const g = this.visita === 'perro' ? this.perro : this.persona
    const p = this.visitaPos
    let corre = false
    if (this.huyendo) {
      corre = true
      const dx = p.x - this.pose.x
      const dz = p.z - this.pose.z
      const d = hypot(dx, dz) || 1
      const vel = this.visita === 'perro' ? 1.5 : 0.9
      p.x += (dx / d) * vel * dt
      p.z += (dz / d) * vel * dt
      g.rotation.y = atan2(dx, dz)
      if (abs(p.x) > CERCA + 0.6 || abs(p.z) > CERCA + 0.6) {
        this.huyendo = false
        this.visita = 'ninguna'
        g.visible = false
        this.ev.visitaSeFue?.()
        return
      }
    } else {
      g.rotation.y = atan2(this.pose.x - p.x, this.pose.z - p.z)
    }
    g.position.copy(p)
    if (this.visita === 'perro') {
      this.colaPerro.rotation.z = (corre ? 0.2 : 0.7) * sin(this.t * (corre ? 8 : 14))
      for (const { grupo, fase } of this.patasPerro) grupo.rotation.x = corre ? 0.7 * sin(this.t * 16 + fase) : 0
      g.position.y = corre ? abs(sin(this.t * 16)) * 0.03 : 0
    } else {
      g.rotation.z = 0.012 * sin(this.t * 1.3)
      g.position.y = corre ? abs(sin(this.t * 9)) * 0.04 : 0
    }
  }

  private mojar(dt: number) {
    const activa = !!this.e.agua && this.tEstado > 0.3
    const pos = this.agua.geometry.getAttribute('position') as THREE.BufferAttribute
    const origen = this.boquilla.getWorldPosition(new THREE.Vector3())
    const dir = new THREE.Vector3(0, 0, 1).transformDirection(this.boquilla.matrixWorld)
    let nuevas = activa ? 6 : 0
    this.gotas.forEach((g, i) => {
      if (!g.viva && nuevas > 0) {
        nuevas--
        g.viva = true
        g.p.copy(origen)
        g.v.copy(dir).multiplyScalar(2.3 + Math.random() * 0.5)
        g.v.x += (Math.random() - 0.5) * 0.35
        g.v.y += 0.9 + (Math.random() - 0.5) * 0.3
        g.v.z += (Math.random() - 0.5) * 0.35
      }
      if (g.viva) {
        g.v.y -= 9.8 * dt
        g.p.addScaledVector(g.v, dt)
        if (g.p.y < 0) g.viva = false
      }
      pos.setXYZ(i, g.p.x, g.viva ? g.p.y : -10, g.p.z)
    })
    pos.needsUpdate = true
  }

  /** LiDAR y ultrasonido: rayos contra la cerca, el huerto y la visita. */
  private sentir(dt: number) {
    this.lidarTope.rotation.y += dt * PI * 2 * 7
    this.lidarPuntos.visible = this.sensores
    this.ultrasonido.visible = this.sensores
    if (!this.sensores) return

    const choque = (ox: number, oz: number, dx: number, dz: number) => {
      let d = Infinity
      if (dx > 1e-9) d = min(d, (CERCA - ox) / dx)
      if (dx < -1e-9) d = min(d, (-CERCA - ox) / dx)
      if (dz < -1e-9) d = min(d, (-CERCA - oz) / dz)
      const h = HUERTO
      d = min(d, rayoCaja(ox, oz, dx, dz, h.x0, h.x1, h.z0, h.z1))
      if (this.visita !== 'ninguna') {
        d = min(d, rayoCirculo(ox, oz, dx, dz, this.visitaPos.x, this.visitaPos.z, 0.2))
      }
      return d
    }

    const o = this.lidarTope.getWorldPosition(new THREE.Vector3())
    const pos = this.lidarPuntos.geometry.getAttribute('position') as THREE.BufferAttribute
    for (let i = 0; i < LIDAR_RAYOS; i++) {
      const a = (i / LIDAR_RAYOS) * PI * 2
      const dx = sin(a)
      const dz = cos(a)
      const d = choque(o.x, o.z, dx, dz)
      if (d < 6) pos.setXYZ(i, o.x + dx * d, 0.03, o.z + dz * d)
      else pos.setXYZ(i, 0, -10, 0)
    }
    pos.needsUpdate = true

    const th = this.pose.th
    const s = new THREE.Vector3(0, 0.075, 0.132)
    this.cuerpoRobot.localToWorld(s)
    const d = min(choque(s.x, s.z, sin(th), cos(th)), 2)
    this.ultrasonido.scale.setScalar(max(0.05, d))
  }

  /**
   * La cámara sigue al bicho. Si está mirando una visita y nadie tocó la vista hace rato,
   * se pone detrás de su hombro para que se vean los dos.
   */
  private seguirConCamara(dt: number) {
    const obj = this.objetivo
    if (obj && this.e.cabeza.mirar === 'objetivo' && this.t - this.ultimoToque > 4) {
      const dx = obj.x - this.pose.x
      const dz = obj.z - this.pose.z
      const d = hypot(dx, dz) || 1
      const ux = dx / d
      const uz = dz / d
      const persona = this.visita === 'persona'
      const alto = persona ? 1.0 : 0.55
      const lejos = (persona ? 1.25 : 0.85) + d * 0.45
      const metaCam = new THREE.Vector3(this.pose.x - ux * lejos - uz * 0.45, alto, this.pose.z - uz * lejos + ux * 0.45)
      const metaMira = new THREE.Vector3(this.pose.x + dx * 0.4, persona ? 0.55 : 0.22, this.pose.z + dz * 0.4)
      const k = 1 - Math.exp(-1.6 * dt)
      this.camara.position.lerp(metaCam, k)
      this.controles.target.lerp(metaMira, k)
      return
    }
    const meta = new THREE.Vector3(this.pose.x, 0.14 + this.pose.y, this.pose.z)
    const delta = meta.sub(this.controles.target).multiplyScalar(min(1, dt * 3))
    this.controles.target.add(delta)
    this.camara.position.add(delta)
  }

  private ajustar() {
    const caja = (this.lienzo.parentElement ?? this.lienzo).getBoundingClientRect()
    this.ancho = max(1, Math.round(caja.width))
    this.alto = max(1, Math.round(caja.height))
    this.renderer.setSize(this.ancho, this.alto, false)
    this.lienzo.style.width = `${this.ancho}px`
    this.lienzo.style.height = `${this.alto}px`
    this.camara.aspect = this.ancho / this.alto
    this.camara.updateProjectionMatrix()
  }

  /* ─────────────────────── mouse ─────────────────────── */

  private puntero(e: PointerEvent) {
    const r = this.lienzo.getBoundingClientRect()
    return new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
  }

  private alApretar = (e: PointerEvent) => {
    this.apretado = { x: e.clientX, y: e.clientY, t: performance.now() }
  }

  private alSoltar = (e: PointerEvent) => {
    const a = this.apretado
    this.apretado = null
    if (!a || hypot(e.clientX - a.x, e.clientY - a.y) > 5 || performance.now() - a.t > 500) return
    if (this.visita === 'ninguna' || this.huyendo) return
    this.raycaster.setFromCamera(this.puntero(e), this.camara)
    const hit = this.raycaster.ray.intersectPlane(this.suelo, new THREE.Vector3())
    if (!hit) return
    hit.x = clamp(hit.x, -LIMITE, LIMITE)
    hit.z = clamp(hit.z, -LIMITE, LIMITE)
    this.visitaPos.set(hit.x, 0, hit.z)
  }

  private alMover = (e: PointerEvent) => {
    this.hoverPendiente = { x: e.clientX, y: e.clientY }
  }

  private alSalir = () => {
    this.hoverPendiente = null
    this.ev.hover?.(null, 0, 0)
  }

  private revisarHover() {
    const h = this.hoverPendiente!
    this.hoverPendiente = null
    if (this.apretado) return
    const r = this.lienzo.getBoundingClientRect()
    const ndc = new THREE.Vector2(((h.x - r.left) / r.width) * 2 - 1, -((h.y - r.top) / r.height) * 2 + 1)
    this.raycaster.setFromCamera(ndc, this.camara)
    const hits = this.raycaster.intersectObject(this.robot, true)
    const hit = hits.find((x) => x.object.userData.pieza)
    this.ev.hover?.(hit ? (hit.object.userData.pieza as string) : null, h.x - r.left, h.y - r.top)
  }
}
