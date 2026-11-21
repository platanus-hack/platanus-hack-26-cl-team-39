#!/bin/sh
# Hook de inicio de Claude Code (SessionStart) para el equipo CRBRC.
# Le pasa a Claude (no a la persona) las últimas entradas de la bitácora y avisa si se está fuera de dev.
# Solo lee: no hace pull, no cambia archivos y no usa la red.

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0

echo "Harness del equipo CRBRC (hook de inicio). El mapa del repo y lo que puedes hacer están en CLAUDE.md."

rama=$(git branch --show-current 2>/dev/null)
if [ "$rama" = "main" ]; then
  echo "OJO: estás en main. Cada push a main cuenta como envío a Platanus: avísale a tu humano y trabaja en dev (git switch dev)."
elif [ -n "$rama" ] && [ "$rama" != "dev" ]; then
  echo "Estás en la rama $rama; la del equipo es dev."
fi

entradas=$(ls contexto/bitacora/*.md 2>/dev/null | grep -v '/README.md$' | sort -r | head -8)
if [ -n "$entradas" ]; then
  echo "Últimas entradas de contexto/bitacora (la más nueva primero):"
  echo "$entradas" | while IFS= read -r f; do
    titulo=$(grep -m1 '^# ' "$f" | sed 's/^# //')
    echo "- $(basename "$f" .md): $titulo"
  done
fi

if command -v node >/dev/null 2>&1; then
  node "$(dirname "$0")/cronograma.mjs" 2>/dev/null
fi

echo "Antes de trabajar: git pull --rebase --autostash origin dev."
exit 0
