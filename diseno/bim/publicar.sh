#!/bin/sh
# Regenera el modelo BIM del brazo y lo deja donde lo lee bicho·dev (web/public/bim/).
# Uso: sh diseno/bim/publicar.sh   (desde la raíz del repo; necesita Blender 4.2 en /Applications)
set -e
B=/Applications/Blender.app/Contents/MacOS/Blender
PY=/Applications/Blender.app/Contents/Resources/4.2/python/bin/python3.11
TMP=$(mktemp -d)
"$B" -b -P diseno/blender/generar_brazo_bim.py -- "$TMP" >/dev/null 2>&1
"$PY" -I diseno/bim/planos.py
mkdir -p web/public/bim/planos
cp "$TMP/brazo.glb" web/public/bim/brazo.glb
cp diseno/bim/registro.json web/public/bim/registro.json
cp diseno/bim/planos/*.svg web/public/bim/planos/
rm -rf "$TMP"
echo "listo: web/public/bim/"
