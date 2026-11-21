# CRBRC · Platanus Hack 26: contexto compartido

Este archivo lo carga el Claude de cada persona del equipo al trabajar en este repo. Junto con [`contexto/`](contexto/) y las skills de [`.claude/skills/`](.claude/skills/) es el **harness del equipo**: el mismo contexto, los mismos links y las mismas herramientas para todos. (No confundir con [`harness/`](harness/), que es el cerebro de IA del bicho.)

## Al empezar

1. Trae lo último: `git pull --rebase --autostash origin dev`. Si no estás en `dev`, avísale a tu humano antes de hacer nada.
2. El hook de inicio te mostró las últimas entradas de la bitácora: léelas si tienen que ver con lo que te pidieron.
3. Ubícate con las dos tablas de abajo antes de buscar a ciegas por el repo.

## Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Estado, idea, quién hace qué, pendientes | `contexto/estado.md` (cargado abajo) |
| Decisiones y su porqué | `contexto/decisiones.md` |
| Lo que ha ido pasando | `contexto/bitacora/` (un archivo por entrada; el nombre empieza con la fecha) |
| Links, comandos y skills del equipo | `contexto/links.md` (cargado abajo) |
| Cronograma del evento (comidas, charlas, fin del hacking, presentaciones) | `web/src/lib/cronograma.json`. El hook de inicio te dice qué pasa ahora y qué viene; bicho·dev lo muestra bajo el cronómetro. |
| bicho·dev, la web interna (firmware, sensores, consola, versiones, inventario) | `web/` (Vite + React; API en `web/api/`, UI en `web/src/`) |
| Agente que corre en la Raspberry Pi 3 | `bicho/` (`bichod.py`; se editan `sensores.py`, `comandos.py` y `version.json`) |
| Versiones publicadas del bicho | `web/public/firmware/` (`manifest.json` + paquetes) |
| Contrato entre el bicho, la web y la IA | `PROTOCOLO.md` |
| Cerebro de IA del bicho | `harness/` (por armar; el equipo aún no decide cómo) |
| Base del inventario | Neon, proyecto `crbrc-platanus` (esquema en `web/db/schema.sql`; conexión en `web/.env`, que no se sube) |
| Datos personales del equipo | `TEAM.md`, solo local. No lo subas ni copies datos de ahí al repo. |

## Qué puedes hacer

| Para | Cómo |
|---|---|
| Correr bicho·dev | `cd web && npm install && npm run dev` → http://localhost:5173 |
| Hablar con el bicho | `curl http://bicho.local:8080/info`; sensores y comandos por `ws://bicho.local:8080/ws` (formato en `PROTOCOLO.md`). Sin hardware: Simulador en bicho·dev. |
| Publicar una versión del bicho | Sube `version` en `bicho/version.json` y corre `npm run release -- --notes "…"` en `web/`. Haz commit de `web/public/firmware/`. |
| Instalar `bichod` en una Pi | `bicho/install.sh` (pasos en `bicho/README.md`) |
| Consultar o editar el inventario | Skill `inventario` (API `/api/inventario`, `/api/preguntar`) |
| Ponerse al día con el equipo | `/al-dia` |
| Dejar algo para el equipo | `/anotar` (bitácora + push a `dev`), o la skill `equipo` para saber qué va en cada archivo |
| Agregar una skill para todos | `.claude/skills/<nombre>/SKILL.md`, anotarla en `contexto/links.md` |

**No hagas:** push a `main`, deploys (Vercel u otro) ni commits con claves o datos personales. Detalle en "Reglas".

## Lo que hay que saber siempre

@contexto/estado.md

@contexto/links.md

## Reglas

- **Se trabaja en la rama `dev`.** Nunca hagas push a `main`: Platanus toma cada push a `main` como un envío del proyecto. Solo se envía cuando el equipo lo decide, y lo hace una persona.
- **El repo es público.** No subas claves, tokens, contraseñas, archivos `.env`, teléfonos, correos ni datos personales.
- **Deploys:** los maneja una persona del equipo. No despliegues por tu cuenta; prepara el código y avisa.
- Otras personas (y sus Claude) trabajan en la misma rama: antes de hacer commit, revisa `git status` y sube solo lo tuyo.
- Docs, interfaz y mensajes en español de Chile.
- Es una hackathon de 36 horas: prioriza que la demo funcione, y ten siempre un plan B.

## Cómo compartimos contexto

Cuando tu humano decida algo, termine algo, se tope con un problema o encuentre un link útil, ofrécele dejarlo para el equipo con `/anotar`. Lo que tú no anotes, los otros Claude no lo saben. La skill `equipo` explica qué va en cada archivo, cómo escribir sin pisar a otros y cómo subirlo.
