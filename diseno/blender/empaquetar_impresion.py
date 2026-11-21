# Arma las bandejas .3mf (cama 220×220, sirve en Ender 3, Prusa MK3/MK4, Bambu A1/P1/X1) a partir de los STL de salida_v3.
# Uso: python3 -I empaquetar_impresion.py <salida_v3> <carpeta_destino>
import json, os, struct, sys, zipfile

SRC, DST = sys.argv[1], sys.argv[2]
STL = os.path.join(SRC, "stl")
BED, MARGIN, GAP = 220.0, 6.0, 6.0
os.makedirs(os.path.join(DST, "3MF_bandejas"), exist_ok=True)

def read_stl(path):
    data = open(path, "rb").read()
    n = struct.unpack("<I", data[80:84])[0]
    verts, idx, tris = [], {}, []
    for i in range(n):
        off = 84 + i * 50
        vals = struct.unpack("<12f", data[off:off + 48])
        t = []
        for k in range(3):
            v = (round(vals[3 + k * 3], 4), round(vals[4 + k * 3], 4), round(vals[5 + k * 3], 4))
            if v not in idx: idx[v] = len(verts); verts.append(v)
            t.append(idx[v])
        if len(set(t)) == 3: tris.append(t)
    xs = [v[0] for v in verts]; ys = [v[1] for v in verts]; zs = [v[2] for v in verts]
    return dict(verts=verts, tris=tris, bb=(min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))

FILES = {f.split("_")[0]: f for f in os.listdir(STL) if f.endswith(".stl")}
MESH = {}
def mesh(pid):
    if pid not in MESH: MESH[pid] = read_stl(os.path.join(STL, FILES[pid]))
    return MESH[pid]

def pack(items, margin=MARGIN, bed=BED):
    """Estantes simples; prueba 0° y 90° por pieza. items = [pid, ...]. Devuelve [(pid, x, y, rot)] o lanza si no cabe."""
    sizes = []
    for pid in items:
        b = mesh(pid)["bb"]; sizes.append((pid, b[1] - b[0], b[3] - b[2]))
    sizes.sort(key=lambda s: -max(s[1], s[2]))
    W = bed - 2 * margin; placed = []; x = 0; y = 0; row = 0
    for pid, w, d in sizes:
        opts = [(w, d, 0), (d, w, 90)]
        ok = None
        for (ww, dd, r) in opts:
            if x + ww <= W and y + dd <= W: ok = (ww, dd, r); break
        if not ok:
            x = 0; y += row + GAP; row = 0
            for (ww, dd, r) in opts:
                if ww <= W and y + dd <= W: ok = (ww, dd, r); break
        if not ok: raise RuntimeError(f"No cabe {pid} en la bandeja")
        ww, dd, r = ok
        placed.append((pid, margin + x + ww / 2, margin + y + dd / 2, r))
        x += ww + GAP; row = max(row, dd)
    return placed

def write_3mf(path, placed, titulo):
    objs, build = [], []
    for i, (pid, cx, cy, r) in enumerate(placed, start=1):
        m = mesh(pid); b = m["bb"]; ox, oy = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
        vx = "".join(f'<vertex x="{v[0]-ox:.4f}" y="{v[1]-oy:.4f}" z="{v[2]-b[4]:.4f}"/>' for v in m["verts"])
        tx = "".join(f'<triangle v1="{t[0]}" v2="{t[1]}" v3="{t[2]}"/>' for t in m["tris"])
        name = FILES[pid][:-4]
        objs.append(f'<object id="{i}" name="{name}" type="model"><mesh><vertices>{vx}</vertices><triangles>{tx}</triangles></mesh></object>')
        c, s = (1, 0) if r == 0 else (0, 1)
        build.append(f'<item objectid="{i}" transform="{c} {s} 0 {-s} {c} 0 0 0 1 {cx:.3f} {cy:.3f} 0"/>')
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="es-CL" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             f'<metadata name="Title">{titulo}</metadata><metadata name="Designer">Equipo CRBRC · Platanus Hack 26</metadata>'
             f'<resources>{"".join(objs)}</resources><build>{"".join(build)}</build></model>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr("3D/3dmodel.model", model)

P = {p["id"]: p for p in json.load(open(os.path.join(SRC, "piezas_v3.json")))["piezas"]}
P["P00"] = dict(id="P00", nombre="Prueba de tolerancia", material="El de las placas", relleno=40, soportes="No", gramos=6.0, horas=0.35,
                medidas_mm=[90, 24, 4], notas="Imprimir primero (20 min): elige el agujero M3 que entra justo y comprueba la cola de milano")

