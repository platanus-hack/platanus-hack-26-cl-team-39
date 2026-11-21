# Protocolo bicho ↔ web

Cada mensaje es **una línea JSON** terminada en `\n`. Es el mismo formato por los dos canales:

| Canal | Dónde | Para qué |
|---|---|---|
| USB | Serial a **115200** baudios | Monitor y flasheo por cable (Web Serial + esptool-js) |
| WiFi | WebSocket `ws://<bicho>:81/` | Monitor inalámbrico |
| WiFi | HTTP `http://<bicho>/update` (POST multipart, campo `firmware`) | Actualización OTA |
| WiFi | HTTP `http://<bicho>/info` | Lo mismo que el mensaje `info`, para probar con curl |

`<bicho>` es `bicho.local` (mDNS) o la IP que el bicho reporta en `info`.

## Bicho → web

### `info`: versión y qué hace

Se manda al arrancar, cuando se conecta un cliente, cuando se pide con `{"cmd":"info"}` y cada 10 s.

```json
{"t":"info","name":"bicho","fw":"0.1.0","desc":"Qué hace esta versión","chip":"ESP32-S3","build":"Nov 21 2026 03:12:00","ip":"192.168.1.50","mac":"AA:BB:CC:DD:EE:FF","uptime":42,"heap":201234}
```

- `fw` (obligatorio): versión **X.Y.Z**. La web la compara con las versiones publicadas.
- `desc`: el "qué hace" que se muestra en la web. Sin comillas dobles adentro.
- El resto es opcional y se muestra si viene.

### `s`: frame de sensores

```json
{"t":"s","ms":12345,"d":{"mic":0.42,"imu":{"pitch":3.1,"roll":-0.4},"servo":[90,45,10],"boton":true}}
```

- `d` acepta cualquier cosa. La web aplana objetos y arrays (`imu.pitch`, `servo[0]`) y grafica todo lo numérico o booleano.
- No hay que registrar nada en la web: si agregas un sensor nuevo al firmware, aparece solo.
- Por defecto va a 20 Hz.

### `log`: mensajes para la consola

```json
{"t":"log","lvl":"info","msg":"WiFi conectado: 192.168.1.50"}
```

Las líneas que no son JSON (por ejemplo `Serial.println("hola")` o los mensajes de arranque del ESP32) también aparecen en la consola. No rompen nada.

## Web → bicho

| Comando | Efecto |
|---|---|
| `{"cmd":"info"}` | Responde con `info` |
| `{"cmd":"rate","hz":50}` | Cambia la frecuencia de los frames de sensores (de 1 a 100 Hz) |
| `{"cmd":"reboot"}` | Reinicia el bicho |

Los comandos propios (actuadores, servos, LEDs) se agregan en `handleCustomCmd()` del firmware y se mandan desde la consola de la web. Por ejemplo: `{"cmd":"servo","i":0,"deg":90}`.

## Versiones de firmware

1. Sube `FW_VERSION` (y `FW_DESC`) en `firmware/bicho/bicho.ino`.
2. Compila exportando los binarios: en el Arduino IDE es **Sketch → Export Compiled Binary**; con la línea de comandos, `arduino-cli compile --export-binaries`.
3. Publica la versión desde `web/`: `npm run release -- --version X.Y.Z --notes "..." --dir ../firmware/bicho/build`.
4. En ~10 s la web la muestra como **disponible**. El botón **Actualizar** la graba por USB (imagen merged en 0x0) o por WiFi (OTA con el .bin de la app).
