#!/bin/zsh
# bicho · hand tracking — arranca el tracker (y opcionalmente el bicho simulado)
#   ./correr.sh            cámara 0
#   ./correr.sh --fake     mano sintética (sin cámara)
#   ./correr.sh --mock     además levanta un bicho simulado en ws://127.0.0.1:8080/ws
set -e
cd "$(dirname "$0")/tracker"
if [ ! -x .venv/bin/python ]; then
  echo "Instalando entorno (una sola vez)…"
  uv venv --python 3.12 .venv -q && uv pip install --python .venv/bin/python -q -r requirements.txt
fi
[ -f models/hand_landmarker.task ] || { mkdir -p models; curl -sL -o models/hand_landmarker.task \
  https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task; }
ARGS=()
for a in "$@"; do
  if [ "$a" = "--mock" ]; then .venv/bin/python -u mock_bicho.py & MOCK=$!; trap "kill $MOCK 2>/dev/null" EXIT
  else ARGS+=("$a"); fi
done
.venv/bin/python -u hand_tracker.py "${ARGS[@]}" 2> >(grep -v -E '^(INFO|W0000|I0000)' >&2)
