# Bicho · soportes del LiDAR (EAI S850 + placa Radar_Con V1.4) y de la cámara frontal (Pi Camera v1.3).
# Las placas entran DESDE ARRIBA en ranuras; el soporte tiene base para pegar (o apernar con 2-4 M3 a la rejilla de
# 10 mm de la cubierta) y muros perpendiculares a la base con cartelas. Imprimir con la base en la cama, sin soportes.
# Medidas de las placas: las de la Pi Camera v1.3 son las de su plano oficial; las del S850 y su adaptadora se
# midieron en foto contra el USB-C (8,94 mm): ±1 mm. MEDIRLAS con pie de metro y ajustar W_* / H_* antes de imprimir.
# Uso: Blender -b -P generar_soportes_sensores.py -- <salida>
import os, sys, math, json
AQUI = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(AQUI, "generar_bicho_v3.py"), encoding="utf-8").read()
exec(compile(src[:src.index("VERS = {}")], "generar_bicho_v3.py", "exec"))

# ---------------- medidas de las placas (mm) ----------------
W_LIDAR, H_LIDAR, T_LIDAR = 20.0, 25.0, 1.6        # módulo S850 (ancho × alto × espesor de la PCB) [foto, ±1]
W_ADAPT, H_ADAPT, T_ADAPT = 25.0, 31.0, 1.6        # placa Radar_Con V1.4 [foto, ±1]
GAP_LIDAR = 14.0                                    # separación sensor → adaptadora (componentes + cable)
W_CAM, H_CAM, T_CAM = 25.0, 24.0, 1.0              # Pi Camera v1.3 [plano oficial]
TILT_CAM = 12.0                                     # la cámara mira 12° hacia arriba (ve personas y manos a 1-2 m)
JUEGO, LABIO, BASE_T, PARED = 0.8, 1.2, 3.0, 3.0    # juego lateral, labio que retiene la placa, base, pared

M3 = 3.4
def bake(o):
    o.data.transform(o.matrix_basis); o.matrix_basis = Matrix.Identity(4); return o
def box(name, x0, x1, y0, y1, z0, z1):
    return bake(pbox(name, x1 - x0, y1 - y0, z1 - z0, ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), m=PLA))
def cyl(name, r, x, y, z0, z1, seg=24):
    return bake(pcyl(name, r, z1 - z0, (x, y, (z0 + z1) / 2), m=PLA, seg=seg))
def cut(o, parts):
    for i, c in enumerate(parts):
        d = 0.0033 * ((i % 7) + 1) * M; c.data.transform(Matrix.Translation(Vector((d, d, d))))
    return boolean(o, parts)

def ranura(x_pcb, W, H, T, z0, alto, abierta_abajo=False, notch_atras=0.0):
    """Dos postes con ranura vertical para una PCB de ancho W y espesor T, plano de la PCB en x = x_pcb (normal +X).
    La PCB entra desde arriba y apoya en el fondo de la ranura (z0)."""
    yb = W / 2 + JUEGO                    # fondo de la ranura
    yl = W / 2 - LABIO                    # cara interior de los labios
    xr0, xr1 = x_pcb - T / 2 - 0.25, x_pcb + T / 2 + 0.25
    posts = []
    for s in (-1, 1):
        p = box("_p", xr0 - 2.0, xr1 + 2.0, min(s * yl, s * (yb + PARED)), max(s * yl, s * (yb + PARED)), 0, z0 + alto)
        cuts = [box("_g", xr0, xr1, min(s * (yl - 0.5), s * yb), max(s * (yl - 0.5), s * yb), z0, z0 + alto + 1)]
        if notch_atras: cuts.append(box("_n", xr0 - 2.1, xr0, min(s * (yl - 0.5), s * (yl + 1.6)), max(s * (yl - 0.5), s * (yl + 1.6)), z0 - 0.01, z0 + notch_atras))
        posts.append(cut(p, cuts))
    return posts

def cartelas(x0, x1, ys, h):
    """Cartelas triangulares perpendiculares a los muros (planos XZ), de la base al muro."""
    out = []
    for y in ys:
        bm = bmesh.new()
        pts = [(x0, 0), (x1, 0), (x1, h)] if x1 > x0 else [(x1, 0), (x0, 0), (x1, h)]
        vs = []
        for yy in (y - 1.25, y + 1.25):
            for (x, z) in pts: vs.append(bm.verts.new(Vector((x * M, yy * M, z * M))))
        bmesh.ops.convex_hull(bm, input=vs); out.append(_obj("_c", bm, PLA))
    return out

