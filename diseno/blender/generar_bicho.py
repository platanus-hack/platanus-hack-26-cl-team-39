# Generador paramétrico del «bicho» — Platanus Hack 26, equipo 39
# Uso: Blender -b -P generar_bicho.py -- <carpeta_salida>
# Unidades: se modela en metros con el helper M (1 mm = 0.001); STL salen en mm.
import bpy, bmesh, math, json, os, sys
from mathutils import Vector, Matrix, Euler

M = 0.001
OUT = sys.argv[sys.argv.index("--") + 1]
for d in ("stl", "glb", "render"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
SPEC = json.load(open(os.path.join(os.path.dirname(__file__), "specs.json")))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = 'METRIC'
sc.unit_settings.length_unit = 'MILLIMETERS'

# ---------------------------------------------------------------- materiales
MATS = {}
def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)
def mat(name, hexc, metal=0.0, rough=0.55, emit=0.0):
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*srgb(hexc), 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*srgb(hexc), 1)
        b.inputs["Emission Strength"].default_value = emit
    MATS[name] = m; return m
PLA   = mat("Impreso PLA/PETG", "#2BF7D4", rough=0.45)
TPU   = mat("Impreso TPU/PETG", "#FF7A1A", rough=0.5)
ACR   = mat("Acrílico negro", "#0B0B0E", rough=0.18)
PCBG  = mat("PCB verde", "#0F5C2E", rough=0.4)
PCBB  = mat("PCB azul", "#123A8C", rough=0.4)
PCBK  = mat("PCB negro", "#151517", rough=0.35)
YEL   = mat("Motor TT", "#F2C200", rough=0.5)
RIM   = mat("Llanta", "#FFC21A", rough=0.45)
TIRE  = mat("Neumático", "#141414", rough=0.85)
BRASS = mat("Latón", "#C9A04A", metal=1, rough=0.3)
SRV   = mat("Servo MG995", "#1A1A1C", rough=0.5)
SRVB  = mat("Servo MG90S", "#1E4FD6", rough=0.5)
CELL  = mat("Celda 18650", "#2E7D4F", rough=0.35)
METAL = mat("Metal", "#A8ADB4", metal=1, rough=0.35)
LENS  = mat("Lente", "#050608", rough=0.05)
DARK  = mat("Plástico oscuro", "#2A2D33", rough=0.6)
FAB   = mat("Tela parlante", "#3A3D44", rough=0.95)
LED   = mat("LED", "#FFF4D6", emit=6)
WHITE = mat("Plástico claro", "#E8E8EA", rough=0.5)

# ---------------------------------------------------------------- utilidades
COL = None
def newcol(name):
    global COL
    c = bpy.data.collections.new(name); sc.collection.children.link(c); COL = c; return c

def _obj(name, bm, loc, rot, m, mass, tipo, etiqueta):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); COL.objects.link(o)
    o.location = Vector(loc) * M
    o.rotation_euler = Euler([math.radians(a) for a in rot])
    if m: me.materials.append(m)
    o["masa_g"] = float(mass); o["tipo"] = tipo; o["etiqueta"] = etiqueta or name
    return o

def box(name, sx, sy, sz, loc=(0, 0, 0), rot=(0, 0, 0), m=None, mass=0, tipo="componente", etiqueta=None):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts: v.co = Vector((v.co.x * sx * M, v.co.y * sy * M, v.co.z * sz * M))
    return _obj(name, bm, loc, rot, m, mass, tipo, etiqueta)

def cyl(name, r, h, loc=(0, 0, 0), rot=(0, 0, 0), m=None, mass=0, tipo="componente", etiqueta=None, seg=32, r2=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r * M,
                          radius2=(r if r2 is None else r2) * M, depth=h * M)
    return _obj(name, bm, loc, rot, m, mass, tipo, etiqueta)

def axis_rot(axis):
    return {"X": (0, 90, 0), "Y": (90, 0, 0), "Z": (0, 0, 0)}[axis]

def cutter_holes(pts, d, h=60, axis="Z", seg=20):
    """Un solo objeto con muchos cilindros (para un único boolean)."""
    bm = bmesh.new()
    R = Euler([math.radians(a) for a in axis_rot(axis)]).to_matrix().to_4x4()
    for p in pts:
        g = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=d / 2 * M, radius2=d / 2 * M, depth=h * M)
        bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(p) * M) @ R, verts=g["verts"])
    return _obj("_cut", bm, (0, 0, 0), (0, 0, 0), None, 0, "_", "_")

def boolean(o, others, op="DIFFERENCE"):
    for c in others:
        md = o.modifiers.new("b", "BOOLEAN"); md.object = c; md.operation = op; md.solver = 'EXACT'
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    o.modifiers.clear(); old = o.data; o.data = me
    bpy.data.meshes.remove(old)
    for c in others: bpy.data.objects.remove(c, do_unlink=True)
    o.data.transform(o.matrix_basis); o.matrix_basis = Matrix.Identity(4)   # hornea la posición en la malla
    return o

def parent(child, par, loc=None, rot=None):
    child.parent = par; child.matrix_parent_inverse = Matrix.Identity(4)
    if loc is not None: child.location = Vector(loc) * M
    if rot is not None: child.rotation_euler = Euler([math.radians(a) for a in rot])
    return child

def empty(name, loc=(0, 0, 0), par=None):
    e = bpy.data.objects.new(name, None); COL.objects.link(e)
    e.empty_display_size = 0.02; e["tipo"] = "articulacion"
    if par: parent(e, par)
    e.location = Vector(loc) * M
    return e

