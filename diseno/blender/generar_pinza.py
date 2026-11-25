# Pinza de dos dedos con engranajes para el brazo del Bicho (P30 a P34).
# Va fija al costado del eslabón 2 (P10) tal como está impreso: no hay muñeca.
# Un MG90S mueve el dedo motriz; el engranaje hace que el otro dedo cierre al mismo tiempo.
#
#   /Applications/Blender.app/Contents/MacOS/Blender -b -P diseno/blender/generar_pinza.py -- diseno/imprimir/STL [vista.png]
#
# Medidas en mm. Sistema del eslabón 2: origen en el eje del codo, X a lo largo del eslabón, Z hacia arriba.
import bpy, bmesh, sys, os, math
from mathutils import Vector, Matrix

M = 0.001
ARGS = sys.argv[sys.argv.index("--") + 1:]
OUT = ARGS[0]
VISTA = ARGS[1] if len(ARGS) > 1 else None
bpy.ops.wm.read_factory_settings(use_empty=True)
col = bpy.context.scene.collection

# ---- medidas ----
MOD, DIENTES = 1.5, 16              # engranajes iguales: diámetro primitivo de 24 mm
DC = 24.3                           # distancia entre ejes (24 + 0,3 de juego para la impresión)
XS = 66.0                           # X de los dos ejes de los dedos
YA = -14.5                          # eje del dedo motriz (el del servo)
YB = YA - DC                        # eje del dedo conducido (tornillo M3)
T_PLACA = 4.0
Z_PLACA = 8.2                       # cara de abajo de la placa: descansa sobre el canto del eslabón (z = 8)
Z_ARRIBA = Z_PLACA + T_PLACA
Z_DEDO = Z_PLACA - 17.7 + 29.6      # las orejas del MG90S van bajo la placa; el dedo se apoya en el horn
T_DEDO, H_MORDAZA = 6.0, 22.0
H_BUJE = Z_DEDO - Z_ARRIBA - 0.2
Y_PESTANA = (-7.5, -2.5)            # pestaña vertical de 5 mm contra la cara plana del eslabón
PERNOS_X = (27.0, 44.0)             # 2 M3×12 por la ranura del eslabón 2 (x de 23,5 a 57,5)


def obj(bm, name):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); col.objects.link(o); return o

def prisma(pts, z0, z1, name="p"):
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new(Vector((x, y, z0)) * M) for (x, y) in pts])
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, vec=Vector((0, 0, z1 - z0)) * M, verts=[e for e in r["geom"] if isinstance(e, bmesh.types.BMVert)])
    return obj(bm, name)

