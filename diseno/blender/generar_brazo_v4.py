# Bicho · brazo v4 (21-nov-2026): rediseño estructural completo del brazo + pinza de dos dedos engranados.
# Por qué existe: el brazo v3 (P07-P10) no se podía armar (servos sin apoyo de orejas, horn del hombro dentro de la
# pared, codo sin ventana) y cargaba todo en voladizo sobre los ejes de los servos. Ver diseno/bim/MEMORIA_v4.md.
# Reglas de diseño (agente ORBI · Ingeniero Estructural):
#   - cada servo en una cuna, apernado por sus 4 orejas con M3 + tuerca;
#   - apoyo doble en hombro y codo: cada eslabón son 2 placas; una va al horn y la otra gira sobre buje + M3 coaxial;
#   - placas impresas planas (capas a lo largo), unidas por separadores comprimidos con varilla M3;
#   - torreta centrada en el eje del giro, con anillo anti-vuelco bajo la plataforma;
#   - el servo es el fusible: ninguna pieza impresa falla antes del torque de bloqueo de su servo.
# Uso: Blender -b -P generar_brazo_v4.py -- <salida>      (exporta stl/, brazo.glb, piezas_brazo.json)
import os, sys, math, json
AQUI = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(AQUI, "generar_bicho_v3.py"), encoding="utf-8").read()
exec(compile(src[:src.index("VERS = {}")], "generar_bicho_v3.py", "exec"))   # helpers, materiales y componentes

# ------------------------------------------------------------------ parámetros (mm)
M3, M3_TAP, SRV_SCR = 3.4, 2.8, 2.2          # pasante M3, autorroscante M3, tornillo del horn
NUT_R = 5.8 / 2 / math.cos(math.radians(30))  # tuerca M3 (5,5 entre caras + 0,3 de juego)
NUT_H = 2.6
H_TORRE, Z_PLAT = 46.0, 65.0                 # placa del servo de giro / cara inferior de la plataforma
R_TORRE = 42.0
L1, L2 = 100.0, 72.0                          # hombro→codo, codo→eje de los dedos
PL_T = 5.0                                    # espesor de las placas de los eslabones
H1, H2 = 18.0, 16.0                           # medio alto de las placas (eslabón 1, eslabón 2)
SPAN1 = 27.05                                 # cara interior de las placas del eslabón 1 (±)
A2_IN, B2_IN = 33.35, -32.55                  # caras interiores de las placas del eslabón 2
Y_PINZA = (A2_IN + B2_IN) / 2                 # plano medio de la pinza
MOD, ZT = 1.5, 16                             # engranaje de los dedos: módulo y dientes (paso Ø24)
FACE = 10.0                                   # ancho de cara del engranaje = espesor del dedo
XG = L2                                       # eje de los dedos en el eslabón 2
PINZA_OPEN = 48                               # apertura máxima de cada dedo (°)

# ------------------------------------------------------------------ utilidades
def bake(o):
    o.data.transform(o.matrix_basis); o.matrix_basis = Matrix.Identity(4); return o
def box(name, x0, x1, y0, y1, z0, z1, m=PLA):
    return bake(pbox(name, x1 - x0, y1 - y0, z1 - z0, ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), m=m))
def cyl(name, r, x, y, z0, z1, axis="Z", seg=48, m=PLA):
    h = z1 - z0; c = (z0 + z1) / 2
    loc = {"Z": (x, y, c), "Y": (x, c, y), "X": (c, x, y)}[axis]
    rot = {"Z": (0, 0, 0), "Y": (90, 0, 0), "X": (0, 90, 0)}[axis]
    return bake(pcyl(name, r, h, loc, rot, m=m, seg=seg))
def hexp(x, y, z0, z1, axis="Z"):
    return cyl("_hex", NUT_R, x, y, z0, z1, axis, seg=6)
def union(o, parts): return boolean(o, parts, op="UNION")
def cut(o, parts):
    # Desplaza cada cortador unas centésimas de mm para que sus tapas nunca queden coplanares entre sí:
    # el booleano EXACT deja anillos sueltos y aristas no manifold cuando eso pasa.
    for i, c in enumerate(parts):
        d = 0.0037 * ((i % 7) + 1) * M
        c.data.transform(Matrix.Translation(Vector((d, d, d))))
    return boolean(o, parts)
