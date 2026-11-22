# Bicho · paneles laterales que cierran el piso entre la placa de abajo y la de arriba (modelo de 2 placas).
# Se calzan sin tornillos: pasadores cuadrados de 2,6 mm entran en la rejilla M3 (Ø3,4) de la placa de abajo y de la de arriba.
# Paneles a 10 mm del borde (fila de agujeros y = ±90 y x = ±150): no tocan ruedas ni nervios del borde.
# Muesca en x = ±40 para los nervios transversales de la placa de arriba. Ventilación + «bicho» y el ojo con curita en relieve.
# Uso: Blender -b -P generar_paneles_laterales.py -- <salida>
import os, sys, math, json
AQUI = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(AQUI, "generar_bicho_v3.py"), encoding="utf-8").read()
exec(compile(src[:src.index("VERS = {}")], "generar_bicho_v3.py", "exec"))

T_P = 0.4                                    # espesor de la hoja: 2 capas de 0,2 mm
REL = 0.2                                    # relieve del texto y el ojo: 1 capa más (máximo 3 capas en total)
Z0, Z1 = ZB + T + 0.2, ZT - 0.4              # entre la cara de arriba de la placa de abajo y la de abajo de la placa de arriba
PIN = 3.0
def bake(o): o.data.transform(o.matrix_basis); o.matrix_basis = Matrix.Identity(4); return o
def box(n, x0, x1, y0, y1, z0, z1): return bake(pbox(n, x1-x0, y1-y0, z1-z0, ((x0+x1)/2, (y0+y1)/2, (z0+z1)/2), m=PLA))
def cyl(n, r, x, y, z0, z1, axis="Z", seg=48):
    h = z1 - z0; c = (z0 + z1) / 2
    loc = {"Z": (x, y, c), "Y": (x, c, y), "X": (c, x, y)}[axis]; rot = {"Z": (0,0,0), "Y": (90,0,0), "X": (0,90,0)}[axis]
    return bake(pcyl(n, r, h, loc, rot, m=PLA, seg=seg))
def cut(o, parts):
    for i, c in enumerate(parts):
        d = 0.0033 * ((i % 7) + 1) * M; c.data.transform(Matrix.Translation(Vector((d, d, d))))
    return boolean(o, parts)
def ventana(u, w, h, zc):                     # ranura de ventilación redondeada (en coordenadas locales u, z del panel)
    r = w / 2
    return [("box", u - r, u + r, zc - h / 2 + r, zc + h / 2 - r), ("cyl", u, zc - h / 2 + r, r), ("cyl", u, zc + h / 2 - r, r)]
def texto(s, size, u, zc, depth, espejo=False):
    cu = bpy.data.curves.new("_txt", "FONT"); cu.body = s; cu.size = size * M; cu.extrude = depth / 2 * M
    cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
    try: cu.font = bpy.data.fonts.load(os.path.join(bpy.utils.system_resource('DATAFILES'), "fonts", "DejaVuSans-Bold.ttf"))
    except Exception: pass
    o = bpy.data.objects.new("_txt", cu); COL.objects.link(o)
    dg = bpy.context.evaluated_depsgraph_get(); me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    bpy.data.objects.remove(o, do_unlink=True); t = bpy.data.objects.new("_txtm", me); COL.objects.link(t)
    if espejo: t.data.transform(Matrix.Scale(-1, 4, Vector((1, 0, 0))))
    t.data.transform(Matrix.Translation(Vector((u * M, zc * M, 0)))); return t   # en el plano (u, z), espesor en ±depth/2

