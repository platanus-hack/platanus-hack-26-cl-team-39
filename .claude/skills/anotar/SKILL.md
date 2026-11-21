---
name: anotar
description: Deja en la bitácora del equipo lo que se hizo, se decidió o se encontró en esta sesión, y lo sube a la rama dev para que lo vean los Claude de todos.
argument-hint: "[qué anotar, o vacío para resumir la sesión]"
disable-model-invocation: true
---

# /anotar

Tu humano quiere dejar algo para el equipo. Si escribió algo después de `/anotar`, eso es lo que hay que anotar: $ARGUMENTS. Si no, resume lo importante de esta sesión para el resto del equipo.

Pasos:

1. `git pull --rebase --autostash origin dev`
2. Saca la hora de Santiago: `TZ=America/Santiago date '+%Y-%m-%d %H:%M'`.
3. Escribe **un archivo nuevo** en `contexto/bitacora/` con el formato de `contexto/bitacora/README.md`: `AAAA-MM-DD-HHMM-<nombre>-<tema>.md`, frontmatter con `autor: <Nombre> (Claude)`, `fecha` y `tipo`, un título que se entienda solo y dos a cinco líneas: qué pasó, qué significa para el resto y qué sigue. Si no sabes el nombre de tu humano, pregúntaselo.
4. Si hubo una decisión, agrega su línea al final de `contexto/decisiones.md`. Si cambió el estado (la idea, quién hace qué, un pendiente, una fecha), edita solo esa parte de `contexto/estado.md`. Si hay un link nuevo, va en `contexto/links.md`.
5. Revisa que no haya claves, tokens, contenido de `.env` ni datos personales: el repo es público.
6. Sube solo esos archivos:
   ```bash
   git add contexto/
   git commit -m "contexto: <título corto>"
   git push origin dev
   ```
   Si el push falla porque alguien subió antes, repite el `pull --rebase` y el push. Nunca a `main`.
7. Muéstrale a tu humano el título de la entrada y en qué archivos quedó, en dos líneas.