def mat_frame(origin, xs, ys, zs):
    m = Matrix(((xs[0], ys[0], zs[0], origin[0] * M), (xs[1], ys[1], zs[1], origin[1] * M),
                (xs[2], ys[2], zs[2], origin[2] * M), (0, 0, 0, 1)))
    return m
def to_frame(o, F):
    o.data.transform(Matrix.Translation(F.to_translation() * 0) @ F); return o   # F ya trae la traslación en metros
def put_comp(comp_obj, F, shaft_off):
    comp_obj.matrix_parent_inverse = Matrix.Identity(4)
    comp_obj.matrix_basis = F @ Matrix.Translation(Vector((-shaft_off * M, 0, 0)))
    return comp_obj
def stadium(name, xa, xb, r, y0, y1):
    o = box(name, xa, xb, y0, y1, -r, r)
    return union(o, [cyl("_e", r, xa, 0, y0, y1, "Y", 64), cyl("_e", r, xb, 0, y0, y1, "Y", 64)])
def horn_pattern(x, z, y0, y1):
    """Ø7 de acceso al tornillo central + 4 Ø2,2 a r = 7 mm (horn redondo del MG995)."""
    return [cyl("_c", 3.5, x, z, y0 - 1, y1 + 1, "Y", 32)] + [cyl("_c", SRV_SCR / 2, x + dx, z + dz, y0 - 1, y1 + 1, "Y", 16)
                                                              for dx, dz in ((7, 0), (-7, 0), (0, 7), (0, -7))]

# ------------------------------------------------------------------ cuna del MG995 (sistema del servo: eje = +Z, base en Z = 0, cuerpo hacia -X)
def cuna_mg995(nombre, z_back, z_top_walls, wall_out, x_min, x_max, con_base=False, varillas=()):
    """Cuna: placa de orejas (bajo las orejas), placa trasera con buje coaxial, 2 muros laterales.
    z_back: cara exterior de la placa trasera. z_top_walls: hasta dónde suben los muros (tope contra la placa del eslabón)."""
    ear = box(nombre, x_min, x_max, -wall_out, wall_out, 21.3, 26.3)
    parts = [box("_b", x_min, x_max, -wall_out, wall_out, z_back, -1.0),
             box("_w", x_min, x_max, 10.3, wall_out, z_back, z_top_walls),
             box("_w", x_min, x_max, -wall_out, -10.3, z_back, z_top_walls)]
    if con_base: parts.append(box("_f", x_min, x_min + 5, -wall_out, wall_out, z_back, 26.3))
    union(ear, parts)
    cuts = [box("_win", -30.8, 10.4, -10.1, 10.1, 20, 27.5)]                                   # ventana del cuerpo
    for x in (-34.95, 14.55):
        for y in (-5, 5):
            cuts += [cyl("_c", M3 / 2, x, y, 20, 27.5, seg=16), hexp(x, y, 21.3 - 0.01, 21.3 + NUT_H)]  # orejas: M3 + tuerca
    cuts += [cyl("_c", M3 / 2, 0, 0, z_back - 1, 0.5, seg=16), hexp(0, 0, -1.0 - NUT_H, -0.99)]      # eje loco coaxial
    cuts.append(box("_cable", x_min + (5 if con_base else 0) - 0.01, -29.5, -wall_out - 1, -9.5, 0.5, 12))  # salida del cable
    for (x, y) in varillas:
        cuts.append(cyl("_v", M3 / 2, x, y, z_back - 1, z_top_walls + 1, seg=16))
    return soften(cut(ear, cuts), 0.6)

# ------------------------------------------------------------------ armado
newcol("Brazo v4")
R = empty("R_brazo", (0, 0, 0), None, modelo="Bicho · brazo", version="v4")
V = ["V4"]
g = grupo(R, "brazo", "Brazo v4: 3 MG995 + pinza MG90S", (0, 0, 0), superficie="cubierta", movible=False)

