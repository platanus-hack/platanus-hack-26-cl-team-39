# Protocolo bicho ↔ web · harness

El bicho es un **Raspberry Pi 3** que corre `bichod` ([`bicho/`](bicho/)). Todo pasa por **un solo puerto, 8080**:

| Qué | Dónde | Para qué |
|---|---|---|
| WebSocket | `ws://<bicho>:8080/ws` | Info, sensores, logs y comandos (líneas JSON) |
| HTTP GET | `http://<bicho>:8080/info` | La misma info, para probar con curl |
| HTTP POST | `http://<bicho>:8080/update` | Instalar una versión nueva (cuerpo: el `.tar.gz`) |

`<bicho>` es `bicho.local` (si se instaló con `--hostname bicho`) o la IP del Pi. Cada mensaje del WebSocket es un objeto JSON en una línea.

## Bicho → web

### `info`: versión y qué hace

Se manda al conectarse, cuando se pide con `{"cmd":"info"}` y cada 10 s.

```json
{"t":"info","name":"bicho","fw":"0.1.0","desc":"Qué hace esta versión","chip":"Raspberry Pi 3 Model B Rev 1.2","build":"2026-11-21 03:12","ip":"192.168.1.50","mac":"B8:27:EB:12:34:56","uptime":42,"heap":512000000,"python":"3.11.2"}
```

- `fw` (obligatorio): versión **X.Y.Z**, sacada de `bicho/version.json`. La web la compara con las versiones publicadas.
- `desc`: el "qué hace" que muestra la web.
- `heap`: memoria libre en bytes. `uptime`: segundos desde que arrancó el agente.

### `s`: lecturas de sensores

```json
{"t":"s","ms":12345,"d":{"temp_cpu":48.3,"mic":0.42,"imu":{"pitch":3.1,"roll":-0.4},"servo":[90,45],"boton":true}}
```

- `d` es lo que devuelve `leer()` en `bicho/sensores.py`. La web aplana objetos y listas (`imu.pitch`, `servo[0]`) y grafica todo lo numérico o booleano. No hay que registrar nada en la web.
- Por defecto va a 20 Hz, y solo mientras haya alguien conectado.

### `log`: mensajes para la consola

```json
{"t":"log","lvl":"info","msg":"v0.2.0 instalada, reiniciando"}
```

## Web → bicho

| Comando | Efecto |
|---|---|
| `{"cmd":"info"}` | Responde con `info` |
| `{"cmd":"rate","hz":50}` | Cambia la frecuencia de las lecturas (de 1 a 100 Hz) |
| `{"cmd":"reboot"}` | Reinicia el agente (no el Pi) |
| cualquier otro | Lo resuelve `manejar()` en `bicho/comandos.py`, p. ej. `{"cmd":"servo","i":0,"deg":90}` |

## Versiones

1. Sube `version` (y `desc`) en `bicho/version.json`.
2. Desde `web/`: `npm run release -- --notes "qué cambia"`. Crea `web/public/firmware/<versión>/bicho-<versión>.tar.gz` y lo agrega a `manifest.json`.
3. bicho·dev la muestra como **disponible**. **Actualizar** hace `POST /update` con el paquete; `bichod` lo instala en `/opt/bicho/releases/<versión>`, apunta `/opt/bicho/current` a esa carpeta y se reinicia solo con la versión nueva. Si el paquete trae un `requirements.txt` distinto, instala esas dependencias antes de cambiar.
