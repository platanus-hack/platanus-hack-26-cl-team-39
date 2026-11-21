# Links del equipo

_Agrega aquí todo link que el resto vaya a necesitar. Nada con claves, tokens ni datos personales: el repo es público._

## Proyecto

- Repo oficial (público): https://github.com/platanus-hack/platanus-hack-26-cl-team-39 (se trabaja en `dev`)
- Plataforma de Platanus Hack: https://hack.platan.us
- Página de votación de referencia (Buenos Aires): https://hack.platan.us/26-ar/vote

## Herramientas

- **bicho·dev** en local: `cd web && npm install && npm run dev` → http://localhost:5173
- **Inventario:** http://localhost:5173/#inventario (versión publicada: pendiente)
- Inventario original (Claude Sheet, ya no se edita): https://claude.ai/artifact/GBWrPQMav9q9mWqdLA92aG
- Base de datos: Neon, proyecto `crbrc-platanus` (la conexión está en `web/.env`; pídela por privado)

## Skills compartidas (`.claude/skills/`)

| Skill | Para qué |
|---|---|
| `equipo` | Leer y actualizar el contexto compartido (estado, decisiones, links, bitácora). |
| `/anotar` | Dejar en la bitácora lo que se hizo o decidió y subirlo a `dev`. |
| `/al-dia` | Resumen de lo que cambió desde la última vez. |
| `inventario` | Buscar y editar el inventario de hardware. |

## Documentos del repo

- [`PROTOCOLO.md`](../PROTOCOLO.md): contrato bicho ↔ web ↔ harness.
- [`web/README.md`](../web/README.md): cómo correr bicho·dev, publicar versiones del bicho y la API del inventario.
- [`bicho/README.md`](../bicho/README.md): instalar `bichod` en la Raspberry Pi.