# --- P07 Torreta (fija a la cubierta). Eje del giro en (0, 0).
# v4.1 (impresión rápida): sin placa base entera, 4 orejas de anclaje; pared de 2,5 mm (cargas bajas: FS > 10 en vuelco)
t = cyl("P07", R_TORRE, 0, 0, 0, H_TORRE)
union(t, [cyl("_r", R_TORRE, 0, 0, H_TORRE - 0.01, Z_PLAT - 1.0)] +
         [box("_o", sx * 30 - 8, sx * 30 + 8, sy * 40 - 8, sy * 40 + 8, 0, 4) for sx in (-1, 1) for sy in (-1, 1)] +
         [box("_o", min(sx * 22, sx * 34), max(sx * 22, sx * 34), min(sy * 26, sy * 40), max(sy * 26, sy * 40), 0, 4) for sx in (-1, 1) for sy in (-1, 1)])
cut(t, [cyl("_i", R_TORRE - 2.5, 0, 0, -1, H_TORRE - 4), cyl("_i", R_TORRE - 2.0, 0, 0, H_TORRE, Z_PLAT)])
cut(t, [box("_win", -30.8 - 10.2 + 10.2, 10.4, -10.1, 10.1, H_TORRE - 5, H_TORRE + 1)] +           # el cuerpo del servo pasa
       [cyl("_c", M3 / 2, x, y, H_TORRE - 5, H_TORRE + 1, seg=16) for x in (-34.95, 14.55) for y in (-5, 5)] +
       [hexp(x, y, H_TORRE - 4 - 0.01, H_TORRE - 4 + NUT_H) for x in (-34.95, 14.55) for y in (-5, 5)] +
       [cyl("_c", M3 / 2, x, y, -1, 6, seg=16) for x in (-30, 30) for y in (-40, 40)] +
       [box("_cable", -50, -30, -12, 12, 4, 30)])
soften(t, 0.6)
registrar(t, "P07", "Torreta", "PETG", .4, "Sí (árbol, bajo la placa del servo)", (0, 0, 0),
          "Centrada en el eje del giro. 4 M3 a la cubierta en (±30, ±40). Anillo anti-vuelco a 1 mm de la plataforma", V)
parent(t, g)
S1 = put_comp(c_mg995().done(g, mass=55, etiqueta="Servo 1 · giro · MG995 · canal 0"),
              mat_frame((0, 0, H_TORRE - 26.3), (1, 0, 0), (0, 1, 0), (0, 0, 1)), 10.2)
S1.name = "S1_giro"
Jy = empty("J_giro", (0, 0, Z_PLAT), g, eje="Z", canal=0)

# --- P08 Plataforma giratoria + cuna del hombro (sistema J_giro)
SF2 = mat_frame((0, -(SPAN1 - 8.5) - 0.0 - 0.0 + 0.0 - 0.0, 49.0), (0, 0, 1), (1, 0, 0), (0, 1, 0))
# El plano medio del eslabón 1 queda en y = 0: la base del servo del hombro va en y = -18,55.
SF2 = mat_frame((0, -18.55, 49.0), (0, 0, 1), (1, 0, 0), (0, 1, 0))
p = cyl("P08", R_TORRE, 0, 0, 0, 5, seg=96)
cr = cuna_mg995("_cuna", -8.0, 26.3, 14.0, -44.0, 21.0, con_base=True)
to_frame(cr, SF2)
union(p, [cr])
cut(p, [cyl("_rh", 12.5, 0, 0, -1, 1.6, seg=64)] + [cyl("_c", 3.5, 0, 0, -1, 6, seg=32)] + [cyl("_c", SRV_SCR / 2, x, y, -1, 4, seg=16) for x, y in ((7, 0), (-7, 0), (0, 7), (0, -7))])
registrar(p, "P08", "Plataforma y cuna del hombro", "PETG", .4, "No", (0, 0, 0),
          "Disco al horn del giro (4 tornillos del horn a r = 7). Cuna: 4 M3 + tuerca en las orejas; eje loco M3 coaxial atrás", V)