# ---------------------------------------------------------------- piezas impresas
PIEZAS = {}       # id -> ficha (se exporta el STL la primera vez)
def mesh_stats(o, prot):
    me = o.data.copy()
    me.transform(Euler([math.radians(a) for a in prot]).to_matrix().to_4x4())
    bm = bmesh.new(); bm.from_mesh(me)
    vol = abs(bm.calc_volume()) / M**3          # mm3
    area = sum(f.calc_area() for f in bm.faces) / M**2   # mm2
    xs = [v.co.x / M for v in bm.verts]; ys = [v.co.y / M for v in bm.verts]; zs = [v.co.z / M for v in bm.verts]
    bm.free()
    return me, vol, area, (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

def registrar(o, pid, nombre, material, relleno, soportes, prot, notas, densidad=1.24, paredes_mm=1.2):
    if pid in PIEZAS:
        PIEZAS[pid]["cantidad_total"] += 1; o["masa_g"] = PIEZAS[pid]["gramos"]; return
    me, vol, area, bb = mesh_stats(o, prot)
    me.transform(Matrix.Translation(Vector((-(bb[0] + bb[1]) / 2 * M, -(bb[2] + bb[3]) / 2 * M, -bb[4] * M))))
    t = bpy.data.objects.new("_stl", me); COL.objects.link(t)
    for ob in bpy.context.view_layer.objects: ob.select_set(False)
    t.select_set(True); bpy.context.view_layer.objects.active = t
    fn = os.path.join(OUT, "stl", f"{pid}_{nombre.lower().replace(' ', '_').replace('/', '-')}.stl")
    bpy.ops.wm.stl_export(filepath=fn, export_selected_objects=True, global_scale=1000.0, ascii_format=False)
    bpy.data.objects.remove(t, do_unlink=True)
    shell = min(vol, area * paredes_mm)
    extruido = shell + relleno * (vol - shell)
    gramos = extruido / 1000 * densidad
    horas = extruido / 4.0 / 3600 + 0.15       # ~4 mm3/s efectivos en impresora de escritorio a 0,2 mm
    PIEZAS[pid] = dict(id=pid, nombre=nombre, material=material, relleno=int(relleno * 100), soportes=soportes,
                       notas=notas, volumen_cm3=round(vol / 1000, 1), gramos=round(gramos, 1), horas=round(horas, 2),
                       medidas_mm=[round(bb[1] - bb[0], 1), round(bb[3] - bb[2], 1), round(bb[5] - bb[4], 1)],
                       stl=os.path.basename(fn), cantidad_total=1)
    o["masa_g"] = round(gramos, 1)

# --- P01 Cubierta modular (rejilla M3 cada 15 mm)
PI_C = (-10, 30); UPS_C = (-10, -32)
def p01_cubierta():
    o = box("P01 Cubierta", 200, 130, 4, (0, 0, 2), m=PLA, tipo="impreso", etiqueta="P01 · Cubierta modular con rejilla M3 cada 15 mm")
    cuts = []
    for cx in (100, -100):
        for cy in (65, -65):
            cuts.append(box("_c", 20, 20, 10, (cx, cy, 2), (0, 0, 45)))
    grid = []
    for i in range(13):
        for j in range(9):
            x = -90 + 15 * i; y = -60 + 15 * j
            if -56 <= x <= 36 and -2 <= y <= 62: continue           # bajo la Pi
            if -59 <= x <= 39 and -56 <= y <= -8: continue           # bajo la UPS
            grid.append((x, y, 2))
    cuts.append(cutter_holes(grid, 3.4, 10))
    pi_h = [(PI_C[0] + dx, PI_C[1] + dy, 2) for dx in (-39, 19) for dy in (-24.5, 24.5)]
    cuts.append(cutter_holes(pi_h, 2.7, 10))
    cuts.append(box("_c", 40, 8, 10, (-10, 0, 2)))           # pasacables central
    cuts.append(box("_c", 8, 30, 10, (40, -32, 2)))          # pasacables UPS
    return boolean(o, cuts)

# --- P02 Mástil con nervios
def p02_mastil(h=140):
    o = box("P02 Mástil", 38, 38, 4, (0, 0, 2), m=PLA, tipo="impreso", etiqueta="P02 · Mástil 22×22 con nervios")
    t = box("_t", 22, 22, h, (0, 0, 4 + h / 2))
    g = []
    for (x, y, r) in ((11, 0, (0, 45, 0)), (-11, 0, (0, 45, 0)), (0, 11, (45, 0, 0)), (0, -11, (45, 0, 0))):
        g.append(box("_g", 3 if y == 0 and x != 0 else 12, 12 if x == 0 else 3, 12, (x, y, 4), r))
    # orientar nervios: placas finas perpendiculares a la cara
    boolean(o, [t] + g, op="UNION")
    cuts = [box("_c", 17.2, 17.2, h + 20, (0, 0, 4 + h / 2 + 1)), box("_c", 60, 60, 20, (0, 0, -10)),
            box("_c", 14, 10, 12, (0, -10, 12)),
            cutter_holes([(sx * 15, sy * 15, 2) for sx in (-1, 1) for sy in (-1, 1)], 3.4, 10),
            cutter_holes([(0, 0, 4 + h - 8)], 3.2, 40, axis="X")]
    return boolean(o, cuts)

# --- P03 Cabeza sensora
def p03_cabeza():
    o = box("P03 Cabeza", 60, 50, 45, (0, 0, 22.5), m=PLA, tipo="impreso", etiqueta="P03 · Cabeza: cámara Pi + dToF + base del LiDAR")
    boolean(o, [box("_c", 54, 44, 39, (0, 0, 22.5))])
    boolean(o, [box("_s", 28.6, 28.6, 22, (0, 0, 11))], op="UNION")
    cuts = [box("_c", 22.6, 22.6, 21, (0, 0, 9.5)),
            cutter_holes([(30, 0, 31)], 9, 10, axis="X"),
            box("_c", 10, 16, 12, (30, 0, 13)),
            cutter_holes([(30, y, z) for y in (-10.5, 10.5) for z in (25, 37.5)], 2.2, 10, axis="X"),
            cutter_holes([(x, y, 45) for x in (-20, 20) for y in (-20, 20)] + [(0, 0, 45)], 3.4, 10),
            cutter_holes([(0, 0, 45)], 10, 10),
            box("_c", 10, 34, 24, (-30, 0, 30))]
    return boolean(o, cuts)

# --- P04 Soporte ESP32-CAM
def p04_pod():
    o = box("P04 Soporte ESP32-CAM", 30, 30, 3, (0, 0, 1.5), m=PLA, tipo="impreso", etiqueta="P04 · Soporte de cámara ESP32-CAM")
    add = [box("_f", 3, 32, 46, (13.5, 0, 26)),
           box("_r", 12, 2, 42, (6, 14.5, 24)), box("_r", 12, 2, 42, (6, -14.5, 24))]
    boolean(o, add, op="UNION")
    cuts = [cutter_holes([(30 / 2 - 2, 0, 34)], 9, 10, axis="X"),
            cutter_holes([(10.607, 10.607, 1.5), (-10.607, -10.607, 1.5)], 3.4, 10)]
    return boolean(o, cuts)

# --- P05 Parachoques frontal
def p05_parachoques():
    o = box("P05 Parachoques", 12, 150, 35, (0, 0, 0), m=TPU, tipo="impreso", etiqueta="P05 · Parachoques: ultrasonido + 2 ToF")
    add = [box("_t", 26, 16, 4, (-18, y, 8.5)) for y in (-50, 50)]
    boolean(o, add, op="UNION")
    cuts = [cutter_holes([(0, y, 0) for y in (-13, 13)], 16.5, 30, axis="X"),
            box("_c", 30, 8, 6, (0, -45, 0)), box("_c", 30, 8, 6, (0, 45, 0)),
            box("_c", 8, 120, 27, (-4, 0, 0)),
            cutter_holes([(-22, y, 8) for y in (-50, 50)], 3.4, 10)]
    return boolean(o, cuts)

# --- P06 Soporte de flujo óptico
def p06_flujo():
    o = box("P06 Soporte flujo óptico", 44, 44, 3, (0, 0, 1.5), m=PLA, tipo="impreso", etiqueta="P06 · Cámara de suelo ADNS-3080 (odometría)")
    boolean(o, [box("_b", 34, 34, 12, (0, 0, -6))], op="UNION")
    cuts = [box("_c", 30, 30, 14, (0, 0, -2)),
            cutter_holes([(0, 0, -10.5)], 15, 10),
            cutter_holes([(12, 12, -10.5)], 6, 10),
            cutter_holes([(sx * 18, sy * 18, 1.5) for sx in (-1, 1) for sy in (-1, 1)], 3.4, 10)]
    return boolean(o, cuts)

# --- P07 Torreta de servo (yaw del brazo o giro de la torre)
def p07_torreta():
    o = box("P07 Torreta servo", 56, 44, 30, (-5, 0, 15), m=PLA, tipo="impreso", etiqueta="P07 · Torreta con MG995 (giro)")
    cuts = [box("_c", 41.2, 20.4, 30, (-10, 0, 18.5)),
            box("_c", 12, 8, 8, (-30, 0, 6)),
            cutter_holes([(-5 + sx * 22.5, sy * 15, 0) for sx in (-1, 1) for sy in (-1, 1)], 3.4, 10),
            cutter_holes([(-10 + sx * 24.5, sy * 5, 30) for sx in (-1, 1) for sy in (-1, 1)], 2.8, 16)]
    return boolean(o, cuts)

# --- P08 Horquilla del hombro
def p08_horquilla():
    o = box("P08 Horquilla hombro", 50, 56, 4, (-5, 0, 2), m=PLA, tipo="impreso", etiqueta="P08 · Horquilla del hombro")
    add = [box("_s", 44, 4, 44, (-5, y, 26)) for y in (-25.5, 25.5)]
    boolean(o, add, op="UNION")
    cuts = [cutter_holes([(0, 0, 0)], 8, 12),
            cutter_holes([(sx * 7, 0, 2) for sx in (-1, 1)], 2.2, 10),
            cutter_holes([(0, 0, 30)], 8.5, 70, axis="Y"),
            cutter_holes([(-10 + sx * 24.5, y, 30) for sx in (-1, 1) for y in (-25.5, 25.5)], 2.8, 8, axis="Y")]
    return boolean(o, cuts)

# --- P09 Eslabón 1 (90 mm entre ejes)
def p09_eslabon1(L=90):
    o = box("P09 Eslabón 1", L, 6, 20, (L / 2, 0, 0), m=PLA, tipo="impreso", etiqueta="P09 · Eslabón 1 (hombro → codo, 90 mm)")
    add = [cyl("_e", 11, 6, (0, 0, 0), (90, 0, 0)), cyl("_e", 11, 6, (L, 0, 0), (90, 0, 0)),
           box("_p", 54, 6, 26, (L - 10, 0, 0))]
    boolean(o, add, op="UNION")
    cuts = [box("_c", 40, 10, 8, (L / 2 - 8, 0, 0)),
            cutter_holes([(0, 0, 0)], 6, 12, axis="Y"),
            cutter_holes([(sx * 7, 0, 0) for sx in (-1, 1)], 2.2, 12, axis="Y"),
            cutter_holes([(L - 10 + sx * 24.5, 0, sz * 5) for sx in (-1, 1) for sz in (-1, 1)], 2.8, 12, axis="Y"),
            cutter_holes([(L, 0, 0)], 8.5, 12, axis="Y")]
    return boolean(o, cuts)

# --- P10 Eslabón 2 con muñeca, dedo fijo y faro LED
def p10_eslabon2(L=80):
    o = box("P10 Eslabón 2", L, 5, 16, (L / 2, 0, 0), m=PLA, tipo="impreso", etiqueta="P10 · Eslabón 2 + pinza + faro LED")
    add = [cyl("_e", 9, 5, (0, 0, 0), (90, 0, 0)),
           box("_m", 32, 16, 30, (L + 8, 0, 0)),
           box("_d", 40, 5, 8, (L + 44, 0, -11)),
           box("_l", 4, 26, 26, (L + 26, 0, 14))]
    boolean(o, add, op="UNION")
    cuts = [box("_c", 23, 12.6, 40, (L + 8, 0, 4)),
            cutter_holes([(0, 0, 0)], 6, 12, axis="Y"),
            cutter_holes([(sx * 7, 0, 0) for sx in (-1, 1)], 2.2, 12, axis="Y"),
            cutter_holes([(L + 26, 0, 14)], 20.2, 10, axis="X"),
            box("_c", 30, 8, 8, (L / 2, 0, 0))]
    return boolean(o, cuts)

def p11_dedo():
    o = box("P11 Dedo móvil", 42, 5, 8, (21, 0, 0), m=PLA, tipo="impreso", etiqueta="P11 · Dedo móvil de la pinza")
    boolean(o, [cyl("_h", 7, 5, (0, 0, 0), (90, 0, 0))], op="UNION")
    return boolean(o, [cutter_holes([(0, 0, 0)], 5, 12, axis="Y")])

def p12_anillo():
    o = cyl("P12 Anillo parlante", 50, 3, (0, 0, 1.5), m=PLA, tipo="impreso", etiqueta="P12 · Anillo que sostiene el parlante omnidireccional", seg=64)
    add = [cyl("_r", 50, 8, (0, 0, 4), seg=64), box("_k", 32, 32, 16, (0, 0, -8))]
    boolean(o, add, op="UNION")
    cuts = [cyl("_c", 46.5, 10, (0, 0, 8), seg=64), box("_c", 22.6, 22.6, 60, (0, 0, 0)),
            cutter_holes([(0, -12, -8)], 3.2, 20, axis="Y"),
            cutter_holes([(30 * math.cos(a), 30 * math.sin(a), 1.5) for a in (0.3, 2.4, 4.5)], 12, 10)]
    return boolean(o, cuts)

def p13_plato():
    o = cyl("P13 Plato giratorio", 30, 5, (0, 0, 2.5), m=PLA, tipo="impreso", etiqueta="P13 · Plato giratorio de la torre", seg=64)
    cuts = [cutter_holes([(sx * 15, sy * 15, 2.5) for sx in (-1, 1) for sy in (-1, 1)], 3.4, 10),
            cutter_holes([(0, 0, 2.5)], 8, 10), cutter_holes([(sx * 7, 0, 2.5) for sx in (-1, 1)], 2.2, 10)]
    return boolean(o, cuts)

# ---------------------------------------------------------------- componentes
def c_pi(x, y, z, par):
    b = box("C Raspberry Pi 3B", 85, 56, 1.4, (x, y, z + 0.7), m=PCBG, mass=SPEC["pi3b_g"], etiqueta="Raspberry Pi 3B · cerebro y puente al servidor IA")
    parts = [box("C Pi USB/Ethernet", 21, 53, 15, (x - 32, y, z + 8.9), m=METAL),
             box("C Pi GPIO", 51, 5, 8.5, (x + 3, y + 25, z + 5.6), m=DARK),
             box("C Pi SoC", 14, 14, 1.2, (x + 4, y - 3, z + 2), m=METAL)]
    for p in [b] + parts: parent(p, par)
    return b

def c_esp32cam(x, y, z, rotz, par, nombre, etq):
    o = empty(nombre + " (grupo)", (x, y, z), par); o.rotation_euler.z = math.radians(rotz)
    b = parent(box(nombre, 1.6, 27, 40, m=PCBK, mass=SPEC["esp32cam_g"], etiqueta=etq), o, (2.7, 0, 24))
    parent(box(nombre + " módulo cámara", 6, 8.5, 8.5, m=DARK), o, (6.5, 0, 34))
    parent(cyl(nombre + " lente", 4, 9, m=LENS, rot=(0, 90, 0)), o, (12, 0, 34), (0, 90, 0))
    return o

def c_servo(nombre, big, loc, rot, par, etq):
    if big:
        dims, ear, mass, m = (40.7, 19.7, 42.9), 54, SPEC["mg995_g"], SRV
    else:
        dims, ear, mass, m = (22.5, 12.2, 28.5), 32.5, SPEC["mg90s_g"], SRVB
    g = empty(nombre + " (grupo)", loc, par); g.rotation_euler = Euler([math.radians(a) for a in rot])
    parent(box(nombre, *dims, m=m, mass=mass, etiqueta=etq), g, (0, 0, 0))
    parent(box(nombre + " orejas", ear, dims[1], 2.5, m=m), g, (0, 0, dims[2] * 0.12))
    sh = dims[0] / 2 - (10.2 if big else 6)
    parent(cyl(nombre + " eje", 3 if big else 2.4, 5, m=WHITE), g, (sh, 0, dims[2] / 2 + 2.5))
    return g

def c_tt(x, y, side, par):
    g = empty("C Motor TT (grupo)", (x, y, 32.5), par)
    parent(box("C Motor TT", 70, 22.5, 18.8, m=YEL, mass=SPEC["tt_motor_g"], etiqueta="Motorreductor TT 1:48"), g, (-24 * (1 if x > 0 else -1), 0, 1.5))
    return g

def c_rueda(x, y, par):
    g = empty("C Rueda (grupo)", (x, y, 32.5), par)
    parent(cyl("C Rueda", 32.5, 26, m=TIRE, mass=SPEC["rueda_g"], etiqueta="Rueda 65 mm", seg=40), g, (0, 0, 0), (90, 0, 0))
    parent(cyl("C Llanta", 22, 27, m=RIM, seg=10), g, (0, 0, 0), (90, 0, 0))
    return g

def c_standoff(x, y, z0, h, par):
    return parent(cyl("C Separador M3", 2.8, h, m=BRASS, mass=h * 0.08, seg=6), par, (x, y, z0 + h / 2))

def c_lidar(x, y, z, par):
    g = empty("C LiDAR (grupo)", (x, y, z), par)
    parent(box("C LiDAR 2D EAI", 86, 58, 22, m=DARK, mass=SPEC["lidar_g"], etiqueta="LiDAR 2D EAI/YDLIDAR (opcional) · mapa de 360°"), g, (0, 0, 11))
    parent(cyl("C LiDAR rotor", 33, 26, m=PCBK, seg=40), g, (8, 0, 35))
    parent(cyl("C LiDAR ventana", 33.5, 8, m=LENS, seg=40), g, (8, 0, 36))
    return g

# ---------------------------------------------------------------- módulo superior (común)
def modulo_superior(R, deck_z, brazo=True, torre=False, sufijo=""):
    """deck_z = cara inferior de la cubierta. Devuelve dict con objetos clave."""
    out = {}
    d = p01_cubierta(); registrar(d, "P01", "Cubierta", "PLA", .25, "No", (0, 0, 0),
                                   "Rejilla M3 cada 15 mm: cualquier módulo nuevo se atornilla sin rediseñar")
    parent(d, R, (0, 0, deck_z))
    top = deck_z + 4
    c_pi(PI_C[0], PI_C[1], top + 5, R)
    for dx in (-39, 19):
        for dy in (-24.5, 24.5):
            parent(cyl("C Separador M2.5", 2.5, 5, m=BRASS, seg=6), R, (PI_C[0] + dx, PI_C[1] + dy, top + 2.5))
    ups = parent(box("C UPS LX-2BUPS", 95, 42, 1.6, m=PCBB, mass=SPEC["ups_g"], etiqueta="UPS 5 V 3 A · lógica (Pi, ESP32)"), R, (UPS_C[0], UPS_C[1], top + 3))
    for dy in (-10, 10):
        parent(cyl("C Celda 18650 lógica", 9.3, 65, m=CELL, mass=SPEC["celda_g"], etiqueta="Samsung 30Q (lógica)", seg=24), R, (UPS_C[0], UPS_C[1] + dy, top + 13.3), (0, 90, 0))
    # cámaras ESP32-CAM
    pods = [((75, 45), 45, "C ESP32-CAM #1", "ESP32-CAM #1 · controlador + cámara del brazo"),
            ((-75, 45), 135, "C ESP32-CAM #2", "ESP32-CAM #2 · cámara trasera izquierda"),
            ((-75, -45), -135, "C ESP32-CAM #3", "ESP32-CAM #3 · cámara trasera derecha")]
    for (px, py), rz, n, e in pods:
        p = p04_pod(); registrar(p, "P04", "Soporte ESP32-CAM", "PLA", .25, "No", (0, 0, 0), "Uno por cámara; la lente asoma por el agujero de 9 mm")
        parent(p, R, (px, py, top), (0, 0, rz))
        c_esp32cam(px, py, top + 3, rz, R, n, e)
    # mástil / torre
    if torre:
        t = p07_torreta(); registrar(t, "P07", "Torreta servo", "PETG", .4, "No", (0, 0, 0), "Aloja un MG995 vertical")
        parent(t, R, (72.5, 0, top))
        c_servo("C MG995 giro torre", True, (72.5 - 10, 0, top + 3.5 + 21.45), (0, 0, 0), R, "MG995 · giro de la torre (pan)")
        J = empty("J_torre" + sufijo, (72.5, 0, top + 49.4), R)
        pl = p13_plato(); registrar(pl, "P13", "Plato giratorio", "PETG", .4, "No", (0, 0, 0), "Va sobre el horn del MG995")
        parent(pl, J, (0, 0, 0))
        mast_par, mast_loc = J, (0, 0, 5)
        out["J_torre"] = J
    else:
        mast_par, mast_loc = R, (-75, 0, top)
    m = p02_mastil(); registrar(m, "P02", "Mástil", "PETG", .4, "No (vertical)", (0, 0, 0),
                                "Imprimir en PETG; los nervios de la base reparten el golpe en una caída")
    parent(m, mast_par, mast_loc)
    mx, my, mz = mast_loc
    a = p12_anillo(); registrar(a, "P12", "Anillo parlante", "PLA", .25, "No", (0, 0, 0), "Abrazadera con prisionero M3 sobre el mástil")
    parent(a, mast_par, (mx, my, mz + 60))
    parent(cyl("C Parlante omnidireccional", 45, 25, m=FAB, mass=SPEC["parlante_g"], etiqueta="Micrófono-parlante omnidireccional (oye de dónde le hablan)", seg=48), mast_par, (mx, my, mz + 63 + 12.5))
    parent(cyl("C Parlante anillo LED", 30, 1.2, m=LED, seg=48), mast_par, (mx, my, mz + 88.6))
    h = p03_cabeza(); registrar(h, "P03", "Cabeza", "PLA", .25, "Sí (árbol, solo en la cavidad)", (180, 0, 0), "Imprimir boca abajo")
    parent(h, mast_par, (mx, my, mz + 124))
    parent(box("C Cámara Pi v1.3", 1, 25, 24, m=PCBG, mass=SPEC["picam_g"], etiqueta="Cámara Pi v1.3 · visión principal"), mast_par, (mx + 25.5, my, mz + 124 + 31))
    parent(cyl("C Cámara Pi lente", 4, 6, m=LENS), mast_par, (mx + 28.5, my, mz + 124 + 31), (0, 90, 0))
    parent(box("C Sensor dToF EAI", 8, 20, 10, m=PCBK, mass=SPEC["dtof_g"], etiqueta="Sensor dToF EAI (distancia al frente)"), mast_par, (mx + 25, my, mz + 124 + 13))
    c_lidar(mx, my, mz + 124 + 45, mast_par)
    out["mast_top"] = mz + 124 + 45 + 48
    # brazo
    if brazo:
        t = p07_torreta(); registrar(t, "P07", "Torreta servo", "PETG", .4, "No", (0, 0, 0), "Aloja un MG995 vertical")
        parent(t, R, (72.5, 0, top))
        c_servo("C MG995 base", True, (72.5 - 10, 0, top + 3.5 + 21.45), (0, 0, 0), R, "MG995 #1 · giro del brazo")
        Jy = empty("J_giro" + sufijo, (72.5, 0, top + 49.4), R)
        hq = p08_horquilla(); registrar(hq, "P08", "Horquilla hombro", "PETG", .4, "No", (0, 0, 0), "Tornillo del horn al centro")
        parent(hq, Jy, (0, 0, 0))
        c_servo("C MG995 hombro", True, (-10, 0, 30), (90, 0, 0), Jy, "MG995 #2 · hombro")
        Js = empty("J_hombro" + sufijo, (0, 0, 30), Jy)
        l1 = p09_eslabon1(); registrar(l1, "P09", "Eslabón 1", "PETG", .4, "No (de canto)", (90, 0, 0), "Imprimir de canto para que las capas sigan el largo")
        parent(l1, Js, (0, 31, 0))
        c_servo("C MG995 codo", True, (80, 13.5, 0), (-90, 0, 0), Js, "MG995 #3 · codo")
        Je = empty("J_codo" + sufijo, (90, 0, 0), Js)
        l2 = p10_eslabon2(); registrar(l2, "P10", "Eslabón 2", "PETG", .4, "Sí (bajo la muñeca)", (90, 0, 0), "Imprimir de canto")
        parent(l2, Je, (0, -12, 0))
        c_servo("C MG90S pinza", False, (88, -12, 0), (0, 0, 0), Je, "MG90S · pinza")
        parent(cyl("C LED 1 W", 10, 3, m=LED, mass=SPEC["led_g"], etiqueta="LED 1 W · faro del brazo (ilumina lo que toca)"), Je, (109, -12, 14), (0, 90, 0))
        Jp = empty("J_pinza" + sufijo, (95, -12, 11), Je)
        dd = p11_dedo(); registrar(dd, "P11", "Dedo móvil", "PETG", .4, "No", (90, 0, 0), "Va al horn del MG90S")
        parent(dd, Jp, (0, 0, 0), (0, 25, 0))
        Jy.rotation_euler.z = math.radians(0)
        Js.rotation_euler.y = math.radians(-60)
        Je.rotation_euler.y = math.radians(80)
        out.update(J_giro=Jy, J_hombro=Js, J_codo=Je, J_pinza=Jp)
    return out

# ---------------------------------------------------------------- chasis
def placa_4wd(name, z, R):
    o = box(name, 255, 147, 3, (0, 0, 0), m=ACR, mass=SPEC["placa_acrilico_g"], tipo="chasis", etiqueta="Placa acrílica del chasis 4WD")
    cuts = [box("_c", 50, 26, 10, (x, 0, 0)) for x in (-70, 0, 70)]
    cuts += [box("_c", 20, 20, 10, (sx * 125, sy * 70, 0), (0, 0, 45)) for sx in (-1, 1) for sy in (-1, 1)]
    cuts.append(cutter_holes([(x, y, 0) for x in range(-105, 106, 15) for y in (-60, -45, 45, 60) if abs(x) > 14], 3.2, 10))
    boolean(o, cuts)
    return parent(o, R, (0, 0, z))

def chasis_4wd(R):
    placa_4wd("X Placa inferior", 45, R); placa_4wd("X Placa superior", 78, R)
    for x, y in ((110, 55), (-110, 55), (110, -55), (-110, -55), (0, 62), (0, -62)):
        c_standoff(x, y, 46.5, 30, R)
    for sx in (-1, 1):
        for sy in (-1, 1):
            c_tt(sx * 62.5, sy * 59, sy, R); c_rueda(sx * 62.5, sy * 86, R)
    # piso 1: potencia
    parent(box("C Portapilas 2×18650 (Pack A)", 77, 41, 21, m=DARK, mass=SPEC["portapilas_g"], etiqueta="Pack A · 2×18650 en serie para motores y servos"), R, (20, 0, 46.5 + 10.5))
    for dy in (-10, 10):
        parent(cyl("C Celda 18650 potencia", 9.3, 65, m=CELL, mass=SPEC["celda_g"], seg=24), R, (20, dy, 46.5 + 12), (0, 90, 0))
    parent(box("C Fusible 5 A + interruptor", 30, 14, 14, m=DARK, mass=12, etiqueta="Fusible 5 A e interruptor"), R, (-45, 30, 46.5 + 7))
    # piso 2: control
    z2 = 79.5
    for (x, y, sx, sy, n, mm, e, mat_) in [
        (45, 30, 62, 25, "C PCA9685 #1", SPEC["pca_g"], "PCA9685 #1 (0x40) · PWM de motores", PCBB),
        (45, -30, 62, 25, "C PCA9685 #2", SPEC["pca_g"], "PCA9685 #2 (0x41) · PWM de servos", PCBB),
        (-20, 45, 21, 20, "C TB6612FNG #1", 3, "TB6612FNG #1 · motores izquierdos", PCBK),
        (-20, 20, 21, 20, "C TB6612FNG #2", 3, "TB6612FNG #2 · motores derechos", PCBK),
        (-25, -5, 28, 18, "C ADS1115 #1", 3, "ADS1115 #1 (0x48) · batería y analógicos", PCBB),
        (-25, -28, 28, 18, "C ADS1115 #2", 3, "ADS1115 #2 (0x49)", PCBB),
        (5, 20, 21, 16, "C MPU-6050", 3, "MPU-6050 · orientación y choques", PCBB),
        (-72, 30, 43, 21, "C LM2596 #1", SPEC["lm2596_g"], "LM2596 #1 · +VM 6,0 V motores", PCBB),
        (-72, -30, 43, 21, "C LM2596 #2", SPEC["lm2596_g"], "LM2596 #2 · +VSERVO 6,0 V", PCBB)]:
        parent(box(n, sx, sy, 1.6, m=mat_, mass=mm, etiqueta=e), R, (x, y, z2 + 4))
        parent(box(n + " componentes", sx * 0.7, sy * 0.6, 8 if "LM" in n else 3, m=DARK), R, (x, y, z2 + 4.8 + (4 if "LM" in n else 1.5)))
    parent(box("C Bornera GND común", 20, 10, 10, m=DARK, mass=6, etiqueta="Bornera de GND común"), R, (-72, 0, z2 + 5))
    for x, y in ((60, 60), (-60, 60), (60, -60), (-60, -60)):
        c_standoff(x, y, z2, 20, R)
    # bajo el chasis: cámara de suelo
    f = p06_flujo(); registrar(f, "P06", "Soporte flujo óptico", "PLA", .25, "No", (180, 0, 0), "Boca abajo. Lente M12 f=8 mm: desenroscar ~3 mm (o anillo espaciador) para enfocar el suelo a ~30 mm")
    parent(f, R, (0, 0, 40.5))
    parent(box("C ADNS-3080", 2, 28, 28, m=PCBB, mass=SPEC["adns_g"], etiqueta="ADNS-3080 · cámara de suelo (5ª cámara, odometría)"), R, (0, 0, 36), (0, 90, 0))
    parent(cyl("C ADNS lente M12", 7, 8, m=LENS), R, (0, 0, 31))
    # parachoques
    b = p05_parachoques(); registrar(b, "P05", "Parachoques", "TPU 95A o PETG", .3, "No (cara al plato)", (0, 90, 0), "En TPU absorbe el choque; en PETG es rígido")
    parent(b, R, (131, 0, 40))
    for y in (-13, 13):
        parent(cyl("C HC-SR04 transductor", 8, 12, m=METAL, mass=4), R, (129, y, 40), (0, 90, 0))
    parent(box("C HC-SR04", 2, 45, 20, m=PCBB, mass=SPEC["hcsr04_g"] - 8, etiqueta="HC-SR04 · ultrasonido frontal"), R, (122, 0, 40))
    for y in (-45, 45):
        parent(box("C VL53L3CX", 2, 13, 10, m=PCBK, mass=2, etiqueta="VL53 ToF · esquina frontal"), R, (124, y, 40))
    return 79.5 + 20

def chasis_oruga(R):
    for sy in (-1, 1):
        y = sy * 76
        g = box("X Oruga", 150, 42, 56, (0, y, 28), m=TIRE, mass=SPEC["oruga_g"] / 2, tipo="chasis", etiqueta="Módulo de oruga (chasis tanque del inventario)")
        boolean(g, [cyl("_e", 28, 42, (sx * 75, y, 28), (90, 0, 0), seg=40) for sx in (-1, 1)], op="UNION")
        parent(g, R)
        for x in (-75, -25, 25, 75):
            parent(cyl("X Rueda dentada", 22, 44, m=METAL, seg=24), R, (x, y, 28), (90, 0, 0))
    parent(box("X Casco", 170, 100, 40, m=ACR, mass=SPEC["casco_tanque_g"], tipo="chasis", etiqueta="Casco del tanque"), R, (0, 0, 35))
    for sy in (-1, 1):
        parent(box("C Motor oruga", 60, 25, 25, m=METAL, mass=SPEC["tt_motor_g"] * 1.5, etiqueta="Motor de oruga"), R, (-60, sy * 30, 30))
    parent(box("C Portapilas 2×18650 (Pack A)", 77, 41, 21, m=DARK, mass=SPEC["portapilas_g"] + 2 * SPEC["celda_g"], etiqueta="Pack A · motores y servos"), R, (25, 0, 45))
    for x, y in ((60, 60), (-60, 60), (60, -60), (-60, -60)):
        c_standoff(x, y, 55, 20, R)
    for (x, y, n, e) in [(40, 30, "C PCA9685 #1", "PCA9685 #1"), (40, -30, "C PCA9685 #2", "PCA9685 #2"), (-20, 30, "C TB6612FNG #1", "TB6612 (2 canales usados)"), (-70, 30, "C LM2596 #1", "LM2596 #1"), (-70, -30, "C LM2596 #2", "LM2596 #2"), (0, 0, "C MPU-6050", "MPU-6050")]:
        parent(box(n, 30 if "LM" not in n else 43, 20, 6, m=PCBB, mass=9, etiqueta=e), R, (x, y, 59))
    b = p05_parachoques(); registrar(b, "P05", "Parachoques", "TPU 95A o PETG", .3, "No (cara al plato)", (0, 90, 0), "")
    parent(b, R, (106, 0, 48.5))
    parent(box("C HC-SR04", 2, 45, 20, m=PCBB, mass=SPEC["hcsr04_g"], etiqueta="HC-SR04 · ultrasonido frontal"), R, (97, 0, 48.5))
    return 55 + 20

def chasis_redondo(R):
    for name, z in (("X Placa redonda inferior", 45), ("X Placa redonda superior", 78)):
        o = cyl(name, 100, 3, m=ACR, mass=SPEC["placa_redonda_g"], tipo="chasis", etiqueta="Placa redonda acrílica (chasis de la caja JOKU)", seg=72)
        boolean(o, [box("_c", 72, 32, 10, (0, sy * 72, 0)) for sy in (-1, 1)] + [cutter_holes([(x, y, 0) for x in range(-75, 76, 15) for y in (-30, -15, 0, 15, 30)], 3.2, 10)])
        parent(o, R, (0, 0, z))
    for x, y in ((70, 40), (-70, 40), (70, -40), (-70, -40)):
        c_standoff(x, y, 46.5, 30, R)
    for sy in (-1, 1):
        g = empty("C Motor TT (grupo)", (0, sy * 48, 32.5), R)
        parent(box("C Motor TT", 70, 22.5, 18.8, m=YEL, mass=SPEC["tt_motor_g"], etiqueta="Motorreductor TT 1:48"), g, (-24, 0, 1.5))
        c_rueda(0, sy * 72, R)
    for x in (80, -80):
        parent(cyl("C Rueda loca", 9, 36, m=METAL, mass=15, etiqueta="Rueda loca (bola)"), R, (x, 0, 43.5 - 18))
        parent(cyl("C Bola", 7, 14, m=METAL, seg=16), R, (x, 0, 7))
    parent(box("C Portapilas 2×18650 (Pack A)", 77, 41, 21, m=DARK, mass=SPEC["portapilas_g"] + 2 * SPEC["celda_g"], etiqueta="Pack A · motores y servo"), R, (-35, 0, 57))
    for (x, y, n, e) in [(40, 0, "C PCA9685 #1", "PCA9685 (motores + servo)"), (-30, 40, "C TB6612FNG #1", "TB6612 #1"), (-30, -40, "C LM2596 #1", "LM2596 #1"), (10, 45, "C MPU-6050", "MPU-6050")]:
        parent(box(n, 30 if "LM" not in n else 43, 20, 6, m=PCBB, mass=9, etiqueta=e), R, (x, y, 83))
    for x, y in ((60, 60), (-60, 60), (60, -60), (-60, -60)):
        c_standoff(x, y, 79.5, 20, R)
    f = p06_flujo(); registrar(f, "P06", "Soporte flujo óptico", "PLA", .25, "No", (180, 0, 0), "")
    parent(f, R, (40, 0, 40.5))
    parent(box("C ADNS-3080", 2, 28, 28, m=PCBB, mass=SPEC["adns_g"], etiqueta="ADNS-3080 · cámara de suelo"), R, (40, 0, 33), (0, 90, 0))
    return 79.5 + 20

# ---------------------------------------------------------------- análisis
def analizar(col, soporte, nombre, ruedas_motrices, torque_total_Nm, radio_rueda_m):
    bpy.context.view_layer.update()
    tot = 0.0; acc = Vector((0, 0, 0)); impresos = 0.0; filas = []
    for o in col.all_objects:
        mg = o.get("masa_g", 0) or 0
        if mg <= 0 or o.type != 'MESH': continue
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        c = sum(bb, Vector()) / 8
        tot += mg; acc += c * mg
        if o.get("tipo") == "impreso": impresos += mg
        filas.append((o.get("etiqueta", o.name), round(mg, 1)))
    extra = SPEC["cables_tornillos_g"]
    cg = acc / tot / M
    tot_g = tot + extra
    h = cg.z
    angs = []
    n = len(soporte)
    for i in range(n):
        a = Vector((*soporte[i], 0)); b = Vector((*soporte[(i + 1) % n], 0))
        p = Vector((cg.x, cg.y, 0))
        ab = b - a; t = max(0, min(1, (p - a).dot(ab) / ab.length_squared))
        d = (a + ab * t - p).length
        angs.append(math.degrees(math.atan2(d, h)))
    W = tot_g / 1000 * 9.81
    F_stall = torque_total_Nm / radio_rueda_m
    pend_max = math.degrees(math.asin(min(1, F_stall * 0.5 / W)))
    return dict(opcion=nombre, masa_total_g=round(tot_g), masa_impresa_g=round(impresos), cg_mm=[round(cg.x, 1), round(cg.y, 1), round(cg.z, 1)],
                angulo_vuelco_min=round(min(angs), 1), angulos_vuelco=[round(a, 1) for a in angs],
                fuerza_traccion_bloqueo_N=round(F_stall, 1), pendiente_max_50pct_deg=round(pend_max, 1),
                componentes=sorted(filas, key=lambda r: -r[1]))

# ---------------------------------------------------------------- construcción de las 3 opciones
RES = {}
def opcion(clave, titulo, chasis_fn, soporte, brazo, torre, motrices, rr):
    newcol(titulo)
    R = empty("R_" + clave, (0, 0, 0)); R["tipo"] = "raiz"
    deck_z = chasis_fn(R)
    info = modulo_superior(R, deck_z, brazo=brazo, torre=torre, sufijo="")
    torque = motrices * SPEC["tt_stall_Nm"]
    RES[clave] = analizar(COL, soporte, titulo, motrices, torque, rr)
    bpy.context.view_layer.update()
    RES[clave]["altura_total_mm"] = round(max((o.matrix_world @ Vector(c)).z for o in COL.all_objects if o.type == 'MESH' for c in o.bound_box) / M)
    RES[clave]["largo_mm"] = round((max((o.matrix_world @ Vector(c)).x for o in COL.all_objects if o.type == 'MESH' for c in o.bound_box) - min((o.matrix_world @ Vector(c)).x for o in COL.all_objects if o.type == 'MESH' for c in o.bound_box)) / M)
    RES[clave]["cubierta_z_mm"] = deck_z
    # exportar GLB de la opción
    for ob in bpy.context.view_layer.objects: ob.select_set(False)
    for ob in COL.all_objects: ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "glb", f"bicho_{clave}.glb"), export_format='GLB',
                              use_selection=True, export_extras=True, export_apply=False, export_yup=True)
    return R

