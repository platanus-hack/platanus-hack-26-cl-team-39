# Bicho · modelo BIM del brazo (sin muñeca, 3 MG995 + pinza MG90S).
# Reutiliza las piezas de generar_bicho_v3.py tal como se imprimieron (P07-P10) y agrega la pinza (P30-P34) si existe
# generar_pinza.py. Exporta: <salida>/brazo.glb (ensamble articulado), <salida>/stl/*.stl (orientadas para imprimir).
# Uso: Blender -b -P generar_brazo_bim.py -- <salida>
import os, sys, math, json
AQUI = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(AQUI, "generar_bicho_v3.py"), encoding="utf-8").read()
src = src[:src.index("VERS = {}")]          # solo definiciones, sin armar V1-V3
exec(compile(src, "generar_bicho_v3.py", "exec"))

newcol("Brazo BIM")
R = empty("R_brazo", (0, 0, 0), None, modelo="Bicho · brazo", version="v4")
V = ["V4"]

g = grupo(R, "brazo", "Brazo de 3 MG995 + pinza MG90S", (0, 0, 0), superficie="cubierta", movible=False)
t = pc_torreta(); registrar(t, "P07", "Torreta alta", "PETG", .4, "No", (0, 0, 0), "Pedestal de 46 mm; 4 M3 a la rejilla", V)
parent(t, g, (5, 0, 0)); t.name = "P07"
c_mg995(horn=False).done(g, (-5, 0, 46 - 37 + 3.6), mass=55, etiqueta="Servo 1 · giro · MG995 · canal 0").name = "S1_giro"
Jy = empty("J_giro", (5.2, 0, 46 + 9.6), g, eje="Z", canal=0)
hq = pc_horquilla(); registrar(hq, "P08", "Horquilla del hombro", "PETG", .4, "No", (0, 0, 0), "Tornillo del horn al centro", V)
parent(hq, Jy); hq.name = "P08"
c_mg995().done(Jy, (-10.2, -21.5, 30), (-90, 0, 0), mass=55, etiqueta="Servo 2 · hombro · MG995 · canal 1").name = "S2_hombro"
Js = empty("J_hombro", (0, 0, 30), Jy, eje="Y", canal=1)
l1 = pc_eslabon("P09 Eslabón 1", 100); registrar(l1, "P09", "Eslabón 1", "PETG", .4, "No (de canto)", (90, 0, 0), "De canto: las capas siguen el largo", V)
parent(l1, Js, (0, 31, 0)); l1.name = "P09"
c_mg995().done(Js, (100 - 10.2, 19, 0), (90, 0, 0), mass=55, etiqueta="Servo 3 · codo · MG995 · canal 2").name = "S3_codo"
Je = empty("J_codo", (100, 0, 0), Js, eje="Y", canal=2)
l2 = pc_eslabon2(90); registrar(l2, "P10", "Eslabón 2", "PETG", .4, "No (de canto)", (90, 0, 0), "El alojamiento del MG90S queda libre: ahí se encaja la pinza", V)
parent(l2, Je, (0, -10, 0)); l2.name = "P10"

PINZA = os.path.join(AQUI, "generar_pinza.py")
if os.path.exists(PINZA):
    exec(compile(open(PINZA, encoding="utf-8").read(), "generar_pinza.py", "exec"))
    pinza(Je, V)            # define J_pinza_a / J_pinza_b, servo 4 y P30-P34

bpy.context.view_layer.update()
for ob in bpy.context.view_layer.objects: ob.select_set(False)
for ob in R.users_collection[0].all_objects: ob.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "brazo.glb"), export_format='GLB', use_selection=True,
                          export_extras=True, export_apply=False, export_yup=True)
json.dump(dict(piezas=list(PIEZAS.values())), open(os.path.join(OUT, "piezas_brazo.json"), "w"), ensure_ascii=False, indent=1)
print("OK brazo", sorted(PIEZAS))