def panel(pid, eje, fijo, u0, u1, pins, muescas=(), deco=None, hueco=None):
    espejo = (eje == "x" and fijo > 0) or (eje == "y" and fijo < 0)   # que el texto se lea desde afuera
    """eje 'x': panel a lo largo de x en y = fijo; eje 'y': a lo largo de y en x = fijo. Se arma en el plano local (u, z, w)."""
    o = box(pid, u0, u1, -T_P / 2, T_P / 2, Z0, Z1)                                  # local: x=u, y=w (espesor), z=z
    add = []
    for u in pins:
        # pestañas planas del mismo espesor de la hoja: entran en los agujeros Ø3,4 de la rejilla como lengüetas
        add += [box("_pb", u - PIN/2, u + PIN/2, -T_P/2, T_P/2, ZB + 0.6, Z0 + 0.5), box("_pt", u - PIN/2, u + PIN/2, -T_P/2, T_P/2, Z1 - 0.5, ZT + 2.4)]
    boolean(o, add, op="UNION")
    cuts = []
    for u in muescas: cuts.append(box("_m", u - 3.5, u + 3.5, -5, 5, ZT - T - 7.5, Z1 + 3))
    zc = (Z0 + Z1) / 2
    libres = []
    if deco: libres.append(deco[1])
    if hueco: cuts.append(box("_h", hueco[0], hueco[1], -5, 5, Z0 - 1, Z0 + 22))
    u = u0 + 14
    while u < u1 - 10:
        if all(abs(u - c) > 34 for c in libres) and all(abs(u - p) > 7 for p in pins) and all(abs(u - m) > 9 for m in muescas) and not (hueco and hueco[0] - 9 < u < hueco[1] + 9):
            for kind, *a in ventana(u, 8, 22, zc):
                cuts.append(box("_v", a[0], a[1], -5, 5, a[2], a[3]) if kind == "box" else cyl("_vc", a[2], a[0], a[1], -5, 5, "Y", 24))
        u += 13
    cut(o, cuts)
    if deco:                                                                            # relieve de 1 capa (0,2 mm) en la cara exterior
        kind, uc = deco
        rel = []
        if kind == "texto":
            t = texto("bicho", 17, uc, zc, REL + 0.1, espejo); t.data.transform(Matrix.Rotation(math.radians(90), 4, 'X'))
            t.data.transform(Matrix.Translation(Vector((0, (T_P / 2 + REL / 2 - 0.05) * M, 0)))); rel.append(t)
        else:                                                                           # ojo con curita (logo de Bicho)
            z0r, z1r = T_P / 2 - 0.1, T_P / 2 + REL
            ojo = cyl("_o", 10, uc, zc, z0r, z1r, "Y", 64); cut(ojo, [cyl("_oi", 6.5, uc, zc, -5, 5, "Y", 64)])
            pupila = cyl("_p", 3.2, uc + 1.2, zc - 0.5, z0r, z1r, "Y", 32)
            cur = box("_c", -9, 9, z0r, z1r, -3, 3); cur.data.transform(Matrix.Rotation(math.radians(-28), 4, 'Y'))
            cur.data.transform(Matrix.Translation(Vector(((uc - 4) * M, 0, (zc + 9) * M)))); rel += [ojo, pupila, cur]
        boolean(o, rel, op="UNION")
    # pasar de local (u, w, z) al chasis: eje x -> (u, fijo + w); eje y -> (fijo + w, u). La cara exterior mira hacia afuera.
    s = 1 if fijo > 0 else -1
    if eje == "x":
        o.data.transform(Matrix(((1, 0, 0, 0), (0, s, 0, fijo * M), (0, 0, 1, 0), (0, 0, 0, 1))))
    else:
        o.data.transform(Matrix(((0, s, 0, fijo * M), (1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))))
        if s < 0: o.data.transform(Matrix(((1, 0, 0, 0), (0, -1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))))
    return soften(o, 0.4)

newcol("Bicho 2 placas + paneles")
R = empty("R_paneles", (0, 0, 0), None); V = ["V5"]
PL = []
# chasis de referencia (2 placas, columnas, cunas, motores y ruedas) para ver cómo queda
placa(R, V, ZB, "inferior"); placa(R, V, ZT, "superior")
for (x, y) in COLS:
    c = pc_columna(); registrar(c, "P23", "Columna 40 mm", "PLA", 1.0, "No", (0, 0, 0), "", V); parent(c, R, (x, y, ZB + T))
for sx in (-1, 1):
    for sy in (-1, 1):
        cu = pc_cuna_motor(); registrar(cu, "P24", "Cuna motor TT", "PETG", .5, "No", (180, 0, 0), "", V)
        parent(cu, R, (sx * (WHEEL_X - 24), sy * MOTOR_Y, ZB), (0, 0, 0 if sx > 0 else 180))
        c_tt_motor().done(R, (sx * (WHEEL_X - 11), sy * MOTOR_Y, 32.5), (0, 0, 0 if sx > 0 else 180), mass=30.6)
        w = empty("W", (sx * WHEEL_X, sy * WHEEL_Y, 32.5), R); c_wheel().done(w, (0, 0, 0), (0, 0, 0 if sy > 0 else 180), mass=36)
for i, x in enumerate((-55, 55)):
    c_holder4().done(grupo(R, f"bat{i}", "Portapilas", (x, 0, ZB + T), superficie="piso1"), (0, 0, 0), (0, 0, 90), mass=25)

# paneles: 2 largos por lado (mitades de 146 mm) + 2 de los extremos
PX = [-140, -110, -80, -50, -20]; PXr = [20, 50, 80, 110, 140]
specs = [
    ("P60", "x", 90.0, -147, -1.0, PX, (-40,), ("ojo", -75), None, "Panel lateral izquierdo · atrás"),
    ("P61", "x", 90.0, 1.0, 147, PXr, (40,), ("texto", 76), None, "Panel lateral izquierdo · adelante"),
    ("P62", "x", -90.0, -147, -1.0, PX, (-40,), ("texto", -76), None, "Panel lateral derecho · atrás"),
    ("P63", "x", -90.0, 1.0, 147, PXr, (40,), ("ojo", 75), None, "Panel lateral derecho · adelante"),
    ("P64", "y", 150.0, -87, 87, [-60, -30, 30, 60], (), None, (-14, 14), "Panel frontal"),
    ("P65", "y", -150.0, -87, 87, [-60, -30, 30, 60], (), None, (-14, 14), "Panel trasero"),
]
paneles = []
for pid, eje, fijo, u0, u1, pins, mues, deco, hueco, nombre in specs:
    p = panel(pid, eje, fijo, u0, u1, pins, mues, deco, hueco)
    prot = (90 * (1 if fijo > 0 else -1), 0, 0) if eje == "x" else (0, -90 * (1 if fijo > 0 else -1), 0)
    registrar(p, pid, nombre, "PLA", .15, "No (cara exterior hacia arriba)", prot,
              "Pasadores de 2,6 mm a la rejilla de las dos placas; doblar levemente para calzar los de arriba", V)
    parent(p, R); paneles.append(p)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "paneles.blend"))
print("OK paneles", sorted(k for k in PIEZAS if k.startswith("P6")))
