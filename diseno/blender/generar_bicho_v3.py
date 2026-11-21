# Bicho v3 — estructura impresa de 32 × 20 cm (placa estándar con rejilla de 10 mm) + 3 distribuciones
# Uso: Blender -b -P generar_bicho_v2.py -- <carpeta_salida>
# Novedades v2: componentes con detalle real, brazo al centro, LiDAR 2D fijo en el brazo,
# 8 celdas 18650 en el piso 1, Pi en el piso 2 cerca del brazo (cable FFC), 2 sensores de flujo abajo.
import bpy, bmesh, math, json, os, sys
from mathutils import Vector, Matrix, Euler

M = 0.001
OUT = sys.argv[sys.argv.index("--") + 1]
for d in ("stl", "glb", "render"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = 'METRIC'; sc.unit_settings.length_unit = 'MILLIMETERS'

# ------------------------------------------------------------------ materiales
MATS = {}
def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)
def mat(name, hexc, metal=0.0, rough=0.5, emit=0.0, alpha=1.0):
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*srgb(hexc), 1)
    b.inputs["Metallic"].default_value = metal; b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*srgb(hexc), 1); b.inputs["Emission Strength"].default_value = emit
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha; m.blend_method = 'BLEND'
    MATS[name] = m; return m
PLA    = mat("Impreso PETG menta", "#5FE3C8", rough=0.42)
GRAF   = mat("Impreso PLA grafito", "#30343B", rough=0.55)
TPU    = mat("Impreso TPU naranjo", "#FF8A3D", rough=0.55)
ACR    = mat("Acrilico negro", "#0A0A0C", rough=0.08)
PVC    = mat("PVC espumado blanco", "#F2F2EE", rough=0.75)
PCBG   = mat("PCB verde", "#1F6B3A", rough=0.35)
PCBB   = mat("PCB azul", "#1B4FA8", rough=0.35)
PCBK   = mat("PCB negro", "#16171A", rough=0.3)
PCBR   = mat("PCB rojo", "#B3262A", rough=0.35)
PCBP   = mat("PCB morado", "#5B2A86", rough=0.35)
YEL    = mat("Caja TT amarilla", "#F6C21C", rough=0.45)
RIM    = mat("Llanta amarilla", "#FFC51F", rough=0.4)
TIRE   = mat("Goma", "#151515", rough=0.92)
BRASS  = mat("Laton", "#C8A04A", metal=1, rough=0.28)
STEEL  = mat("Acero", "#B9BEC4", metal=1, rough=0.25)
ALU    = mat("Aluminio", "#D7DBDF", metal=1, rough=0.32)
GOLD   = mat("Pines dorados", "#D9B24C", metal=1, rough=0.25)
BLK    = mat("Plastico negro", "#1C1D20", rough=0.55)
BLK2   = mat("Plastico negro mate", "#2B2D31", rough=0.8)
WHITE  = mat("Plastico blanco", "#EDEDEA", rough=0.5)
SRVB   = mat("Servo azul translucido", "#2A63E0", rough=0.3)
CELLP  = mat("Celda 30Q rosada", "#E0457B", rough=0.3)
CELLG  = mat("Celda verde", "#2F8F5B", rough=0.3)
COPPER = mat("Cobre", "#B87333", metal=1, rough=0.35)
LENS   = mat("Lente", "#06070A", rough=0.04)
FAB    = mat("Tela parlante", "#34373D", rough=0.95)
LEDW   = mat("LED blanco", "#FFF6DE", emit=5)
LEDC   = mat("LED anillo", "#FFD36B", emit=4)
CAP    = mat("Condensador", "#2B2F6B", rough=0.4)
CABLE_R = mat("Cable rojo", "#C62828", rough=0.6)
CABLE_N = mat("Cable negro", "#151515", rough=0.6)
FFC    = mat("Cable FFC", "#E9E4D6", rough=0.5)

# ------------------------------------------------------------------ utilidades
COL = None
def newcol(name):
    global COL
    c = bpy.data.collections.new(name); sc.collection.children.link(c); COL = c; return c

def parent(child, par, loc=None, rot=None):
    child.parent = par; child.matrix_parent_inverse = Matrix.Identity(4)
    if loc is not None: child.location = Vector(loc) * M
    if rot is not None: child.rotation_euler = Euler([math.radians(a) for a in rot])
    return child

def empty(name, loc=(0, 0, 0), par=None, rot=None, **props):
    e = bpy.data.objects.new(name, None); COL.objects.link(e); e.empty_display_size = 0.02
    if par: parent(e, par)
    e.location = Vector(loc) * M
    if rot: e.rotation_euler = Euler([math.radians(a) for a in rot])
    for k, v in props.items(): e[k] = v
    return e

def axis_rot(axis):
    return {"X": (0, 90, 0), "Y": (90, 0, 0), "Z": (0, 0, 0)}[axis]

def smooth(me, ang=35):
    for p in me.polygons: p.use_smooth = True
    try: me.set_sharp_from_angle(angle=math.radians(ang))
    except Exception: pass

class Comp:
    """Un componente = una malla con varios materiales (un nodo en el GLB)."""
    def __init__(s, name): s.name = name; s.bm = bmesh.new(); s.mats = []
    def _add(s, bm2, m, loc, rot):
        if m not in s.mats: s.mats.append(m)
        mi = s.mats.index(m)
        for f in bm2.faces: f.material_index = mi
        R = Euler([math.radians(a) for a in rot]).to_matrix().to_4x4()
        bmesh.ops.transform(bm2, matrix=Matrix.Translation(Vector(loc) * M) @ R, verts=bm2.verts)
        me = bpy.data.meshes.new("_t"); bm2.to_mesh(me); bm2.free(); s.bm.from_mesh(me); bpy.data.meshes.remove(me)
        return s
    def box(s, dims, loc=(0, 0, 0), m=BLK, bev=0.0, rot=(0, 0, 0)):
        bm2 = bmesh.new(); bmesh.ops.create_cube(bm2, size=1)
        for v in bm2.verts: v.co = Vector((v.co.x * dims[0] * M, v.co.y * dims[1] * M, v.co.z * dims[2] * M))
        if bev > 0:
            bmesh.ops.bevel(bm2, geom=list(bm2.edges), offset=bev * M, segments=2, affect='EDGES', profile=0.5, clamp_overlap=True)
        return s._add(bm2, m, loc, rot)
    def cyl(s, r, h, loc=(0, 0, 0), m=BLK, axis='Z', seg=24, r2=None, rot=None, bev=0.0):
        bm2 = bmesh.new()
        bmesh.ops.create_cone(bm2, cap_ends=True, segments=seg, radius1=r * M, radius2=(r if r2 is None else r2) * M, depth=h * M)
        if bev > 0:
            caps = [e for e in bm2.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-9]
            bmesh.ops.bevel(bm2, geom=caps, offset=bev * M, segments=2, affect='EDGES', profile=0.5, clamp_overlap=True)
        return s._add(bm2, m, loc, rot if rot else axis_rot(axis))
    def ring(s, r_out, r_in, h, loc=(0, 0, 0), m=BLK, axis='Z', seg=48):
        bm2 = bmesh.new()
        g1 = bmesh.ops.create_circle(bm2, cap_ends=False, segments=seg, radius=r_out * M)
        g2 = bmesh.ops.create_circle(bm2, cap_ends=False, segments=seg, radius=r_in * M)
        bmesh.ops.bridge_loops(bm2, edges=list(bm2.edges))
        ext = bmesh.ops.extrude_face_region(bm2, geom=list(bm2.faces))
        bmesh.ops.translate(bm2, vec=(0, 0, h * M), verts=[v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)])
        bmesh.ops.translate(bm2, vec=(0, 0, -h / 2 * M), verts=bm2.verts)
        bmesh.ops.recalc_face_normals(bm2, faces=bm2.faces)
        return s._add(bm2, m, loc, axis_rot(axis))
    def pins(s, nx, ny, pitch, loc, h=8.5, base=2.5):
        x0 = loc[0] - (nx - 1) * pitch / 2; y0 = loc[1] - (ny - 1) * pitch / 2
        s.box((nx * pitch, ny * pitch, base), (loc[0], loc[1], loc[2] + base / 2), BLK)
        for i in range(nx):
            for j in range(ny):
                s.box((0.64, 0.64, h), (x0 + i * pitch, y0 + j * pitch, loc[2] + h / 2 - 1), GOLD)
        return s
    def done(s, par, loc=(0, 0, 0), rot=(0, 0, 0), mass=0, tipo="componente", etiqueta=None, **props):
        me = bpy.data.meshes.new(s.name); s.bm.to_mesh(me); s.bm.free()
        for m in s.mats: me.materials.append(m)
        smooth(me)
        o = bpy.data.objects.new(s.name, me); COL.objects.link(o)
        o["masa_g"] = float(mass); o["tipo"] = tipo; o["etiqueta"] = etiqueta or s.name
        for k, v in props.items(): o[k] = v
        parent(o, par, loc, rot)
        return o

