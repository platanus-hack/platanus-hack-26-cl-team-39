# Aplana un perfil de sistema de Bambu Studio: sigue 'inherits' y mete los 'include' (templates de G-code).
import json, os, sys, glob
BBL = "/Applications/BambuStudio.app/Contents/Resources/profiles/BBL"
IDX = {}
for kind in ("machine", "process", "filament"):
    for f in glob.glob(f"{BBL}/{kind}/**/*.json", recursive=True):
        try: d = json.load(open(f))
        except Exception: continue
        IDX[(kind, d.get("name", os.path.basename(f)[:-5]))] = d
def flat(kind, name):
    d = IDX[(kind, name)]
    base = flat(kind, d["inherits"]) if d.get("inherits") else {}
    out = dict(base)
    for inc in d.get("include", []):
        out.update({k: v for k, v in IDX[(kind, inc)].items() if k not in ("name", "type", "from", "instantiation", "inherits", "setting_id")})
    out.update({k: v for k, v in d.items() if k not in ("inherits", "include")})
    return out
kind, name, dst = sys.argv[1], sys.argv[2], sys.argv[3]
d = flat(kind, name); d["from"] = "system"; d.pop("include", None)
if len(sys.argv) > 4: d.update(json.loads(sys.argv[4]))
json.dump(d, open(dst, "w"), indent=1)
print(kind, name, len(d), "claves")
