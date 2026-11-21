# rele: el relé del bicho

Servicio aparte que une al bicho con la web cuando no están en la misma red.

El bicho está detrás de un WiFi sin dirección pública, así que nadie puede conectarse a él desde internet. En vez de eso, el bicho sale a conectarse al relé y deja la conexión abierta; bicho·dev (o cualquier navegador) habla con el relé, que pasa los mensajes de un lado al otro. Hacia la web, el relé se ve igual que un bicho: mismas rutas (`/ws`, `/info`, `/update`) y mismos mensajes. El contrato está en [`../PROTOCOLO.md`](../PROTOCOLO.md).

No tiene dependencias: solo Node 20 o más.

## Correrlo

```bash
BICHO_RELE_TOKEN=un-secreto node rele/servidor.mjs
```

Queda en `http://127.0.0.1:8787`. Para que sirva de algo tiene que estar publicado con HTTPS (un túnel o un proxy delante).

| Variable | Para qué |
|---|---|
| `BICHO_RELE_TOKEN` | Secreto que comparte con el bicho. Obligatorio: sin él, el bicho no puede conectarse. |
| `CLAVE_EQUIPO` | Clave para mandar comandos y actualizar (la misma del inventario). Sin ella, cualquiera con la dirección puede. |
| `RELE_PUERTO`, `RELE_HOST` | Puerto (8787) e interfaz (127.0.0.1). |
| `GROQ_API_KEY` | Para transcribir lo que oye el bicho con Groq (`whisper-large-v3-turbo`). Es lo más rápido. |
| `WHISPER_URL` | Alternativa a Groq: un servicio propio que recibe el audio por POST y responde `{"text": "…"}`. |
| `OIDO_IDIOMA` | Idioma de lo que se le dice al bicho (`es` por defecto; solo lo usa Groq). |

También se pueden poner en `rele/.env`, que no se sube al repo.

## Conectar el bicho

En el Pi, crea `rele.json` junto a la carpeta `releases/` (`/opt/bicho/rele.json`, o `~/.bicho/rele.json`):

```json
{ "url": "https://<dirección del relé>", "token": "<el mismo BICHO_RELE_TOKEN>" }
```

y reinicia el agente. En los logs debe aparecer `conectado al relé`.

## Conectar la web

La dirección pública del relé va en [`../web/src/lib/rele.json`](../web/src/lib/rele.json). Con eso bicho·dev se conecta sola al abrir, en local y publicada. Mirar es libre; para mandar comandos o actualizar hay que tener puesta la clave del equipo (Equipo → Inventario).

## Probarlo sin hardware

```bash
BICHO_RELE_TOKEN=dev node rele/servidor.mjs
```

```bash
cd bicho && BICHO_SIMULAR=1 BICHO_RELE_URL=http://localhost:8787 BICHO_RELE_TOKEN=dev python3 bichod.py
```

Después, en bicho·dev → Conexión, escribe `http://localhost:8787`.