# ------------------------------------------------------------------ booleanos (piezas impresas)
def _obj(name, bm, m):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); COL.objects.link(o)
    if m: me.materials.append(m)
    return o
def pbox(name, sx, sy, sz, loc=(0, 0, 0), rot=(0, 0, 0), m=None):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts: v.co = Vector((v.co.x * sx * M, v.co.y * sy * M, v.co.z * sz * M))
    o = _obj(name, bm, m); o.location = Vector(loc) * M; o.rotation_euler = Euler([math.radians(a) for a in rot]); return o
def pcyl(name, r, h, loc=(0, 0, 0), rot=(0, 0, 0), m=None, seg=40):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r * M, radius2=r * M, depth=h * M)
    o = _obj(name, bm, m); o.location = Vector(loc) * M; o.rotation_euler = Euler([math.radians(a) for a in rot]); return o
def holes(pts, d, h=60, axis="Z", seg=20):
    bm = bmesh.new(); R = Euler([math.radians(a) for a in axis_rot(axis)]).to_matrix().to_4x4()
    for p in pts:
        g = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=d / 2 * M, radius2=d / 2 * M, depth=h * M)
        bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(p) * M) @ R, verts=g["verts"])
    return _obj("_cut", bm, None)
def boolean(o, others, op="DIFFERENCE"):
    for c in others:
        md = o.modifiers.new("b", "BOOLEAN"); md.object = c; md.operation = op; md.solver = 'EXACT'
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    o.modifiers.clear(); old = o.data; o.data = me; bpy.data.meshes.remove(old)
    for c in others: bpy.data.objects.remove(c, do_unlink=True)
    o.data.transform(o.matrix_basis); o.matrix_basis = Matrix.Identity(4)
    return o
def soften(o, w=0.7):
    md = o.modifiers.new("bev", "BEVEL"); md.width = w * M; md.segments = 2; md.limit_method = 'ANGLE'
    md.angle_limit = math.radians(40); md.harden_normals = False
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    o.modifiers.clear(); old = o.data; o.data = me; bpy.data.meshes.remove(old)
    smooth(o.data, 40)
    return o