newcol("Soportes de sensores")
R = empty("R_sensores", (0, 0, 0), None)
V = ["V4"]
PIEZAS_OUT = []

# ================= P40 · Soporte del LiDAR (sensor adelante, adaptadora atrás; las dos entran desde arriba) =================
XS, XA = 6.0, 6.0 - GAP_LIDAR                     # plano de la PCB del sensor y de la adaptadora
yA = W_ADAPT / 2 + JUEGO + PARED
base = box("P40", XA - 6, XS + 6, -(yA + 4), yA + 4, 0, BASE_T)
union_parts = ranura(XS, W_LIDAR, H_LIDAR, T_LIDAR, BASE_T, H_LIDAR - 4) + ranura(XA, W_ADAPT, H_ADAPT, T_ADAPT, BASE_T, H_ADAPT - 8)
ys_s = W_LIDAR / 2 + JUEGO + PARED; ys_a = yA
union_parts += [box("_w", XA + 2.5, XS - 2.5, s * ys_s - PARED if s > 0 else -ys_s, ys_s if s > 0 else -ys_s + PARED, 0, 12) for s in (1, -1)]   # muros que unen las dos ranuras
union_parts += cartelas(XA - 6, XA - 2, (-ys_a + 1.5, ys_a - 1.5), H_ADAPT - 10) + cartelas(XS + 6, XS + 2, (-ys_s + 1.5, ys_s - 1.5), H_LIDAR - 8)
boolean(base, union_parts, op="UNION")
cut(base, [cyl("_h", M3 / 2, x, y, -1, BASE_T + 1) for x in (XA - 3, XS + 3) for y in (-(yA + 1), yA + 1)] +
    [box("_cable", XA + 2, XS - 2, -6, 6, -1, BASE_T + 1)])                  # paso del cable de 4 hilos, por si va abajo
soften(base, 0.4)
registrar(base, "P40", "Soporte del LiDAR", "PETG o PLA", .4, "No (base en la cama)", (0, 0, 0),
          "El S850 entra desde arriba con el conector arriba, mirando al frente; la Radar_Con entra atrás con el USB-C arriba. Pegar o 4 M3 a la rejilla", V)
parent(base, R)

# ================= P41 · Soporte de la cámara frontal (inclinada TILT_CAM° hacia arriba) =================
cam = box("P41", -14, 10, -(W_CAM / 2 + 12), W_CAM / 2 + 12, 0, BASE_T)
alto = H_CAM - 5
posts = ranura(0.0, W_CAM, H_CAM, T_CAM, BASE_T, alto, notch_atras=7.0)
ys_c = W_CAM / 2 + JUEGO + PARED
posts += cartelas(-12, -2.5, (-ys_c + 1.5, ys_c - 1.5), alto - 2)
grp = posts
for o in grp:                                      # inclinar los postes alrededor del borde delantero de la base
    o.data.transform(Matrix.Translation(Vector((0, 0, BASE_T * M))) @ Matrix.Rotation(math.radians(-TILT_CAM), 4, 'Y') @ Matrix.Translation(Vector((0, 0, -BASE_T * M))))
boolean(cam, grp, op="UNION")
cut(cam, [box("_cinta", -6.5, 1.5, -(W_CAM / 2 - 1.5), W_CAM / 2 - 1.5, -1, BASE_T + 1)] +        # la cinta FFC baja por aquí
    [cyl("_h", M3 / 2, x, y, -1, BASE_T + 1) for x in (-6, 4) for y in (-20, 20)] + [box("_suelo", -40, 40, -40, 40, -10, 0)])
soften(cam, 0.4)
registrar(cam, "P41", "Soporte de la cámara frontal", "PETG o PLA", .4, "No (base en la cama)", (0, 0, 0),
          f"La Pi Camera entra desde arriba, lente al frente, inclinada {TILT_CAM:.0f}° hacia arriba; la cinta baja por la ventana de la base al pasacables delantero (x = 130)", V)
parent(cam, R)

json.dump(dict(piezas=list(PIEZAS.values())), open(os.path.join(OUT, "piezas_sensores.json"), "w"), ensure_ascii=False, indent=1)
print("OK sensores", sorted(PIEZAS))
