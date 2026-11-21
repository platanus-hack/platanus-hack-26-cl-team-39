---
name: equipo
description: Contexto compartido del equipo CRBRC en Platanus Hack 26 (estado, decisiones, links y bitácora en contexto/). Úsala al empezar a trabajar en el repo, cuando tu humano pregunte en qué está el equipo o qué se decidió, y cuando pase algo que el resto deba saber (una decisión, un avance, un problema, un link útil, el resumen de una reunión).
---

# Contexto compartido del equipo

El equipo son cinco personas (Carlos, Cristian, Guty, Renate y Walls), cada una con su Claude. Todos trabajan sobre este repo y comparten la memoria en `contexto/`. Lo que tú no anotes, los otros Claude no lo saben.

## Leer

- `contexto/estado.md` y `contexto/links.md` ya vienen cargados por `CLAUDE.md`.
- `contexto/decisiones.md`: léelo antes de proponer algo que choque con una decisión tomada.
- `contexto/bitacora/`: lo más nuevo tiene el nombre mayor (`ls contexto/bitacora | sort -r | head`). El hook de inicio te muestra las últimas ocho.
- Antes de leer, trae lo último: `git pull --rebase --autostash origin dev`.

## Escribir

Qué va dónde:

| Pasó esto | Escríbelo en |
|---|---|
| Se terminó algo, apareció un problema, una idea o se hizo una reunión | Un archivo nuevo en `contexto/bitacora/` (formato en su README) |
| Se decidió algo | Una línea al final de `contexto/decisiones.md` **y** una entrada en la bitácora |
| Cambió la idea, quién hace qué, un pendiente o una fecha | Edita la parte que cambió de `contexto/estado.md` (corto: lo viejo se borra; ya queda en la bitácora) |
| Hay un link, comando o skill que todos van a usar | `contexto/links.md` |

Reglas:

- **Pregúntale a tu humano antes de subir algo.** Si no te pidió `/anotar`, ofrécelo en una línea ("¿Lo dejo en la bitácora del equipo?").
- Escribe para alguien que no estuvo: qué pasó, qué significa para el resto y qué sigue. Dos a cinco líneas.
- Firma como `Nombre de tu humano (Claude)`. Usa la hora de Santiago: `TZ=America/Santiago date '+%Y-%m-%d %H:%M'`.
- No reescribas lo que anotó otro. En `estado.md` toca solo lo que cambió; si dudas, escribe una entrada en la bitácora.
- **El repo es público:** nada de claves, tokens, contenido de `.env`, teléfonos, correos ni datos personales. Los links privados van sin credenciales.
- Lo que no esté confirmado se marca como tal ("por confirmar", "según el resumen de Granola").

## Subir

Solo los archivos de contexto, a `dev`, nunca a `main`:

```bash
git pull --rebase --autostash origin dev
git add contexto/ CLAUDE.md .claude/skills/   # solo lo que tocaste
git commit -m "contexto: <qué>"
git push origin dev
```

Si el push falla porque alguien subió antes, repite el `pull --rebase` y el push. Si hay un conflicto en `estado.md` o `decisiones.md`, junta las dos versiones (no descartes la del otro).

## Agregar una skill para todo el equipo

Crea `.claude/skills/<nombre>/SKILL.md` con `name` y `description` en el frontmatter, anótala en la tabla de `contexto/links.md` y avísalo en la bitácora.
