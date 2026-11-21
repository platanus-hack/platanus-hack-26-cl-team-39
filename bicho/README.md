# bicho: lo que corre en el Raspberry Pi 3

`bichod.py` es el agente del bicho. Corre en el Pi como servicio y, en un solo puerto (8080), hace tres cosas:

- manda la **info** (versión, qué hace, placa, IP) y los **sensores** a 20 Hz por WebSocket (`ws://bicho.local:8080/ws`);
- recibe **comandos** (servos, LEDs…) por el mismo WebSocket;
- recibe **versiones nuevas** desde bicho·dev (`POST /update` con un `.tar.gz`), las instala y se reinicia solo.

Usa solo la librería estándar de Python, así que en el Pi no hay que instalar nada con pip. El contrato está en [`../PROTOCOLO.md`](../PROTOCOLO.md).

## Qué editar

| Archivo | Para qué |
|---|---|
| [`sensores.py`](sensores.py) | `leer()` devuelve un dict con las lecturas. La web las grafica solas. Hay ejemplos de botón GPIO e IMU por I2C. |
| [`comandos.py`](comandos.py) | `manejar(cmd)` ejecuta comandos propios, como `{"cmd":"servo","i":0,"deg":90}`. |
| [`version.json`](version.json) | `version` y `desc` ("qué hace"). Sube la versión en cada cambio: la web compara contra eso. |
| [`requirements.txt`](requirements.txt) | Paquetes de pip para los sensores (por ejemplo `smbus2`). Se instalan solos al actualizar. |

## Instalar en el Pi (una vez)

Con Raspberry Pi OS, WiFi configurado y SSH:

```bash
git clone https://github.com/platanus-hack/platanus-hack-26-cl-team-39.git
```

```bash
cd platanus-hack-26-cl-team-39/bicho && sudo ./install.sh --hostname bicho
```

Queda como servicio `bichod` (arranca solo al prender el Pi) en `http://bicho.local:8080`. Para ver los logs:

```bash
journalctl -u bichod -f
```

Para los sensores I2C, activa I2C con `sudo raspi-config` (Interface Options → I2C).

## Probar sin el Pi

```bash
BICHO_SIMULAR=1 python3 bichod.py
```

Después conecta bicho·dev por WiFi a `localhost:8080`.

## Publicar una versión nueva

Desde `web/`:

```bash
npm run release -- --notes "Qué cambia en esta versión"
```

Empaqueta esta carpeta como `.tar.gz` con la versión de `version.json`. bicho·dev la muestra como disponible y la manda al Pi con el botón **Actualizar**. En el Pi, cada versión queda en `/opt/bicho/releases/<versión>` y `/opt/bicho/current` apunta a la activa (se guardan las últimas 5).