RA = opcion("A", "Opción A · Explorador 4WD", chasis_4wd, [(62.5, 86 + 13), (62.5, -86 - 13), (-62.5, -86 - 13), (-62.5, 86 + 13)], True, False, 4, 0.0325)
RB = opcion("B", "Opción B · Tanque de orugas", chasis_oruga, [(103, 97), (103, -97), (-103, -97), (-103, 97)], True, False, 2, 0.028)
RC = opcion("C", "Opción C · Torre 2WD", chasis_redondo, [(80 + 7, 0), (0, 72 + 13), (-80 - 7, 0), (0, -72 - 13)], False, True, 2, 0.0325)
# Para la opción B el torque por motor de oruga es mayor; se ajusta en el JSON
RB_extra = SPEC.get("oruga_stall_Nm_por_motor")

# ---------------------------------------------------------------- bandeja de impresión (render)
newcol("Bandeja de impresión")
import glob
xoff = 0; yoff = 0; rowh = 0
for f in sorted(glob.glob(os.path.join(OUT, "stl", "*.stl"))):
    bpy.ops.wm.stl_import(filepath=f, global_scale=0.001)
    o = bpy.context.selected_objects[0]
    for c in o.users_collection: c.objects.unlink(o)
    COL.objects.link(o); o.data.materials.append(TPU if "P05" in f else PLA)
    for pg in o.data.polygons: pg.use_smooth = False
    dx = o.dimensions.x / M; dy = o.dimensions.y / M
    if xoff + dx > 420: xoff = 0; yoff += rowh + 15; rowh = 0
    o.location = Vector((xoff + dx / 2, yoff + dy / 2, 0)) * M
    xoff += dx + 15; rowh = max(rowh, dy)