def caja(x0, x1, y0, y1, z0, z1, name="b"):
    return prisma([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1, name)

def circulo(r, cx=0, cy=0, seg=40, fase=0):
    return [(cx + r * math.cos(fase + 2 * math.pi * i / seg), cy + r * math.sin(fase + 2 * math.pi * i / seg)) for i in range(seg)]

def cil(r, cx, cy, z0, z1, seg=40, name="c"):
    return prisma(circulo(r, cx, cy, seg), z0, z1, name)

def cil_y(r, x, z, y0, y1, seg=40):
    """Cilindro con el eje a lo largo de Y."""
    o = prisma(circulo(r, 0, 0, seg), y0, y1)
    o.data.transform(Matrix.Translation(Vector((x, 0, z)) * M) @ Matrix.Rotation(math.radians(-90), 4, 'X'))
    return o

def boolean(o, others, op="DIFFERENCE"):
    for c in others:
        md = o.modifiers.new("b", "BOOLEAN"); md.object = c; md.operation = op; md.solver = 'EXACT'
    dg = bpy.context.evaluated_depsgraph_get(); me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    o.modifiers.clear(); o.data = me
    for c in others: bpy.data.objects.remove(c, do_unlink=True)
    return o

def engranaje(fase_grados, juego=0.1):
    """Perfil de evolvente, ángulo de presión de 20°. Un diente queda centrado en fase_grados."""
    rp = MOD * DIENTES / 2; a0 = math.radians(20); rb = rp * math.cos(a0); ra = rp + MOD; rf = rp - 1.25 * MOD
    inv = lambda a: math.tan(a) - a
    medio = math.pi / (2 * DIENTES) - juego / (2 * rp)
    ancho = lambda r: medio + inv(a0) - (inv(math.acos(rb / r)) if r > rb else 0)
    radios = [rb + (ra - rb) * i / 5 for i in range(6)]
    pts = []
    for k in range(DIENTES):
        c = math.radians(fase_grados) + 2 * math.pi * k / DIENTES
        flanco = [(rf, c - ancho(rb))] + [(r, c - ancho(r)) for r in radios] + [(r, c + ancho(r)) for r in reversed(radios)] + [(rf, c + ancho(rb))]
        pts += [(r * math.cos(a), r * math.sin(a)) for (r, a) in flanco]
    return pts

# Dedo motriz, con el eje en el origen y la pinza cerrada. El otro dedo queda hacia -Y, a DC.
# La cara que aprieta va de (34, -2) a (64, -9,5); el gancho de la punta evita que el objeto se escape hacia adelante.
DEDO = [(4, -8), (18, -4), (34, -2), (64, -9.5), (67, -11.9), (72, -11.9), (72, -5), (64, -2), (36, 7), (18, 7), (4, 9), (-4, 6), (-4, -6)]
MORDAZA = [(34, -2), (64, -9.5), (67, -11.9), (72, -11.9), (72, -5), (64, -2), (36, 7)]
espejo = lambda pts: [(x, -y) for (x, y) in reversed(pts)]

def dedo(name, motriz):
    cuerpo = prisma(DEDO if motriz else espejo(DEDO), 0, T_DEDO, name)
    extra = [prisma(engranaje(-90 if motriz else 90 + 180 / DIENTES), 0, T_DEDO),
             prisma(MORDAZA if motriz else espejo(MORDAZA), 0, H_MORDAZA)]
    boolean(cuerpo, extra, "UNION")
    if motriz:
        cortes = [cil(2.75, 0, 0, -1, T_DEDO + 1),                 # paso para el tornillo central del horn
                  cil(4.1, 0, 0, -1, 1.8), caja(-14, 21, -3.1, 3.1, -1, 1.8),   # rebaje para el horn de un brazo
                  caja(5, 19, -0.7, 0.7, 1.7, 4.8)]                # ranura donde muerden los tornillos chicos del horn
    else:
        cortes = [cil(1.7, 0, 0, -1, T_DEDO + 1)]                  # gira sobre un M3
    return boolean(cuerpo, cortes)

def palma():
    """En el sistema del eslabón 2. Se imprime dada vuelta, con la cara de arriba de la placa en la cama."""
    o = caja(36, 70, YB - 8.7, 2.5, Z_PLACA, Z_ARRIBA, "P30 Palma")
    suma = [caja(70, 80, YB - 8.7, -2.8, Z_PLACA, Z_ARRIBA),                   # adelante esquiva el alojamiento del eslabón
            caja(20, 80, Y_PESTANA[0], Y_PESTANA[1], -8, Z_PLACA)]             # pestaña
    for x0 in (36, 77):                                                        # 2 escuadras bajo la placa
        e = prisma([(Y_PESTANA[0], -6), (Y_PESTANA[0], Z_PLACA), (-22, Z_PLACA)], x0, x0 + 3)
        e.data.transform(Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1))))   # (y, z, x) -> (x, y, z)
        suma.append(e)
    boolean(o, suma, "UNION")
    cx = XS - 5.9                                                              # centro del cuerpo del MG90S
    cortes = [caja(cx - 11.6, cx + 11.6, YA - 6.3, YA + 6.3, 0, 20),           # el servo entra por abajo
              cil(0.85, cx - 13.9, YA, 0, 20, 16), cil(0.85, cx + 13.9, YA, 0, 20, 16),   # tornillos de las orejas
              cil(1.7, XS, YB, 0, 20)]                                         # eje del dedo conducido
    for x in PERNOS_X:
        cortes += [cil_y(1.7, x, 0, -12, 0), cil_y(3.3, x, 0, Y_PESTANA[0] - 1, Y_PESTANA[0] + 2.4, 6)]   # perno y tuerca M3 encajada
    return boolean(o, cortes)

def buje():
    return boolean(cil(4.5, 0, 0, 0, H_BUJE, name="P33 Buje"), [cil(1.7, 0, 0, -1, H_BUJE + 1)])

def contraplaca():
    o = caja(-15, 15, -6, 6, 0, 2, "P34 Contraplaca")
    boolean(o, [caja(-13, 13, -3.2, 3.2, 2, 5)], "UNION")                     # nervio que entra en la ranura de 7 mm
    d = (PERNOS_X[1] - PERNOS_X[0]) / 2
    return boolean(o, [cil(1.7, -d, 0, -1, 6), cil(1.7, d, 0, -1, 6)])


