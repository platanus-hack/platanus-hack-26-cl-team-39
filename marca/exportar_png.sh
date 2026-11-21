#!/usr/bin/env bash
# Pasa los SVG de marca/logo/ a PNG con Chrome sin ventana (se ven igual que en el navegador).
# Uso: bash marca/exportar_png.sh   (antes: python3 marca/generar_logo.py)
set -euo pipefail
cd "$(dirname "$0")"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

png() { # svg ancho alto salida [fondo transparente: si|no]
  local svg="$PWD/logo/$1" w="$2" h="$3" out="$4" transp="${5:-si}"
  printf '<html><body style="margin:0"><img src="file://%s" width="%s" height="%s" style="display:block"></body></html>' "$svg" "$w" "$h" > "$TMP/p.html"
  local bg=()
  [ "$transp" = si ] && bg=(--default-background-color=00000000)
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files \
    --force-device-scale-factor=1 ${bg[@]+"${bg[@]}"} --window-size="$w,$h" --screenshot="$out" "file://$TMP/p.html" 2>/dev/null
  echo "$out ($(du -h "$out" | cut -f1 | tr -d ' '))"
}

# Logo que pide Platanus: 1000 × 1000, máximo 500 KB.
png bicho-cuadrado.svg 1000 1000 ../project-logo.png no
# Los degradés del fondo pesan: se recomprime sin perder calidad (queda bajo 400 KB).
magick ../project-logo.png -strip -define png:compression-level=9 -define png:compression-filter=5 ../project-logo.png
echo "../project-logo.png recomprimido ($(du -h ../project-logo.png | cut -f1 | tr -d ' '))"
cp ../project-logo.png logo/bicho-cuadrado.png
# Ícono de app y favicons.
png bicho-icono.svg 512 512 logo/bicho-icono-512.png
png bicho-icono.svg 180 180 logo/apple-touch-icon.png
png favicon.svg 32 32 logo/favicon-32.png
# Para láminas y documentos (fondo transparente, el doble del tamaño del SVG).
png bicho-horizontal-fondo-oscuro.svg 1554 480 logo/bicho-horizontal-fondo-oscuro.png
png bicho-horizontal-fondo-claro.svg 1554 480 logo/bicho-horizontal-fondo-claro.png
png bicho-ojo-fondo-oscuro.svg 960 960 logo/bicho-ojo-fondo-oscuro.png
png bicho-ojo-fondo-claro.svg 960 960 logo/bicho-ojo-fondo-claro.png