parent(p, Jy)
S2 = put_comp(c_mg995().done(Jy, mass=55, etiqueta="Servo 2 · hombro · MG995 · canal 1"), SF2, 10.2); S2.name = "S2_hombro"
Js = empty("J_hombro", (0, 0, 49.0), Jy, eje="Y", canal=1)

# --- Eslabón 1: placas P09A (al horn) y P09B (loca), separadores y cuna del codo (sistema J_hombro)
X_SEP1 = (36.0, 50.0)
VAR_C = [(-36.0, 14.0), (-36.0, -14.0), (-18.0, 14.0), (-18.0, -14.0)]          # varillas de la cuna del codo (sistema del servo 3)
def var_c_world(): return [(L1 + xs, -ys) for xs, ys in VAR_C]                  # → (x, z) en J_hombro
a1 = stadium("P09A", 0, L1, H1, SPAN1, SPAN1 + PL_T)
cut(a1, horn_pattern(0, 0, SPAN1, SPAN1 + PL_T) + [cyl("_rh", 12.5, 0, 0, SPAN1 - 1, SPAN1 + 1.6, "Y", 64)] +
    [cyl("_c", 8.0, L1, 0, SPAN1 - 1, SPAN1 + PL_T + 1, "Y", 48), cyl("_cb", 13.0, L1, 0, SPAN1 + PL_T - 1.2, SPAN1 + PL_T + 1, "Y", 64)] +
    [cyl("_c", M3 / 2, x, z, SPAN1 - 1, SPAN1 + PL_T + 1, "Y", 16) for x, z in [(x, 0) for x in X_SEP1] + var_c_world()])
soften(a1, 0.6)
b1 = stadium("P09B", 0, L1, H1, -SPAN1 - PL_T, -SPAN1)
cut(b1, [cyl("_c", 4.15, 0, 0, -SPAN1 - PL_T - 1, -SPAN1 + 1, "Y", 48), cyl("_c", M3 / 2, L1, 0, -SPAN1 - PL_T - 1, -SPAN1 + 1, "Y", 16)] +
    [cyl("_c", M3 / 2, x, z, -SPAN1 - PL_T - 1, -SPAN1 + 1, "Y", 16) for x, z in [(x, 0) for x in X_SEP1] + var_c_world()])
soften(b1, 0.6)
registrar(a1, "P09A", "Eslabón 1 · placa del horn", "PETG", .4, "No (plana, cara exterior arriba)", (90, 0, 0),
          "Al horn del hombro (4 tornillos del horn); ventana Ø16 y rebaje Ø26 para el horn del codo", V)
registrar(b1, "P09B", "Eslabón 1 · placa loca", "PETG", .4, "No (plana)", (90, 0, 0),
          "Gira sobre el buje P33 y un M3×12 coaxial con el hombro; recibe el eje loco del codo", V)
parent(a1, Js); parent(b1, Js)
for i, x in enumerate(X_SEP1):
    s = cyl(f"P36_{i}", 6.0, x, 0, -SPAN1, SPAN1, "Y", 32)
    cut(s, [cyl("_c", M3 / 2, x, 0, -SPAN1 - 1, SPAN1 + 1, "Y", 16)])
    if i == 0: registrar(s, "P36", "Separador del eslabón 1 (54,1 mm)", "PETG", .4, "No (de pie)", (90, 0, 0),
                         "Varilla M3 de 66 mm + 2 tuercas: queda comprimido", V)
    else: registrar(s, "P36", "Separador del eslabón 1 (54,1 mm)", "PETG", .4, "No (de pie)", (90, 0, 0), "", V)
    parent(s, Js)
SF3 = mat_frame((L1, -12.25, 0), (1, 0, 0), (0, 0, -1), (0, 1, 0))
c3 = cuna_mg995("P35", -14.8, 39.3, 17.7, -41.0, 19.0, varillas=VAR_C)
to_frame(c3, SF3)
registrar(c3, "P35", "Cuna del codo", "PETG", .4, "No (de pie sobre la placa trasera)", (-90, 0, 0),
          "Entre las placas del eslabón 1 con 4 varillas M3; 4 M3 + tuerca en las orejas; eje loco del codo atrás", V)