BANDEJA = COL

# ---------------------------------------------------------------- render
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.render.film_transparent = True
sc.render.resolution_x, sc.render.resolution_y = 1600, 1100
sc.eevee.taa_render_samples = 48
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.9, 0.92, 0.95, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("Sol", bpy.data.lights.new("Sol", "SUN")); sc.collection.objects.link(sun)
sun.data.energy = 3.5; sun.rotation_euler = Euler((math.radians(50), math.radians(10), math.radians(30)))
fill = bpy.data.objects.new("Relleno", bpy.data.lights.new("Relleno", "AREA")); sc.collection.objects.link(fill)
fill.data.energy = 60; fill.data.size = 1.2; fill.location = (-0.5, -0.6, 0.6)
fill.rotation_euler = (Vector((0, 0, 0.12)) - fill.location).to_track_quat('-Z', 'Y').to_euler()
cam = bpy.data.objects.new("Cámara", bpy.data.cameras.new("Cámara")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 50

def solo(col):
    for c in bpy.data.collections:
        lc = bpy.context.view_layer.layer_collection.children.get(c.name)
        if lc: lc.exclude = (c != col)

def render(col, fname, az, el, dist, target):
    solo(col)
    a, e = math.radians(az), math.radians(el)
    t = Vector(target) * M
    cam.location = t + Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))) * dist
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(OUT, "render", fname); bpy.ops.render.render(write_still=True)

