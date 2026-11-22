# Links del equipo

_Agrega aquí todo link que el resto vaya a necesitar. Nada con claves, tokens ni datos personales: el repo es público._

## Proyecto

- Repo oficial (público): https://github.com/platanus-hack/platanus-hack-26-cl-team-39 (se trabaja en `dev`)
- Plataforma de Platanus Hack: https://hack.platan.us
- Página de votación de referencia (Buenos Aires): https://hack.platan.us/26-ar/vote

## Herramientas

- **bicho·dev** en local: `cd web && npm install && npm run dev` → http://localhost:5173
- **Relé del bicho** (para verlo desde cualquier red): https://promotional-precision-lincoln-david.trycloudflare.com. Es una dirección temporal: si cambia, hay que actualizarla en `web/src/lib/rele.json` y en el `rele.json` del Pi. Código y cómo funciona: [`rele/`](../rele/).
- **Inventario:** http://localhost:5173/#inventario (versión publicada: pendiente)
- Inventario original (Claude Sheet, ya no se edita): https://claude.ai/artifact/GBWrPQMav9q9mWqdLA92aG
- Base de datos: Neon, proyecto `crbrc-platanus` (la conexión está en `web/.env`; pídela por privado)

## Diseño e impresión 3D

- **Brazo v4 listo para la SD (G-code A1/A2L, PETG/PLA, STL y guía):** https://drive.google.com/drive/folders/1tgVAXhTr5cy_0PL6q8t-ZDHyu3ACUdJh · en el repo: `diseno/imprimir/brazo_v4/`
- **Archivos para imprimir (Drive):** https://drive.google.com/drive/folders/1a9WasSzIEE1wSZMqfCm-AzRK_FrVOw_S (placas enteras de 320 × 200)
- Versión con las placas en dos mitades, para camas chicas, y versiones anteriores: https://drive.google.com/drive/folders/1YMCR-BZjomPj6vu6_y4VduugyFtjLoXz
- Fotos y videos del proceso: https://drive.google.com/drive/folders/1-Ze_hGI7VpxI-U5A6CU_j8Gqs-QH9ReH
- Taller 3D en local: `cd diseno && python3 -m http.server 8000` → http://localhost:8000/taller3d/
- Taller 3D publicado (privado, pedir acceso a Walls): https://claude.ai/artifact/EVKma9DkW9tp2xa4Zq7xeD
- Ideas del proyecto (22 ideas + kit de entrega, privado): https://claude.ai/artifact/5B7JYRVsV8Uq7vwyLrxGri

## Marca y pitch

- **Manual de marca** (logo, colores, letra, voz; privado, pedir acceso a Guty): https://claude.ai/artifact/AFqF74EGV951uugDiV9pvJ
- **Guion del pitch, editable** (el que vale; se edita y comenta en línea; privado, pedir acceso a Guty): https://claude.ai/artifact/MQWVsTP9RmfJCaA4kxwWNs
- **Deck del pitch** (6 láminas en dark mode, como pidió la charla, con el gráfico de lo que aprendió solo y notas para quien presenta; termina en «gracias»; privado, pedir acceso a Guty): https://claude.ai/artifact/Q9PgQu6yFWAbDWSDyrahgm
- **Deck de preguntas y respaldo** (lo que no se presenta: qué usamos, cómo funciona por dentro, qué no hace todavía y el respaldo de la demo; privado, pedir acceso a Guty): https://claude.ai/artifact/GZDozwCsmpM7jS1U4V5xRV
- En el repo: [`marca/MARCA.md`](../marca/MARCA.md) (el manual en texto), [`marca/PITCH.md`](../marca/PITCH.md) (guion, demo, plan B, preguntas) y [`marca/logo/`](../marca/logo/) (SVG y PNG; se regeneran con `python3 marca/generar_logo.py && bash marca/exportar_png.sh`).

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
