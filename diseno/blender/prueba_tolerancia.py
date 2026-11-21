# P00 · Pieza de prueba (20 min): agujeros M3 de 3,2/3,4/3,6 mm a paso de 10 mm + cola de milano macho/hembra con 0,15 mm de juego
import bpy, bmesh, sys, os, math
from mathutils import Vector, Matrix
M = 0.001; OUT = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
col = bpy.context.scene.collection
def obj(bm, name):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me); col.objects.link(o); return o
def box(sx, sy, sz, loc):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts: v.co = Vector((v.co.x * sx + loc[0], v.co.y * sy + loc[1], v.co.z * sz + loc[2])) * M
    return obj(bm, "b")
def cyl(r, h, loc):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=r * M, radius2=r * M, depth=h * M)
    bmesh.ops.translate(bm, vec=Vector(loc) * M, verts=bm.verts); return obj(bm, "c")
def tail(cl, x0, z0, z1):  # la cola va del alto de la tira (0 a 4 mm); antes iba de -10 a 10 y la tira quedaba en el aire
    bm = bmesh.new(); vs = []
    for z in (z0, z1):
        for (x, y) in ((0.6, -5 - cl), (-14 - cl, -8.5 - cl), (-14 - cl, 8.5 + cl), (0.6, 5 + cl)):
            vs.append(bm.verts.new(Vector((x + x0, y, z)) * M))
    bmesh.ops.convex_hull(bm, input=vs); return obj(bm, "t")
def boolean(o, others, op):
    for c in others:
        md = o.modifiers.new("b", "BOOLEAN"); md.object = c; md.operation = op; md.solver = 'EXACT'
    dg = bpy.context.evaluated_depsgraph_get(); me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    o.modifiers.clear(); o.data = me
    for c in others: bpy.data.objects.remove(c, do_unlink=True)
# macho: tira con 3 agujeros + cola
a = box(40, 24, 4, (-20, 0, 2))
boolean(a, [tail(0, 0, 0, 4)], "UNION")
boolean(a, [cyl(d / 2, 10, (-35 + i * 10, 0, 2)) for i, d in enumerate((3.2, 3.4, 3.6))], "DIFFERENCE")
# hembra: tira con alojamiento (+0,15 mm) separada 10 mm
b = box(40, 24, 4, (30, 0, 2))
boolean(b, [tail(0.15, 10.15 + 0.0, -1, 5)], "DIFFERENCE")
boolean(b, [cyl(1.7, 10, (40, 0, 2)), cyl(1.7, 10, (50, 0, 2))], "DIFFERENCE")
bpy.context.view_layer.update()
bpy.ops.object.select_all(action="DESELECT")
a.select_set(True); b.select_set(True)
bpy.ops.wm.stl_export(filepath=os.path.join(OUT, "P00_prueba_de_tolerancia.stl"), export_selected_objects=True, global_scale=1000.0)
print("OK P00")
