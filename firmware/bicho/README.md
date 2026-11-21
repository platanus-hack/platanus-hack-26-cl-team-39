# Firmware del bicho (ESP32)

Firmware base en Arduino. Expone los sensores por Serial (115200) y por WebSocket (`ws://bicho.local:81/`), y acepta actualizaciones OTA en `http://bicho.local/update`. El contrato está en [`../../PROTOCOLO.md`](../../PROTOCOLO.md).

## Qué editar

En [`bicho.ino`](bicho.ino):

- `FW_VERSION` y `FW_DESC`: súbelos en cada versión. La web los muestra y compara.
- `readSensors()`: agrega aquí los sensores. La web los grafica solos.
- `handleCustomCmd()`: agrega aquí los comandos propios (servos, LEDs…).

## Compilar

1. Copia `secrets.example.h` a `secrets.h` y pon la red WiFi. Ese archivo no se sube al repo; si no hay red, el bicho levanta su propio punto de acceso.
2. Instala la librería **WebSockets** de Markus Sattler.
3. Exporta los binarios.

En el Arduino IDE: elige la placa ESP32 y usa **Sketch → Export Compiled Binary**.

Con la línea de comandos:

```bash
arduino-cli lib install WebSockets
```

```bash
arduino-cli compile --fqbn esp32:esp32:esp32s3 --export-binaries --output-dir firmware/bicho/build firmware/bicho
```

Cambia `esp32s3` por `esp32` si es un ESP32 clásico. Después publica la versión desde `web/` con `npm run release` (ver [`../../web/README.md`](../../web/README.md)).