PIEZAS = {}
def registrar(o, pid, nombre, material, relleno, soportes, prot, notas, versiones):
    o["tipo"] = "impreso"; o["pieza"] = pid
    if pid in PIEZAS:
        P = PIEZAS[pid]; P["cantidad_total"] += 1; o["masa_g"] = P["gramos"]
        for v in versiones:
            if v not in P["versiones"]: P["versiones"].append(v)
        o["etiqueta"] = f"{pid} · {nombre}"; return
    me = o.data.copy(); me.transform(Euler([math.radians(a) for a in prot]).to_matrix().to_4x4())
    bm = bmesh.new(); bm.from_mesh(me)
    vol = abs(bm.calc_volume()) / M**3; area = sum(f.calc_area() for f in bm.faces) / M**2
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]; zs = [v.co.z for v in bm.verts]; bm.free()
    me.transform(Matrix.Translation(Vector((-(min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2, -min(zs)))))
    bmc = bmesh.new(); bmc.from_mesh(me)
    bmesh.ops.remove_doubles(bmc, verts=bmc.verts, dist=0.002 * M)
    bmesh.ops.dissolve_degenerate(bmc, edges=bmc.edges, dist=0.002 * M)
    bnd = [e for e in bmc.edges if e.is_boundary]
    if bnd: bmesh.ops.holes_fill(bmc, edges=bnd, sides=0)
    bmesh.ops.triangulate(bmc, faces=bmc.faces)
    bmesh.ops.recalc_face_normals(bmc, faces=bmc.faces); bmc.to_mesh(me); bmc.free()
    t = bpy.data.objects.new("_stl", me); COL.objects.link(t)
    bpy.context.view_layer.update()
    for ob in list(bpy.context.view_layer.objects): ob.select_set(False)
    t.select_set(True); bpy.context.view_layer.objects.active = t
    slug = nombre.lower().replace(' ', '_').replace('/', '-')
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")): slug = slug.replace(a, b)
    fn = os.path.join(OUT, "stl", f"{pid}_{slug}.stl")
    bpy.ops.wm.stl_export(filepath=fn, export_selected_objects=True, global_scale=1000.0, ascii_format=False)
    bpy.data.objects.remove(t, do_unlink=True)
    shell = min(vol, area * 1.2); extr = shell + relleno * (vol - shell)
    dens = 1.27 if "PETG" in material else 1.21 if "TPU" in material else 1.24
    g = extr / 1000 * dens; h = extr / 4.0 / 3600 + 0.15
    PIEZAS[pid] = dict(id=pid, nombre=nombre, material=material, relleno=int(relleno * 100), soportes=soportes, notas=notas,
                       volumen_cm3=round(vol / 1000, 1), gramos=round(g, 1), horas=round(h, 2),
                       medidas_mm=[round((max(xs) - min(xs)) / M), round((max(ys) - min(ys)) / M), round((max(zs) - min(zs)) / M)],
                       stl=os.path.basename(fn), cantidad_total=1, versiones=list(versiones))
    o["masa_g"] = round(g, 1); o["etiqueta"] = f"{pid} · {nombre}"

# ------------------------------------------------------------------ componentes realistas
def c_pi3b(par, loc, rot=(0, 0, 0)):
    c = Comp("Raspberry Pi 3B")
    c.box((85, 56, 1.4), (0, 0, 0.7), PCBG, bev=0.6)
    for hx in (-39, 19):
        for hy in (-24.5, 24.5): c.cyl(3.1, 1.5, (hx, hy, 0.75), GOLD, seg=16)
    c.box((21.3, 16, 13.5), (-32.5, -19.5, 8.15), ALU, bev=0.4)           # Ethernet
    c.box((17.4, 13.3, 15.6), (-34.5, 2.5, 9.2), ALU, bev=0.4)            # USB 1
    c.box((17.4, 13.3, 15.6), (-34.5, 20.5, 9.2), ALU, bev=0.4)           # USB 2
    for y in (2.5, 20.5): c.box((1.5, 11, 5.5), (-43.2, y, 9.2), BLK)
    c.pins(20, 2, 2.54, (3.5, 24.5, 1.4))                                   # GPIO 40
    c.box((14, 14, 1.2), (2, -2, 2.0), BLK2, bev=0.3)                      # SoC
    c.box((14.2, 14.2, 6), (2, -2, 5.6), BLK2)                             # disipador base
    for i in range(6): c.box((14.2, 1.1, 6), (2, -8.5 + i * 2.6, 9.6), BLK2)
    c.box((9, 9, 1), (-15, -15, 1.9), BLK)                                  # LAN9514
    c.box((15, 11.5, 6.3), (10, -24.6, 4.5), ALU, bev=0.3)                  # HDMI
    c.box((8, 5.6, 3), (32, -25.3, 2.9), ALU)                               # micro USB
    c.cyl(3, 12, (-12, -26, 4.4), BLK, axis='Y')                            # audio
    c.box((3, 22, 5.5), (-10, -14, 4.1), WHITE)                             # CSI
    c.box((3, 22, 5.5), (40, 0, 4.1), WHITE)                                # DSI
    return c

def c_esp32cam():
    c = Comp("ESP32-CAM")
    c.box((27, 40.5, 1.0), (0, 0, 0.5), PCBK, bev=0.3)
    c.box((18, 25.5, 3.2), (0, 5.5, 2.6), STEEL, bev=0.3)                  # módulo ESP32 blindado
    c.box((8.5, 8.5, 5), (0, -11, 3.5), BLK, bev=0.4)                       # cámara
    c.cyl(3.6, 4, (0, -11, 8), BLK2, seg=24); c.cyl(2.4, 0.6, (0, -11, 10.1), LENS, seg=24)
    c.box((3.5, 3.5, 1.2), (9, -16, 1.6), LEDW)                             # flash
    c.box((14, 15, 2), (0, 9, -1), ALU)                                     # microSD (abajo)
    c.pins(8, 1, 2.54, (11.2, 0, -1.0), h=6, base=2.5)
    c.pins(8, 1, 2.54, (-11.2, 0, -1.0), h=6, base=2.5)
    return c

def c_picam():
    c = Comp("Cámara Pi v1.3")
    c.box((25, 24, 1), (0, 0, 0.5), PCBG, bev=0.3)
    for x in (-10.5, 10.5):
        for y in (-6.25, 6.25): c.cyl(1.2, 1.1, (x, y + 2, 0.55), GOLD, seg=12)
    c.box((8.5, 8.5, 4.5), (0, 3.5, 3.25), BLK, bev=0.4)
    c.cyl(3.5, 2.5, (0, 3.5, 6.75), BLK2); c.cyl(2.2, 0.4, (0, 3.5, 8.1), LENS)
    c.box((21, 5.5, 2.5), (0, -9.5, -1.25), BLK)                            # conector FFC
    return c

def c_ring24():
    c = Comp("Anillo WS2812 24 LED")
    c.ring(33.5, 26, 1.6, (0, 0, 0.8), PCBK, seg=64)
    for i in range(24):
        a = 2 * math.pi * i / 24; r = 29.75
        c.box((5, 5, 1.6), (r * math.cos(a), r * math.sin(a), 2.4), LEDC, rot=(0, 0, math.degrees(a)))
    return c

def c_lidar_eai():
    c = Comp("LiDAR 2D EAI")
    c.box((32, 24, 1.6), (0, 0, 0.8), PCBK, bev=0.4)
    c.box((24, 16, 7), (0, 0, 5.1), BLK, bev=1.0)
    c.cyl(3.2, 2.2, (-6, 0, 9.7), LENS, seg=24); c.cyl(4.2, 2.2, (6, 0, 9.7), BLK2, seg=24); c.cyl(3.0, 0.4, (6, 0, 10.9), LENS)
    c.box((6, 4, 3), (14, 0, 2.5), WHITE)                                   # conector
    return c

def c_tt_motor():
    c = Comp("Motorreductor TT")
    c.box((47, 22.4, 18.8), (-8.5, 0, 0), YEL, bev=1.2)
    c.cyl(9.8, 26, (-45, 0, 0), STEEL, axis='X', seg=28, bev=0.6)
    c.box((26, 15.2, 18.8), (-45, 0, 0), STEEL)                              # caras planas de la carcasa
    c.box((4, 12, 10), (-59.5, 0, 0), WHITE, bev=0.6)
    c.cyl(2.7, 9, (11, 0, 0), WHITE, axis='Y', seg=12)                      # eje doble D
    c.cyl(3.5, 25, (-20, 0, 6), YEL, axis='Y', seg=16)                       # orejas de montaje
    c.cyl(0.9, 14, (-61, 4, 3), CABLE_R, axis='X', seg=8); c.cyl(0.9, 14, (-61, -4, 3), CABLE_N, axis='X', seg=8)
    return c

def c_wheel():
    c = Comp("Rueda 65 mm")
    c.cyl(32.5, 26.5, (0, 0, 0), TIRE, axis='Y', seg=56, bev=3.0)
    for i in range(36):
        a = 360 * i / 36
        c.box((3.2, 27, 1.6), (32.6 * math.cos(math.radians(a)), 0, 32.6 * math.sin(math.radians(a))), BLK2, rot=(0, -a + 90, 0))
    c.cyl(23, 27.0, (0, 0, 0), RIM, axis='Y', seg=48)
    c.cyl(20.5, 27.4, (0, 2.5, 0), BLK, axis='Y', seg=48)
    for i in range(5):
        a = 72 * i
        c.box((19, 4, 6), (10 * math.cos(math.radians(a)), -12.2, 10 * math.sin(math.radians(a))), RIM, rot=(0, -a, 0), bev=0.8)
    c.cyl(6.5, 6, (0, -11.5, 0), RIM, axis='Y', seg=24)
    return c

def c_cell(m=CELLP):
    c = Comp("Celda 18650")
    c.cyl(9.2, 63.4, (0, 0, 0), m, axis='X', seg=28, bev=0.8)
    c.cyl(9.0, 0.8, (31.9, 0, 0), STEEL, axis='X', seg=28)
    c.cyl(3.5, 1.2, (32.6, 0, 0), STEEL, axis='X', seg=16)
    c.cyl(9.0, 0.8, (-31.9, 0, 0), STEEL, axis='X', seg=28)
    return c

def c_holder4():
    c = Comp("Portapilas 4×18650")
    c.box((77, 80, 2), (0, 0, 1), BLK, bev=0.6)
    for x in (-37.5, 37.5): c.box((2, 80, 20), (x, 0, 10), BLK, bev=0.5)
    for i in range(5): c.box((73, 1.2, 13), (0, -39.4 + i * 19.7, 7.5), BLK)
    for i in range(4):
        y = -29.5 + i * 19.7
        c.cyl(4, 6, (33, y, 10), STEEL, axis='X', seg=10)                    # resortes
    return c

def c_mg995(horn=True):
    c = Comp("Servo MG995")
    c.box((40.7, 19.7, 37), (0, 0, 18.5), BLK, bev=0.8)
    c.box((54, 19.7, 2.6), (0, 0, 27.6), BLK, bev=0.6)
    for x in (-24.5, 24.5):
        for y in (-5, 5): c.cyl(1.9, 2.8, (x, y, 27.6), STEEL, seg=10)
    c.cyl(6.5, 4, (10.2, 0, 39), BLK, seg=28)
    c.cyl(2.9, 4.5, (10.2, 0, 42.6), BRASS, seg=16)
    if horn:
        c.cyl(10.5, 2.4, (10.2, 0, 45.6), WHITE, seg=32)
        c.box((40, 7, 2.4), (10.2, 0, 45.6), WHITE, bev=0.8); c.box((7, 40, 2.4), (10.2, 0, 45.6), WHITE, bev=0.8)
    c.box((6, 3, 4), (-23, 0, 6), BLK2)
    c.cyl(0.8, 14, (-30, -1.6, 6), mat("Cable cafe", "#5D3A1A"), axis='X', seg=8)
    c.cyl(0.8, 14, (-30, 0, 6), CABLE_R, axis='X', seg=8)
    c.cyl(0.8, 14, (-30, 1.6, 6), mat("Cable naranjo", "#F28C28"), axis='X', seg=8)
    return c

def c_mg90s():
    c = Comp("Servo MG90S")
    c.box((22.8, 12.2, 22.5), (0, 0, 11.25), SRVB, bev=0.6)
    c.box((32.5, 12.2, 2.4), (0, 0, 16.5), SRVB, bev=0.4)
    c.cyl(6.1, 4.5, (5.9, 0, 24.7), SRVB, seg=24); c.cyl(2.3, 3.5, (5.9, 0, 28.5), BRASS, seg=12)
    c.box((20, 5, 1.6), (5.9, 0, 30.6), WHITE, bev=0.5); c.cyl(3.5, 1.6, (5.9, 0, 30.6), WHITE)
    return c

def c_board(name, w, d, m, chips=(), pins=None):
    c = Comp(name); c.box((w, d, 1.6), (0, 0, 0.8), m, bev=0.4)
    for (cx, cy, cw, cd, ch, cm) in chips: c.box((cw, cd, ch), (cx, cy, 1.6 + ch / 2), cm, bev=min(cw, cd, ch) * 0.12)
    if pins: c.pins(*pins)
    return c

def c_pca9685():
    c = c_board("PCA9685", 62, 25.4, PCBB, chips=[(-2, -3, 8, 8, 1.2, BLK2), (22, 3, 6, 6, 9, CAP)])
    c.pins(16, 3, 2.54, (-6, 6, 1.6), h=8.5, base=2.5)
    c.pins(1, 6, 2.54, (-28, -2, 1.6), h=8.5, base=2.5)
    c.box((8, 7, 8), (25, -7, 5.6), mat("Bornera azul", "#2A6BD6"))
    return c

def c_lm2596():
    c = c_board("LM2596", 43, 21, PCBB, chips=[(-6, 0, 12, 12, 7, BLK2), (8, 3, 4, 7, 4.5, BLK)])
    c.cyl(4, 10, (13, -5, 6.6), CAP); c.cyl(4, 10, (-17, 5, 6.6), CAP)
    c.box((9.5, 4.5, 10), (-4, -7, 6.6), mat("Trimpot azul", "#2E7FE0")); c.cyl(1.2, 1.5, (-4, -7, 12.3), GOLD)
    return c

def c_hcsr04():
    c = c_board("HC-SR04", 45, 20, PCBB, chips=[(0, 7, 6, 3, 2, ALU)])
    for x in (-13, 13):
        c.cyl(8, 12, (x, 0, 7.6), ALU, seg=32); c.cyl(7, 0.6, (x, 0, 13.7), BLK2, seg=32)
    c.pins(4, 1, 2.54, (0, -9, -1.0), h=6, base=2.5)
    return c

def c_adns():
    c = c_board("ADNS-3080", 30, 30, PCBB, chips=[(0, 0, 10, 10, 3, BLK2)])
    c.cyl(7, 13, (0, 0, 8.6), BLK, seg=28); c.cyl(5, 0.4, (0, 0, 15.2), LENS)
    c.box((3, 3, 1.2), (11, 11, 2.2), LEDW)
    return c

def c_speaker():
    c = Comp("Parlante omnidireccional")
    c.cyl(45, 22, (0, 0, 11), BLK, seg=64, bev=4)
    c.cyl(40, 1.5, (0, 0, 22.4), FAB, seg=64)
    c.ring(30, 27, 1.2, (0, 0, 23.4), LEDW, seg=64)
    c.cyl(7, 1.2, (0, 0, 23.4), BLK2, seg=24)
    return c

def c_ups():
    c = c_board("UPS LX-2BUPS", 90, 42, PCBB, chips=[(38, -12, 8, 7, 3, ALU), (38, 12, 9, 6, 3, ALU)])
    c.box((77, 40, 2), (-4, 0, 2.6), BLK)
    for x in (-42, 34): c.box((2, 40, 18), (x, 0, 10.6), BLK)
    for y in (-10, 10):
        c.cyl(9.2, 63.4, (-4, y, 12.8), CELLP, axis='X', seg=28, bev=0.8)
    return c

# ------------------------------------------------------------------ piezas impresas v3 (rejilla de 10 mm)
L, W, T, RIB, PITCH = 320.0, 200.0, 4.0, 6.0, 10
WHEEL_X, MOTOR_Y, WHEEL_Y = 104.0, 80.0, 114.0
RIB_X = 40
ENTERA = True                              # placa de una sola pieza (sin junta); requiere cama ≥ 330 × 210
ZB, ZT, ZK = 45.0, 89.0, 133.0          # cara inferior de placa: inferior, superior, cubierta
DT = ZK + T                              # cara superior de la cubierta
COLS = [(sx * x, sy * 80) for x in (130, 20) for sx in (-1, 1) for sy in (-1, 1)]

def grid_pts():
    pts = []
    for x in range(-int(L / 2 - 10), int(L / 2 - 10) + 1, PITCH):
        for y in range(-int(W / 2 - 10), int(W / 2 - 10) + 1, PITCH):
            if abs(x) == RIB_X: continue                                   # nervios transversales
            if not ENTERA and (abs(x) < 6 or (x == -10 and any(abs(y - s * 45) < 12 for s in (-1, 1)))): continue
            pts.append((x, y))
    return pts

def dovetail(cl):
    bm = bmesh.new(); vs = []
    for z in (-30, 30):
        for (x, y) in ((0.6, -5 - cl), (-14 - cl, -8.5 - cl), (-14 - cl, 8.5 + cl), (0.6, 5 + cl)):
            vs.append(bm.verts.new(Vector((x * M, y * M, z * M))))
    bmesh.ops.convex_hull(bm, input=vs)
    return bm

def pc_placa_completa():
    o = pbox("_placa", L, W, T, (0, 0, T / 2), m=GRAF)
    add = [pbox("_r", L - 30, 3, RIB, (0, sy * (W / 2 - 1.5), -RIB / 2)) for sy in (-1, 1)]
    add += [pbox("_r", 3, W - 30, RIB, (sx * (L / 2 - 1.5), 0, -RIB / 2)) for sx in (-1, 1)]
    add += [pbox("_r", 3, W - 6, RIB, (sx * RIB_X, 0, -RIB / 2)) for sx in (-1, 1)]
    boolean(o, add, op="UNION")
    boolean(o, [pbox("_c", 30.02, 30.02, 40, (sx * L / 2, sy * W / 2, 0)) for sx in (-1, 1) for sy in (-1, 1)])
    boolean(o, [pcyl("_k", 15, T, (sx * (L / 2 - 15), sy * (W / 2 - 15), T / 2), seg=48) for sx in (-1, 1) for sy in (-1, 1)], op="UNION")
    cuts = [pbox("_n", 76, 12, 40, (sx * WHEEL_X, sy * W / 2, 0)) for sx in (-1, 1) for sy in (-1, 1)]
    cuts.append(holes([(x, y, 0) for x, y in grid_pts()], 3.4, 30, seg=12))
    cuts.append(pbox("_c", 40, 14, 40, (-130, 0, 0)))                     # pasacables trasero
    cuts.append(pbox("_c", 40, 14, 40, (130, 0, 0)))                      # pasacables delantero
    return boolean(o, cuts)

def mitades(plate):
    """Corta la placa en dos mitades (≤214 mm) unidas con 2 colas de milano + empalme atornillado."""
    pF = plate.copy(); pF.data = plate.data.copy(); COL.objects.link(pF)
    reg = pbox("_reg", 260, 260, 60, (130, 0, 0))
    tabs = []
    for sy in (-1, 1):
        t = _obj("_tab", dovetail(0), None); t.location = Vector((0, sy * 45, 0)) * M; tabs.append(t)
    boolean(reg, tabs, op="UNION")
    boolean(pF, [reg], op="INTERSECT"); pF.name = "P20 Placa estándar · mitad delantera"
    reg2 = pbox("_reg", 260, 260, 60, (130 - 0.15, 0, 0))
    tabs = []
    for sy in (-1, 1):
        t = _obj("_tab", dovetail(0.15), None); t.location = Vector((0, sy * 45, 0)) * M; tabs.append(t)
    boolean(reg2, tabs, op="UNION")
    boolean(plate, [reg2]); plate.name = "P21 Placa estándar · mitad trasera"
    return pF, plate

def pc_empalme():
    o = pbox("P22 Empalme central", 30, W - 20, 4, (0, 0, -2), m=GRAF)
    return soften(boolean(o, [holes([(sx * 10, y, -2) for sx in (-1, 1) for y in (-80, -30, -10, 10, 30, 80)], 3.4, 10)]), 0.5)

def pc_columna():
    o = pcyl("P23 Columna 40 mm", 4.6, 40, (0, 0, 20), m=GRAF, seg=6)
    return boolean(o, [holes([(0, 0, 20)], 3.4, 50)])

def pc_cuna_motor():
    o = pbox("P24 Cuna motor TT", 50, 34, 3, (0, 0, -1.5), m=GRAF)
    boolean(o, [pbox("_w", 44, 3, 21, (-3, sy * 12.9, -3 - 9.75 + 0.75)) for sy in (-1, 1)], op="UNION")
    cuts = [holes([(sx * 20, sy * 10, -1.5) for sx in (-1, 1) for sy in (-1, 1)], 3.4, 10),
            pbox("_s", 14, 40, 3.4, (-2, 0, -12.4)), pbox("_s", 14, 40, 3.4, (16, 0, -12.4))]
    return soften(boolean(o, cuts), 0.5)

def pc_torreta(h=46):
    o = pbox("P07 Torreta", 56, 44, h, (-5, 0, h / 2), m=PLA)
    hp = [(-5 + sx * 20, sy * 10, 0) for sx in (-1, 1) for sy in (-1, 1)]
    cuts = [pbox("_c", 41.2, 20.4, 40, (-10, 0, h - 16.4 + 20)), pbox("_c", 46, 34, h - 10, (-5, 0, (h - 10) / 2 - 1)),
            pbox("_c", 20, 60, 16, (-5, 0, 10)), holes([(-10 + sx * 24.5, sy * 5, h) for sx in (-1, 1) for sy in (-1, 1)], 2.8, 16)]
    boolean(o, cuts)
    boolean(o, [pbox("_f", 56, 44, 3, (-5, 0, 1.5))], op="UNION")
    boolean(o, [holes(hp, 3.4, 10), pbox("_c", 40, 6, 10, (-5, 0, 1))])
    return soften(o)

def pc_horquilla():
    o = pbox("P08 Horquilla", 50, 56, 4, (-5, 0, 2), m=PLA)
    boolean(o, [pbox("_s", 44, 4, 44, (-5, y, 26)) for y in (-25.5, 25.5)], op="UNION")
    cuts = [holes([(0, 0, 0)], 8, 12), holes([(sx * 7, 0, 2) for sx in (-1, 1)], 2.2, 10), holes([(0, 0, 30)], 8.5, 70, axis="Y"),
            holes([(-10 + sx * 24.5, y, 30) for sx in (-1, 1) for y in (-25.5, 25.5)], 2.8, 8, axis="Y")]
    return soften(boolean(o, cuts))

def pc_eslabon(name, L_, t=6, hgt=20):
    o = pbox(name, L_, t, hgt, (L_ / 2, 0, 0), m=PLA)
    boolean(o, [pcyl("_e", hgt / 2 + 1, t, (0, 0, 0), (90, 0, 0)), pcyl("_e", hgt / 2 + 1, t, (L_, 0, 0), (90, 0, 0)), pbox("_p", 54, t, 26, (L_ - 10, 0, 0))], op="UNION")
    cuts = [pbox("_c", L_ * 0.42, t + 4, hgt * 0.4, (L_ * 0.42, 0, 0)), holes([(0, 0, 0)], 6, 12, axis="Y"),
            holes([(sx * 7, 0, 0) for sx in (-1, 1)], 2.2, 12, axis="Y"), holes([(L_, 0, 0)], 6, 12, axis="Y"),
            holes([(L_ - 10 + sx * 24.5, 0, sz * 5) for sx in (-1, 1) for sz in (-1, 1)], 2.8, 12, axis="Y")]
    return soften(boolean(o, cuts))

def pc_eslabon2(L_=90):
    o = pbox("P10 Eslabón 2", L_, 5, 16, (L_ / 2, 0, 0), m=PLA)
    boolean(o, [pcyl("_e", 9, 5, (0, 0, 0), (90, 0, 0)), pbox("_m", 30, 16, 26, (L_ - 4, 6, 0))], op="UNION")
    cuts = [pbox("_c", 23.2, 12.6, 40, (L_ - 4, 6, 0), (90, 0, 0)), holes([(0, 0, 0)], 6, 12, axis="Y"),
            holes([(sx * 7, 0, 0) for sx in (-1, 1)], 2.2, 12, axis="Y"), pbox("_c", 34, 8, 7, (L_ * 0.45, 0, 0))]
    return soften(boolean(o, cuts))

def pc_cabeza_muneca(con_camara=True):
    nm = "P14 Cabeza de muñeca" if con_camara else "P15 Muñeca con LiDAR"
    o = pbox(nm, 4, 30, 40, (2, 0, 0), m=PLA)
    add = [pbox("_b", 45, 30, 3, (22.5, 0, 18.0)), pbox("_g", 42, 4, 22, (24, 0, -14))]
    if con_camara:
        add += [pcyl("_r", 36, 4, (46, 0, 0), (0, 90, 0), seg=64), pbox("_k", 42, 12, 12, (24, 0, 0))]
    boolean(o, add, op="UNION")
    cuts = [holes([(0, 0, 0)], 7, 12, axis="X"), holes([(0, 0, sz * 9) for sz in (-1, 1)], 2.2, 12, axis="X"),
            holes([(22 + sx * 13, sy * 9, 18.5) for sx in (-1, 1) for sy in (-1, 1)], 2.2, 10)]
    if con_camara:
        cuts += [holes([(46, 0, 0)], 10, 10, axis="X"), holes([(46, y, z) for y in (-10.5, 10.5) for z in (-4.25, 8.25)], 2.2, 10, axis="X")]
    return boolean(o, cuts)

def pc_dedo():
    o = pbox("P11 Dedo móvil", 40, 4, 8, (20, 0, 0), m=PLA)
    boolean(o, [pcyl("_h", 7, 4, (0, 0, 0), (90, 0, 0))], op="UNION")
    return soften(boolean(o, [holes([(0, 0, 0)], 5, 12, axis="Y")]))

def pc_pod():
    o = pbox("P04 Soporte ESP32-CAM", 30, 34, 3, (0, 0, 1.5), m=PLA)
    boolean(o, [pbox("_f", 3, 34, 47, (13.5, 0, 25.5)), pbox("_r", 11, 2, 43, (7.5, 15.5, 23.5)), pbox("_r", 11, 2, 43, (7.5, -15.5, 23.5))], op="UNION")
    return soften(boolean(o, [holes([(13.5, 0, 34)], 9, 10, axis="X"), holes([(-10, sy * 10, 1.5) for sy in (-1, 1)], 3.4, 10)]))

def pc_flujo():
    o = pbox("P06 Soporte flujo óptico", 50, 50, 3, (0, 0, -1.5), m=PLA)
    boolean(o, [pbox("_b", 36, 36, 13, (0, 0, -8.5))], op="UNION")
    cuts = [pbox("_c", 31, 31, 14, (0, 0, -5)), holes([(0, 0, -13.5)], 15, 10), holes([(11, 11, -13.5)], 5, 10),
            holes([(sx * 20, sy * 20, -1.5) for sx in (-1, 1) for sy in (-1, 1)], 3.4, 10)]
    return soften(boolean(o, cuts))

def pc_parachoques():
    o = pbox("P05 Parachoques", 12, 170, 35, (0, 0, 0), m=TPU)
    boolean(o, [pbox("_t", 26, 16, 4, (-18, y, 8.5)) for y in (-50, 50)], op="UNION")
    cuts = [holes([(0, y, 0) for y in (-13, 13)], 16.5, 30, axis="X"), pbox("_c", 30, 8, 6, (0, -45, 0)), pbox("_c", 30, 8, 6, (0, 45, 0)),
            pbox("_c", 8, 140, 27, (-4, 0, 0)), holes([(-26, y, 8) for y in (-50, 50)], 3.4, 10)]
    return soften(boolean(o, cuts))

def pc_mastil(h=150):
    o = pbox("P02 Torre", 50, 50, 4, (0, 0, 2), m=PLA)
    boolean(o, [pbox("_t", 22, 22, h, (0, 0, 4 + h / 2)), pbox("_s", 32, 32, 5, (0, 0, 6))], op="UNION")
    cuts = [pbox("_c", 17.2, 17.2, h + 20, (0, 0, 4 + h / 2 + 1)), pbox("_c", 60, 60, 20, (0, 0, -10)), pbox("_c", 14, 10, 12, (0, -10, 20)),
            holes([(sx * 20, sy * 20, 2) for sx in (-1, 1) for sy in (-1, 1)], 3.4, 10)]
    return soften(boolean(o, cuts))

def pc_cara(base="torre"):
    nm = "P03 Cara en la torre" if base == "torre" else "P18 Cara frontal"
    o = pcyl(nm, 37, 4, (0, 0, 0), (0, 90, 0), m=PLA, seg=64)
    if base == "torre":
        boolean(o, [pbox("_s", 30, 28.6, 26, (-15, 0, -24))], op="UNION"); cuts = [pbox("_c", 22.6, 22.6, 22, (-15, 0, -26))]
    else:
        boolean(o, [pbox("_s", 30, 50, 4, (-13, 0, -35)), pbox("_k", 4, 30, 34, (-2, 0, -20))], op="UNION")
        cuts = [holes([(-13, sy * 20, -35) for sy in (-1, 1)], 3.4, 10)]
    cuts += [holes([(0, 0, 0)], 10, 10, axis="X"), holes([(0, y, z) for y in (-10.5, 10.5) for z in (-4.25, 8.25)], 2.2, 10, axis="X")]
    return soften(boolean(o, cuts))

def pc_anillo_parlante():
    o = pcyl("P12 Anillo del parlante", 50, 3, (0, 0, 1.5), m=PLA, seg=72)
    boolean(o, [pcyl("_r", 50, 8, (0, 0, 4), seg=72), pbox("_k", 32, 32, 16, (0, 0, -8))], op="UNION")
    return soften(boolean(o, [pcyl("_c", 46.5, 10, (0, 0, 8), seg=72), pbox("_c", 22.6, 22.6, 60, (0, 0, 0)), holes([(0, -12, -8)], 3.2, 20, axis="Y")]))

def pc_barredor():
    o = pbox("P16 Barredor LiDAR", 40, 30, 3, (0, 0, 1.5), m=PLA)
    boolean(o, [pbox("_w", 26, 3, 24, (0, sy * 7.6, 13.5)) for sy in (-1, 1)], op="UNION")
    return soften(boolean(o, [holes([(sx * 10, 0, 1.5) for sx in (-1, 1)], 3.4, 10), holes([(sx * 13.8, sy * 7.6, 22) for sx in (-1, 1) for sy in (-1, 1)], 2.0, 6, axis="Y")]))

# ------------------------------------------------------------------ armado v3
def grupo(R, gid, etiqueta, loc, rot=(0, 0, 0), superficie="cubierta", movible=True, **props):
    return empty("G_" + gid, loc, R, rot, movible=movible, superficie=superficie, etiqueta=etiqueta, **props)

PLACA_CACHE = {}
def placa(R, V, z, nivel):
    if "E" not in PLACA_CACHE:
        full = pc_placa_completa(); PLACA_CACHE["E"] = full.data; bpy.data.objects.remove(full, do_unlink=True)
    o = bpy.data.objects.new(f"P20 {nivel}", PLACA_CACHE["E"].copy()); COL.objects.link(o); smooth(o.data, 30)
    registrar(o, "P20", "Placa estándar 320×200", "PLA", .40, "No (cara superior contra la cama)", (180, 0, 0),
              "Una sola pieza rígida, sin juntas: 4 mm + nervios de 6 mm, rejilla M3 cada 10 mm. Requiere cama de 330 × 210 mm o más", V)
    o["etiqueta"] = f"P20 · Placa estándar 320×200 ({nivel})"; parent(o, R, (0, 0, z))

def chasis(R, V):
    placa(R, V, ZB, "inferior"); placa(R, V, ZT, "superior"); placa(R, V, ZK, "cubierta")
    for (x, y) in COLS:
        for z0, nivel in ((ZB + T, "1"), (ZT + T, "2")):
            c = pc_columna(); registrar(c, "P23", "Columna 40 mm", "PLA", 1.0, "No (de pie)", (0, 0, 0), "Opcional: o separadores de latón del kit (ítem 11) que sumen 40 mm", V)
            parent(c, R, (x, y, z0))
    for sx in (-1, 1):
        for sy in (-1, 1):
            cu = pc_cuna_motor(); registrar(cu, "P24", "Cuna motor TT", "PETG", .5, "No (pestaña contra la cama)", (180, 0, 0),
                                            "Atornillar al TT con 2 M3×30 por las ranuras (±7 mm de juego para calzar los agujeros del motor)", V)
            parent(cu, R, (sx * (WHEEL_X - 24), sy * MOTOR_Y, ZB), (0, 0, 0 if sx > 0 else 180))
            m = c_tt_motor().done(R, (sx * (WHEEL_X - 11), sy * MOTOR_Y, 32.5), (0, 0, 0 if sx > 0 else 180), mass=30.6, etiqueta="Motorreductor TT 1:48 (ítem 54)")
            w = empty(f"W_{'d' if sx > 0 else 't'}{'i' if sy > 0 else 'd'}", (sx * WHEEL_X, sy * WHEEL_Y, 32.5), R, rueda=True)
            c_wheel().done(w, (0, 0, 0), (0, 0, 0 if sy > 0 else 180), mass=36, etiqueta="Rueda 65 mm (ítem 55)")
    for i, x in enumerate((100, -100)):
        g = grupo(R, f"flujo{i+1}", f"Cámara de suelo ADNS-3080 #{i+1}", (x, 0, ZB), superficie="bajo", item=86)
        f = pc_flujo(); registrar(f, "P06", "Soporte flujo óptico", "PLA", .25, "No", (180, 0, 0), "Boca abajo; desenroscar la lente M12 ~3 mm para enfocar el suelo a ~28 mm", V)
        parent(f, g)
        c_adns().done(g, (0, 0, -6.5), (180, 0, 0), mass=8, etiqueta=f"ADNS-3080 #{i+1} · odometría óptica", sensor="flujo")
    for i, x in enumerate((-55, 55)):
        g = grupo(R, f"bat{i+1}", f"Portapilas 4×18650 #{i+1}", (x, 0, ZB + T), superficie="piso1", item=106)
        c_holder4().done(g, (0, 0, 0), (0, 0, 90), mass=25, etiqueta="Portapilas 4×18650")
        for j in range(4):
            cell = c_cell(CELLG if (i * 4 + j) % 2 else CELLP).done(g, (-29.5 + j * 19.7, 0, 11.2), (0, 0, 90), mass=48, etiqueta="Celda 18650 (ítems 104–105)", celda=i * 4 + j + 1)
            cell.name = f"CELL_{i*4+j+1}"
    gs = grupo(R, "interruptor", "Interruptor + fusible 5 A", (-135, 0, ZB + T), superficie="piso1")
    Comp("Interruptor").box((20, 13, 13), (0, 0, 6.5), BLK, bev=1).box((10, 8, 6), (0, 0, 15), PCBR, bev=1).done(gs, mass=12, etiqueta="Interruptor + fusible 5 A")
    z2 = ZT + T
    g = grupo(R, "pi", "Raspberry Pi 3B", (-60, 35, z2 + 5), superficie="piso2", item=77)
    c_pi3b(g, (0, 0)).done(g, mass=45, etiqueta="Raspberry Pi 3B · cerebro (ítem 77)")
    for (gid, et, x, y, fn, ms) in [("pca1", "PCA9685 #1 · motores", 60, 50, c_pca9685, 9), ("pca2", "PCA9685 #2 · servos", 60, 20, c_pca9685, 9),
                                    ("lm1", "LM2596 #1 · motores", -130, -15, c_lm2596, 12), ("lm2", "Convertidor 5 A · servos (ítem 110)", -130, -45, c_lm2596, 12)]:
        fn().done(grupo(R, gid, et, (x, y, z2 + 3), superficie="piso2"), mass=ms, etiqueta=et)
    for (gid, et, x, y, w_, d_, m_, ch) in [("tb1", "TB6612FNG #1 · motores izquierdos", 60, -15, 20.3, 20.3, PCBR, [(0, 0, 7, 5, 1.2, BLK2)]),
                                          ("tb2", "TB6612FNG #2 · motores derechos", 60, -45, 20.3, 20.3, PCBR, [(0, 0, 7, 5, 1.2, BLK2)]),
                                          ("ads", "ADS1115 · batería y analógicos", -20, -50, 28, 17.8, PCBB, [(0, 0, 5, 3, 1, BLK2)]),
                                          ("imu", "MPU-6050 · orientación (al centro de giro)", 5, 0, 21, 16, PCBB, [(0, 0, 4, 4, 0.9, BLK2)])]:
        c_board(et.split(" ·")[0], w_, d_, m_, chips=ch, pins=(8, 1, 2.54, (0, -d_ / 2 + 2, 1.6))).done(grupo(R, gid, et, (x, y, z2 + 3), superficie="piso2"), mass=3, etiqueta=et)
    g = grupo(R, "parachoques", "Parachoques con ultrasonido y 2 ToF", (L / 2 + 6, 0, ZB + T - 6.5), superficie="frente", movible=False)
    b = pc_parachoques(); registrar(b, "P05", "Parachoques", "TPU 95A (o PETG)", .3, "No (cara al plato)", (0, 90, 0), "Se atornilla a la placa inferior con 2 M3", V)
    parent(b, g)
    c_hcsr04().done(g, (-8, 0, 0), (0, -90, 0), mass=9, etiqueta="HC-SR04 · ultrasonido (ítem 89)", sensor="ultrasonido")
    for y in (-45, 45):
        c_board("VL53L3CX", 13, 18, PCBP, chips=[(0, 2, 4.4, 2.4, 1, BLK)]).done(g, (-3, y, 0), (0, -90, 90), mass=2, etiqueta="VL53L3CX · ToF (ítem 88)", sensor="tof")

def brazo(R, V, cabeza):
    g = grupo(R, "brazo", "Brazo de 5 servos", (0, 0, DT), superficie="cubierta", movible=True, item=1)
    t = pc_torreta(); registrar(t, "P07", "Torreta alta", "PETG", .4, "No", (0, 0, 0), "Pedestal de 46 mm; 4 M3 a la rejilla", V)
    parent(t, g, (5, 0, 0))
    c_mg995(horn=False).done(g, (-5, 0, 46 - 37 + 3.6), mass=55, etiqueta="MG995 #1 · giro (ítem 1)")
    Jy = empty("J_giro", (5.2, 0, 46 + 9.6), g)
    hq = pc_horquilla(); registrar(hq, "P08", "Horquilla del hombro", "PETG", .4, "No", (0, 0, 0), "Tornillo del horn al centro", V)
    parent(hq, Jy)
    c_mg995().done(Jy, (-10.2, -21.5, 30), (-90, 0, 0), mass=55, etiqueta="MG995 #2 · hombro")
    Js = empty("J_hombro", (0, 0, 30), Jy)
    l1 = pc_eslabon("P09 Eslabón 1", 100); registrar(l1, "P09", "Eslabón 1", "PETG", .4, "No (de canto)", (90, 0, 0), "De canto: las capas siguen el largo", V)
    parent(l1, Js, (0, 31, 0))
    c_mg995().done(Js, (100 - 10.2, 19, 0), (90, 0, 0), mass=55, etiqueta="MG995 #3 · codo")
    Je = empty("J_codo", (100, 0, 0), Js)
    l2 = pc_eslabon2(90); registrar(l2, "P10", "Eslabón 2", "PETG", .4, "Sí (bajo la muñeca)", (90, 0, 0), "Termina en el alojamiento del MG90S", V)
    parent(l2, Je, (0, -10, 0))
    c_mg90s().done(Je, (90 - 4 - 5.9, -7, 0), (90, 0, 0), mass=13.4, etiqueta="MG90S #1 · muñeca")
    Jw = empty("J_muneca", (86, -38.6, 0), Je)
    h = pc_cabeza_muneca(cabeza == "camara")
    if cabeza == "camara":
        registrar(h, "P14", "Cabeza de muñeca", "PETG", .35, "Sí (bajo la repisa)", (0, -90, 0), "Cámara Pi + anillo 24 LED al frente, LiDAR arriba, pinza abajo", V)
    else:
        registrar(h, "P15", "Muñeca con LiDAR", "PETG", .35, "Sí (bajo la repisa)", (0, -90, 0), "LiDAR arriba y pinza abajo", V)
    parent(h, Jw)
    if cabeza != "sinlidar":
        c_lidar_eai().done(Jw, (22, 0, 20), mass=5.4, etiqueta="LiDAR 2D EAI (ítem 87) · barre con el brazo", sensor="lidar").name = "S_lidar"
        empty("S_lidar_rayo", (22, 0, 31), Jw, rot=(0, 90, 0), rayo=True)
    if cabeza == "camara":
        c_ring24().done(Jw, (48.5, 0, 0), (0, 90, 0), mass=8, etiqueta="Anillo WS2812 de 24 LED (ítem 5) · la cara")
        c_picam().done(Jw, (49, 0, 2), (0, 90, 0), mass=3, etiqueta="Cámara Pi v1.3 (ítem 78) · cable FFC de 1 m por el brazo", sensor="camara", fov_h=53.5, fov_v=41.4).name = "S_cam_pi"
    c_mg90s().done(Jw, (24, 5, -14), (90, 0, 0), mass=13.4, etiqueta="MG90S #2 · pinza")
    Jp = empty("J_pinza", (30, -3.1, -10), Jw)
    dd = pc_dedo(); registrar(dd, "P11", "Dedo móvil", "PETG", .4, "No", (90, 0, 0), "Al horn del MG90S", V)
    parent(dd, Jp)
    Js.rotation_euler.y = math.radians(-55); Je.rotation_euler.y = math.radians(85); Jw.rotation_euler.y = math.radians(-20)

def pod(R, V, gid, n, loc, rz, etiqueta):
    g = grupo(R, gid, etiqueta, loc, (0, 0, rz), superficie="cubierta", item=79)
    p = pc_pod(); registrar(p, "P04", "Soporte ESP32-CAM", "PLA", .25, "No", (0, 0, 0), "2 M3 a la rejilla; la lente asoma por el agujero de 9 mm", V)
    parent(p, g)
    c_esp32cam().done(g, (9.6, 0, 26), (0, -90, 180), mass=10, etiqueta=etiqueta, sensor="camara", fov_h=52, fov_v=40).name = f"S_cam_esp{n}"

def ups(R, loc):
    c_ups().done(grupo(R, "ups", "UPS 5 V 3 A (lógica)", loc, superficie="cubierta", item=103), mass=141, etiqueta="UPS LX-2BUPS con 2×18650 · Pi y ESP32")

def parlante(R, loc):
    c_speaker().done(grupo(R, "parlante", "Parlante omnidireccional", loc, superficie="cubierta"), mass=180, etiqueta="Parlante omnidireccional")

def version(clave, titulo, desc):
    newcol(titulo)
    R = empty("R_" + clave, (0, 0, 0), None, version=clave, titulo=titulo, desc=desc)
    chasis(R, [clave]); return R

VERS = {}
R = version("V1", "V1 · Brazo-cuello", "Brazo al centro sin torre; cara y LiDAR en la muñeca.")
brazo(R, ["V1"], "camara"); ups(R, (-90, -50, DT)); parlante(R, (-110, 40, DT))
pod(R, ["V1"], "esp1", 1, (130, 50, DT), 0, "ESP32-CAM #1 · controlador, mira al frente")
pod(R, ["V1"], "esp2", 2, (130, -50, DT), 0, "ESP32-CAM #2 · frente derecho")
pod(R, ["V1"], "esp3", 3, (-140, -10, DT), 180, "ESP32-CAM #3 · retroceso")
VERS["V1"] = R
R = version("V2", "V2 · Brazo + torre", "Brazo al centro con LiDAR; torre trasera con cara, parlante y cámara.")
brazo(R, ["V2"], "lidar"); ups(R, (-80, -50, DT))
tg = grupo(R, "torre", "Torre trasera", (-120, 60, DT), superficie="cubierta")
mt = pc_mastil(150); registrar(mt, "P02", "Torre", "PETG", .4, "No (imprimir acostada)", (0, 90, 0), "Acostada: las capas siguen el largo y aguanta un vuelco", ["V2"]); parent(mt, tg)
an = pc_anillo_parlante(); registrar(an, "P12", "Anillo del parlante", "PLA", .25, "No", (0, 0, 0), "Prisionero M3 contra la torre", ["V2"]); parent(an, tg, (0, 0, 70))
c_speaker().done(tg, (0, 0, 73), mass=180, etiqueta="Parlante omnidireccional")
cf = pc_cara("torre"); registrar(cf, "P03", "Cara en la torre", "PLA", .25, "Sí (árbol)", (0, -90, 0), "Enchufa en el tubo de 22×22", ["V2"]); parent(cf, tg, (15, 0, 180))
c_ring24().done(tg, (17.5, 0, 180), (0, 90, 0), mass=8, etiqueta="Anillo WS2812 de 24 LED (ítem 5)")
c_picam().done(tg, (18, 0, 182), (0, 90, 0), mass=3, etiqueta="Cámara Pi v1.3 · cara fija", sensor="camara", fov_h=53.5, fov_v=41.4).name = "S_cam_pi"
c_esp32cam().done(tg, (-14, 0, 120), (0, -90, 0), mass=10, etiqueta="ESP32-CAM #3 · retroceso, en la torre", sensor="camara", fov_h=52, fov_v=40).name = "S_cam_esp3"
pod(R, ["V2"], "esp1", 1, (130, 50, DT), 0, "ESP32-CAM #1 · controlador, mira al frente")
pod(R, ["V2"], "esp2", 2, (130, -50, DT), 0, "ESP32-CAM #2 · frente derecho")
VERS["V2"] = R
R = version("V3", "V3 · Barredor bajo", "LiDAR barriendo en la proa con un MG90S; cara al frente; brazo-pinza al centro.")
brazo(R, ["V3"], "sinlidar"); ups(R, (-90, -50, DT)); parlante(R, (-110, 40, DT))
bg = grupo(R, "barredor", "Barredor del LiDAR", (140, 0, DT), superficie="cubierta", movible=False)
pb = pc_barredor(); registrar(pb, "P16", "Barredor LiDAR", "PETG", .4, "No", (0, 0, 0), "MG90S de repuesto (ítem 2) barre el LiDAR ±90°", ["V3"]); parent(pb, bg)
c_mg90s().done(bg, (-5.9, 0, 3), mass=13.4, etiqueta="MG90S #3 · barre el LiDAR")
Jb = empty("J_barrido", (0, 0, 34.6), bg)
c_lidar_eai().done(Jb, (4, 0, 0), mass=5.4, etiqueta="LiDAR 2D EAI · barre ±90°", sensor="lidar").name = "S_lidar"
empty("S_lidar_rayo", (4, 0, 11), Jb, rot=(0, 90, 0), rayo=True)
cg_ = grupo(R, "cara", "Cara frontal", (103, 0, DT), superficie="cubierta")
cf = pc_cara("frontal"); registrar(cf, "P18", "Cara frontal", "PLA", .25, "No", (0, -90, 0), "Pie con 2 M3 a la rejilla", ["V3"]); parent(cf, cg_, (13, 0, 38))
c_ring24().done(cg_, (15.5, 0, 38), (0, 90, 0), mass=8, etiqueta="Anillo WS2812 de 24 LED (ítem 5)")
c_picam().done(cg_, (16, 0, 40), (0, 90, 0), mass=3, etiqueta="Cámara Pi v1.3 · cara al frente", sensor="camara", fov_h=53.5, fov_v=41.4).name = "S_cam_pi"
pod(R, ["V3"], "esp1", 1, (130, -60, DT), 0, "ESP32-CAM #1 · controlador")
pod(R, ["V3"], "esp3", 3, (-140, -10, DT), 180, "ESP32-CAM #3 · retroceso")
VERS["V3"] = R

# ------------------------------------------------------------------ exportar
for clave, R in VERS.items():
    col = R.users_collection[0]
    for ob in bpy.context.view_layer.objects: ob.select_set(False)
    for ob in col.all_objects: ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "glb", f"bicho_{clave}.glb"), export_format='GLB', use_selection=True,
                              export_extras=True, export_apply=False, export_yup=True)
sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.render.film_transparent = True
sc.render.resolution_x, sc.render.resolution_y = 1400, 1000; sc.eevee.taa_render_samples = 48
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 0.97, 0.94, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sun = bpy.data.objects.new("Sol", bpy.data.lights.new("Sol", "SUN")); sc.collection.objects.link(sun)
sun.data.energy = 3.2; sun.data.angle = math.radians(8); sun.rotation_euler = Euler((math.radians(48), math.radians(8), math.radians(35)))
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 50
def solo(col):
    for c in bpy.data.collections:
        lc = bpy.context.view_layer.layer_collection.children.get(c.name)
        if lc: lc.exclude = (c != col)
for clave, R in VERS.items():
    solo(R.users_collection[0])
    t = Vector((0, 0, 150)) * M; a, e = math.radians(35), math.radians(24)
    cam.location = t + Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))) * 1.25
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(OUT, "render", f"bicho_{clave}.png"); bpy.ops.render.render(write_still=True)
for c in bpy.data.collections:
    lc = bpy.context.view_layer.layer_collection.children.get(c.name)
    if lc: lc.exclude = False
VERS["V2"].location.x = 0.6; VERS["V3"].location.x = 1.2
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "bicho_v3_32cm.blend"))
json.dump(dict(piezas=list(PIEZAS.values())), open(os.path.join(OUT, "piezas_v3.json"), "w"), ensure_ascii=False, indent=1)
print("OK", len(PIEZAS), "piezas")