parent(c3, Js)
S3 = put_comp(c_mg995().done(Js, mass=55, etiqueta="Servo 3 · codo · MG995 · canal 2"), SF3, 10.2); S3.name = "S3_codo"
Je = empty("J_codo", (L1, 0, 0), Js, eje="Y", canal=2)

# --- Eslabón 2: placas P10A (al horn del codo) y P10B (loca), separador y pinza (sistema J_codo)
X_SEP2 = 34.0
RODS = [(47.0, -5.0), (56.0, -5.0)]                       # varillas de la palma
END2 = 60.0
a2 = stadium("P10A", 0, END2, H2, A2_IN, A2_IN + PL_T)
cut(a2, horn_pattern(0, 0, A2_IN, A2_IN + PL_T) + [cyl("_rh", 12.5, 0, 0, A2_IN - 1, A2_IN + 1.6, "Y", 64)] + [cyl("_c", M3 / 2, x, z, A2_IN - 1, A2_IN + PL_T + 1, "Y", 16) for x, z in [(X_SEP2, 0)] + RODS])
b2 = stadium("P10B", 0, END2, H2, B2_IN - PL_T, B2_IN)
cut(b2, [cyl("_c", 4.15, 0, 0, B2_IN - PL_T - 1, B2_IN + 1, "Y", 48)] + [cyl("_c", M3 / 2, x, z, B2_IN - PL_T - 1, B2_IN + 1, "Y", 16) for x, z in [(X_SEP2, 0)] + RODS])
registrar(a2, "P10A", "Eslabón 2 · placa del horn", "PETG", .4, "No (plana)", (90, 0, 0), "Al horn del codo (4 tornillos del horn)", V)
registrar(b2, "P10B", "Eslabón 2 · placa loca", "PETG", .4, "No (plana)", (90, 0, 0), "Gira sobre el buje P33 y un M3×20 coaxial con el codo", V)
parent(a2, Je); parent(b2, Je)
s2 = cyl("P37", 6.0, X_SEP2, 0, B2_IN, A2_IN, "Y", 32); cut(s2, [cyl("_c", M3 / 2, X_SEP2, 0, B2_IN - 1, A2_IN + 1, "Y", 16)])
registrar(s2, "P37", "Separador del eslabón 2 (65,9 mm)", "PETG", .4, "No (de pie)", (90, 0, 0), "Varilla M3 de 78 mm + 2 tuercas", V)
parent(s2, Je)

# --- Pinza
YA, YB = Y_PINZA - 12.0, Y_PINZA + 12.0                    # ejes del dedo motriz (A, sobre el MG90S) y del conducido (B)
Z_PALM0, Z_PALM1 = -15.9, -10.9                            # palma bajo los dedos; las orejas del MG90S van debajo
Z_F0, Z_F1 = -5.0, 5.0                                     # plano de los dedos
Z_BR0, Z_BR1 = 5.4, 10.4                                    # contraplaca (puente)
LUG = 6.0
palm = box("P30", 41, 86, B2_IN, A2_IN, Z_PALM0, Z_PALM1)
union(palm, [box("_l", 41, 60, B2_IN, B2_IN + LUG, Z_PALM0, Z_BR0), box("_l", 41, 60, A2_IN - LUG, A2_IN, Z_PALM0, Z_BR0),
             cyl("_boss", 5.0, XG, YB, Z_PALM1 - 0.01, Z_F0 - 0.4)])
