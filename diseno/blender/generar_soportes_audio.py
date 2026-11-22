# Bicho · soportes del ReSpeaker XVF3800 (P42) y del parlante (P43). Base con 4 agujeros M3 a la rejilla de 10 mm de la cubierta.
import os, sys, math, json
src = open(os.environ["GEN_V3"], encoding="utf-8").read()
exec(compile(src[:src.index("VERS = {}")], "generar_bicho_v3.py", "exec"))
M3 = 3.4
def bake(o): o.data.transform(o.matrix_basis); o.matrix_basis = Matrix.Identity(4); return o
def box(n, x0, x1, y0, y1, z0, z1): return bake(pbox(n, x1-x0, y1-y0, z1-z0, ((x0+x1)/2, (y0+y1)/2, (z0+z1)/2), m=PLA))
def cyl(n, r, x, y, z0, z1, axis="Z", seg=64):
    h = z1 - z0; c = (z0 + z1) / 2
    loc = {"Z": (x, y, c), "Y": (x, c, y), "X": (c, x, y)}[axis]; rot = {"Z": (0,0,0), "Y": (90,0,0), "X": (0,90,0)}[axis]
    return bake(pcyl(n, r, h, loc, rot, m=PLA, seg=seg))
def cut(o, parts):
    for i, c in enumerate(parts):
        d = 0.0033 * ((i % 7) + 1) * M; c.data.transform(Matrix.Translation(Vector((d, d, d))))
    return boolean(o, parts)
newcol("Audio"); V = ["V4"]
# ---- P42 ReSpeaker XVF3800 (placa redonda Ø99): anillo con repisa a 10 mm, 3 trabas con ranura, salida de cables
D_RS = 99.0; RI = D_RS / 2 + 0.8; RO = RI + 2.4; Z_REP = 10.0
o = cyl("P42", RO, 0, 0, 0, Z_REP + 4.5, seg=128)
cut(o, [cyl("_i", RI, 0, 0, Z_REP, 30, seg=128), cyl("_i", RI - 5, 0, 0, 3, 30, seg=128)])          # repisa de 5 mm, piso de 3 mm
cut(o, [cyl("_a", 30, 0, 0, -1, 4, seg=96)] + [box("_c", -14, 14, RO - 6, RO + 2, 3, 30)])          # aligerado central y salida USB/parlante
for k in range(3):                                                                                     # trabas: diente de 0,7 mm sobre la placa
    a = math.radians(90 + 120 * k + 60); x, y = (RI - 0.35) * math.cos(a), (RI - 0.35) * math.sin(a)
    t = cyl("_t", 2.2, x, y, Z_REP + 1.9, Z_REP + 3.4, seg=24); boolean(o, [t], op="UNION")
    for s in (-1, 1):
        b = math.radians(90 + 120 * k + 60 + s * 9)
        sl = box("_s", -0.6, 0.6, -3.5, 3.5, Z_REP - 4, 40); sl.data.transform(Matrix.Rotation(b, 4, 'Z') @ Matrix.Translation(Vector(((RI + 1.2) * M, 0, 0))))
        cut(o, [sl])
cut(o, [cyl("_h", M3 / 2, x, y, -1, 5, seg=16) for (x, y) in ((40, 0), (-40, 0), (0, 40), (0, -40))])
soften(o, 0.4)
registrar(o, "P42", "Soporte del ReSpeaker XVF3800", "PLA", .15, "No", (0, 0, 0),
          "Placa Ø99 apoyada en una repisa a 10 mm; 3 trabas con ranura la retienen; salida de 28 mm para USB y parlante; 4 M3 a ±40 mm", V)
# ---- P43 Parlante (cuadrado o redondo de 40 a 52 mm): caja abierta arriba, rejilla al frente
W, DP, H = 53.0, 30.0, 46.0
p = box("P43", -W/2 - 2.4, W/2 + 2.4, -DP/2 - 2.4, DP/2 + 2.4, 0, H)
cut(p, [box("_i", -W/2, W/2, -DP/2, DP/2, 2.4, H + 1), cyl("_g", 20, 0, -DP/2 - 1.2, 20, 0, "Y", 96)])
p.data.transform(Matrix.Identity(4))
cut(p, [cyl("_g", 19, 0, H * 0.48, -DP/2 - 3, -DP/2 + 0.5, "Y", 96), box("_cab", -6, 6, DP/2 - 0.5, DP/2 + 3, 2.4, 14)])
base = box("_b", -W/2 - 12, W/2 + 12, -DP/2 - 2.4, DP/2 + 2.4, 0, 3)
boolean(p, [base], op="UNION")
cut(p, [cyl("_h", M3 / 2, x, 0, -1, 5, seg=16) for x in (-W/2 - 6, W/2 + 6)])
soften(p, 0.4)
registrar(p, "P43", "Soporte del parlante", "PLA", .15, "No", (0, 0, 0),
          "Parlante de 40 a 52 mm, entra desde arriba mirando al frente (rejilla Ø38); fijar con silicona caliente; salida de cable atrás; 2 M3", V)
print("OK audio", sorted(PIEZAS))
