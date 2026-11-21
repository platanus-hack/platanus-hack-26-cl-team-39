---
autor: Guty (Claude)
fecha: 2026-11-21 04:20
tipo: avance
---

# Harness del equipo: mismo contexto para todos los Claude

- `CLAUDE.md` en la raíz le dice a cada Claude, al empezar, dónde está cada cosa y qué puede hacer, y le carga el estado y los links del equipo.
- `contexto/` guarda estado, decisiones, links y esta bitácora. Un hook de inicio le muestra a Claude las últimas entradas.
- Skills compartidas: `/al-dia` (resumen de lo nuevo), `/anotar` (deja una entrada y la sube a `dev`), `equipo` e `inventario`.
- Para que te llegue: `git pull origin dev` y abre Claude Code en la carpeta del repo. La primera vez acepta el aviso de confianza de la carpeta.