LUGY = (B2_IN + LUG / 2, A2_IN - LUG / 2)
cut(palm, [box("_win", XG - 17.3 - 0.2, XG + 5.5 + 0.2, YA - 6.1 - 0.2, YA + 6.1 + 0.2, Z_PALM0 - 1, Z_PALM1 + 1)] +
    [cyl("_c", 1.0, XG + dx, YA, Z_PALM0 - 1, Z_PALM1 + 1, seg=12) for dx in (-19.8, 8.0)] +          # orejas del MG90S (sus tornillos)
    [cyl("_c", M3 / 2, XG, YB, Z_PALM0 - 1, Z_F0, seg=16), hexp(XG, YB, Z_PALM0 - 0.01, Z_PALM0 + NUT_H)] +
    [cyl("_c", M3 / 2, x, z, B2_IN - 1, A2_IN + 1, "Y", 16) for x, z in RODS] +
    [cyl("_c", M3 / 2, 51.5, y, Z_PALM0 - 1, Z_BR0 + 1, seg=16) for y in LUGY] + [hexp(51.5, y, Z_PALM0 - 0.01, Z_PALM0 + NUT_H) for y in LUGY])
soften(palm, 0.5)
registrar(palm, "P30", "Palma de la pinza", "PETG", .4, "No (palma contra la cama)", (0, 0, 0),
          "Entre las placas del eslabón 2 con 2 varillas M3; MG90S por debajo; pivote del dedo conducido", V)
parent(palm, Je)
br = box("P34", 41, 84, B2_IN, A2_IN, Z_BR0, Z_BR1)
cut(br, [cyl("_j", 5.3, XG, YA, Z_BR0 - 1, Z_BR1 + 1, seg=48), cyl("_c", M3 / 2, XG, YB, Z_BR0 - 1, Z_BR1 + 1, seg=16),
         hexp(XG, YB, Z_BR1 - NUT_H, Z_BR1 + 0.01)] + [cyl("_c", M3 / 2, 51.5, y, Z_BR0 - 1, Z_BR1 + 1, seg=16) for y in LUGY] +
        [box("_aligera", 43, 58, -22, 22, Z_BR0 - 1, Z_BR1 + 1)])
soften(br, 0.5)
registrar(br, "P34", "Contraplaca de los dedos", "PETG", .4, "No (plana)", (0, 0, 0),
          "Segundo apoyo de los dos pivotes: el dedo conducido queda en corte doble y el motriz no carga el eje del MG90S", V)
parent(br, Je)
S4 = put_comp(c_mg90s().done(Je, mass=13.4, etiqueta="Servo 4 · pinza · MG90S · canal 3"),
              mat_frame((XG, YA, Z_F0 + 1.8 - 31.4), (1, 0, 0), (0, 1, 0), (0, 0, 1)), 5.9)
S4.name = "S4_pinza"

def engranaje(fase):
    z, mod = ZT, MOD; rp = mod * z / 2; a0 = math.radians(20); rb = rp * math.cos(a0); ra = rp + mod; rf = rp - 1.25 * mod
    inv = lambda a: math.tan(a) - a; medio = math.pi / (2 * z) - 0.004
    ancho = lambda r: medio + inv(a0) - (inv(math.acos(rb / r)) if r > rb else 0)
    pts = []
    for k in range(z):
        c = math.radians(fase) + 2 * math.pi * k / z
        f = [(rf, c - ancho(rb))] + [(rb + (ra - rb) * i / 4, c - ancho(rb + (ra - rb) * i / 4)) for i in range(5)]
        f += [(rb + (ra - rb) * i / 4, c + ancho(rb + (ra - rb) * i / 4)) for i in range(4, -1, -1)] + [(rf, c + ancho(rb))]
        pts += [(r * math.cos(a), r * math.sin(a)) for r, a in f]
    return pts
