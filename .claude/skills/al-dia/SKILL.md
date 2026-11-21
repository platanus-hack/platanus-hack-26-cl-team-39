---
name: al-dia
description: Pone a tu humano al día con lo que hizo y decidió el resto del equipo CRBRC (bitácora, decisiones, commits e inventario). Úsala cuando pregunte "¿qué hay de nuevo?", "¿en qué va el equipo?" o vuelva después de un rato.
argument-hint: "[desde cuándo, ej: 3h, hoy, desde las 2]"
---

# /al-dia

Resume lo nuevo del equipo desde: $ARGUMENTS (si está vacío, desde las últimas 6 horas).

1. `git pull --rebase --autostash origin dev` (si falla por un conflicto, avísale y sigue con lo que hay en local).
2. Lee las entradas de `contexto/bitacora/` de ese período: el nombre empieza con la fecha y la hora (`ls contexto/bitacora | sort -r`).
3. Mira qué cambió en `contexto/decisiones.md` y `contexto/estado.md` en ese período: `git log --since="<período>" -p -- contexto/decisiones.md contexto/estado.md`.
4. Mira los commits del resto: `git log --since="<período>" --format="%h %an %ar: %s" origin/dev`.
5. Si bicho·dev está corriendo o publicado, mira los cambios del inventario: `curl -s http://localhost:5173/api/historial?limite=20` (o la URL publicada de `contexto/links.md`). Si no responde, sáltatelo.

Responde corto, en este orden y solo con lo que haya:

- **Decisiones** nuevas.
- **Avances** por persona.
- **Problemas** o cosas que bloquean.
- **Qué le toca a tu humano** o qué le afecta, si algo de lo anterior lo toca.

Termina con lo que quedó pendiente según `contexto/estado.md`. No anotes nada en la bitácora: esto es solo para leer.