cols = {c.name: c for c in bpy.data.collections}
for clave, nombre in (("A", "Opción A · Explorador 4WD"), ("B", "Opción B · Tanque de orugas"), ("C", "Opción C · Torre 2WD")):
    render(cols[nombre], f"bicho_{clave}.png", 35, 22, 0.95, (20, 0, 150))
render(cols["Opción A · Explorador 4WD"], "bicho_A_lateral.png", 90, 5, 0.95, (20, 0, 150))
render(cols["Opción A · Explorador 4WD"], "bicho_A_planta.png", 0.01, 89, 0.9, (20, 0, 100))
sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 0.46
render(BANDEJA, "bandeja_impresion.png", -90, 60, 0.9, (205, 130, 0))
cam.data.type = 'PERSP'

# layout del .blend: separar las opciones
RB.location.x = 0.45; RC.location.x = 0.9
for c in bpy.data.collections:
    lc = bpy.context.view_layer.layer_collection.children.get(c.name)
    if lc: lc.exclude = False
lc = bpy.context.view_layer.layer_collection.children.get("Bandeja de impresión"); lc.hide_viewport = True
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "bicho_prototipos.blend"))

json.dump(dict(opciones=RES, piezas=list(PIEZAS.values())), open(os.path.join(OUT, "resultado.json"), "w"), ensure_ascii=False, indent=1)
print("OK", json.dumps({k: {kk: v[kk] for kk in ("masa_total_g", "cg_mm", "angulo_vuelco_min", "altura_total_mm")} for k, v in RES.items()}))
