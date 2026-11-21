# Bambu Studio por CLI deja vacío printer_model_id en Metadata/slice_info.config; la impresora lo revisa al abrir el
# archivo desde la SD. Esto lo rellena con el ID oficial (A1 = N2S, A2L = N9, A1 mini = N1).
# Uso: python3 -I fijar_modelo_impresora.py <archivo.gcode.3mf> [...]
import sys, zipfile, os, re, shutil, tempfile
IDS = {"Bambu Lab A1": "N2S", "Bambu Lab A2L": "N9", "Bambu Lab A1 mini": "N1"}
for f in sys.argv[1:]:
    zin = zipfile.ZipFile(f)
    ps = zin.read("Metadata/project_settings.config").decode()
    model = re.search(r'"printer_model":\s*"([^"]+)"', ps).group(1); mid = IDS[model]
    tmp = tempfile.mktemp(suffix=".3mf")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            data = zin.read(it.filename)
            if it.filename == "Metadata/slice_info.config":
                data = data.decode().replace('key="printer_model_id" value=""', f'key="printer_model_id" value="{mid}"').encode()
            zout.writestr(it, data)
    zin.close(); shutil.move(tmp, f)
    print(os.path.basename(f), "->", model, mid)