piezas = []   # (objeto, archivo, matriz de impresión -> armado)
p = palma()
vuelta = Matrix.Translation(Vector((0, 0, Z_ARRIBA)) * M) @ Matrix.Rotation(math.pi, 4, 'X')   # es su propia inversa
p.data.transform(vuelta)
piezas.append((p, "P30_palma_de_la_pinza.stl", vuelta))
piezas.append((dedo("P31 Dedo motriz", True), "P31_dedo_motriz.stl", Matrix.Translation(Vector((XS, YA, Z_DEDO)) * M)))
piezas.append((dedo("P32 Dedo conducido", False), "P32_dedo_conducido.stl", Matrix.Translation(Vector((XS, YB, Z_DEDO)) * M)))
piezas.append((buje(), "P33_buje_del_dedo.stl", Matrix.Translation(Vector((XS, YB, Z_ARRIBA)) * M)))
xm = sum(PERNOS_X) / 2
piezas.append((contraplaca(), "P34_contraplaca.stl",
               Matrix.Translation(Vector((xm, 4.5, 0)) * M) @ Matrix.Rotation(math.radians(90), 4, 'X')))

os.makedirs(OUT, exist_ok=True)
for (o, archivo, _) in piezas:
    bm = bmesh.new(); bm.from_mesh(o.data)
    abiertas = sum(1 for e in bm.edges if not e.is_manifold)
    vol = bm.calc_volume() * 1e6                                               # cm³
    co = [v.co / M for v in bm.verts]; bm.free()
    dim = [max(c[i] for c in co) - min(c[i] for c in co) for i in range(3)]
    zmin = min(c[2] for c in co)
    bpy.ops.object.select_all(action="DESELECT"); o.select_set(True)
    bpy.ops.wm.stl_export(filepath=os.path.join(OUT, archivo), export_selected_objects=True, global_scale=1000.0)
    print("PIEZA %-28s %5.1f x %5.1f x %5.1f mm | %4.1f cm3 | %4.1f g PETG | z min %.2f | aristas abiertas %d"
          % (archivo, dim[0], dim[1], dim[2], vol, vol * 1.27, zmin, abiertas))

if VISTA:
    # Vista de la pinza armada sobre el eslabón 2, con los dedos a medio abrir.
    def color(o, rgb):
        m = bpy.data.materials.new("m"); m.diffuse_color = (*rgb, 1); o.data.materials.append(m)
    abre = math.radians(18)
    for (o, archivo, arm) in piezas:
        giro = Matrix.Rotation(abre if "motriz" in archivo else -abre if "conducido" in archivo else 0, 4, 'Z')
        o.data.transform(arm @ giro)
        color(o, (0.45, 0.85, 0.75) if "dedo" in archivo else (0.95, 0.78, 0.2) if "palma" in archivo else (0.9, 0.4, 0.3))
    esl = caja(0, 71, -2.5, 2.5, -8, 8); boolean(esl, [caja(71, 101, -2.5, 14, -13, 13)], "UNION")
    boolean(esl, [caja(23.5, 57.5, -5, 5, -3.5, 3.5)]); color(esl, (0.6, 0.62, 0.68))
    cx = XS - 5.9; zb = Z_PLACA - 17.7
    srv = caja(cx - 11.4, cx + 11.4, YA - 6.1, YA + 6.1, zb, zb + 22.5)
    boolean(srv, [caja(cx - 16.25, cx + 16.25, YA - 6.1, YA + 6.1, zb + 15.3, zb + 17.7), cil(2.3, XS, YA, zb + 22.5, zb + 29.6)], "UNION")
    color(srv, (0.15, 0.35, 0.85))
    lata = cil(18, XS + 48, (YA + YB) / 2, Z_DEDO - 30, Z_DEDO + 50, name="objeto"); color(lata, (0.85, 0.85, 0.85))
    sc = bpy.context.scene
    for i, (pos, nombre) in enumerate([((230, -230, 190), "a"), ((90, -27, 330), "b")]):
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); col.objects.link(cam)
        cam.location = Vector(pos) * M
        d = Vector((80, -25, 15)) * M - cam.location
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        cam.data.clip_start = 0.01; cam.data.lens = 60
        sc.camera = cam; sc.render.engine = 'BLENDER_WORKBENCH'
        sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'; sc.display.shading.show_cavity = True
        sc.render.resolution_x, sc.render.resolution_y = 900, 700
        sc.render.filepath = VISTA.replace(".png", "_%s.png" % nombre)
        bpy.ops.render.render(write_still=True)
print("OK pinza")
