# Arma las bandejas .3mf del brazo v4 (cama de 256 × 256: sirve en A2L, A1, P1S, X1, MK4) desde <salida>/stl.
# Uso: python3 -I empaquetar_brazo_v4.py <salida_v4> <destino>
import json, os, sys, shutil, unicodedata, re
AQUI = os.path.dirname(os.path.abspath(__file__))
SRC, DST = sys.argv[1], sys.argv[2]; SRC0 = SRC
stl_in = os.path.join(SRC, "stl"); stl_out = os.path.join(DST, "STL")
os.makedirs(stl_out, exist_ok=True)
def ascii_slug(f):
    f = unicodedata.normalize("NFKD", f).encode("ascii", "ignore").decode()
    f = f.replace("_(", "_").replace(")", "").replace(",", "")
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9_.-]", "_", f))
for f in os.listdir(stl_in):
    if f.endswith(".stl"): shutil.copy(os.path.join(stl_in, f), os.path.join(stl_out, ascii_slug(f)))
code = open(os.path.join(AQUI, "empaquetar_impresion.py"), encoding="utf-8").read()
code = code[:code.index('P = {p["id"]: p')]
sys.argv = ["x", DST, DST]                      # el módulo lee <SRC>/stl → aquí DST/STL
code = code.replace('STL = os.path.join(SRC, "stl")', 'STL = os.path.join(SRC, "STL")')
exec(compile(code, "empaquetar_impresion.py", "exec"))
P = {p["id"]: p for p in json.load(open(os.path.join(SRC0, "piezas_brazo.json"), encoding="utf-8"))["piezas"]}
BANDEJAS = [
 ("B10", "Torreta", ["P07"], "PETG 4 paredes, 40 % giroide. SOPORTES ÁRBOL solo bajo la placa del servo (interior)."),
 ("B11", "Plataforma y cuna del hombro", ["P08"], "PETG 4 paredes, 40 % giroide. Sin soportes."),
 ("B12", "Placas de los eslabones", ["P09A", "P09B", "P10A", "P10B"], "PETG 4 paredes, 5/5 capas, 40 % giroide. Planas, sin soportes, brim 4 mm."),
 ("B13", "Cuna del codo, palma, contraplaca y separadores", ["P35", "P30", "P34", "P36", "P36", "P37"], "PETG 4 paredes, 40 % giroide. Sin soportes."),
 ("B14", "Dedos y bujes (100 %)", ["P31", "P32", "P33"], "PETG 100 % de relleno (dedos y bujes macizos). Sin soportes."),
]
out = []
for bid, titulo, items, nota in BANDEJAS:
    placed = pack(items, 6.0, 256.0)
    fn = f"{bid}_" + ascii_slug(titulo.lower().replace(" ", "_")) + ".3mf"
    write_3mf(os.path.join(DST, "3MF_bandejas", fn), placed, f"Bicho · brazo v4 · {bid} · {titulo}")
    g = sum(P[i]["gramos"] for i in items)
    out.append(dict(id=bid, titulo=titulo, archivo=fn, piezas=sorted({i: items.count(i) for i in items}.items()), gramos=round(g), perfil=nota))
json.dump(dict(bandejas=out, piezas=list(P.values())), open(os.path.join(DST, "impresion_brazo_v4.json"), "w"), ensure_ascii=False, indent=1)
for b in out: print(b["id"], b["archivo"], b["gramos"], "g", b["piezas"])
