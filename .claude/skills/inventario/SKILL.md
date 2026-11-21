---
name: inventario
description: Leer y modificar el inventario de hardware del equipo CRBRC (sensores, motores, placas, cables, herramientas) para Platanus Hack 26. Úsala cuando tu humano pregunte si tenemos algo ("¿hay servos?", "¿qué sensor de distancia hay?"), cuando use, consuma, rompa, preste, mueva o consiga una pieza, o cuando haya que decidir qué hardware usar en el bicho.
---

# Inventario de hardware del equipo

El inventario vive en una base Neon y se ve en bicho·dev (barra lateral → **Equipo → Inventario**). Lo editan las personas desde la web y sus Claude desde aquí. Cada cambio queda en un historial con quién lo hizo.

## Conexión

- URL base: `https://bicho-dev.vercel.app` (si tu humano corre la web en local con `web/.env`, también sirve `http://localhost:5173`).
- **Leer y buscar no pide clave.** Agregar, editar, borrar y preguntarle a Claude piden la clave del equipo como `Authorization: Bearer <clave>`.
- La clave sale de la variable `INVENTARIO_TOKEN`, o de la línea `INVENTARIO_TOKEN="…"` en `web/.env`. Si no está en ninguna, pídele a tu humano "la clave del inventario" y guárdala en `web/.env` (está en `.gitignore`). **Nunca la pongas en un commit, un issue ni en el chat del equipo.**
- Manda siempre `x-autor: <Nombre de tu humano> (Claude)`, por ejemplo `x-autor: Renate (Claude)`.

```bash
INV=https://bicho-dev.vercel.app
CLAVE=${INVENTARIO_TOKEN:-$(grep -s '^INVENTARIO_TOKEN=' web/.env | cut -d'"' -f2)}
AUTOR="Renate (Claude)"   # cambia el nombre
```

## Leer

```bash
curl -s "$INV/api/inventario"                     # todo (≈130 ítems)
curl -s "$INV/api/inventario?q=servo"             # busca texto en todos los campos, sin importar tildes
curl -s "$INV/api/inventario?categoria=Sensores"  # también: &estado=Listo  &origen=Carlos
curl -s "$INV/api/inventario?id=42"               # un ítem
curl -s "$INV/api/historial?limite=20"            # últimos cambios (&id=42 para uno)
```

Para preguntas abiertas ("¿qué podemos usar para que el robot vea?"), pregúntale a Claude con todo el inventario como contexto. Responde `{respuesta, ids}`:

```bash
curl -s -X POST "$INV/api/preguntar" -H "authorization: Bearer $CLAVE" -H 'content-type: application/json' \
  -d '{"pregunta":"¿qué tenemos para medir distancia?"}'
```

## Escribir

Antes de agregar, **busca si ya existe**: si existe, edita la cantidad en vez de duplicar.

```bash
# agregar uno (o varios con {"items":[...]})
curl -s -X POST "$INV/api/inventario" -H "authorization: Bearer $CLAVE" -H "x-autor: $AUTOR" -H 'content-type: application/json' \
  -d '{"item":{"nombre":"Sensor ultrasónico HC-SR04","cantidad":2,"categoria":"Sensores","origen":"Compra AFEL","estado":"Listo"}}'

# editar solo los campos que mandes
curl -s -X PATCH "$INV/api/inventario?id=42" -H "authorization: Bearer $CLAVE" -H "x-autor: $AUTOR" -H 'content-type: application/json' \
  -d '{"cantidad":3,"estado":"En uso","uso_bicho":"Sensor frontal anti-choque","ubicacion":"Montado en el chasis"}'

# borrar (solo duplicados o errores; si se rompió, cambia el estado a "Dañado")
curl -s -X DELETE "$INV/api/inventario?id=42" -H "authorization: Bearer $CLAVE" -H "x-autor: $AUTOR"
```

## Campos

| Campo | Qué va |
|---|---|
| `nombre` | Obligatorio. Nombre con modelo si se sabe: "Servomotor MG995". |
| `cantidad` | Entero ≥ 0, o `null` si no se sabe. |
| `categoria` | Usa una existente: Placas y módulos, Sensores, Motores, Alimentación, Cables y conectores, Luz y pantallas, Estructura, Prototipado, Herramientas, Consumibles, Control. |
| `origen` | De quién es o de dónde salió: "Inventario de Carlos", "Compra AFEL", "Caja de herramientas", "Renate". |
| `estado` | Listo, En uso, Por verificar, Sin identificar, Prestado o Dañado. |
| `uso_bicho` | Para qué se usa en el robot. |
| `ubicacion` | Dónde está físicamente. |
| `notas` | Specs, voltaje, qué falta, etc. |

`uso_lampara` y `fuente` son de la carga inicial desde el Sheet (la idea anterior era una lámpara): se leen, no se editan.

## Reglas

- Si tu humano dice que usó, sacó, rompió o prestó algo, actualiza el ítem en el momento y díselo en una línea.
- No inventes cantidades: si no sabes, pregunta o deja `null`.
- Hay ítems que pueden estar repetidos entre la pestaña "Inventario" y "Inventario (Renate)" del Sheet original. Si ves un duplicado claro, avísale a tu humano antes de borrar.
- Respuestas con error traen `{"error": "…"}` en español; léelo antes de reintentar.

## Alternativa: servidor MCP

Si tu humano prefiere herramientas en vez de curl:

```bash
claude mcp add --transport http inventario https://bicho-dev.vercel.app/api/mcp --header "Authorization: Bearer <clave>"
```

Herramientas: `buscar_items`, `ver_item`, `preguntar_inventario`, `agregar_items`, `editar_item`, `borrar_item`, `ver_historial`.
