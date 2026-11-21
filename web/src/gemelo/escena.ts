// Gemelo digital del Bicho: el chasis impreso (diseno/modelos/bicho_V1.glb → /modelos/bicho_V1.glb) con el brazo v4
// definitivo (/bim/brazo.glb, el mismo de la vista Brazo) montado en la cubierta, y los sensores en vivo encima.
// Metros, +Y arriba, el robot mira a +X.
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { formula, type Articulacion } from '../brazo/visor'

export type Pieza = { nodo: string; etiqueta: string; item?: number; masa?: number; tipo?: string; superficie?: string }

/** Lo que el gemelo sabe del bicho real en este momento (todo opcional: muestra lo que llegue). */
export type Vivo = {
  luz?: boolean
  verde?: boolean
  rojo?: boolean
  tempCpu?: number
  vozAngulo?: number
  vozActiva?: boolean
  camara?: string | null
  servos?: Record<number, number>
  avance?: { dx: number; dy: number } | null // metros desde la última lectura (flujo óptico)
}


function eje(txt: string) {
  const t = txt.trim().toUpperCase()
  const s = t.startsWith('-') ? -1 : 1
  const c = t.replace(/[+-]/g, '')
  return new THREE.Vector3(c === 'X' ? s : 0, c === 'Y' ? s : 0, c === 'Z' ? s : 0)
}

type Junta = { obj: THREE.Object3D; base: THREE.Quaternion; eje: THREE.Vector3; f: (d: number) => number; espejo?: THREE.Object3D; baseEspejo?: THREE.Quaternion }

export class Gemelo3D {
  private renderer: THREE.WebGLRenderer
  private scene = new THREE.Scene()
  private cam: THREE.PerspectiveCamera
  private orbit: OrbitControls
  private ro: ResizeObserver
  private raf = 0
  private robot = new THREE.Group() // se mueve por el patio
  private juntas = new Map<string, Junta>()
  private angulos = new Map<string, number>()
  private destino = new Map<string, number>()
  private piezas: THREE.Object3D[] = []
  private resaltadas: [THREE.Mesh, THREE.Material | THREE.Material[]][] = []
  private leds: Record<'luz' | 'verde' | 'rojo', THREE.Mesh> = {} as never
  private ledLuz: Record<'luz' | 'verde' | 'rojo', THREE.PointLight> = {} as never
  private piMallas: THREE.Mesh[] = []
  private voz = new THREE.Group()
  private vozFlecha!: THREE.Mesh
  private vozAnillo!: THREE.Mesh
  private pantalla!: THREE.Mesh
  private pantallaTex: THREE.Texture | null = null
  private camUrl: string | null = null
  private frustum = new THREE.Group()
  private estela: THREE.Line
  private estelaPts: THREE.Vector3[] = []
  private camPos = new THREE.Vector3(0.17, 0.16, 0)
  private vivo: Vivo = {}
  private t0 = performance.now()
  cargado = false

  constructor(private host: HTMLElement, private avisos: { clic: (p: Pieza | null) => void }) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
    this.renderer.outputColorSpace = THREE.SRGBColorSpace
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    this.renderer.shadowMap.enabled = true
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap
    host.appendChild(this.renderer.domElement)
    this.scene.environment = new THREE.PMREMGenerator(this.renderer).fromScene(new RoomEnvironment(), 0.04).texture
    this.cam = new THREE.PerspectiveCamera(34, 1, 0.01, 30)
    this.cam.position.set(0.95, 0.68, 1.0)
    this.orbit = new OrbitControls(this.cam, this.renderer.domElement)
    this.orbit.enableDamping = true
    this.orbit.target.set(0, 0.2, 0)
    this.orbit.maxPolarAngle = Math.PI * 0.49
    this.orbit.minDistance = 0.18
    this.orbit.maxDistance = 4