def prisma(name, pts, z0, z1):
    bm = bmesh.new(); vs = [bm.verts.new(Vector((x * M, y * M, z0 * M))) for x, y in pts]
    f = bm.faces.new(vs); ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, vec=(0, 0, (z1 - z0) * M), verts=[v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _obj(name, bm, PLA)
def dedo(nombre, s, fase, motriz):
    """Dedo en su sistema: pivote en el origen, apunta a +X, lado de agarre hacia s·Y (s = +1 dedo A, -1 dedo B)."""
    yy = lambda pts: [(x, s * y) for x, y in pts]
    o = prisma(nombre, yy([(8, 1), (26, 1), (26, 12), (14, 12), (8, 9)]), Z_F0, Z_F1)               # raíz
    union(o, [prisma("_g", engranaje(fase), Z_F0, Z_F1),
              prisma("_n", yy([(25.9, 6), (32.1, 6), (32.1, 12), (25.9, 12)]), Z_F0, Z_F0 + 7),         # cuello fusible 6 × 7
              prisma("_m", yy([(32, 3), (46, 3), (46, 12), (32, 12)]), Z_F0, Z_F1),
              prisma("_j", yy([(44, 4), (64, 4), (64, 12), (44, 12)]), Z_F0, 14.0)])                    # mordaza de 18 mm de alto
    cuts = [prisma("_r", yy([(x, 11.2), (x + 1.2, 11.2), (x + 1.2, 12.5), (x, 12.5)]), Z_F0 - 1, 15) for x in range(46, 63, 3)]
    if motriz:
        union(o, [cyl("_ring", 5.0, 0, 0, Z_F1 - 0.01, Z_BR1, seg=48)])
        cuts += [cyl("_c", 2.75, 0, 0, Z_F0 - 1, Z_BR1 + 1, seg=32), cyl("_hub", 4.0, 0, 0, Z_F0 - 1, Z_F0 + 1.8, seg=32),
                 box("_arm", -21.5, 21.5, -2.9, 2.9, Z_F0 - 1, Z_F0 + 1.8)]                                  # rebaje del horn de un brazo
    else:
        cuts += [cyl("_c", 3.15, 0, 0, Z_F0 - 1, Z_F1 + 1, seg=32)]
    return soften(cut(o, cuts), 0.4)
Ja = empty("J_pinza_a", (XG, YA, 0), Je, eje="Z", canal=3)
Jb = empty("J_pinza_b", (XG, YB, 0), Je, eje="Z", espejo="J_pinza_a")
fa = dedo("P31", +1, 90.0, True)
registrar(fa, "P31", "Dedo motriz", "PETG", 1.0, "No (plano)", (0, 0, 0),
          "Va sobre el horn de un brazo del MG90S; engranaje m 1,5 z 16 de 10 mm; cuello fusible 6 × 6 a 26 mm del eje", V)
parent(fa, Ja)
fb = dedo("P32", -1, 270.0 + 180.0 / ZT, False)
registrar(fb, "P32", "Dedo conducido", "PETG", 1.0, "No (plano)", (0, 0, 0),
          "Gira sobre el buje P33 y un M3×30 en corte doble (palma abajo, contraplaca arriba)", V)
parent(fb, Jb)
# P33 bujes: 2 de Ø8 × 5,4 (hombro y codo) + 1 de Ø6 × 10,8 (dedo conducido), una sola bandeja
bj = cyl("P33", 4.0, 0, 0, 0, 5.4, seg=32); union(bj, [cyl("_b", 4.0, 12, 0, 0, 5.4, seg=32), cyl("_b", 3.0, 24, 0, 0, 10.8, seg=32)])
cut(bj, [cyl("_c", M3 / 2, x, 0, -1, 10, seg=16) for x in (0, 12, 24)])
registrar(bj, "P33", "Bujes (hombro, codo y dedo)", "PETG", 1.0, "No (de pie)", (0, 0, 0),
          "Ø8 × 5,4 en las placas locas P09B y P10B; Ø6 × 10,8 en el dedo conducido. Al 100 %", V)
bj.hide_render = True; bj.hide_viewport = True; parent(bj, g, (-200, 0, 0))

# ------------------------------------------------------------------ pose de muestra y exportación
bpy.context.view_layer.update()
for ob in bpy.context.view_layer.objects: ob.select_set(False)
for ob in R.users_collection[0].all_objects:
    if ob.name.startswith("P33"): continue
    ob.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "brazo.glb"), export_format='GLB', use_selection=True,
                          export_extras=True, export_apply=False, export_yup=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "brazo_v4.blend"))
json.dump(dict(piezas=list(PIEZAS.values())), open(os.path.join(OUT, "piezas_brazo.json"), "w"), ensure_ascii=False, indent=1)
print("OK brazo v4", sorted(PIEZAS))