# perfiles de impresión (valores probados para FDM con boquilla 0,4 mm)
PERFIL = {
 "PLA-ESTRUCTURA": dict(material="PLA (o PLA+)", boquilla="210 °C", cama="60 °C", capa="0,20 mm", paredes="4 (1,6 mm)", superior_inferior="5 / 5",
                        relleno="40 % giroide", velocidad="perímetro exterior 60 mm/s · relleno 120 mm/s (Bambu/MK4: perfil «Standard»)",
                        ventilador="100 % desde la capa 3", adherencia="brim de 5 mm en las placas de 32 cm (evita que se levanten las esquinas); PEI liso limpio con alcohol",
                        compensacion="compensación de pata de elefante 0,15 mm · compensación XY de agujeros +0,1 mm", soportes="no"),
 "PLA-SOPORTES": dict(material="PLA", boquilla="210 °C", cama="60 °C", capa="0,20 mm", paredes="3", superior_inferior="4 / 4", relleno="25 % giroide",
                      velocidad="perfil estándar", ventilador="100 %", adherencia="sin brim", compensacion="pata de elefante 0,15 mm", soportes="solo donde dice la tabla (tipo árbol)"),
 "PETG-MECANICA": dict(material="PETG", boquilla="240 °C", cama="80 °C", capa="0,20 mm", paredes="4", superior_inferior="5 / 5", relleno="40 % giroide",
                       velocidad="perímetro exterior 50 mm/s · relleno 100 mm/s", ventilador="40 %", adherencia="brim de 4 mm en los eslabones; pegamento en barra en PEI liso",
                       compensacion="pata de elefante 0,15 mm · agujeros +0,1 mm", soportes="árbol, solo donde dice la tabla"),
 "TPU-PARACHOQUES": dict(material="TPU 95A", boquilla="225 °C", cama="45 °C", capa="0,24 mm", paredes="3", superior_inferior="4 / 4", relleno="30 % giroide",
                         velocidad="25 mm/s todo · retracción 0,8 mm o desactivada", ventilador="50 %", adherencia="sin brim", compensacion="—", soportes="no"),
}
GRUPO = {"P20": "PLA-ESTRUCTURA", "P23": "PLA-ESTRUCTURA", "P00": "PLA-ESTRUCTURA",
         "P24": "PETG-MECANICA", "P07": "PETG-MECANICA", "P08": "PETG-MECANICA", "P09": "PETG-MECANICA", "P10": "PETG-MECANICA", "P11": "PETG-MECANICA",
         "P14": "PETG-MECANICA", "P15": "PETG-MECANICA", "P02": "PETG-MECANICA", "P16": "PETG-MECANICA",
         "P04": "PLA-SOPORTES", "P06": "PLA-SOPORTES", "P12": "PLA-SOPORTES", "P03": "PLA-SOPORTES", "P18": "PLA-SOPORTES", "P05": "TPU-PARACHOQUES"}
CANT = {"comun": {"P00": 1, "P20": 3, "P23": 16, "P24": 4, "P06": 2, "P05": 1, "P07": 1, "P08": 1, "P09": 1, "P10": 1, "P11": 1},
        "V1": {"P14": 1, "P04": 3}, "V2": {"P15": 1, "P04": 2, "P02": 1, "P12": 1, "P03": 1}, "V3": {"P15": 1, "P04": 2, "P16": 1, "P18": 1}}

BANDEJAS = [
 ("B00", "Prueba de tolerancia", "comun", ["P00"]),
 ("B01", "Placa inferior (entera)", "comun", ["P20"]), ("B02", "Placa superior (entera)", "comun", ["P20"]), ("B03", "Cubierta (entera)", "comun", ["P20"]),
 ("B04", "Columnas", "comun", ["P23"] * 16),
 ("B05", "Cunas de motor", "comun", ["P24"] * 4),
 ("B06", "Parachoques (TPU)", "comun", ["P05"]),
 ("B07", "Brazo (PETG)", "comun", ["P07", "P08", "P09", "P10", "P11"]),
 ("B08-V1", "Muñeca V1 (PETG)", "V1", ["P14"]),
 ("B09-V1", "Sensores V1 (PLA)", "V1", ["P04"] * 3 + ["P06"] * 2),
 ("B08-V2", "Muñeca + torre V2 (PETG)", "V2", ["P15", "P02"]),
 ("B09-V2", "Sensores V2 (PLA)", "V2", ["P04"] * 2 + ["P06"] * 2 + ["P12", "P03"]),
 ("B08-V3", "Muñeca + barredor V3 (PETG)", "V3", ["P15", "P16"]),
 ("B09-V3", "Sensores V3 (PLA)", "V3", ["P04"] * 2 + ["P06"] * 2 + ["P18"]),
]
def horas_a(p, flujo):  # horas a un flujo volumétrico efectivo (mm³/s)
    extr = max(0.0, (p["horas"] - 0.15)) * 4.0 * 3600
    return extr / flujo / 3600 + 0.12
out = []
for bid, titulo, grupo, items in BANDEJAS:
    placed = pack(items, 3.0 if len(items) == 1 else MARGIN, 340.0 if items == ["P20"] else BED)
    fn = f"{bid}_{titulo.split(' (')[0].lower().replace(' · ', '_').replace(' + ', '_').replace(' ', '_')}.3mf"
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")): fn = fn.replace(a, b)
    write_3mf(os.path.join(DST, "3MF_bandejas", fn), placed, f"Bicho · {bid} · {titulo}")
    perfiles = sorted({GRUPO[i] for i in items})
    g = sum(P[i]["gramos"] for i in items)
    out.append(dict(id=bid, titulo=titulo, grupo=grupo, archivo=fn, piezas=sorted({i: items.count(i) for i in items}.items()),
                    perfil=perfiles, gramos=round(g), h_clasica=round(sum(horas_a(P[i], 6) for i in items), 1), h_rapida=round(sum(horas_a(P[i], 15) for i in items), 1)))
json.dump(dict(bandejas=out, perfiles=PERFIL, grupos=GRUPO, cantidades=CANT, piezas=list(P.values())), open(os.path.join(DST, "impresion.json"), "w"), ensure_ascii=False, indent=1)
for b in out: print(b["id"], b["archivo"], b["gramos"], "g", b["h_clasica"], "h /", b["h_rapida"], "h", b["perfil"])