    const sol = new THREE.DirectionalLight(0xfff3e2, 2.2)
    sol.position.set(1.2, 2.2, 0.9)
    sol.castShadow = true
    sol.shadow.mapSize.set(2048, 2048)
    Object.assign(sol.shadow.camera, { left: -1.2, right: 1.2, top: 1.2, bottom: -1.2 })
    sol.shadow.bias = -0.0004
    this.scene.add(sol, new THREE.HemisphereLight(0xfff6ec, 0xcfd8c9, 0.55))
    const piso = new THREE.Mesh(new THREE.PlaneGeometry(6, 6), new THREE.MeshStandardMaterial({ color: 0xdfe6d3, roughness: 0.95 }))
    piso.rotation.x = -Math.PI / 2
    piso.receiveShadow = true
    const grilla = new THREE.GridHelper(6, 60, 0xbcc8b0, 0xcdd6c2)
    grilla.position.y = 0.0005
    this.scene.add(piso, grilla, this.robot)

    // estela de la odometría (flujo óptico)
    this.estela = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0x007aff }))
    this.scene.add(this.estela)

    // anillo y flecha de la dirección de la voz (ReSpeaker XVF3800)
    this.vozAnillo = new THREE.Mesh(new THREE.RingGeometry(0.27, 0.285, 64), new THREE.MeshBasicMaterial({ color: 0xaf52de, transparent: true, opacity: 0.35, side: THREE.DoubleSide }))
    this.vozAnillo.rotation.x = -Math.PI / 2
    this.vozAnillo.position.y = 0.002
    const flecha = new THREE.Shape()
    flecha.moveTo(0.3, 0)
    flecha.lineTo(0.38, 0.035)
    flecha.lineTo(0.38, -0.035)
    flecha.closePath()
    this.vozFlecha = new THREE.Mesh(new THREE.ShapeGeometry(flecha), new THREE.MeshBasicMaterial({ color: 0xaf52de, side: THREE.DoubleSide, transparent: true, opacity: 0.9 }))
    this.vozFlecha.rotation.x = -Math.PI / 2
    this.vozFlecha.position.y = 0.003
    this.voz.add(this.vozAnillo, this.vozFlecha)
    this.voz.visible = false
    this.robot.add(this.voz)

    // pantalla flotante con la última imagen de la cámara del bicho
    this.pantalla = new THREE.Mesh(new THREE.PlaneGeometry(0.24, 0.18), new THREE.MeshBasicMaterial({ color: 0x11161c, side: THREE.DoubleSide }))
    this.pantalla.visible = false
    this.scene.add(this.pantalla)
    this.robot.add(this.frustum)

    const r = new THREE.Raycaster()
    const p = new THREE.Vector2()
    let abajo: [number, number] | null = null
    this.renderer.domElement.addEventListener('pointerdown', (e) => (abajo = [e.clientX, e.clientY]))
    this.renderer.domElement.addEventListener('pointerup', (e) => {
      if (!abajo || Math.hypot(e.clientX - abajo[0], e.clientY - abajo[1]) > 5) return
      const b = this.renderer.domElement.getBoundingClientRect()
      p.set(((e.clientX - b.left) / b.width) * 2 - 1, -((e.clientY - b.top) / b.height) * 2 + 1)
      r.setFromCamera(p, this.cam)
      const hit = r.intersectObjects(this.piezas, true).find((h) => h.object.visible)
      let o: THREE.Object3D | null = hit?.object ?? null
      while (o && !o.userData.etiqueta) o = o.parent
      if (!o) return this.avisos.clic(null)
      this.resaltar(o.name)
      this.avisos.clic(this.ficha(o))
    })

    this.ro = new ResizeObserver(() => this.resize())
    this.ro.observe(host)
    this.resize()
    const loop = () => {
      this.raf = requestAnimationFrame(loop)
      this.tick()
    }
    loop()
  }

  private ficha(o: THREE.Object3D): Pieza {
    let masa = 0
    o.traverse((x) => (masa += Number(x.userData.masa_g) || 0))
    const u = o.userData
    return { nodo: o.name, etiqueta: String(u.etiqueta), item: u.item, masa: masa || undefined, tipo: u.tipo, superficie: u.superficie }
  }

  async cargar(articulaciones: Articulacion[]) {
    const loader = new GLTFLoader()
    const [chasisG, brazoG] = await Promise.all([loader.loadAsync('/modelos/bicho_V1.glb'), loader.loadAsync('/bim/brazo.glb')])
    const chasis = chasisG.scene
    chasis.updateMatrixWorld(true)
    // el brazo viejo del modelo V1 se reemplaza por el brazo v4: se toma su lugar en la cubierta y se esconde
    const viejo = chasis.getObjectByName('G_brazo')
    const jg = chasis.getObjectByName('J_giro')
    const base = new THREE.Vector3()
    if (viejo) {
      const caja = new THREE.Box3().setFromObject(viejo)
      base.set(0, caja.min.y, 0)
      viejo.visible = false
    }
    if (jg) {
      const w = jg.getWorldPosition(new THREE.Vector3())
      base.x = w.x
      base.z = w.z
    }
    const brazo = brazoG.scene
    const cb = new THREE.Box3().setFromObject(brazo)
    brazo.position.set(base.x, base.y - cb.min.y, base.z)
    chasis.add(brazo)
    // la cámara CSI va en el soporte frontal (bandeja B15), no en la muñeca
    const front = chasis.getObjectByName('S_cam_esp1')
    if (front) {
      front.getWorldPosition(this.camPos)
      this.camPos.y += 0.01
    }
    chasis.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) {
        o.castShadow = true
        o.receiveShadow = true
      }
      if (o.userData.etiqueta) this.piezas.push(o)
    })
    chasis.getObjectByName('G_pi')?.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) {
        const m = o as THREE.Mesh
        m.material = (m.material as THREE.MeshStandardMaterial).clone()
        this.piMallas.push(m)
      }
    })
    this.robot.add(chasis)

    for (const a of articulaciones) {
      const obj = brazo.getObjectByName(a.nodo)
      const f = formula(a.angulo_nodo)
      if (!obj || !f) continue
      const esp = a.espejo ? brazo.getObjectByName(a.espejo) ?? undefined : undefined
      this.juntas.set(a.nodo, { obj, base: obj.quaternion.clone(), eje: eje(a.eje_gltf), f, espejo: esp, baseEspejo: esp?.quaternion.clone() })
      this.angulos.set(a.nodo, a.inicio)
      this.destino.set(a.nodo, a.inicio)
      this.aplicar(a.nodo, a.inicio)
    }

    // LED de las luces que el bicho ya maneja (GPIO 17, 27 y 22), sobre la cubierta, atrás del brazo
    const cubierta = chasis.getObjectByName('P20 cubierta')
    const top = cubierta ? new THREE.Box3().setFromObject(cubierta).max.y : 0.14
    const defs: [keyof typeof this.leds, number, number][] = [
      ['luz', 0xfff1b8, -0.035],
      ['verde', 0x34c759, 0],
      ['rojo', 0xff3b30, 0.035],
    ]
    for (const [k, color, z] of defs) {
      const m = new THREE.Mesh(new THREE.SphereGeometry(0.009, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2), new THREE.MeshStandardMaterial({ color: 0x3a3a3c, emissive: color, emissiveIntensity: 0, roughness: 0.3 }))
      m.position.set(-0.13, top, z)
      m.name = `LED_${k}`
      m.userData.etiqueta = { luz: 'Luz de prueba · GPIO 17 (comando luz)', verde: 'Luz verde · GPIO 27 (comandos verde, si)', rojo: 'Luz roja · GPIO 22 (comandos rojo, no)' }[k]
      const pl = new THREE.PointLight(color, 0, 0.35)
      pl.position.set(-0.13, top + 0.02, z)
      this.robot.add(m, pl)
      this.leds[k] = m
      this.ledLuz[k] = pl
      this.piezas.push(m)
    }

    // campo de visión de la cámara (ov5647: 54° × 41°)
    const L = 0.55
    const tx = Math.tan(THREE.MathUtils.degToRad(27)) * L
    const ty = Math.tan(THREE.MathUtils.degToRad(20.5)) * L
    const o = this.camPos
    const P = [o, o.clone().add(new THREE.Vector3(L, ty, tx)), o.clone().add(new THREE.Vector3(L, ty, -tx)), o.clone().add(new THREE.Vector3(L, -ty, -tx)), o.clone().add(new THREE.Vector3(L, -ty, tx))]
    const lineas = new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints([P[0], P[1], P[0], P[2], P[0], P[3], P[0], P[4], P[1], P[2], P[2], P[3], P[3], P[4], P[4], P[1]]),
      new THREE.LineBasicMaterial({ color: 0x007aff, transparent: true, opacity: 0.6 }),
    )
    this.frustum.add(lineas)
    this.frustum.visible = false
    this.cargado = true
  }

  /** Mueve una articulación (grados de servo) de inmediato. */
  private aplicar(nodo: string, deg: number) {
    const j = this.juntas.get(nodo)
    if (!j) return
    const rad = THREE.MathUtils.degToRad(j.f(deg))
    j.obj.quaternion.copy(j.base).multiply(new THREE.Quaternion().setFromAxisAngle(j.eje, rad))
    if (j.espejo && j.baseEspejo) j.espejo.quaternion.copy(j.baseEspejo).multiply(new THREE.Quaternion().setFromAxisAngle(j.eje, -rad))
  }

  /** Lleva una articulación a `deg` con un movimiento suave (como un servo real). */
  setAngulo(nodo: string, deg: number) {
    this.destino.set(nodo, deg)
  }
  angulo(nodo: string) {
    return this.angulos.get(nodo) ?? 0
  }

  setVivo(v: Vivo) {
    this.vivo = { ...this.vivo, ...v }
    if (v.camara !== undefined && v.camara !== this.camUrl) {
      this.camUrl = v.camara
      if (v.camara) {
        new THREE.TextureLoader().load(v.camara, (t) => {
          t.colorSpace = THREE.SRGBColorSpace
          this.pantallaTex?.dispose()
          this.pantallaTex = t
          ;(this.pantalla.material as THREE.MeshBasicMaterial).map = t
          ;(this.pantalla.material as THREE.MeshBasicMaterial).color.set(0xffffff)
          ;(this.pantalla.material as THREE.MeshBasicMaterial).needsUpdate = true
        })
      }
    }
    if (v.avance) {
      const r = this.robot
      // dx hacia adelante, dy hacia el lado; se integra en el marco del robot
      const h = r.rotation.y
      r.position.x += Math.cos(h) * v.avance.dx + Math.sin(h) * v.avance.dy
      r.position.z += -Math.sin(h) * v.avance.dx + Math.cos(h) * v.avance.dy
      this.estelaPts.push(r.position.clone().setY(0.003))
      if (this.estelaPts.length > 600) this.estelaPts.shift()
      this.estela.geometry.setFromPoints(this.estelaPts)
    }
    if (v.servos) {
      for (const [nodo, j] of this.juntas) {
        void j
        const canal = Gemelo3D.canalDe.get(nodo)
        if (canal !== undefined && v.servos[canal] !== undefined) this.setAngulo(nodo, v.servos[canal])
      }
    }
  }
  static canalDe = new Map<string, number>()

  volverAlCentro() {
    this.robot.position.set(0, 0, 0)
    this.robot.rotation.set(0, 0, 0)
    this.estelaPts = []
    this.estela.geometry.setFromPoints([])
  }

  resaltar(nodo: string | null) {
    for (const [m, mat] of this.resaltadas) m.material = mat
    this.resaltadas = []
    if (!nodo) return
    const o = this.robot.getObjectByName(nodo)
    if (!o) return
    o.traverse((x) => {
      const m = x as THREE.Mesh
      if (!m.isMesh) return
      this.resaltadas.push([m, m.material])
      const c = (Array.isArray(m.material) ? m.material[0] : m.material).clone() as THREE.MeshStandardMaterial
      if (c.emissive) {
        c.emissive = new THREE.Color(0x007aff)
        c.emissiveIntensity = 0.45
      }
      m.material = c
    })
  }

  private tick() {
    const t = (performance.now() - this.t0) / 1000
    // servos: se acercan al destino a ~240°/s, como un MG995 sin carga
    for (const [nodo, d] of this.destino) {
      const a = this.angulos.get(nodo) ?? d
      if (Math.abs(d - a) > 0.05) {
        const n = a + Math.sign(d - a) * Math.min(Math.abs(d - a), 4)
        this.angulos.set(nodo, n)
        this.aplicar(nodo, n)
      }
    }
    const v = this.vivo
    for (const k of ['luz', 'verde', 'rojo'] as const) {
      const on = !!v[k]
      const m = this.leds[k]?.material as THREE.MeshStandardMaterial | undefined
      if (m) m.emissiveIntensity += ((on ? 2.2 : 0) - m.emissiveIntensity) * 0.25
      if (this.ledLuz[k]) this.ledLuz[k].intensity = on ? 0.5 : 0
    }
    // la Pi se pone roja si se calienta (40 °C normal, 75 °C límite de la Pi 3)
    if (v.tempCpu !== undefined) {
      const k = THREE.MathUtils.clamp((v.tempCpu - 45) / 30, 0, 1)
      for (const m of this.piMallas) {
        const mat = m.material as THREE.MeshStandardMaterial
        if (mat.emissive && !this.resaltadas.some(([x]) => x === m)) {
          mat.emissive.setRGB(1, 0.25, 0.1)
          mat.emissiveIntensity = k * 0.8
        }
      }
    }
    if (v.vozAngulo !== undefined) {
      this.voz.visible = true
      // el ReSpeaker da 0–359°; 0° = frente del bicho, creciendo hacia su izquierda
      this.voz.rotation.y = THREE.MathUtils.degToRad(v.vozAngulo)
      const pulso = v.vozActiva ? 0.55 + 0.35 * Math.sin(t * 10) : 0.25
      ;(this.vozAnillo.material as THREE.MeshBasicMaterial).opacity = pulso
      ;(this.vozFlecha.material as THREE.MeshBasicMaterial).opacity = v.vozActiva ? 1 : 0.45
    }
    this.frustum.visible = !!this.camUrl
    if (this.camUrl) {
      this.pantalla.visible = true
      const w = this.robot.localToWorld(new THREE.Vector3(-0.05, 0.52, 0))
      this.pantalla.position.copy(w)
      this.pantalla.quaternion.copy(this.cam.quaternion)
    }
    this.orbit.target.lerp(new THREE.Vector3(this.robot.position.x, 0.2, this.robot.position.z), 0.04)
    this.orbit.update()
    this.renderer.render(this.scene, this.cam)
  }

  private resize() {
    const r = this.host.getBoundingClientRect()
    if (!r.width || !r.height) return
    this.renderer.setSize(r.width, r.height, false)
    this.renderer.domElement.style.width = '100%'
    this.renderer.domElement.style.height = '100%'
    this.cam.aspect = r.width / r.height
    this.cam.updateProjectionMatrix()
  }

  destruir() {
    cancelAnimationFrame(this.raf)
    this.ro.disconnect()
    this.orbit.dispose()
    this.renderer.dispose()
    this.renderer.domElement.remove()
  }
}
