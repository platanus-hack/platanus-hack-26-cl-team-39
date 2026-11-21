# Lamina las bandejas del brazo v4 para la SD: A1 y A2L, en PETG y PLA, con Bambu Studio 2.09 por línea de comandos.
# Uso (desde la raíz del repo): python3 -I diseno/blender/laminar_brazo_v4.py
# Perfiles: diseno/imprimir/brazo_v4/perfiles_bambu/ (perfiles oficiales aplanados con aplanar_perfil_bambu.py:
# herencia + include de los G-code de inicio/fin; si no se aplanan, sale el G-code de otra impresora).
import json, os, shutil, subprocess, tempfile
BS = "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"
D = "diseno/imprimir/brazo_v4"; P = f"{D}/perfiles_bambu"
BANDEJAS = [("B10_torreta", "sop"), ("B11_plataforma_y_cuna_del_hombro", "base"), ("B12_placas_de_los_eslabones", "brim"),
            ("B13_cuna_del_codo_palma_contraplaca_y_separadores", "base"), ("B14_dedos_y_bujes_100_", "full"),
            ("B15_soportes_lidar_y_camara", "base")]
out = []
for m in ("A1", "A2L"):
    for mat in ("PETG", "PLA"):
        dst = f"{D}/SD/{m}_{mat}"; os.makedirs(dst, exist_ok=True)
        for t, v in BANDEJAS:
            tmp = tempfile.mkdtemp(); f = f"{t}_{m}_{mat}.gcode.3mf"
            subprocess.run([BS, "--slice", "0", "--arrange", "0", "--load-settings", f"{P}/maq_{m}.json;{P}/proc_{m}_{v}.json",
                            "--load-filaments", f"{P}/{mat.lower()}_{m}.json", "--outputdir", tmp, "--export-3mf", f,
                            f"{D}/3MF_bandejas/{t}.3mf"], capture_output=True)
            r = json.load(open(f"{tmp}/result.json")); pl = r["sliced_plates"][0]
            shutil.move(f"{tmp}/{f}", f"{dst}/{f}"); shutil.rmtree(tmp)
            out.append(dict(impresora=m, material=mat, bandeja=t[:3], horas=round(pl["total_predication"] / 3600, 2),
                            gramos=round(pl["filaments"][0]["total_used_g"]), aviso=pl.get("warning_message", "")))
            print(m, mat, t[:3], out[-1]["horas"], "h", out[-1]["gramos"], "g")
json.dump(out, open(f"{D}/SD/tiempos_bambu.json", "w"), ensure_ascii=False, indent=1)
